from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gxp_core.policy_client import PolicyUnavailable, relation_id
from gxp_core.schema_config import SchemaSnapshotConfig
from gxp_core.schema_snapshot import SCHEMA_SEARCH_INDEX, SchemaRefreshCooldown, SchemaSnapshotManager


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

    def load_table_metadata(self, table, **kwargs):
        return next((item for item in self.load_schema()["tables"] if item["table_name"] == table), None)

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
        self.enterContext(patch.dict(os.environ, {"GXP_LOWCODE_RUNTIME_ROOT": self.temp.name}))
        self.config = SchemaSnapshotConfig(
            snapshot_dir=str(Path(self.temp.name) / "snapshot"),
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

    def test_explicit_live_does_not_refresh_or_persist_snapshot(self):
        self.manager.ensure_fresh = lambda: self.fail("Full schema must not be refreshed")
        result = self.manager.resolve("orders", ["user_id"], target_table="users", target_columns=["id"], force_live=True)
        self.assertEqual("live_verified", result["status"])
        self.assertEqual("explicit_target", result["verification_scope"])
        self.assertFalse(result["candidate_group_complete"])
        self.assertFalse(self.manager.root.exists())

    def test_explicit_live_rejects_non_unique_and_incomplete_target_keys(self):
        for indexes in ([], [{"index_name": "u", "non_unique": 0, "seq_in_index": 1, "column_name": "id"},
                            {"index_name": "u", "non_unique": 0, "seq_in_index": 2, "column_name": None}],
                        [{"index_name": "u", "non_unique": 0, "seq_in_index": 1, "column_name": "id", "sub_part": 3}]):
            original = self.repository.load_table_metadata
            def metadata(table, **kwargs):
                row = original(table, **kwargs)
                if table == "users":
                    row["indexes"] = indexes
                return row
            self.repository.load_table_metadata = metadata
            result = self.manager.resolve("orders", ["user_id"], target_table="users", target_columns=["id"], force_live=True)
            self.assertEqual("target_unique_key_not_proven", result["reason"])
            self.repository.load_table_metadata = original
        self.assertEqual(0, self.repository.validation_calls)

    def test_explicit_live_policy_and_timeout_are_never_verified(self):
        self.policy.available = False
        result = self.manager.resolve("orders", ["user_id"], target_table="users", target_columns=["id"], force_live=True)
        self.assertEqual("policy_unavailable", result["reason"])
        self.assertEqual(0, self.repository.validation_calls)
        self.policy.available = True
        self.repository.error = TimeoutError("deadline")
        result = self.manager.resolve("orders", ["user_id"], target_table="users", target_columns=["id"], force_live=True)
        self.assertEqual("query_timeout", result["reason"])
        self.assertEqual("unresolved", result["status"])

    def test_explicit_live_rechecks_policy_after_aggregate(self):
        validate = self.repository.validate_relation
        def changed(*args, **kwargs):
            result = validate(*args, **kwargs)
            self.policy.reject(relation_id("shared-dev", "orders", ["user_id"], "users", ["id"]), "test")
            return result
        self.repository.validate_relation = changed
        result = self.manager.resolve("orders", ["user_id"], target_table="users", target_columns=["id"], force_live=True)
        self.assertEqual("rejected_by_policy", result["reason"])
        self.assertNotEqual("live_verified", result["status"])

    def test_failed_full_refresh_returns_narrow_next_read(self):
        def failed():
            raise TimeoutError("full refresh")
        self.manager.ensure_fresh = failed
        result = self.manager.resolve("orders", ["user_id"], target_table="users", target_columns=["id"])
        self.assertEqual("unresolved", result["status"])
        self.assertEqual("resolve_table_relation", result["next_read"]["tool"])
        self.assertTrue(result["next_read"]["arguments"]["force_live"])

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

    def test_refresh_writes_deep_windows_snapshot_and_reads_legacy_filenames(self):
        parent = Path(self.temp.name).resolve() / ("a" * 90)
        deep = parent / ("b" * (209 - len(str(parent)) - 1)) / "snapshot"
        long_name = "schema_fixture_" + ("t" * 45)
        self.assertGreater(len(str(deep / "tables" / f"{long_name}-01234567.json")), 260)
        self.manager = SchemaSnapshotManager(replace(self.config, snapshot_dir=str(deep)), FakeDatabase(), self.policy)
        self.manager.repository = self.repository
        schema = json.loads(json.dumps(SCHEMA))
        schema["tables"].append(make_table(long_name, [bigint("id")], []))
        with patch.object(self.repository, "load_schema", return_value=schema):
            self.manager.refresh(force=True)
        index_path = deep / "indexes" / "tables.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        for row in index:
            self.assertRegex(Path(row["file"]).name, r"^[0-9a-f]{24}\.json$")
        old_name = "tables/orders-01234567.json"
        (deep / index[0]["file"]).rename(deep / old_name)
        index[0]["file"] = old_name
        index_path.write_text(json.dumps(index), encoding="utf-8")
        self.assertEqual("orders", self.manager.inspect("orders")["table"]["table_name"])

    def test_warm_search_uses_only_v2_index_and_matches_column_comment(self):
        schema = json.loads(json.dumps(SCHEMA))
        schema["tables"][0]["columns"][1]["column_comment"] = "Owner reference"
        with patch.object(self.repository, "load_schema", return_value=schema):
            self.manager.refresh(force=True)
        with patch.object(self.manager, "ensure_fresh", side_effect=AssertionError("No schema refresh")), \
             patch.object(self.manager, "_load_tables", side_effect=AssertionError("No table JSON scan")):
            result = self.manager.search("Owner Reference")
        self.assertEqual("fresh_index", result["source"])
        self.assertTrue(result["complete"])
        self.assertEqual(["user_id"], [c["column_name"] for c in result["matches"][0]["matched_columns"]])
        self.assertFalse(result["relationship_evidence"])

    def test_cold_and_legacy_search_use_live_metadata_then_label_fallback(self):
        with patch.object(self.manager, "ensure_fresh", side_effect=AssertionError("No schema refresh")):
            with patch.object(self.repository, "search_metadata", create=True, return_value=([{"table_name": "orders"}], True)) as search:
                self.assertEqual("live_metadata", self.manager.search("User_ID", limit=200)["source"])
                self.assertEqual(("user_id",), search.call_args.args)
                self.assertEqual(100, search.call_args.kwargs["limit"])
            with patch.object(self.repository, "search_metadata", create=True, side_effect=TimeoutError("no catalog")):
                self.assertEqual("unavailable", self.manager.search("orders")["source"])
                self.manager.refresh(force=True)
                manifest_path = self.manager.root / "manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest["version"] = 1
                manifest["completed_at"] = "2000-01-01T00:00:00Z"
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                (self.manager.root / SCHEMA_SEARCH_INDEX).unlink()
                result = self.manager.search("user_id")
                self.assertEqual("snapshot_fallback", result["source"])
                self.assertEqual("legacy_index_missing_column_comments", result["partial_reason"])
                self.assertTrue(result["stale"])
                self.assertFalse(result["complete"])
                self.assertFalse(result["relationship_evidence"])
                self.assertEqual([{"column_name": "user_id"}], result["matches"][0]["matched_columns"])

    def test_failed_refresh_has_per_snapshot_cooldown_after_failure(self):
        with patch.object(self.repository, "load_schema", side_effect=RuntimeError("offline")) as load:
            with self.assertRaisesRegex(RuntimeError, "offline"):
                self.manager.refresh()
            with self.assertRaisesRegex(SchemaRefreshCooldown, "Recent full schema refresh failed"):
                self.manager.refresh()
            load.assert_called_once()
            self.assertGreater(self.manager.status()["retry_after_seconds"], 0)
            with self.assertRaisesRegex(RuntimeError, "offline"):
                self.manager.refresh(force=True)
            self.assertEqual(2, load.call_count)
        result = self.manager.refresh(force=True)
        self.assertTrue(result["refreshed"])
        self.assertEqual(0, self.manager.status()["retry_after_seconds"])


if __name__ == "__main__":
    unittest.main()
