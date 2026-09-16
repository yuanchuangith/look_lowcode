from __future__ import annotations

import hashlib
import json
from typing import Any

from .schema_config import SchemaSnapshotConfig, schema_policy_cache_path
from .relation_policy import RelationPolicyStore


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


class RelationPolicyClient:
    """Local-only decisions; the class name is retained for existing callers."""

    def __init__(self, config: SchemaSnapshotConfig):
        self.config = config
        self.store = RelationPolicyStore()
        self._initialized = False

    def _initialize(self) -> None:
        if self._initialized:
            return
        # Import only a cache already on this computer. Never fetch remote history.
        if not self.store.has_scope(self.config.policy_scope_id):
            try:
                cached = json.loads(schema_policy_cache_path().read_text(encoding="utf-8"))
            except FileNotFoundError:
                cached = None
            if not isinstance(cached, dict) or cached.get("scope_id") != self.config.policy_scope_id:
                cached = None
            self.store.create_scope(self.config.policy_scope_id, initial_policy=cached)
        self._initialized = True

    def sync(self) -> dict[str, Any]:
        """Read the current local decisions, without network access."""
        try:
            self._initialize()
            payload = self.store.snapshot(self.config.policy_scope_id)
            return {**payload, "storage": "local",
                    "rejections": [item["relation_id"] for item in payload["rejections"]]}
        except (OSError, RuntimeError, ValueError, TypeError, KeyError) as exc:
            raise PolicyUnavailable(f"local relation policy unavailable: {type(exc).__name__}") from exc

    def reject(self, relation: str, reason_code: str) -> dict[str, Any]:
        self.sync()
        return {**self.store.reject(self.config.policy_scope_id, relation, reason_code), "storage": "local"}

    def restore(self, relation: str) -> dict[str, Any]:
        self.sync()
        return {**self.store.restore(self.config.policy_scope_id, relation), "storage": "local"}
