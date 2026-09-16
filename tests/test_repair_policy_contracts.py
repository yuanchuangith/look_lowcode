from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core.policy_client import PolicyUnavailable, RelationPolicyClient
from gxp_core.relation_policy import RelationPolicyStore
from gxp_core.schema_config import SchemaSnapshotConfig
from gxp_core.schema_repository import generate_candidates
from test_repair_regressions import VersionedPolicy
from test_schema_snapshot import FakeDatabase, FakeRepository, SCHEMA, bigint, make_table
from gxp_core.schema_snapshot import SchemaSnapshotManager


class PolicyRepairContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.config = SchemaSnapshotConfig(snapshot_dir=str(self.root / "schema"), policy_scope_id="shared-dev")
        self.enterContext(patch("gxp_core.policy_client.schema_policy_cache_path", return_value=self.root / "policy-cache.json"))
        self.enterContext(patch("gxp_core.relation_policy.default_policy_file_path", return_value=self.root / "local-policy.json"))
        self.enterContext(patch("gxp_core.schema_snapshot.schema_lock_path", return_value=self.root / "schema.lock"))
        self.enterContext(patch("gxp_core.schema_snapshot.schema_status_path", return_value=self.root / "status.json"))

    def tearDown(self):
        self.temporary.cleanup()

    def test_local_decisions_persist_without_network_access(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")) as request:
            client = RelationPolicyClient(self.config)
            self.assertEqual([], client.sync()["rejections"])
            client.reject("a" * 64, "wrong_columns")
            second = RelationPolicyClient(self.config)
            self.assertEqual(["a" * 64], second.sync()["rejections"])
            restored = second.restore("a" * 64)
            self.assertEqual([], client.sync()["rejections"])
            self.assertEqual(restored["revision"], client.sync()["restore_revisions"]["a" * 64])
            request.assert_not_called()

    def test_existing_local_cache_is_imported_once(self):
        cache = {"scope_id": "shared-dev", "revision": 4, "protocol_version": 2,
                 "rejections": ["a" * 64], "restore_revisions": {"b" * 64: 3}}
        (self.root / "policy-cache.json").write_text(json.dumps(cache), encoding="utf-8")
        client = RelationPolicyClient(self.config)
        result = client.sync()
        self.assertEqual(["a" * 64], result["rejections"])
        self.assertEqual({"b" * 64: 3}, result["restore_revisions"])
        client.restore("a" * 64)
        self.assertEqual([], RelationPolicyClient(self.config).sync()["rejections"])
        other = RelationPolicyClient(SchemaSnapshotConfig(snapshot_dir=str(self.root / "schema"), policy_scope_id="other"))
        self.assertEqual([], other.sync()["rejections"])

    def test_invalid_local_store_fails_without_network_fallback(self):
        (self.root / "local-policy.json").write_text("broken", encoding="utf-8")
        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")) as request:
            with self.assertRaisesRegex(PolicyUnavailable, "local relation policy unavailable"):
                RelationPolicyClient(self.config).sync()
            request.assert_not_called()

    def test_local_restore_invalidates_previous_validation(self):
        policy = RelationPolicyClient(self.config)
        manager = SchemaSnapshotManager(self.config, database=FakeDatabase(), policy=policy)
        manager.repository = FakeRepository()
        manager.refresh(force=True)
        verified = manager.resolve("orders", ["user_id"])
        self.assertEqual("data_verified", verified["status"])
        relation = verified["relation"]["relation_id"]
        manager.reject(relation)
        self.assertEqual("rejected", manager.resolve("orders", ["user_id"], target_table="users", target_columns=["id"])["status"])
        manager.restore(relation)
        self.assertEqual("live_verified", manager.resolve("orders", ["user_id"])["status"])

    def test_remote_era_validation_is_not_reused_as_local_evidence(self):
        from gxp_core.schema_snapshot import _policy_allows
        old = {"relation_id": "a" * 64, "policy_revision_at_validation": 0}
        self.assertFalse(_policy_allows(old, RelationPolicyClient(self.config).sync()))

    def test_truncated_candidates_are_never_unique(self):
        schema = json.loads(json.dumps(SCHEMA))
        for name in ("user", "user_profile", "user_account", "user_archive"):
            schema["tables"].append(make_table(name, [bigint("id")], [{"index_name": "PRIMARY", "non_unique": 0, "seq_in_index": 1, "column_name": "id"}], comment="user"))
        candidates = generate_candidates(schema, max_targets_per_source=1)
        self.assertTrue(any(item["candidate_truncated"] for item in candidates))
        policy = VersionedPolicy()
        manager = SchemaSnapshotManager(self.config, database=FakeDatabase(), policy=policy)
        manager.repository = FakeRepository()
        with patch("gxp_core.schema_snapshot.generate_candidates", return_value=[{**candidates[0], "candidate_truncated": True}]):
            manager.refresh(force=True)
            result = manager.resolve("orders", ["user_id"])
        self.assertEqual("unresolved", result["status"])
        self.assertEqual([], manager.inspect("orders")["relations"])

    def test_legacy_protocol_invalidates_on_scope_revision_change(self):
        from test_schema_snapshot import FakePolicy
        policy = FakePolicy()
        manager = SchemaSnapshotManager(self.config, database=FakeDatabase(), policy=policy)
        manager.repository = FakeRepository()
        manager.refresh(force=True)
        calls = manager.repository.validation_calls
        policy.reject("b" * 64, "wrong_columns")
        result = manager.resolve("orders", ["user_id"])
        self.assertEqual("live_verified", result["status"])
        self.assertGreater(manager.repository.validation_calls, calls)

    def test_legacy_restore_tombstone_migration_is_stable(self):
        store = RelationPolicyStore(self.root / "store.json")
        store.create_scope("shared-dev")
        store.reject("shared-dev", "a" * 64, "wrong_columns")
        store.restore("shared-dev", "a" * 64)
        payload = json.loads(store.path.read_text(encoding="utf-8"))
        payload["decisions"]["shared-dev"]["a" * 64].pop("last_restore_revision")
        store.path.write_text(json.dumps(payload), encoding="utf-8")
        restored_revision = store.snapshot("shared-dev")["restore_revisions"]["a" * 64]
        store.reject("shared-dev", "b" * 64, "wrong_columns")
        self.assertEqual(restored_revision, store.snapshot("shared-dev")["restore_revisions"]["a" * 64])

    def test_restored_competing_candidate_invalidates_unique_cache(self):
        from gxp_core.policy_client import relation_id
        schema = json.loads(json.dumps(SCHEMA))
        schema["tables"].append(make_table("user", [bigint("id")], [{"index_name": "PRIMARY", "non_unique": 0, "seq_in_index": 1, "column_name": "id"}]))
        policy = VersionedPolicy()
        competitor = relation_id("shared-dev", "orders", ["user_id"], "user", ["id"])
        policy.reject(competitor, "wrong_columns")
        repository = FakeRepository()
        manager = SchemaSnapshotManager(self.config, database=FakeDatabase(), policy=policy)
        manager.repository = repository
        with patch.object(repository, "load_schema", return_value=schema):
            manager.refresh(force=True)
        self.assertEqual("data_verified", manager.resolve("orders", ["user_id"])["status"])
        policy.restore(competitor)
        calls = repository.validation_calls
        self.assertEqual("unresolved", manager.resolve("orders", ["user_id"])["status"])
        self.assertGreater(repository.validation_calls, calls)

    def test_competitor_restored_during_refresh_is_not_treated_as_rejected(self):
        from gxp_core.policy_client import relation_id
        schema = json.loads(json.dumps(SCHEMA))
        schema["tables"].append(make_table("user", [bigint("id")], [{"index_name": "PRIMARY", "non_unique": 0, "seq_in_index": 1, "column_name": "id"}]))
        policy = VersionedPolicy()
        competitor = relation_id("shared-dev", "orders", ["user_id"], "user", ["id"])
        policy.reject(competitor, "wrong_columns")

        class Repository(FakeRepository):
            def load_schema(self, **kwargs):
                return schema

            def validate_relation(self, *args, **kwargs):
                policy.restore(competitor)
                return super().validate_relation(*args, **kwargs)

        manager = SchemaSnapshotManager(self.config, database=FakeDatabase(), policy=policy)
        manager.repository = Repository()
        manager.refresh(force=True)
        self.assertEqual([], manager.inspect("orders")["relations"])


if __name__ == "__main__":
    unittest.main()
