from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cpm_runner import _FileLock
from .db import ReadOnlyDatabase
from .policy_client import PolicyUnavailable, RelationPolicyClient, relation_id
from .schema_config import (
    SchemaSnapshotConfig,
    _atomic_json,
    load_schema_config,
    schema_lock_path,
    schema_status_path,
)
from .schema_repository import (
    SchemaMetadataRepository,
    columns_compatible,
    generate_candidates,
    unique_keys,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _schema_fingerprint(schema: dict[str, Any]) -> str:
    stable = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()


def _table_file_name(table: str) -> str:
    readable = re.sub(r"[^A-Za-z0-9_.-]+", "_", table).strip("._") or "table"
    return f"{readable[:80]}-{hashlib.sha256(table.encode('utf-8')).hexdigest()[:8]}.json"


def _column_map(table: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["column_name"]): item for item in table.get("columns", [])}


def _relation_matches(item: dict[str, Any], source_table: str, source_columns: list[str], target_table: str | None, target_columns: list[str] | None) -> bool:
    if item.get("source_table") != source_table or list(item.get("source_columns", [])) != source_columns:
        return False
    if target_table is not None and item.get("target_table") != target_table:
        return False
    if target_columns is not None and list(item.get("target_columns", [])) != target_columns:
        return False
    return True


class SchemaSnapshotManager:
    def __init__(
        self,
        config: SchemaSnapshotConfig | None = None,
        database: ReadOnlyDatabase | None = None,
        policy: RelationPolicyClient | None = None,
    ):
        self.config = config or load_schema_config()
        self.database = database or ReadOnlyDatabase()
        self.repository = SchemaMetadataRepository(self.database, query_timeout_ms=self.config.query_timeout_ms)
        self.policy = policy or RelationPolicyClient(self.config)
        self.root = Path(self.config.snapshot_dir).resolve()

    def _manifest(self) -> dict[str, Any]:
        return _read_json(self.root / "manifest.json", {})

    def _fresh(self, manifest: dict[str, Any]) -> bool:
        return bool(manifest.get("completed_at")) and time.time() - _parse_time(manifest.get("completed_at")) < self.config.ttl_seconds

    def status(self) -> dict[str, Any]:
        manifest = self._manifest()
        status = _read_json(schema_status_path(), {})
        return {
            "configured": True,
            "snapshot_dir": str(self.root),
            "exists": self.root.is_dir() and bool(manifest),
            "completed_at": manifest.get("completed_at"),
            "ttl_seconds": self.config.ttl_seconds,
            "stale": not self._fresh(manifest),
            "schema_fingerprint": manifest.get("schema_fingerprint"),
            "counts": manifest.get("counts", {}),
            "policy": manifest.get("policy", {}),
            "last_error": status.get("last_error"),
        }

    def ensure_fresh(self) -> dict[str, Any]:
        return self.refresh(force=False)

    def refresh(self, *, force: bool = False) -> dict[str, Any]:
        manifest = self._manifest()
        if not force and self._fresh(manifest):
            return {"refreshed": False, **self.status()}
        started = time.monotonic()
        timeout = float(self.config.refresh_timeout_seconds)
        with _FileLock(schema_lock_path(), timeout):
            manifest = self._manifest()
            if not force and self._fresh(manifest):
                return {"refreshed": False, **self.status()}
            try:
                result = self._refresh_locked(started, timeout)
                _atomic_json(schema_status_path(), {"last_success_at": _now(), "last_error": None})
                return result
            except Exception as exc:
                _atomic_json(schema_status_path(), {
                    "last_success_at": _read_json(schema_status_path(), {}).get("last_success_at"),
                    "last_error": f"{type(exc).__name__}: {str(exc)[:240]}",
                    "failed_at": _now(),
                })
                raise

    def _refresh_locked(self, started: float, timeout: float) -> dict[str, Any]:
        deadline = started + timeout
        validation_deadline = deadline - min(5.0, timeout * 0.1)
        schema = self.repository.load_schema(deadline=validation_deadline)
        fingerprint = _schema_fingerprint(schema)
        policy_payload = None
        policy_error = None
        try:
            policy_payload = self.policy.sync()
        except Exception as exc:
            policy_error = f"{type(exc).__name__}: {str(exc)[:160]}"
        rejected = set((policy_payload or {}).get("rejections", []))
        candidates = generate_candidates(schema)
        previous_verified_ids = {
            str(item.get("relation_id"))
            for item in _read_json(self.root / "relations" / "verified.json", [])
            if item.get("relation_id")
        }
        previous_attempt_status = {
            str(item.get("relation_id")): str(item.get("status"))
            for item in _read_json(self.root / "validation-attempts.json", [])
            if item.get("relation_id")
        }
        attempts: list[dict[str, Any]] = []
        passed_by_source: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = {}
        if policy_payload is not None:
            eligible = []
            for candidate in candidates:
                rid = relation_id(
                    self.config.policy_scope_id,
                    candidate["source_table"], candidate["source_columns"],
                    candidate["target_table"], candidate["target_columns"],
                )
                if rid in rejected:
                    attempts.append({**candidate, "relation_id": rid, "status": "rejected_by_policy"})
                    continue
                eligible.append((candidate, rid))
            eligible.sort(key=lambda item: (
                0 if item[1] in previous_verified_ids else (
                    1 if previous_attempt_status.get(item[1]) in {"refresh_timeout", "query_timeout"} else (
                        2 if item[1] not in previous_attempt_status else 3
                    )
                ),
                -int(item[0].get("candidate_score", 0)),
                item[1],
            ))

            def verify(item):
                candidate, rid = item
                try:
                    evidence = self.repository.validate_relation(
                        candidate["source_table"], candidate["source_columns"],
                        candidate["target_table"], candidate["target_columns"],
                        min_distinct_values=self.config.min_distinct_values,
                        deadline=validation_deadline,
                    )
                    return {**candidate, "relation_id": rid, "status": evidence["reason"], "evidence": evidence}
                except Exception as exc:
                    message = f"{type(exc).__name__}: {str(exc)[:160]}"
                    lowered = message.lower()
                    return {
                        **candidate,
                        "relation_id": rid,
                        "status": "query_timeout" if "timed out" in lowered or "timeout" in lowered else "verification_error",
                        "error": message,
                    }

            futures = {}
            executor = ThreadPoolExecutor(max_workers=self.config.validation_concurrency)
            completed = set()
            try:
                for item in eligible:
                    futures[executor.submit(verify, item)] = item
                remaining = validation_deadline - time.monotonic()
                if remaining > 0:
                    for future in as_completed(futures, timeout=remaining):
                        completed.add(future)
                        attempt = future.result()
                        attempts.append(attempt)
                        if attempt.get("evidence", {}).get("passed"):
                            key = (attempt["source_table"], tuple(attempt["source_columns"]))
                            passed_by_source.setdefault(key, []).append(attempt)
            except FuturesTimeout:
                pass
            finally:
                for future, (candidate, rid) in futures.items():
                    if future not in completed:
                        future.cancel()
                        attempts.append({**candidate, "relation_id": rid, "status": "refresh_timeout"})
                executor.shutdown(wait=False, cancel_futures=True)
            attempts.sort(key=lambda item: (
                item.get("source_table", ""), item.get("source_columns", []),
                item.get("target_table", ""), item.get("target_columns", []),
            ))
        verified: list[dict[str, Any]] = []
        verified_at = _now()
        for _, passed in passed_by_source.items():
            if len(passed) != 1:
                for item in passed:
                    item["status"] = "ambiguous"
                continue
            item = passed[0]
            item["status"] = "data_verified"
            verified.append({
                "relation_id": item["relation_id"],
                "source_table": item["source_table"],
                "source_columns": item["source_columns"],
                "target_table": item["target_table"],
                "target_columns": item["target_columns"],
                "kind": "data_verified",
                "cardinality": "one_to_one" if item["evidence"]["source_unique"] else "many_to_one",
                "verified_at": verified_at,
                "schema_fingerprint": fingerprint,
                "evidence": item["evidence"],
            })
        if time.monotonic() >= deadline:
            raise TimeoutError("schema refresh deadline exceeded")
        self._write_snapshot(schema, fingerprint, verified, attempts, policy_payload, policy_error)
        return {"refreshed": True, **self.status()}

    def _write_snapshot(
        self,
        schema: dict[str, Any],
        fingerprint: str,
        verified: list[dict[str, Any]],
        attempts: list[dict[str, Any]],
        policy_payload: dict[str, Any] | None,
        policy_error: str | None,
    ) -> None:
        self.root.parent.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix=".schema-refresh-", dir=self.root.parent))
        backup = self.root.parent / f".{self.root.name}.previous"
        try:
            table_index = []
            declared_count = 0
            for table in schema.get("tables", []):
                name = str(table["table_name"])
                file_name = _table_file_name(name)
                _write_json(work / "tables" / file_name, table)
                table_index.append({
                    "table_name": name,
                    "table_comment": table.get("table_comment"),
                    "table_type": table.get("table_type"),
                    "file": f"tables/{file_name}",
                    "columns": [item.get("column_name") for item in table.get("columns", [])],
                })
                declared_count += len(table.get("foreign_keys", []))
            _write_json(work / "relations" / "verified.json", verified)
            _write_json(work / "validation-attempts.json", attempts)
            _write_json(work / "indexes" / "tables.json", table_index)
            _write_json(work / "indexes" / "table-usage.json", {
                "generated_at": _now(), "usages": [],
                "note": "Low-code table usage is enriched at query time from action facts.",
            })
            _write_json(work / "manifest.json", {
                "version": 1,
                "database": schema.get("database"),
                "completed_at": _now(),
                "ttl_seconds": self.config.ttl_seconds,
                "schema_fingerprint": fingerprint,
                "counts": {
                    "tables": len(schema.get("tables", [])),
                    "declared_foreign_keys": declared_count,
                    "candidates": len(attempts),
                    "verified_relations": len(verified),
                },
                "policy": {
                    "available": policy_payload is not None,
                    "scope_id": self.config.policy_scope_id,
                    "revision": (policy_payload or {}).get("revision"),
                    "error": policy_error,
                },
            })
            if backup.exists():
                shutil.rmtree(backup)
            if self.root.exists():
                os.replace(self.root, backup)
            try:
                os.replace(work, self.root)
            except Exception:
                if backup.exists() and not self.root.exists():
                    os.replace(backup, self.root)
                raise
            if backup.exists():
                shutil.rmtree(backup)
        finally:
            if work.exists():
                shutil.rmtree(work, ignore_errors=True)

    def _load_tables(self) -> dict[str, dict[str, Any]]:
        index = _read_json(self.root / "indexes" / "tables.json", [])
        result = {}
        for item in index:
            table = _read_json(self.root / str(item.get("file", "")), None)
            if isinstance(table, dict):
                result[str(table.get("table_name"))] = table
        return result

    def search(self, query: str, *, limit: int = 20) -> dict[str, Any]:
        self.ensure_fresh()
        needle = query.strip().lower()
        if not needle:
            raise ValueError("query 不能为空")
        matches = []
        for table in self._load_tables().values():
            table_hit = needle in str(table.get("table_name", "")).lower() or needle in str(table.get("table_comment", "")).lower()
            columns = [column for column in table.get("columns", []) if needle in str(column.get("column_name", "")).lower() or needle in str(column.get("column_comment", "")).lower()]
            if table_hit or columns:
                matches.append({
                    "table_name": table.get("table_name"),
                    "table_comment": table.get("table_comment"),
                    "matched_columns": columns[:20],
                })
            if len(matches) >= max(1, min(limit, 100)):
                break
        return {"evidence_layer": "数据库架构快照", "query": query, "matches": matches}

    def inspect(self, table: str, *, include_relations: bool = True) -> dict[str, Any]:
        self.ensure_fresh()
        tables = self._load_tables()
        if table not in tables:
            raise ValueError(f"Unknown table {table!r}")
        result = {"evidence_layer": "数据库架构快照", "table": tables[table], "relations": []}
        if not include_relations:
            return result
        try:
            policy = self.policy.sync()
        except PolicyUnavailable as exc:
            result["relation_status"] = "policy_unavailable"
            result["relation_error"] = str(exc)
            result["relations"] = self._declared_relations_for_table(tables, table)
            return result
        rejected = set(policy["rejections"])
        verified = _read_json(self.root / "relations" / "verified.json", [])
        result["relations"] = self._declared_relations_for_table(tables, table) + [
            item for item in verified
            if item.get("relation_id") not in rejected
            and (item.get("source_table") == table or item.get("target_table") == table)
            and item.get("schema_fingerprint") == self._manifest().get("schema_fingerprint")
            and self._fresh(self._manifest())
        ]
        result["relation_status"] = "current_policy_applied"
        result["policy_revision"] = policy["revision"]
        return result

    def _declared_relations_for_table(self, tables: dict[str, dict[str, Any]], table_name: str) -> list[dict[str, Any]]:
        result = []
        for table in tables.values():
            for fk in table.get("foreign_keys", []):
                item = {
                    "kind": "declared_fk",
                    "source_table": table["table_name"],
                    "source_columns": fk["columns"],
                    "target_table": fk["referenced_table_name"],
                    "target_columns": fk["referenced_columns"],
                    "constraint_name": fk["constraint_name"],
                    "update_rule": fk.get("update_rule"),
                    "delete_rule": fk.get("delete_rule"),
                }
                if item["source_table"] == table_name or item["target_table"] == table_name:
                    result.append(item)
        return result

    def resolve(
        self,
        source_table: str,
        source_columns: list[str],
        *,
        target_table: str | None = None,
        target_columns: list[str] | None = None,
        force_live: bool = False,
    ) -> dict[str, Any]:
        self.ensure_fresh()
        try:
            policy = self.policy.sync()
        except PolicyUnavailable as exc:
            return {"status": "unresolved", "evidence_layer": "尚未确认", "reason": "policy_unavailable", "error": str(exc)}
        rejected = set(policy["rejections"])
        if target_table and target_columns:
            rid = relation_id(self.config.policy_scope_id, source_table, source_columns, target_table, target_columns)
            if rid in rejected:
                return {"status": "rejected", "evidence_layer": "远程用户否决", "relation_id": rid, "policy_revision": policy["revision"]}
        manifest = self._manifest()
        verified = _read_json(self.root / "relations" / "verified.json", [])
        cached = [item for item in verified if _relation_matches(item, source_table, source_columns, target_table, target_columns)]
        cached = [item for item in cached if item.get("relation_id") not in rejected]
        if not force_live and self._fresh(manifest) and len(cached) == 1 and cached[0].get("schema_fingerprint") == manifest.get("schema_fingerprint"):
            return {"status": "data_verified", "evidence_layer": "数据验证关系", "relation": cached[0], "policy_revision": policy["revision"]}
        tables = self._load_tables()
        source = tables.get(source_table)
        if not source:
            return {"status": "unresolved", "evidence_layer": "尚未确认", "reason": "unknown_source_table"}
        if target_table:
            target = tables.get(target_table)
            target_keys = [target_columns] if target_columns else (unique_keys(target) if target else [])
            candidates = [{
                "source_table": source_table, "source_columns": source_columns,
                "target_table": target_table, "target_columns": key,
            } for key in target_keys if key and len(key) == len(source_columns)] if target else []
        else:
            candidates = [item for item in generate_candidates({"tables": list(tables.values())}) if item["source_table"] == source_table and item["source_columns"] == source_columns]
        live = []
        source_map = _column_map(source)
        for candidate in candidates:
            target = tables.get(candidate["target_table"])
            target_cols = candidate["target_columns"]
            target_map = _column_map(target) if target else {}
            if not target or target_cols not in unique_keys(target):
                continue
            if len(source_columns) != len(target_cols) or any(
                left not in source_map or right not in target_map or not columns_compatible(source_map[left], target_map[right])
                for left, right in zip(source_columns, target_cols)
            ):
                continue
            rid = relation_id(self.config.policy_scope_id, source_table, source_columns, target["table_name"], target_cols)
            if rid in rejected:
                continue
            try:
                evidence = self.repository.validate_relation(
                    source_table, source_columns, target["table_name"], target_cols,
                    min_distinct_values=self.config.min_distinct_values,
                )
                if evidence["passed"]:
                    live.append({**candidate, "relation_id": rid, "evidence": evidence})
            except Exception as exc:
                return {"status": "unresolved", "evidence_layer": "尚未确认", "reason": "live_query_failed", "error": f"{type(exc).__name__}: {str(exc)[:160]}"}
        if len(live) == 1:
            return {"status": "live_verified", "evidence_layer": "实时数据库验证", "relation": live[0], "persisted": False, "policy_revision": policy["revision"]}
        return {"status": "unresolved", "evidence_layer": "尚未确认", "reason": "ambiguous" if len(live) > 1 else "not_verified", "matches": len(live)}

    def reject(self, relation: str, reason_code: str = "user_confirmed_incorrect") -> dict[str, Any]:
        result = self.policy.reject(relation, reason_code)
        return {"evidence_layer": "远程用户否决", **result}

    def restore(self, relation: str) -> dict[str, Any]:
        with _FileLock(schema_lock_path(), float(self.config.refresh_timeout_seconds)):
            result = self.policy.restore(relation)
            verified_path = self.root / "relations" / "verified.json"
            verified = _read_json(verified_path, [])
            if isinstance(verified, list):
                remaining = [item for item in verified if item.get("relation_id") != relation]
                if len(remaining) != len(verified):
                    _atomic_json(verified_path, remaining)
        return {"evidence_layer": "远程用户否决", **result}


def schema_snapshot_status() -> dict[str, Any]:
    """Return local development-database Schema snapshot freshness and policy status."""
    try:
        return SchemaSnapshotManager().status()
    except Exception as exc:
        return {"configured": False, "error": f"{type(exc).__name__}: {str(exc)[:240]}"}


def refresh_schema_snapshot(force: bool = False) -> dict[str, Any]:
    """Refresh local Schema metadata and strictly data-verified logical relationships."""
    return SchemaSnapshotManager().refresh(force=force)


def search_database_schema(query: str, limit: int = 20) -> dict[str, Any]:
    """Search local table/column names and comments without reading business rows."""
    return SchemaSnapshotManager().search(query, limit=limit)


def inspect_table_schema(table: str, include_relations: bool = True) -> dict[str, Any]:
    """Inspect one local Schema table and policy-filtered trusted relationships."""
    return SchemaSnapshotManager().inspect(table, include_relations=include_relations)


def resolve_table_relation(
    source_table: str,
    source_columns: list[str],
    target_table: str | None = None,
    target_columns: list[str] | None = None,
    force_live: bool = False,
) -> dict[str, Any]:
    """Resolve a relationship through policy, a fresh verified snapshot, or live aggregate checks."""
    return SchemaSnapshotManager().resolve(
        source_table, source_columns,
        target_table=target_table, target_columns=target_columns, force_live=force_live,
    )


def reject_table_relation(relation_id: str, reason_code: str = "user_confirmed_incorrect") -> dict[str, Any]:
    """Persist an explicit user rejection remotely using only an opaque relationship ID."""
    return SchemaSnapshotManager().reject(relation_id, reason_code)


def restore_table_relation(relation_id: str) -> dict[str, Any]:
    """Restore a remotely rejected relationship and require fresh data validation."""
    return SchemaSnapshotManager().restore(relation_id)
