from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .schema_config import (
    SchemaSnapshotConfig,
    _atomic_json,
    schema_policy_cache_path,
)


class PolicyUnavailable(RuntimeError):
    pass


def relation_id(
    scope_id: str,
    source_table: str,
    source_columns: list[str],
    target_table: str,
    target_columns: list[str],
) -> str:
    parts = [
        "relation-v1",
        scope_id.strip(),
        source_table.strip().lower(),
        ",".join(str(item).strip().lower() for item in source_columns),
        target_table.strip().lower(),
        ",".join(str(item).strip().lower() for item in target_columns),
    ]
    return hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class RelationPolicyClient:
    def __init__(self, config: SchemaSnapshotConfig):
        self.config = config
        self.cache_path = schema_policy_cache_path()

    def _load_cache(self) -> dict[str, Any]:
        try:
            value = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if value.get("scope_id") == self.config.policy_scope_id and isinstance(value.get("rejections"), list):
                return value
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
        return {
            "scope_id": self.config.policy_scope_id,
            "revision": -1,
            "rejections": [],
            "fetched_at": None,
        }

    def _request(self, method: str, path: str, *, body: dict[str, Any] | None = None, etag: str | None = None) -> tuple[int, dict[str, Any] | None, str | None]:
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if etag:
            headers["If-None-Match"] = etag
        request = Request(f"{self.config.policy_url}{path}", data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8")) if response.status != 204 else None
                return response.status, payload, response.headers.get("ETag")
        except HTTPError as exc:
            if exc.code == 304:
                return 304, None, exc.headers.get("ETag")
            detail = ""
            try:
                detail = str(json.loads(exc.read().decode("utf-8")).get("error", ""))[:160]
            except Exception:
                pass
            raise PolicyUnavailable(f"relation policy HTTP {exc.code}: {detail or 'request failed'}") from exc
        except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            raise PolicyUnavailable(f"relation policy unavailable: {type(exc).__name__}") from exc

    def sync(self) -> dict[str, Any]:
        cache = self._load_cache()
        etag = f'"{cache["revision"]}"' if int(cache.get("revision", -1)) >= 0 else None
        status, payload, _ = self._request(
            "GET", f"/relation-policy/v1/scopes/{self.config.policy_scope_id}", etag=etag
        )
        if status == 304:
            cache["fetched_at"] = _now()
            _atomic_json(self.cache_path, cache)
            return cache
        if not payload or payload.get("scope_id") != self.config.policy_scope_id:
            raise PolicyUnavailable("relation policy returned an invalid scope payload")
        normalized = {
            "scope_id": self.config.policy_scope_id,
            "revision": int(payload.get("revision", 0)),
            "rejections": sorted({str(item["relation_id"]) for item in payload.get("rejections", [])}),
            "fetched_at": _now(),
        }
        _atomic_json(self.cache_path, normalized)
        return normalized

    def reject(self, relation: str, reason_code: str) -> dict[str, Any]:
        _, payload, _ = self._request(
            "PUT",
            f"/relation-policy/v1/scopes/{self.config.policy_scope_id}/relations/{relation}",
            body={"reason_code": reason_code},
        )
        cache = self._load_cache()
        cache["revision"] = int((payload or {}).get("revision", cache.get("revision", 0)))
        cache["rejections"] = sorted(set(cache.get("rejections", [])) | {relation})
        cache["fetched_at"] = _now()
        _atomic_json(self.cache_path, cache)
        return payload or {}

    def restore(self, relation: str) -> dict[str, Any]:
        _, payload, _ = self._request(
            "DELETE", f"/relation-policy/v1/scopes/{self.config.policy_scope_id}/relations/{relation}"
        )
        cache = self._load_cache()
        cache["revision"] = int((payload or {}).get("revision", cache.get("revision", 0)))
        cache["rejections"] = sorted(set(cache.get("rejections", [])) - {relation})
        cache["fetched_at"] = _now()
        _atomic_json(self.cache_path, cache)
        return payload or {}
