from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gxp_core.cache_scope import database_cache_scope
from gxp_core.config import ConfigurationError, DatabaseConfig
from gxp_core.cpm_config import CpmConfig, cpm_lock_path, cpm_status_path, load_cpm_config, save_cpm_config
from gxp_core.cpm_runner import CpmRefreshManager, _read_status, _write_status
from gxp_core.business_graph_store import BusinessGraphStore
from gxp_core.business_logic_graph import GraphValidationError
from gxp_core.relation_policy import RelationPolicyStore
from gxp_core.schema_config import load_schema_config, save_schema_config, schema_lock_path, schema_status_path
from gxp_core.schema_snapshot import SchemaSnapshotManager
from test_business_graph import observation


class DatabaseCacheIsolationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.look = self.root / "look.json"
        self.shared = self.root / "shared.json"
        self.schema = self.root / "schema.json"
        self.cpm = self.root / "cpm.json"
        self.enterContext(patch.dict(os.environ, {
            "GXP_LOWCODE_CONFIG": str(self.look), "GXP_LOWCODE_SHARED_CONFIG": str(self.shared),
            "GXP_LOWCODE_SCHEMA_CONFIG": str(self.schema), "GXP_LOWCODE_CPM_CONFIG": str(self.cpm),
            "GXP_LOWCODE_RUNTIME_ROOT": str(self.root / "runtime"),
            "GXP_LOWCODE_CONFIG_ROOT": str(self.root / "config"),
        }))
        self.a = DatabaseConfig("synthetic.invalid", 3306, "database_a", "reader")
        self.b = DatabaseConfig("synthetic.invalid", 3306, "database_b", "reader")
        self.select(self.a)
        self.base_cpm = CpmConfig("https://synthetic.invalid", "tester", str(self.root / "node"),
            str(self.root / "cli.js"), str(self.root / "snapshot"))
        save_cpm_config(self.base_cpm)

    def select(self, config):
        self.look.write_text(json.dumps(config.public_dict()), encoding="utf-8")

    def test_legacy_actual_database_partitions_schema_and_reuses_original_partition(self):
        first = load_schema_config()
        self.select(self.b)
        second = load_schema_config()
        self.assertNotEqual(first.snapshot_dir, second.snapshot_dir)
        self.assertNotEqual(first.policy_scope_id, second.policy_scope_id)
        self.assertNotEqual(schema_status_path(first), schema_status_path(second))
        self.assertNotEqual(schema_lock_path(first), schema_lock_path(second))
        self.select(self.a)
        self.assertEqual(first, load_schema_config())
        save_schema_config(first)
        saved = json.loads(self.schema.read_text(encoding="utf-8"))
        self.assertNotIn("|database:", saved["policy_scope_id"])
        self.assertEqual(first, load_schema_config())

    def test_shared_settings_overlay_uses_the_effective_database(self):
        self.shared.write_text(json.dumps({"schema_version": 1, "revision": "a" * 32,
            "host": self.b.host, "port": self.b.port, "database": self.b.database,
            "accounts": {role: {"user": role, "credential_target": "GxpLowcode.Connection.fixture." + role}
                         for role in ("look", "write")}}), encoding="utf-8")
        self.assertTrue(load_schema_config().policy_scope_id.endswith(database_cache_scope(self.b)))
        self.assertEqual(database_cache_scope(self.b), load_cpm_config().cache_scope)

    def test_schema_manager_uses_its_loaded_database_configuration(self):
        database = SimpleNamespace(config=self.a)
        self.select(self.b)
        manager = SchemaSnapshotManager(database=database, policy=object())
        self.assertTrue(manager.config.policy_scope_id.endswith(database_cache_scope(self.a)))

    def test_cpm_snapshot_status_and_lock_are_isolated_without_rewriting_settings(self):
        original = self.cpm.read_bytes()
        old_snapshot = Path(self.base_cpm.snapshot_dir)
        old_snapshot.mkdir()
        (old_snapshot / "old-project.txt").write_text("unknown ownership", encoding="utf-8")
        first = load_cpm_config()
        self.select(self.b)
        second = load_cpm_config()
        self.assertNotEqual(first.snapshot_dir, second.snapshot_dir)
        self.assertNotEqual(cpm_status_path(first), cpm_status_path(second))
        self.assertNotEqual(cpm_lock_path(first), cpm_lock_path(second))
        self.assertFalse(Path(first.snapshot_dir).exists())
        self.assertFalse(Path(second.snapshot_dir).exists())
        _write_status({"version": 1, "full": {"marker": "a"}, "pages": {}}, first)
        self.assertEqual("a", _read_status(first)["full"]["marker"])
        self.assertEqual({}, _read_status(second)["full"])
        self.assertEqual(first, CpmRefreshManager(first).config)
        self.assertEqual(original, self.cpm.read_bytes())
        save_cpm_config(first)
        saved = json.loads(self.cpm.read_text(encoding="utf-8"))
        self.assertEqual(self.base_cpm.snapshot_dir, saved["snapshot_dir"])
        self.assertNotIn("cache_scope", saved)

    def test_graph_scope_arguments_and_invalidation_cannot_reach_another_database(self):
        path = self.root / "graph.sqlite3"
        a = BusinessGraphStore(path, scope_id="a")
        b = BusinessGraphStore(path, scope_id="b")
        claim = {**observation(), "scope_id": "a"}
        saved = a.upsert(claim)
        with self.assertRaisesRegex(GraphValidationError, "GRAPH_SCOPE_MISMATCH"):
            b.upsert(claim)
        with self.assertRaisesRegex(GraphValidationError, "GRAPH_SCOPE_MISMATCH"):
            b.search(scope_id="a")
        self.assertEqual(0, b.invalidate(saved["relation"]["relation_id"], reason="evidence_invalidated")["changed"])
        self.assertTrue(a.search(case_key="case")["found"])
        self.assertEqual([], b.get_graph()["nodes"])

    def test_default_graph_does_not_claim_unowned_legacy_json(self):
        runtime = self.root / "runtime"
        runtime.mkdir()
        fixture = json.loads((Path(__file__).parent / "fixtures/business_logic_graph_training.json").read_text(encoding="utf-8"))
        source = runtime / "business-logic-graph.json"
        source.write_text(json.dumps({"version": 2, "relations": [fixture]}), encoding="utf-8")
        original = source.read_bytes()
        store = BusinessGraphStore()
        result = store.search()
        self.assertEqual([], result["relations"])
        self.assertEqual(1, result["migration"]["unassigned"])
        self.assertEqual(original, source.read_bytes())
        with closing(sqlite3.connect(store.path)) as connection:
            self.assertEqual("legacy-unassigned", connection.execute("SELECT scope FROM tasks").fetchone()[0])

    def test_database_scoped_policy_is_valid_and_has_separate_decisions(self):
        policy = RelationPolicyStore(self.root / "policy.json")
        first = load_schema_config(self.a).policy_scope_id
        second = load_schema_config(self.b).policy_scope_id
        policy.create_scope(first)
        policy.create_scope(second)
        policy.reject(first, "a" * 64, "wrong_columns")
        self.assertEqual([], policy.snapshot(second)["rejections"])

    def test_missing_database_preserves_standalone_cpm_but_invalid_config_does_not(self):
        self.look.unlink()
        self.assertIsNone(database_cache_scope())
        self.assertEqual(self.base_cpm, load_cpm_config())
        self.look.write_text("{}", encoding="utf-8")
        with self.assertRaises(ConfigurationError):
            load_cpm_config()

    def test_restored_project_refresh_and_online_readers_use_the_same_database_generation(self):
        from gxp_project_context import ProjectContext, pin_context
        scope = database_cache_scope(self.a)
        context = ProjectContext(scope, scope, "gxp-development|database:" + scope,
                                 activation_id="a" * 32, refresh_generation="b" * 32, managed=True,
                                 database_configs={"look": self.a.public_dict()},
                                 platform_binding={"platform_url": "https://project.invalid", "account": "project",
                                                   "credential_target": "fixture.platform"})
        with pin_context(context):
            schema = load_schema_config(self.a)
            cpm = load_cpm_config(self.a)
            self.assertEqual(context.snapshot_root("schema"), Path(schema.snapshot_dir))
            self.assertEqual(context.snapshot_root("cpm"), Path(cpm.snapshot_dir))
            self.assertEqual("fixture.platform", cpm.credential_target)
            save_schema_config(schema)
            save_cpm_config(cpm)
        saved_schema = json.loads(self.schema.read_text(encoding="utf-8"))
        saved_cpm = json.loads(self.cpm.read_text(encoding="utf-8"))
        self.assertNotIn(context.refresh_generation, saved_schema["snapshot_dir"])
        self.assertEqual(self.base_cpm.snapshot_dir, saved_cpm["snapshot_dir"])
        self.assertEqual(self.base_cpm.platform_url, saved_cpm["platform_url"])


if __name__ == "__main__":
    unittest.main()
