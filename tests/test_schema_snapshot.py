from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from gxp_core.policy_client import PolicyUnavailable, relation_id
from gxp_core.schema_config import SchemaSnapshotConfig
from gxp_core.schema_snapshot import SchemaSnapshotManager


def make_table(name, columns, indexes, foreign_keys=None, comment=""):
    return {
        "table_name": name,
        "table_type": "BASE TABLE",
        "engine": "InnoDB",
        "table_collation": "utf8mb4_general_ci",
        "table_comment": comment,
        "columns": columns,
        "indexes": indexes,
        "constraints": [],
        "foreign_keys": foreign_keys or [],
        "checks": [],
    }


def bigint(name):
    return {
        "column_name": name,
        "data_type": "bigint",
        "column_type": "bigint",
        "character_set_name": None,
        "collation_name": None,
        "column_comment": "",
    }


SCHEMA = {
    "database": "dev",
    "tables": [
        make_table("orders", [bigint("id"), bigint("user_id")], [
            {"index_name": "PRIMARY", "non_unique": 0, "seq_in_index": 1, "column_name": "id"}
        ]),
        make_table("users", [bigint("id")], [
            {"index_name": "PRIMARY", "non_unique": 0, "seq_in_index": 1, "column_name": "id"}
        ]),
    ],
}


class FakeDatabase:
    config = SimpleNamespace(database="dev")


class FakeRepository:
    def __init__(self, evidence=None, error=None):
        self.evidence = evidence or {
            "non_null_count": 30,
            "distinct_count": 25,
            "unmatched_count": 0,
            "source_unique": False,
            "match_rate": 1.0,
            "passed": True,
            "reason": "verified",
        }
        self.error = error
        self.validation_calls = 0

    def load_schema(self, **kwargs):
        return json.loads(json.dumps(SCHEMA))

    def validate_relation(self, *args, **kwargs):
        self.validation_calls += 1
        if self.error:
            raise self.error
        return dict(self.evidence)


class FakePolicy:
    def __init__(self):
        self.rejections = set()
        self.revision = 0
        self.available = True

    def sync(self):
        if not self.available:
            raise PolicyUnavailable("offline")
        return {"scope_id": "shared-dev", "revision": self.revision, "rejections": sorted(self.rejections)}

    def reject(self, relation, reason_code):
        self.rejections.add(relation)
        self.revision += 1
        return {"relation_id": relation, "state": "rejected", "revision": self.revision}

    def restore(self, relation):
        self.rejections.discard(relation)
        self.revision += 1
        return {"relation_id": relation, "state": "restored", "revision": self.revision}


class SchemaSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.config = SchemaSnapshotConfig(
            snapshot_dir=str(Path(self.temp.name) / "snapshot"),
            policy_url="http://localhost:8890",
            policy_scope_id="shared-dev",
        )
        self.policy = FakePolicy()
        self.manager = SchemaSnapshotManager(self.config, database=FakeDatabase(), policy=self.policy)
        self.repository = FakeRepository()
        self.manager.repository = self.repository

    def tearDown(self):
        self.temp.cleanup()

    def test_refresh_persists_only_verified_counts_and_lazy_refreshes_once(self):
        first = self.manager.refresh(force=False)
        self.assertTrue(first["refreshed"])
        second = self.manager.ensure_fresh()
        self.assertFalse(second["refreshed"])
        self.assertEqual(1, self.repository.validation_calls)
        verified = json.loads((Path(self.config.snapshot_dir) / "relations" / "verified.json").read_text(encoding="utf-8"))
        self.assertEqual(1, len(verified))
        self.assertEqual("data_verified", verified[0]["kind"])
        serialized = json.dumps(verified, ensure_ascii=False)
        self.assertNotIn("sample", serialized.lower())
        self.assertNotIn("secret-value", serialized)

    def test_user_rejection_suppresses_existing_snapshot_and_future_refresh(self):
        self.manager.refresh(force=True)
        rid = relation_id("shared-dev", "orders", ["user_id"], "users", ["id"])
        self.manager.reject(rid)
        inspected = self.manager.inspect("orders")
        self.assertEqual([], [item for item in inspected["relations"] if item.get("kind") == "data_verified"])
        calls = self.repository.validation_calls
        self.manager.refresh(force=True)
        self.assertEqual(calls, self.repository.validation_calls)
        attempts = json.loads((Path(self.config.snapshot_dir) / "validation-attempts.json").read_text(encoding="utf-8"))
        self.assertEqual("rejected_by_policy", attempts[0]["status"])

    def test_restore_invalidates_old_snapshot_and_requires_live_revalidation(self):
        self.manager.refresh(force=True)
        rid = relation_id("shared-dev", "orders", ["user_id"], "users", ["id"])
        self.manager.reject(rid)
        self.manager.restore(rid)
        verified = json.loads(
            (Path(self.config.snapshot_dir) / "relations" / "verified.json").read_text(encoding="utf-8")
        )
        self.assertEqual([], verified)
        calls = self.repository.validation_calls
        resolved = self.manager.resolve(
            "orders", ["user_id"], target_table="users", target_columns=["id"]
        )
        self.assertEqual("live_verified", resolved["status"])
        self.assertEqual(calls + 1, self.repository.validation_calls)
        self.assertFalse(resolved["persisted"])

    def test_multiple_verified_targets_are_ambiguous_and_not_persisted(self):
        ambiguous_schema = json.loads(json.dumps(SCHEMA))
        ambiguous_schema["tables"].append(make_table("user", [bigint("id")], [
            {"index_name": "PRIMARY", "non_unique": 0, "seq_in_index": 1, "column_name": "id"}
        ]))

        class AmbiguousRepository(FakeRepository):
            def load_schema(self, **kwargs):
                return ambiguous_schema

        self.manager.repository = AmbiguousRepository()
        self.manager.refresh(force=True)
        verified = json.loads(
            (Path(self.config.snapshot_dir) / "relations" / "verified.json").read_text(encoding="utf-8")
        )
        self.assertEqual([], verified)
        attempts = json.loads(
            (Path(self.config.snapshot_dir) / "validation-attempts.json").read_text(encoding="utf-8")
        )
        self.assertEqual({"ambiguous"}, {item["status"] for item in attempts})

    def test_unreliable_relation_uses_live_database_without_persisting(self):
        self.manager.refresh(force=True)
        resolved = self.manager.resolve(
            "orders", ["user_id"], target_table="users", target_columns=["id"], force_live=True
        )
        self.assertEqual("live_verified", resolved["status"])
        self.assertFalse(resolved["persisted"])

    def test_query_timeout_is_recorded_but_never_verified(self):
        self.manager.repository = FakeRepository(error=TimeoutError("read operation timed out"))
        self.manager.refresh(force=True)
        verified = json.loads(
            (Path(self.config.snapshot_dir) / "relations" / "verified.json").read_text(encoding="utf-8")
        )
        attempts = json.loads(
            (Path(self.config.snapshot_dir) / "validation-attempts.json").read_text(encoding="utf-8")
        )
        self.assertEqual([], verified)
        self.assertEqual("query_timeout", attempts[0]["status"])

    def test_policy_outage_fails_closed_for_inferred_relations(self):
        self.policy.available = False
        self.manager.refresh(force=True)
        verified = json.loads((Path(self.config.snapshot_dir) / "relations" / "verified.json").read_text(encoding="utf-8"))
        self.assertEqual([], verified)
        resolved = self.manager.resolve("orders", ["user_id"], target_table="users", target_columns=["id"])
        self.assertEqual("unresolved", resolved["status"])
        self.assertEqual("policy_unavailable", resolved["reason"])

    def test_refresh_failure_keeps_previous_snapshot(self):
        self.manager.refresh(force=True)
        manifest_path = Path(self.config.snapshot_dir) / "manifest.json"
        before = manifest_path.read_bytes()

        class BrokenRepository(FakeRepository):
            def load_schema(self, **kwargs):
                raise RuntimeError("metadata unavailable")

        self.manager.repository = BrokenRepository()
        with self.assertRaises(RuntimeError):
            self.manager.refresh(force=True)
        self.assertEqual(before, manifest_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
