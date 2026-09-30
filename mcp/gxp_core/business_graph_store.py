from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import tempfile
import time
import queue
import threading
from contextlib import contextmanager
from pathlib import Path

from .business_graph_model import adapt_legacy, namespace, normalize_v3, stable_identity
from .business_logic_graph import (
    BusinessLogicGraphError, CONFIRMED_STATUSES, LIFECYCLE_STATUSES, REASON_CODES,
    RELATION_FIELDS, GraphValidationError, MAX_GRAPH_BYTES, MAX_RESPONSE_BYTES,
    _digest, _encoded, _hash, _legacy_relation, _text, render_mermaid,
)
from .relation_policy import _PolicyFileLock, utc_now
from .schema_config import load_schema_config, schema_runtime_root

SCHEMA_VERSION = 3
MAX_DATABASE_BYTES = 256 * 1024 * 1024
DDL = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE cases (id TEXT PRIMARY KEY, scope TEXT NOT NULL, environment TEXT NOT NULL, case_key TEXT NOT NULL);
CREATE TABLE observations (id TEXT PRIMARY KEY, case_id TEXT NOT NULL REFERENCES cases(id),
 revision INTEGER NOT NULL, lifecycle TEXT NOT NULL, level TEXT NOT NULL, fingerprint TEXT NOT NULL,
 body TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(case_id, revision));
CREATE TABLE entities (id TEXT PRIMARY KEY, scope TEXT NOT NULL, environment TEXT NOT NULL,
 kind TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE aliases (entity_id TEXT NOT NULL REFERENCES entities(id), label TEXT NOT NULL, PRIMARY KEY(entity_id,label));
CREATE TABLE sightings (entity_id TEXT NOT NULL REFERENCES entities(id), observation_id TEXT NOT NULL REFERENCES observations(id),
 catalog INTEGER NOT NULL, PRIMARY KEY(entity_id,observation_id));
CREATE TABLE facts (id TEXT PRIMARY KEY, scope TEXT NOT NULL, environment TEXT NOT NULL,
 source TEXT NOT NULL REFERENCES entities(id), target TEXT NOT NULL REFERENCES entities(id), kind TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE evidence (id TEXT PRIMARY KEY, observation_id TEXT NOT NULL REFERENCES observations(id), body TEXT NOT NULL);
CREATE TABLE supports (id TEXT PRIMARY KEY, fact_id TEXT NOT NULL REFERENCES facts(id),
 observation_id TEXT NOT NULL REFERENCES observations(id), lifecycle TEXT NOT NULL, level TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE support_evidence (support_id TEXT NOT NULL REFERENCES supports(id), evidence_id TEXT NOT NULL REFERENCES evidence(id),
 PRIMARY KEY(support_id,evidence_id));
CREATE TABLE dependencies (support_id TEXT NOT NULL REFERENCES supports(id), kind TEXT NOT NULL,
 dep_key TEXT NOT NULL, version TEXT NOT NULL, PRIMARY KEY(support_id,kind,dep_key));
CREATE TABLE versions (scope TEXT NOT NULL, environment TEXT NOT NULL, kind TEXT NOT NULL, dep_key TEXT NOT NULL,
 version TEXT NOT NULL, PRIMARY KEY(scope,environment,kind,dep_key));
CREATE TABLE tasks (id TEXT PRIMARY KEY, scope TEXT NOT NULL, environment TEXT NOT NULL, entity_id TEXT,
 reason TEXT NOT NULL, body TEXT NOT NULL, state TEXT NOT NULL);
CREATE TABLE catalogs (id TEXT PRIMARY KEY, scope TEXT NOT NULL, environment TEXT NOT NULL,
 source TEXT NOT NULL, version TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE catalog_members (catalog_id TEXT NOT NULL REFERENCES catalogs(id), entity_id TEXT NOT NULL REFERENCES entities(id),
 PRIMARY KEY(catalog_id,entity_id));
CREATE TABLE requests (id TEXT PRIMARY KEY, started REAL NOT NULL, attempts INTEGER NOT NULL);
CREATE TABLE request_attempts (request_id TEXT NOT NULL REFERENCES requests(id), target TEXT NOT NULL,
 PRIMARY KEY(request_id,target));
CREATE TABLE audit (id INTEGER PRIMARY KEY, action TEXT NOT NULL, subject TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX case_scope ON cases(scope,environment);
CREATE INDEX entity_scope ON entities(scope,environment);
CREATE INDEX fact_source ON facts(scope,environment,source);
CREATE INDEX fact_target ON facts(scope,environment,target);
CREATE INDEX fact_source_identity ON facts(source);
CREATE INDEX fact_target_identity ON facts(target);
CREATE INDEX support_fact ON supports(fact_id,lifecycle);
CREATE INDEX support_case ON supports(observation_id,lifecycle);
CREATE INDEX dependency_lookup ON dependencies(kind,dep_key,version);
"""


def _json(value) -> str:
    return _encoded(value).decode("utf-8")


class BusinessGraphStore:
    def __init__(self, path: Path | None = None, *, legacy_path: Path | None = None,
                 scope_id: str | None = None, lock_timeout_seconds: float = 5):
        self.path = (path or schema_runtime_root() / "business-graph.sqlite3").resolve()
        self.legacy_path = (legacy_path or self.path.with_name("business-logic-graph.json")).resolve()
        self.scope = _text(scope_id or load_schema_config().policy_scope_id)
        self.timeout = lock_timeout_seconds

    @staticmethod
    def _sqlite_error(exc: sqlite3.Error) -> BusinessLogicGraphError:
        code = "GRAPH_LOCK_TIMEOUT" if "locked" in str(exc).lower() else "GRAPH_DATABASE_UNAVAILABLE"
        return BusinessLogicGraphError(code)

    def _connect(self, path: Path | None = None, *, staged: bool = False) -> sqlite3.Connection:
        connection = sqlite3.connect(str(path or self.path), timeout=self.timeout)
        try:
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(f"PRAGMA busy_timeout={int(self.timeout * 1000)}")
            if not staged:
                if connection.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                    raise BusinessLogicGraphError("GRAPH_UNSUPPORTED_VERSION")
                if connection.execute("PRAGMA journal_mode").fetchone()[0].casefold() != "wal":
                    with _PolicyFileLock(self.path.with_name(self.path.name + ".migration.lock"), self.timeout):
                        connection.execute("PRAGMA journal_mode=WAL").fetchall()
            return connection
        except TimeoutError as exc:
            connection.close()
            raise BusinessLogicGraphError("GRAPH_LOCK_TIMEOUT") from exc
        except Exception:
            connection.close()
            raise

    def _initialize(self) -> None:
        if self.path.exists():
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with _PolicyFileLock(self.path.with_name(self.path.name + ".migration.lock"), self.timeout):
                if self.path.exists():
                    return
                descriptor, name = tempfile.mkstemp(prefix=".business-graph-", suffix=".sqlite3", dir=self.path.parent)
                os.close(descriptor)
                staging = Path(name)
                connection = None
                try:
                    connection = self._connect(staging, staged=True)
                    connection.executescript(DDL)
                    connection.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                    connection.execute("INSERT INTO meta VALUES ('revision','0')")
                    report = self._import_json(connection)
                    connection.execute("INSERT INTO meta VALUES ('migration',?)", (_json(report),))
                    connection.commit()
                    checked = connection.execute("PRAGMA quick_check").fetchall()
                    if len(checked) != 1 or checked[0][0] != "ok":
                        raise BusinessLogicGraphError("GRAPH_MIGRATION_FAILED")
                    connection.close()
                    connection = self._connect(staging, staged=True)
                    connection.execute("PRAGMA journal_mode=WAL").fetchall()
                    connection.close()
                    connection = None
                    os.replace(staging, self.path)
                finally:
                    if connection is not None:
                        connection.close()
                    staging.unlink(missing_ok=True)
        except TimeoutError as exc:
            raise BusinessLogicGraphError("GRAPH_LOCK_TIMEOUT") from exc
        except sqlite3.Error as exc:
            raise self._sqlite_error(exc) from exc

    @contextmanager
    def _transaction(self, write: bool = False):
        connection = None
        try:
            self._initialize()
            if self.path.stat().st_size > MAX_DATABASE_BYTES:
                raise BusinessLogicGraphError("GRAPH_TOO_LARGE")
            connection = self._connect()
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            if write and (self.path.stat().st_size + (self.path.with_name(self.path.name + "-wal").stat().st_size
                    if self.path.with_name(self.path.name + "-wal").exists() else 0) > MAX_DATABASE_BYTES):
                raise BusinessLogicGraphError("GRAPH_TOO_LARGE")
            connection.commit()
        except sqlite3.Error as exc:
            if connection is not None:
                connection.rollback()
            raise self._sqlite_error(exc) from exc
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _audit(connection, action: str, subject: str, reason: str = "") -> None:
        connection.execute("INSERT INTO audit(action,subject,reason,created_at) VALUES (?,?,?,?)",
                           (action, subject, reason, utc_now()))

    @staticmethod
    def _bump(connection) -> int:
        connection.execute("UPDATE meta SET value=CAST(value AS INTEGER)+1 WHERE key='revision'")
        return int(connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])

    def _task(self, connection, scope: str, environment: str, reason: str, payload: dict,
              entity_id: str | None = None) -> None:
        task_id = _digest([scope, environment, entity_id, reason, payload])
        connection.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?, 'pending') ON CONFLICT(id) DO UPDATE SET state='pending'",
                           (task_id, scope, environment, entity_id, reason, _json(payload)))

    def _review_legacy(self, connection, source: Path, index: int, item, reason: str) -> None:
        payload = {"source": source.name, "record_index": index, "reason": reason,
                   "label": "Legacy record requires re-verification", "environment": "unknown"}
        if isinstance(item, dict):
            try:
                payload["label"] = _text(item.get("summary", item.get("conclusion", payload["label"])), 1000)
            except GraphValidationError:
                pass
        self._task(connection, self.scope, "unknown", "legacy_review_required", payload)

    def _import_json(self, connection) -> dict:
        report = {"attempted": False, "imported": 0, "skipped": 0, "rejected": 0, "sources": []}
        archive = self.legacy_path.with_name(self.legacy_path.stem + ".legacy-v1.json")
        for source in (self.legacy_path, archive):
            if not source.exists():
                continue
            report["attempted"] = True
            with source.open("rb") as stream:
                data = stream.read(MAX_GRAPH_BYTES + 1)
            record = {"file": source.name, "fingerprint": hashlib.sha256(data).hexdigest(), "imported": 0, "rejected": 0}
            report["sources"].append(record)
            try:
                if len(data) > MAX_GRAPH_BYTES:
                    raise GraphValidationError("GRAPH_TOO_LARGE")
                document = json.loads(data.decode("utf-8-sig"))
                if isinstance(document, list):
                    items = document
                elif isinstance(document, dict) and document.get("version") in (None, 0, 1, 2):
                    if document.get("schema_version", 1) != 1:
                        raise GraphValidationError("GRAPH_UNSUPPORTED_VERSION")
                    items = document.get("relations", document.get("records"))
                else:
                    raise GraphValidationError("GRAPH_UNSUPPORTED_VERSION")
                if not isinstance(items, list) or len(items) > 10000:
                    raise GraphValidationError("GRAPH_MIGRATION_FAILED")
            except (ValueError, UnicodeError, RecursionError):
                report["rejected"] += 1
                record["rejected"] += 1
                self._review_legacy(connection, source, 0, None, "unreadable_legacy_source")
                continue
            for index, item in enumerate(items):
                if not isinstance(item, dict) or not isinstance(item.get("status"), str) or item["status"] not in CONFIRMED_STATUSES:
                    report["skipped"] += 1
                    self._review_legacy(connection, source, index, item, "unconfirmed_legacy_record")
                    continue
                try:
                    connection.execute("SAVEPOINT legacy_record")
                    if document and isinstance(document, dict) and document.get("version") == 2:
                        raw = {key: item[key] for key in RELATION_FIELDS if key in item}
                    else:
                        raw = _legacy_relation(item)
                    normalized = adapt_legacy(raw, self.scope)
                    result = self._put(connection, normalized, lifecycle=item.get("lifecycle", "active"))
                    connection.execute("RELEASE legacy_record")
                    report["imported"] += int(result["written"])
                    record["imported"] += int(result["written"])
                except (ValueError, TypeError, KeyError):
                    connection.execute("ROLLBACK TO legacy_record")
                    connection.execute("RELEASE legacy_record")
                    report["rejected"] += 1
                    record["rejected"] += 1
                    self._review_legacy(connection, source, index, item, "identity_or_evidence_incomplete")
        return report

    def _versions(self, connection, scope: str, environment: str, dependencies: list[dict]) -> None:
        unique = {(item["kind"], item["key"]): item["version"] for item in dependencies}
        for (kind, key), version in unique.items():
            affected = connection.execute("""SELECT DISTINCT supports.id,supports.observation_id FROM supports
                JOIN dependencies ON dependencies.support_id=supports.id
                JOIN facts ON facts.id=supports.fact_id
                WHERE facts.scope=? AND facts.environment=? AND supports.lifecycle='active'
                AND dependencies.kind=? AND dependencies.dep_key=? AND dependencies.version<>?""",
                (scope, environment, kind, key, version)).fetchall()
            for support in affected:
                connection.execute("UPDATE supports SET lifecycle='stale' WHERE id=?", (support["id"],))
                connection.execute("""UPDATE observations SET lifecycle='stale' WHERE id=? AND lifecycle='active'
                    AND NOT EXISTS(SELECT 1 FROM supports WHERE observation_id=? AND lifecycle='active')""",
                                   (support["observation_id"], support["observation_id"]))
                self._audit(connection, "stale", support["id"], "dependency_version_changed")
            connection.execute("""INSERT INTO versions VALUES (?,?,?,?,?) ON CONFLICT(scope,environment,kind,dep_key)
                DO UPDATE SET version=excluded.version""", (scope, environment, kind, key, version))

    def _put(self, connection, observation: dict, lifecycle: str = "active") -> dict:
        if lifecycle not in {"active", "stale", "invalidated", "superseded"}:
            raise GraphValidationError("GRAPH_INVALID_LIFECYCLE")
        scope, environment, case_id = observation["scope_id"], observation["environment"], observation["case_id"]
        previous = connection.execute("SELECT * FROM observations WHERE case_id=? ORDER BY revision DESC LIMIT 1", (case_id,)).fetchone()
        identity = _digest([observation["fingerprint"], observation["conclusion"], observation["status"]])
        if previous and previous["lifecycle"] == lifecycle and previous["fingerprint"] == identity:
            return {"written": False, "idempotent": True, "observation_id": previous["id"],
                    "relation": self._relation(previous), "delta": {"new_entities": 0, "reused_entities": 0, "new_facts": 0,
                    "reused_facts": 0, "updated_entities": 0, "updated_cases": 0,
                    "new_supports": 0, "pending_review": len(observation["unresolved"])}}
        revision = previous["revision"] + 1 if previous else 1
        observation_id = _digest([case_id, revision, identity])
        connection.execute("INSERT OR IGNORE INTO cases VALUES (?,?,?,?)", (case_id, scope, environment, observation["case_key"]))
        if previous:
            for issue in json.loads(previous["body"])["unresolved"]:
                task_id = _digest([scope, environment, None, issue["reason"], {**issue, "case_id": case_id}])
                connection.execute("UPDATE tasks SET state='resolved' WHERE id=?", (task_id,))
            connection.execute("UPDATE observations SET lifecycle='superseded' WHERE case_id=? AND lifecycle='active'", (case_id,))
            connection.execute("""UPDATE supports SET lifecycle='superseded' WHERE observation_id IN
                (SELECT id FROM observations WHERE case_id=?) AND lifecycle='active'""", (case_id,))
        connection.execute("INSERT INTO observations VALUES (?,?,?,?,?,?,?,?)",
                           (observation_id, case_id, revision, lifecycle, observation["status"], identity, _json(observation), utc_now()))
        delta = {"new_entities": 0, "reused_entities": 0, "new_facts": 0, "reused_facts": 0,
                 "updated_entities": 0, "updated_cases": int(previous is not None), "new_supports": 0,
                 "pending_review": len(observation["unresolved"])}
        catalog_evidence = all(item["type"] in {"schema_catalog", "cpm_catalog", "source_static"}
                               for item in observation["evidence"])
        business_entities = {fact[key] for fact in observation["facts"] if fact["kind"] not in {"contains", "belongs_to"}
                             for key in ("source", "target")}
        for item in observation["entities"]:
            catalog = int(catalog_evidence and item["id"] not in business_entities)
            existing = connection.execute("SELECT id,body FROM entities WHERE id=?", (item["id"],)).fetchone()
            delta["reused_entities" if existing else "new_entities"] += 1
            if existing and item["boundary"] == "unknown":
                item = {**item, "boundary": json.loads(existing["body"])["boundary"]}
            delta["updated_entities"] += int(existing is not None and existing["body"] != _json(item))
            connection.execute("INSERT INTO entities VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                               (item["id"], scope, environment, item["kind"], _json(item)))
            connection.execute("INSERT OR IGNORE INTO aliases VALUES (?,?)", (item["id"], item["label"]))
            connection.execute("INSERT INTO sightings VALUES (?,?,?)", (item["id"], observation_id, catalog))
        evidence_ids = {}
        proof_index = {item["id"]: item for item in observation["evidence"]}
        for item in observation["evidence"]:
            evidence_id = _digest([observation_id, item["id"]])
            evidence_ids[item["id"]] = evidence_id
            connection.execute("INSERT INTO evidence VALUES (?,?,?)", (evidence_id, observation_id, _json(item)))
        if lifecycle == "active":
            self._versions(connection, scope, environment, [dependency for item in observation["evidence"] for dependency in item["dependencies"]])
        for fact in observation["facts"]:
            existing = connection.execute("SELECT id FROM facts WHERE id=?", (fact["id"],)).fetchone()
            delta["new_facts"] += int(existing is None)
            delta["reused_facts"] += int(existing is not None)
            body = {key: value for key, value in fact.items() if key != "evidence"}
            connection.execute("INSERT INTO facts VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                               (fact["id"], scope, environment, fact["source"], fact["target"], fact["kind"], _json(body)))
            support_id = _digest([observation_id, fact["id"]])
            connection.execute("INSERT OR IGNORE INTO supports VALUES (?,?,?,?,?,?)",
                               (support_id, fact["id"], observation_id, lifecycle, observation["status"], _json(body)))
            delta["new_supports"] += 1
            for proof_id in fact["evidence_ids"]:
                item = proof_index[proof_id]
                connection.execute("INSERT OR IGNORE INTO support_evidence VALUES (?,?)", (support_id, evidence_ids[item["id"]]))
                for dependency in item["dependencies"]:
                    connection.execute("INSERT OR IGNORE INTO dependencies VALUES (?,?,?,?)",
                                       (support_id, dependency["kind"], dependency["key"], dependency["version"]))
        for issue in observation["unresolved"]:
            self._task(connection, scope, environment, issue["reason"], {**issue, "case_id": case_id})
        self._audit(connection, "upsert", observation_id)
        self._bump(connection)
        current = connection.execute("SELECT * FROM observations WHERE id=?", (observation_id,)).fetchone()
        return {"written": True, "idempotent": False, "observation_id": observation_id,
                "relation": self._relation(current), "delta": delta}

    @staticmethod
    def _relation(row) -> dict:
        observation = json.loads(row["body"])
        legacy = observation["legacy"]
        result = copy.deepcopy(legacy) if legacy else {
            "format_version": 3, "relation_id": observation["case_id"], "scope_id": observation["scope_id"],
            "environment": observation["environment"], "conclusion": observation["conclusion"],
            "status": observation["status"], "entities": observation["entities"],
            "facts": observation["facts"], "evidence": observation["evidence"],
            "evidence_fingerprint": observation["fingerprint"]}
        result.update(revision=row["revision"], lifecycle=row["lifecycle"], created_at=row["created_at"])
        return result

    def upsert(self, relation: dict) -> dict:
        normalized = normalize_v3(relation, self.scope) if isinstance(relation, dict) and "format_version" in relation else adapt_legacy(relation, self.scope)
        with self._transaction(write=True) as connection:
            result = self._put(connection, normalized)
            result["graph_revision"] = int(connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])
            if len(_encoded(result)) > MAX_RESPONSE_BYTES:
                result["relation"].update(entities=[], facts=[], evidence=[], truncated=True,
                                          next_step="Query get_business_graph for the committed entities and complete supports.")
            return result

    def invalidate(self, relation_id: str, *, reason: str) -> dict:
        _hash(relation_id)
        if _text(reason) not in REASON_CODES:
            raise GraphValidationError("GRAPH_INVALID_REASON")
        lifecycle = "invalidated" if reason == "user_confirmed_incorrect" else "stale"
        changed = 0
        with self._transaction(write=True) as connection:
            rows = connection.execute("SELECT observations.* FROM observations JOIN cases ON cases.id=observations.case_id WHERE cases.scope=? OR cases.id=?",
                                      (self.scope, relation_id)).fetchall()
            for row in rows:
                observation = json.loads(row["body"])
                public_id = (observation["legacy"] or {}).get("relation_id", observation["case_id"])
                if public_id != relation_id or row["lifecycle"] not in {"active", "stale"}:
                    continue
                if row["lifecycle"] == lifecycle:
                    continue
                connection.execute("UPDATE observations SET lifecycle=? WHERE id=?", (lifecycle, row["id"]))
                connection.execute("UPDATE supports SET lifecycle=? WHERE observation_id=? AND lifecycle IN ('active','stale')",
                                   (lifecycle, row["id"]))
                self._audit(connection, lifecycle, row["id"], reason)
                changed += 1
            if changed:
                self._bump(connection)
        return {"relation_id": relation_id, "changed": changed}

    def search(self, *, query=None, action=None, page=None, table=None, field=None, status=None,
               environment="development", limit=20, relation_id=None, current_published_designs=None,
               current_evidence_fingerprints=None, scope_id=None) -> dict:
        scope, environment = namespace(scope_id or self.scope, environment)
        if (type(limit) is not int or not 1 <= limit <= 50 or
                status is not None and status not in CONFIRMED_STATUSES | LIFECYCLE_STATUSES):
            raise GraphValidationError("GRAPH_INVALID_SEARCH")
        filters = {key: _text(value).casefold() for key, value in
                   (("query", query), ("action", action), ("page", page), ("table", table), ("field", field)) if value is not None}
        if relation_id is not None:
            _hash(relation_id)
        designs = current_published_designs or {}
        fingerprints = current_evidence_fingerprints or {}
        if not isinstance(designs, dict) or not isinstance(fingerprints, dict) or len(designs) > 60 or len(fingerprints) > 60:
            raise GraphValidationError("GRAPH_INVALID_CURRENT_EVIDENCE")
        dependencies = [{"kind": "action", "key": stable_identity(key), "version": stable_identity(value)} for key, value in designs.items()]
        if fingerprints and relation_id is None:
            raise GraphValidationError("GRAPH_RELATION_ID_REQUIRED")
        for key, value in fingerprints.items():
            _text(key)
            _hash(value)
        with self._transaction(write=True) as connection:
            if dependencies:
                self._versions(connection, scope, environment, dependencies)
                self._bump(connection)
            rows = connection.execute("""SELECT observations.* FROM observations JOIN cases ON cases.id=observations.case_id
                WHERE cases.scope=? AND cases.environment=? ORDER BY observations.created_at DESC,observations.revision DESC""",
                                      (scope, environment)).fetchall()
            matches = []
            for row in rows:
                relation = self._relation(row)
                if relation_id and relation["relation_id"] != relation_id:
                    continue
                if fingerprints:
                    observation = json.loads(row["body"])
                    changed = any(item["id"] in fingerprints and fingerprints[item["id"]] != item["fingerprint"] for item in observation["evidence"])
                    if changed and row["lifecycle"] == "active":
                        connection.execute("UPDATE observations SET lifecycle='stale' WHERE id=?", (row["id"],))
                        connection.execute("UPDATE supports SET lifecycle='stale' WHERE observation_id=? AND lifecycle='active'", (row["id"],))
                        self._audit(connection, "stale", row["id"], "evidence_invalidated")
                        relation["lifecycle"] = "stale"
                        self._bump(connection)
                if status in LIFECYCLE_STATUSES:
                    if relation["lifecycle"] != status:
                        continue
                elif relation["lifecycle"] != "active" or status and relation["status"] != status:
                    continue
                anchors = relation.get("anchors", [])
                searchable = {"query": _json(relation),
                              "action": " ".join(item["action_code"] + " " + item["ref_id"] for item in anchors),
                              "page": " ".join(item["page"] for item in anchors),
                              "table": " ".join(relation.get("tables", []) + relation.get("views", [])),
                              "field": " ".join(relation.get("fields", []))}
                if relation.get("format_version") == 3:
                    for category in ("action", "page", "table", "field"):
                        searchable[category] = _json(relation["entities"])
                if all(all(term in searchable[key].casefold() for term in value.split()) for key, value in filters.items()):
                    matches.append(relation)
            migration = json.loads(connection.execute("SELECT value FROM meta WHERE key='migration'").fetchone()[0])
            pending = [{"reason": row["reason"], **json.loads(row["body"])} for row in connection.execute("""SELECT reason,body FROM tasks
                WHERE scope=? AND state='pending' AND reason IN ('legacy_review_required','identity_unresolved') LIMIT 50""", (scope,))]
            if query:
                pending = [item for item in pending if all(term in _json(item).casefold() for term in query.casefold().split())]
            result = {"available": True, "source": "local_diagnostic_cache", "must_reverify_current_published_copy": True,
                      "reverification": "必须重新核对当前发布副本及当前只读证据。", "migration": migration,
                      "legacy_review_required": migration["rejected"] > 0 or bool(pending), "pending_review": pending,
                      "matched_count": len(matches), "relations": [], "count": 0, "truncated": False}
            for relation in matches[:limit]:
                result["relations"].append(relation)
                if len(_encoded(result)) > MAX_RESPONSE_BYTES:
                    result["relations"].pop()
                    break
            result["count"] = len(result["relations"])
            result["truncated"] = result["count"] < len(matches)
            return result

    def _snapshot(self, connection, scope: str, environment: str, include_catalog: bool) -> dict:
        started = time.monotonic()
        entity_rows = connection.execute("""SELECT entities.*,
            EXISTS(SELECT 1 FROM sightings WHERE sightings.entity_id=entities.id AND sightings.catalog=0) AS diagnostic,
            EXISTS(SELECT 1 FROM sightings JOIN observations ON observations.id=sightings.observation_id
                WHERE sightings.entity_id=entities.id AND sightings.catalog=0 AND observations.lifecycle='active') AS observed,
            EXISTS(SELECT 1 FROM facts JOIN supports ON supports.fact_id=facts.id
                WHERE (facts.source=entities.id OR facts.target=entities.id) AND supports.lifecycle='active'
                AND facts.kind NOT IN ('contains','belongs_to')) AS connected
            FROM entities WHERE entities.scope=? AND entities.environment=?
            AND (? OR EXISTS(SELECT 1 FROM sightings WHERE sightings.entity_id=entities.id AND sightings.catalog=0)
                 OR EXISTS(SELECT 1 FROM facts WHERE (facts.source=entities.id OR facts.target=entities.id)
                           AND facts.kind NOT IN ('contains','belongs_to')))
            ORDER BY entities.id LIMIT 10001""",
                                         (scope, environment, include_catalog)).fetchall()
        fact_rows = connection.execute("""SELECT facts.*,COUNT(supports.id) AS support_count FROM facts
            JOIN supports ON supports.fact_id=facts.id AND supports.lifecycle='active'
            WHERE facts.scope=? AND facts.environment=? GROUP BY facts.id ORDER BY facts.id LIMIT 20001""",
                                       (scope, environment)).fetchall()
        nodes = []
        for row in entity_rows[:10000]:
            if time.monotonic() - started >= 5:
                break
            item = json.loads(row["body"])
            if item.get("boundary", "unknown") != "unknown":
                item["boundary"] = "unknown"
                boundary_rows = connection.execute("""SELECT observations.body FROM sightings
                    JOIN observations ON observations.id=sightings.observation_id WHERE sightings.entity_id=?
                    AND sightings.catalog=0 AND observations.lifecycle='active'
                    ORDER BY observations.created_at DESC LIMIT 100""", (row["id"],))
                for observed in boundary_rows:
                    boundary = next((candidate["boundary"] for candidate in json.loads(observed["body"])["entities"]
                                     if candidate["id"] == row["id"]), "unknown")
                    if boundary != "unknown":
                        item["boundary"] = boundary
                        break
            item["aliases"] = [alias[0] for alias in connection.execute(
                "SELECT label FROM aliases WHERE entity_id=? ORDER BY label LIMIT 20", (row["id"],))]
            item["catalog"] = not bool(row["diagnostic"])
            nodes.append(item)
        node_ids = {node["id"] for node in nodes}
        edges = []
        for row in fact_rows[:20000]:
            if time.monotonic() - started >= 5:
                break
            if row["source"] in node_ids and row["target"] in node_ids:
                active = connection.execute("SELECT body FROM supports WHERE fact_id=? AND lifecycle='active' ORDER BY id LIMIT 1",
                                            (row["id"],)).fetchone()
                item = json.loads(active["body"])
                item.pop("evidence_ids", None)
                item["support_count"] = row["support_count"]
                item["review_status"] = "historical_requires_current_reverification"
                edges.append(item)
        stale = connection.execute("""SELECT DISTINCT facts.source,facts.target FROM facts
            JOIN supports ON supports.fact_id=facts.id WHERE facts.scope=? AND facts.environment=?
            AND supports.lifecycle='stale'""", (scope, environment)).fetchall()
        stale_entities = {row[key] for row in stale for key in ("source", "target")}
        for node in nodes:
            node["evidence_expired"] = node["id"] in stale_entities
        return {"nodes": nodes, "edges": edges,
                "complete": len(entity_rows) <= 10000 and len(fact_rows) <= 20000 and time.monotonic() - started < 5,
                "graph_revision": int(connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])}

    @staticmethod
    def _bundles(connection, fact_id: str) -> list[dict]:
        rows = connection.execute("""SELECT supports.*,observations.case_id FROM supports
            JOIN observations ON observations.id=supports.observation_id
            WHERE supports.fact_id=? AND supports.lifecycle='active' ORDER BY supports.id LIMIT 3""", (fact_id,)).fetchall()
        result = []
        for row in rows:
            evidence_rows = connection.execute("""SELECT evidence.id,evidence.body FROM evidence
                JOIN support_evidence ON support_evidence.evidence_id=evidence.id
                WHERE support_evidence.support_id=? ORDER BY evidence.id""", (row["id"],)).fetchall()
            evidence, identifiers = [], {}
            for item in evidence_rows:
                body = json.loads(item["body"])
                identifiers[body["id"]] = item["id"]
                evidence.append({**body, "local_id": body["id"], "id": item["id"]})
            if not evidence:
                raise BusinessLogicGraphError("GRAPH_CORRUPT")
            fact = json.loads(row["body"])
            fact["evidence_ids"] = [identifiers[key] for key in fact["evidence_ids"]]
            result.append({"id": row["id"], "case_id": row["case_id"], "observation_id": row["observation_id"],
                           "level": row["level"], "fact": fact, "evidence": evidence})
        return result

    def _pack(self, connection, snapshot: dict, nodes: list[dict], edges: list[dict],
              scope: str, environment: str, projection: str, frontier: list[str], truncated: bool) -> dict:
        result = {"available": True, "format_version": 3, "scope_id": scope, "environment": environment,
                  "projection": projection, "graph_revision": snapshot["graph_revision"],
                  "must_reverify_current_published_copy": True, "nodes": nodes, "edges": [], "evidence": [],
                  "frontier": frontier[:200], "truncated": truncated or not snapshot["complete"],
                  "scope_complete": snapshot["complete"], "mermaid": render_mermaid(nodes, [])}
        if len(_encoded(result)) > MAX_RESPONSE_BYTES:
            while result["nodes"] and len(_encoded(result)) > MAX_RESPONSE_BYTES // 2:
                omitted = result["nodes"].pop()
                result["mermaid"] = render_mermaid(result["nodes"], [])
                if len(result["frontier"]) < 200:
                    result["frontier"].append(omitted["id"])
            result["truncated"] = True
        selected = {node["id"] for node in result["nodes"]}
        for edge in edges:
            if edge["source"] not in selected or edge["target"] not in selected:
                result["truncated"] = True
                for endpoint in (edge["source"], edge["target"]):
                    if endpoint not in selected and len(result["frontier"]) < 200:
                        result["frontier"].append(endpoint)
                continue
            bundles = self._bundles(connection, edge["id"])
            packed = {**edge, "support_ids": [bundle["id"] for bundle in bundles],
                      "evidence_page_complete": len(bundles) == edge["support_count"]}
            while len(bundles) > 1 and len(_encoded({**result, "edges": result["edges"] + [packed],
                                                   "evidence": result["evidence"] + bundles})) > MAX_RESPONSE_BYTES - 65536:
                bundles.pop()
                packed["support_ids"] = [bundle["id"] for bundle in bundles]
                packed["evidence_page_complete"] = False
            result["edges"].append(packed)
            result["evidence"].extend(bundles)
            result["mermaid"] = render_mermaid(result["nodes"], result["edges"])
            if len(_encoded(result)) > MAX_RESPONSE_BYTES - 65536:
                result["edges"].pop()
                if bundles:
                    del result["evidence"][-len(bundles):]
                result["truncated"] = True
                if len(result["frontier"]) < 200:
                    result["frontier"].append(edge["target"])
                break
        result["mermaid"] = render_mermaid(result["nodes"], result["edges"])
        return result

    @staticmethod
    def _seeds(nodes: list[dict], entity_ids: list[str] | None, query: str | None) -> list[str]:
        if entity_ids is not None:
            if not isinstance(entity_ids, list) or len(entity_ids) > 200:
                raise GraphValidationError("GRAPH_INVALID_COLLECTION")
            return [_hash(value) for value in entity_ids]
        if query is not None:
            words = _text(query).casefold().split()
            return [node["id"] for node in nodes if all(word in _json(node).casefold() for word in words)]
        return [node["id"] for node in nodes[:200]]

    def _case_seeds(self, connection, seeds, nodes, query, scope, environment):
        if query is None:
            return seeds, True
        words, selected = _text(query).casefold().split(), set(seeds)
        known = {node["id"] for node in nodes}
        deadline = time.monotonic() + 1
        rows = connection.execute("""SELECT observations.body FROM observations JOIN cases ON cases.id=observations.case_id
            WHERE cases.scope=? AND cases.environment=? AND observations.lifecycle='active'
            ORDER BY observations.created_at DESC LIMIT 1001""", (scope, environment))
        for index, row in enumerate(rows):
            if index >= 1000 or time.monotonic() >= deadline:
                return sorted(selected), False
            observation = json.loads(row["body"])
            text = _json([observation["case_key"], observation["conclusion"],
                          (observation["legacy"] or {}).get("business_keywords", [])]).casefold()
            if all(word in text for word in words):
                selected.update(item["id"] for item in observation["entities"] if item["id"] in known)
        return sorted(selected), True

    def get_graph(self, *, entity_ids=None, query=None, scope_id=None, environment="development",
                  projection="business", depth=2, include_catalog=False, request_id=None, edge_cursor=None) -> dict:
        from .business_graph_algorithms import neighborhood, project
        scope, environment = namespace(scope_id or self.scope, environment)
        if type(include_catalog) is not bool:
            raise GraphValidationError("GRAPH_INVALID_CATALOG_FLAG")
        if edge_cursor is not None:
            _hash(edge_cursor)
        expansion = self.expand_catalog(entity_ids=entity_ids, query=query, scope_id=scope,
                                        environment=environment, request_id=request_id) if request_id else None
        with self._transaction() as connection:
            snapshot = self._snapshot(connection, scope, environment, include_catalog)
            projected = project(snapshot["edges"], projection)
            seeds = self._seeds(snapshot["nodes"], entity_ids, query)
            seeds, query_complete = self._case_seeds(connection, seeds, snapshot["nodes"], query if entity_ids is None else None, scope, environment)
            nodes, edges, frontier, truncated = neighborhood(snapshot["nodes"], projected, seeds, depth, edge_cursor=edge_cursor)
            result = self._pack(connection, snapshot, nodes, edges, scope, environment, projection, frontier, truncated)
            if expansion is not None:
                result["expansion"] = expansion
            result["next_edge_cursor"] = result["edges"][-1]["id"] if result["truncated"] and result["edges"] else None
            result["query_complete"] = query_complete
            result["truncated"] = result["truncated"] or not query_complete
            return result

    def trace(self, *, start: str, target=None, direction="downstream", max_depth=8, max_paths=5,
              scope_id=None, environment="development") -> dict:
        from .business_graph_algorithms import paths, project
        scope, environment = namespace(scope_id or self.scope, environment)
        _hash(start)
        if target is not None:
            _hash(target)
        with self._transaction() as connection:
            snapshot = self._snapshot(connection, scope, environment, False)
            projected = project(snapshot["edges"], "data")
            found = paths(snapshot["nodes"], projected, start, target, direction, max_depth, max_paths)
            selected = {entity_id for path in found["paths"] for entity_id in path["entities"]}
            edge_ids = {edge_id for path in found["paths"] for edge_id in path["edges"]}
            result = self._pack(connection, snapshot,
                                [node for node in snapshot["nodes"] if node["id"] in selected],
                                [edge for edge in projected if edge["id"] in edge_ids], scope, environment,
                                "data", found["frontier"], found["truncated"])
            retained = {edge["id"] for edge in result["edges"]}
            result.update({key: value for key, value in found.items() if key not in {"frontier", "truncated", "paths"}})
            retained_nodes = {node["id"] for node in result["nodes"]}
            result["paths"] = [path for path in found["paths"] if set(path["edges"]) <= retained
                               and set(path["entities"]) <= retained_nodes]
            if len(result["paths"]) != len(found["paths"]):
                result["truncated"] = True
            result["direction"] = direction
            edge_index = {edge["id"]: edge for edge in projected}
            for path in result["paths"]:
                path["granularity"] = "field_level" if path["edges"] and all(
                    edge_index[key]["granularity"] == "field_level" for key in path["edges"]) else "dataset_level"
                path["conditions_jointly_evaluated"] = False
            return result

    def analyze(self, *, scope_id=None, environment="development", projection="business",
                include_catalog=True, entity_ids=None, request_id=None) -> dict:
        from .business_graph_algorithms import adjacency, components, condensation, project, strongly_connected
        scope, environment = namespace(scope_id or self.scope, environment)
        if type(include_catalog) is not bool:
            raise GraphValidationError("GRAPH_INVALID_CATALOG_FLAG")
        expansion = self.expand_catalog(entity_ids=entity_ids, scope_id=scope, environment=environment,
                                        request_id=request_id) if request_id else None
        with self._transaction(write=True) as connection:
            snapshot = self._snapshot(connection, scope, environment, include_catalog)
            edges = project(snapshot["edges"], projection)
            nodes = snapshot["nodes"]
            summary = {"known_entities": len(nodes), "active_facts": len(edges),
                       "scope_complete": snapshot["complete"], "global_platform_completeness": "unknown"}
            catalogs = [json.loads(row[0]) for row in connection.execute("SELECT body FROM catalogs WHERE scope=? AND environment=?", (scope, environment))]
            membership = {row[0] for row in connection.execute("""SELECT catalog_members.entity_id FROM catalog_members
                JOIN catalogs ON catalogs.id=catalog_members.catalog_id WHERE catalogs.scope=? AND catalogs.environment=?""", (scope, environment))}
            connected = {edge[key] for edge in edges if edge["kind"] not in {"contains", "belongs_to"}
                         for key in ("source", "target")}
            coverage = {"denominator_scope": "materialized_on_demand_catalog_entities", "snapshot_versions": catalogs,
                        "known_directory_entities": len(membership), "entities_with_confirmed_relations": len(membership & connected),
                        "ratio": len(membership & connected) / len(membership) if membership else None}
            if not snapshot["complete"]:
                result = self._pack(connection, snapshot, nodes[:200], edges[:400], scope, environment, projection, [], True)
                result.update(status="incomplete", summary=summary, coverage=coverage, components=[], isolated=[], cycles=[], gaps=[], suggestions=[])
                return result
            groups = components(nodes, edges)
            strongly = strongly_connected(nodes, edges)
            self_loops = {edge["source"] for edge in edges if edge["source"] == edge["target"]}
            cycles = [group for group in strongly if len(group) > 1 or group[0] in self_loops]
            forward, reverse = adjacency(nodes, edges), adjacency(nodes, edges, reverse=True)
            gaps = []
            for node in nodes:
                isolated = not forward[node["id"]] and not reverse[node["id"]]
                boundary = node.get("boundary", "unknown")
                if boundary != "unknown":
                    reason = "business_independent" if boundary == "independent" else "legal_boundary"
                elif node["evidence_expired"] and isolated:
                    reason = "evidence_expired"
                elif isolated or projection == "data" and node["kind"] == "field" and (
                        not forward[node["id"]] or not reverse[node["id"]]):
                    reason = "evidence_missing"
                else:
                    continue
                gap = {"entity_id": node["id"], "label": node["label"], "reason": reason,
                       "is_business_bug": False, "missing_known_producer": not bool(reverse[node["id"]]),
                       "missing_known_consumer": not bool(forward[node["id"]])}
                gaps.append(gap)
                if reason in {"evidence_missing", "evidence_expired"}:
                    self._task(connection, scope, environment, reason, gap, node["id"])
            pending_review = [{"id": row["id"], "reason": row["reason"], **json.loads(row["body"])}
                              for row in connection.execute("""SELECT id,reason,body FROM tasks
                                  WHERE scope=? AND environment IN (?, 'unknown') AND state='pending'
                                  AND reason IN ('identity_unresolved','legacy_review_required') LIMIT 20""", (scope, environment))]
            unresolved = {gap["entity_id"] for gap in gaps if gap["reason"] in {"evidence_missing", "evidence_expired"}}
            for node in nodes:
                if node["id"] not in unresolved:
                    connection.execute("UPDATE tasks SET state='resolved' WHERE entity_id=? AND reason IN ('evidence_missing','evidence_expired')",
                                       (node["id"],))
            suggestions = [{"entity_id": gap["entity_id"], "reason": gap["reason"],
                            "next_step": "Check an existing local catalog or a precise published design; do not infer an edge."}
                           for gap in gaps if gap["reason"] in {"evidence_missing", "evidence_expired"}][:3]
            result = self._pack(connection, snapshot, nodes[:200], edges[:400], scope, environment, projection, [], len(nodes) > 200 or len(edges) > 400)
            condensed = condensation(strongly, edges)
            result.update(status="ok", summary={**summary, "component_count": len(groups), "cycle_count": len(cycles)},
                          components=[{"size": len(group), "members": group[:20], "truncated": len(group) > 20} for group in groups[:200]],
                          isolated=[group[0] for group in groups if len(group) == 1 and not forward[group[0]]][:200],
                          cycles=[{"size": len(group), "members": group[:20], "truncated": len(group) > 20} for group in cycles[:200]],
                          gaps=gaps[:200], pending_review=pending_review, suggestions=suggestions, coverage=coverage,
                          condensation={"nodes": [{**node, "size": len(node["members"]), "members": node["members"][:20],
                                                   "members_truncated": len(node["members"]) > 20} for node in condensed["nodes"][:200]],
                                        "edges": condensed["edges"][:400],
                                        "truncated": len(condensed["nodes"]) > 200 or len(condensed["edges"]) > 400})
            condensed_ids = {node["id"] for node in result["condensation"]["nodes"]}
            result["condensation"]["edges"] = [edge for edge in result["condensation"]["edges"]
                if edge["source"] in condensed_ids and edge["target"] in condensed_ids]
            result["condensation"]["mermaid"] = render_mermaid(result["condensation"]["nodes"], result["condensation"]["edges"])
            if expansion is not None:
                result["expansion"] = expansion
            while len(_encoded(result)) > MAX_RESPONSE_BYTES and any(result[key] for key in ("gaps", "components", "cycles", "isolated")):
                for key in ("gaps", "components", "cycles", "isolated"):
                    result[key] = result[key][:len(result[key]) // 2]
                result["truncated"] = True
            while len(_encoded(result)) > MAX_RESPONSE_BYTES and result["condensation"]["nodes"]:
                result["condensation"]["nodes"] = result["condensation"]["nodes"][:len(result["condensation"]["nodes"]) // 2]
                condensed_ids = {node["id"] for node in result["condensation"]["nodes"]}
                result["condensation"]["edges"] = [edge for edge in result["condensation"]["edges"]
                    if edge["source"] in condensed_ids and edge["target"] in condensed_ids]
                result["condensation"]["mermaid"] = render_mermaid(result["condensation"]["nodes"], result["condensation"]["edges"])
                result["condensation"]["truncated"] = result["truncated"] = True
            return result

    @staticmethod
    def _bounded_lookup(lookup, node, scope, environment, timeout):
        results = queue.Queue(maxsize=1)
        deadline = time.monotonic() + timeout
        def collect():
            try:
                results.put(lookup(node, scope, environment, deadline=deadline))
            except Exception:
                results.put({"reason": "catalog_unavailable"})
        threading.Thread(target=collect, daemon=True).start()
        try:
            return results.get(timeout=timeout)
        except queue.Empty:
            return {"reason": "catalog_budget_exhausted"}

    def expand_catalog(self, *, entity_ids=None, query=None, scope_id=None, environment="development", request_id: str) -> dict:
        from .business_graph_catalog import lookup
        scope, environment = namespace(scope_id or self.scope, environment)
        request_id = _text(request_id)
        started = time.time()
        request_key = _digest([scope, environment, request_id])
        with self._transaction() as connection:
            snapshot = self._snapshot(connection, scope, environment, True)
            seeds = set(self._seeds(snapshot["nodes"], entity_ids, query))
            seeds, _ = self._case_seeds(connection, seeds, snapshot["nodes"], query if entity_ids is None else None, scope, environment)
            seeds = set(seeds)
            roots = [node for node in snapshot["nodes"] if node["id"] in seeds]
        attempted, added, deferred = 0, 0, []
        for node in roots[:3]:
            now = time.time()
            with self._transaction(write=True) as connection:
                connection.execute("INSERT OR IGNORE INTO requests VALUES (?,?,0)", (request_key, started))
                budget = connection.execute("SELECT * FROM requests WHERE id=?", (request_key,)).fetchone()
                if budget["attempts"] >= 3 or time.time() - budget["started"] >= 25:
                    break
                if connection.execute("SELECT 1 FROM request_attempts WHERE request_id=? AND target=?", (request_key, node["id"])).fetchone():
                    continue
                connection.execute("INSERT INTO request_attempts VALUES (?,?)", (request_key, node["id"]))
                connection.execute("UPDATE requests SET attempts=attempts+1 WHERE id=?", (request_key,))
            attempted += 1
            try:
                found = self._bounded_lookup(lookup, node, scope, environment, min(10, max(0, 25 - (time.time() - budget["started"]))))
            except (ValueError, OSError, KeyError, TypeError):
                found = {"reason": "catalog_unavailable"}
            if "observation" not in found:
                reason = found.get("reason", "catalog_unavailable")
                with self._transaction(write=True) as connection:
                    self._task(connection, scope, environment, reason, {"entity_id": node["id"], "label": node["label"]}, node["id"])
                deferred.append({"entity_id": node["id"], "reason": reason})
                continue
            try:
                normalized = normalize_v3(found["observation"], scope)
                source, version = _text(found["source"]), _text(found["version"])
                if normalized["scope_id"] != scope or normalized["environment"] != environment:
                    raise GraphValidationError("GRAPH_CATALOG_NAMESPACE_MISMATCH")
            except (ValueError, KeyError, TypeError):
                with self._transaction(write=True) as connection:
                    self._task(connection, scope, environment, "catalog_evidence_incomplete", {"entity_id": node["id"]}, node["id"])
                deferred.append({"entity_id": node["id"], "reason": "catalog_evidence_incomplete"})
                continue
            with self._transaction(write=True) as connection:
                result = self._put(connection, normalized)
                catalog_id = _digest([scope, environment, source])
                previous = connection.execute("SELECT version FROM catalogs WHERE id=?", (catalog_id,)).fetchone()
                if previous and previous["version"] != version:
                    connection.execute("DELETE FROM catalog_members WHERE catalog_id=?", (catalog_id,))
                body = {"source": source, "snapshot_version": version, "scope_id": scope,
                        "directory_scope": "on_demand_verified_identity"}
                connection.execute("INSERT INTO catalogs VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET version=excluded.version,body=excluded.body",
                                   (catalog_id, scope, environment, source, version, _json(body)))
                for item in normalized["entities"]:
                    connection.execute("INSERT OR IGNORE INTO catalog_members VALUES (?,?)", (catalog_id, item["id"]))
                added += result["delta"]["new_entities"]
        with self._transaction() as connection:
            budget = connection.execute("SELECT * FROM requests WHERE id=?", (request_key,)).fetchone()
        return {"request_id": request_id, "attempted": attempted, "total_attempts": budget["attempts"] if budget else 0,
                "new_directory_entities": added, "deferred": deferred, "max_calls": 3, "max_hops": 1,
                "deadline_seconds": 30, "recursive": False}
