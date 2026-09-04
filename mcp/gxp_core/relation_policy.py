from __future__ import annotations

import json
import os
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .schema_config import schema_runtime_root


IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
RELATION_ID_RE = re.compile(r"^[a-f0-9]{64}$")
REASON_CODES = {
    "user_confirmed_incorrect",
    "wrong_direction",
    "wrong_columns",
    "not_business_relation",
}
POLICY_VERSION = 1
MAX_POLICY_BYTES = 16 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def default_policy_file_path() -> Path:
    configured = os.environ.get("GXP_RELATION_POLICY_FILE")
    return Path(configured).expanduser().resolve() if configured else schema_runtime_root() / "relation-policy.json"


def _identifier(value: str, label: str) -> str:
    if not IDENTIFIER_RE.fullmatch(value or ""):
        raise ValueError(f"invalid {label}")
    return value


def _relation_id(value: str) -> str:
    if not RELATION_ID_RE.fullmatch(value or ""):
        raise ValueError("invalid relation_id")
    return value


def _empty_document() -> dict[str, Any]:
    return {
        "version": POLICY_VERSION,
        "next_audit_id": 1,
        "scopes": {},
        "decisions": {},
        "audit": [],
    }


class _PolicyFileLock:
    def __init__(self, path: Path, timeout_seconds: float = 10.0):
        self.path = path
        self.timeout_seconds = timeout_seconds
        self.stream: Any = None

    def __enter__(self) -> "_PolicyFileLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stream = self.path.open("a+b")
        self.stream.seek(0, os.SEEK_END)
        if self.stream.tell() == 0:
            self.stream.write(b"0")
            self.stream.flush()
        deadline = time.monotonic() + self.timeout_seconds
        while True:
            try:
                self.stream.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(self.stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except (BlockingIOError, OSError):
                if time.monotonic() >= deadline:
                    self.stream.close()
                    self.stream = None
                    raise TimeoutError("RELATION_POLICY_LOCK_TIMEOUT")
                time.sleep(0.05)

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self.stream is None:
            return
        try:
            self.stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        finally:
            self.stream.close()
            self.stream = None


class RelationPolicyStore:
    """Small, locked and atomically replaced JSON policy store."""

    def __init__(self, path: Path | None = None):
        self.path = (path or default_policy_file_path()).resolve()
        self.lock_path = self.path.with_name(f"{self.path.name}.lock")

    def _read_unlocked(self) -> dict[str, Any]:
        try:
            if self.path.stat().st_size > MAX_POLICY_BYTES:
                raise RuntimeError("relation policy JSON is too large")
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return _empty_document()
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("relation policy JSON is invalid") from exc
        required = {"scopes", "decisions", "audit"}
        if value.get("version") != POLICY_VERSION or not required.issubset(value):
            raise RuntimeError("relation policy JSON has an unsupported structure")
        expected_types = {"scopes": dict, "decisions": dict, "audit": list}
        if not all(isinstance(value[key], expected) for key, expected in expected_types.items()):
            raise RuntimeError("relation policy JSON has invalid collection types")
        value.setdefault("next_audit_id", len(value["audit"]) + 1)
        return value

    def _write_unlocked(self, value: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

    def _read(self) -> dict[str, Any]:
        with _PolicyFileLock(self.lock_path):
            return self._read_unlocked()

    def _mutate(self, operation):
        with _PolicyFileLock(self.lock_path):
            value = self._read_unlocked()
            result = operation(value)
            self._write_unlocked(value)
            return result

    @staticmethod
    def _append_audit(
        value: dict[str, Any], *, scope_id: str, relation_id: str,
        action: str, reason_code: str, client_id: str, created_at: str,
    ) -> None:
        audit_id = int(value.get("next_audit_id", 1))
        value["next_audit_id"] = audit_id + 1
        value["audit"].append({
            "audit_id": audit_id,
            "scope_id": scope_id,
            "relation_id": relation_id,
            "action": action,
            "reason_code": reason_code,
            "client_id": client_id,
            "created_at": created_at,
        })

    def health(self) -> dict[str, Any]:
        self._mutate(lambda _: None)
        return {"ok": True, "storage": "json", "schema_payload": False}

    def create_scope(self, scope_id: str) -> dict[str, Any]:
        scope_id = _identifier(scope_id, "scope_id")
        now = utc_now()

        def create(value: dict[str, Any]) -> dict[str, Any]:
            scope = value["scopes"].setdefault(scope_id, {
                "scope_id": scope_id, "revision": 0, "created_at": now,
            })
            value["decisions"].setdefault(scope_id, {})
            return dict(scope)

        return self._mutate(create)

    def snapshot(self, scope_id: str) -> dict[str, Any]:
        scope_id = _identifier(scope_id, "scope_id")
        value = self._read()
        scope = value["scopes"].get(scope_id)
        if not scope:
            raise ValueError("scope does not exist")
        decisions = value["decisions"].get(scope_id, {})
        rejections = [
            {
                "relation_id": relation_id,
                "reason_code": item["reason_code"],
                "updated_at": item["updated_at"],
            }
            for relation_id, item in sorted(decisions.items())
            if item.get("state") == "rejected"
        ]
        return {"scope_id": scope_id, "revision": int(scope["revision"]), "rejections": rejections}

    def reject(self, scope_id: str, relation_id: str, reason_code: str) -> dict[str, Any]:
        scope_id = _identifier(scope_id, "scope_id")
        relation_id = _relation_id(relation_id)
        client_id = "public"
        if reason_code not in REASON_CODES:
            raise ValueError("invalid reason_code")
        now = utc_now()

        def reject_relation(value: dict[str, Any]) -> dict[str, Any]:
            scope = value["scopes"].get(scope_id)
            if not scope:
                raise ValueError("scope does not exist")
            decisions = value["decisions"].setdefault(scope_id, {})
            current = decisions.get(relation_id)
            repeated = bool(current and current.get("state") == "rejected")
            decisions[relation_id] = {
                "relation_id": relation_id,
                "state": "rejected",
                "reason_code": reason_code,
                "client_id": client_id,
                "created_at": current.get("created_at", now) if current else now,
                "updated_at": now,
            }
            self._append_audit(
                value, scope_id=scope_id, relation_id=relation_id,
                action="reject_repeat" if repeated else "reject",
                reason_code=reason_code, client_id=client_id, created_at=now,
            )
            if not repeated:
                scope["revision"] = int(scope["revision"]) + 1
            return {
                "relation_id": relation_id, "state": "rejected",
                "revision": int(scope["revision"]), "repeated": repeated,
            }

        return self._mutate(reject_relation)

    def restore(self, scope_id: str, relation_id: str) -> dict[str, Any]:
        scope_id = _identifier(scope_id, "scope_id")
        relation_id = _relation_id(relation_id)
        client_id = "public"
        now = utc_now()

        def restore_relation(value: dict[str, Any]) -> dict[str, Any]:
            scope = value["scopes"].get(scope_id)
            if not scope:
                raise ValueError("scope does not exist")
            decisions = value["decisions"].setdefault(scope_id, {})
            current = decisions.get(relation_id)
            changed = bool(current and current.get("state") == "rejected")
            decisions[relation_id] = {
                "relation_id": relation_id,
                "state": "restored",
                "reason_code": "admin_restore",
                "client_id": client_id,
                "created_at": current.get("created_at", now) if current else now,
                "updated_at": now,
            }
            self._append_audit(
                value, scope_id=scope_id, relation_id=relation_id,
                action="restore" if changed else "restore_repeat",
                reason_code="admin_restore", client_id=client_id, created_at=now,
            )
            if changed:
                scope["revision"] = int(scope["revision"]) + 1
            return {
                "relation_id": relation_id, "state": "restored",
                "revision": int(scope["revision"]), "changed": changed,
            }

        return self._mutate(restore_relation)


def add_relation_policy_routes(app, store: RelationPolicyStore | None = None) -> None:
    policy_store = store or RelationPolicyStore()

    async def health(_: Request) -> Response:
        return JSONResponse(policy_store.health())

    async def get_scope(request: Request) -> Response:
        try:
            scope_id = request.path_params["scope_id"]
            payload = policy_store.snapshot(scope_id)
            etag = f'"{payload["revision"]}"'
            if request.headers.get("if-none-match") == etag:
                return Response(status_code=304, headers={"ETag": etag})
            return JSONResponse(payload, headers={"ETag": etag})
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    async def reject(request: Request) -> Response:
        try:
            scope_id = request.path_params["scope_id"]
            relation_id = request.path_params["relation_id"]
            body = await request.json() if request.headers.get("content-length") != "0" else {}
            reason_code = str((body or {}).get("reason_code") or "user_confirmed_incorrect")
            return JSONResponse(policy_store.reject(scope_id, relation_id, reason_code))
        except (json.JSONDecodeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    async def restore(request: Request) -> Response:
        try:
            scope_id = request.path_params["scope_id"]
            relation_id = request.path_params["relation_id"]
            return JSONResponse(policy_store.restore(scope_id, relation_id))
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    app.add_route("/relation-policy/v1/health", health, methods=["GET"])
    app.add_route("/relation-policy/v1/scopes/{scope_id}", get_scope, methods=["GET"])
    app.add_route(
        "/relation-policy/v1/scopes/{scope_id}/relations/{relation_id}", reject, methods=["PUT"]
    )
    app.add_route(
        "/relation-policy/v1/scopes/{scope_id}/relations/{relation_id}", restore, methods=["DELETE"]
    )
