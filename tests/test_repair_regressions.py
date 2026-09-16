from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core import source_analysis, source_index
from gxp_core.canvas import condition_ast, evaluate_condition_ast
from gxp_core.policy_client import relation_id
from gxp_core.relation_policy import RelationPolicyStore
from gxp_core.schema_config import SchemaSnapshotConfig
from gxp_core.schema_snapshot import SchemaSnapshotManager
from gxp_core.source_config import repository_metadata
from test_control_flow import predicate
from test_schema_snapshot import FakeDatabase, FakePolicy, FakeRepository, SCHEMA, bigint, make_table
import test_source_config as source_config_fixtures


class VersionedPolicy(FakePolicy):
    def __init__(self):
        super().__init__()
        self.restores = {}

    def sync(self):
        return {**super().sync(), "protocol_version": 2, "restore_revisions": dict(self.restores)}

    def restore(self, relation):
        result = super().restore(relation)
        self.restores[relation] = self.revision
        return result


class RepairRegressions(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.enterContext(patch("gxp_core.schema_snapshot.schema_lock_path", return_value=self.root / "schema.lock"))
        self.enterContext(patch("gxp_core.schema_snapshot.schema_status_path", return_value=self.root / "status.json"))

    def tearDown(self):
        self.temporary.cleanup()

    def manager(self, name, policy, repository=None):
        config = SchemaSnapshotConfig(snapshot_dir=str(self.root / name), policy_scope_id="shared-dev")
        manager = SchemaSnapshotManager(config, database=FakeDatabase(), policy=policy)
        manager.repository = repository or FakeRepository()
        return manager

    def test_symbolic_operators_remain_compatible(self):
        for operator, expected in {"Equal": "true", "=": "true", "==": "true", "!=": "false", "<>": "false"}.items():
            with self.subTest(operator=operator):
                ast = condition_ast({"Logic": "And", "Filters": [predicate("name", operator, "'A'")]})
                self.assertEqual(expected, evaluate_condition_ast(ast, {"name": "A"})["result"])

    def test_first_unstaged_same_length_edit_changes_content_fingerprint(self):
        checkout = self.root / "repo"
        source_config_fixtures.SourceConfigTests._repo(checkout)
        source = checkout / "source.txt"
        source.write_text("two", encoding="utf-8")
        before = repository_metadata(checkout)
        original = source.stat()
        source.write_text("six", encoding="utf-8")
        os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
        after = repository_metadata(checkout)
        self.assertEqual("source.txt", after["dirty_files"][0]["path"])
        self.assertNotEqual(before["fingerprint"], after["fingerprint"])

    def test_git_status_preserves_rename_and_unicode_paths(self):
        checkout = self.root / "repo"
        source_config_fixtures.SourceConfigTests._repo(checkout)
        subprocess.run(["git", "mv", "source.txt", "中文 file.txt"], cwd=checkout, check=True)
        (checkout / "untracked file.ts").write_text("new", encoding="utf-8")
        result = repository_metadata(checkout)
        names = {item["path"] for item in result["dirty_files"]}
        self.assertIn("中文 file.txt", names)
        self.assertIn("untracked file.ts", names)
        renamed = next(item for item in result["dirty_files"] if item["path"] == "中文 file.txt")
        self.assertEqual("source.txt", renamed["original_path"])

    def test_stale_repository_never_emits_exact(self):
        status = {"status": "error", "index": {"exists": True, "version": 1}, "repositories": {}, "errors": [{"layer": "frontend", "code": "REPOSITORY_AMBIGUOUS"}]}
        indexes = {"frontend/components.json": [{"component_type": "TestPaper", "behavior_names": [{"value": "TestPaper", "path": "old.ts", "line": 7}], "files": []}]}
        with patch.object(source_analysis, "ensure_source_index", return_value=status), patch.object(source_analysis, "load_index_file", side_effect=lambda name, default: indexes.get(name, default)):
            result = source_analysis.inspect_component_source("TestPaper")
        self.assertNotEqual("ok", result["status"])
        self.assertEqual([], [item for item in result["evidence"] if item["confidence"] == "exact"])
        self.assertTrue(result["errors"])

    def test_comments_literals_and_closed_function_are_not_requests(self):
        source = self.root / "src/core/common/service.ts"
        source.parent.mkdir(parents=True)
        source.write_text("export function previous() { return 1; }\n// request.get('/api/commented');\n/* request.post('/api/block'); */\nconst text = '/api/explanation';\nexport const actual = () => request.post('/api/actual');\n", encoding="utf-8")
        data, failures = source_index._scan_frontend(self.root)
        self.assertFalse(failures)
        self.assertEqual([("/api/actual", "POST", "actual")], [(item["route"], item["method"], item["function"]) for item in data["requests"]])

    def test_unrelated_unique_short_name_is_not_a_target(self):
        status = {"index": {"exists": True}, "repositories": {"backend": {"stale": False}}}
        indexes = {
            "backend/symbols.json": [{"kind": "method", "name": "Orders.Save", "path": "Order.cs", "line": 1}, {"kind": "method", "name": "Unrelated.Update", "path": "Other.cs", "line": 1}],
            "graph/backend-call-edges.json": [{"caller": "Orders.Save", "receiver": "ctx", "callee_member": "Update", "path": "Order.cs", "line": 2}],
        }
        with patch.object(source_analysis, "ensure_source_index", return_value=status), patch.object(source_analysis, "load_index_file", side_effect=lambda name, default: indexes.get(name, default)):
            result = source_analysis.trace_backend_call_chain("Orders.Save")
        self.assertEqual([], result["call_tree"][0]["targets"])
        self.assertEqual("candidate", next(item["confidence"] for item in result["evidence"] if item["kind"] == "call"))

    def test_partial_candidate_validation_is_not_unique(self):
        class PartialRepository(FakeRepository):
            def load_schema(self, **kwargs):
                schema = json.loads(json.dumps(SCHEMA))
                schema["tables"].append(make_table("user", [bigint("id")], [{"index_name": "PRIMARY", "non_unique": 0, "seq_in_index": 1, "column_name": "id"}]))
                return schema

            def validate_relation(self, source, columns, target, target_columns, **kwargs):
                if target == "user":
                    raise TimeoutError("query timeout")
                return super().validate_relation(source, columns, target, target_columns, **kwargs)

        manager = self.manager("partial", VersionedPolicy(), PartialRepository())
        manager.refresh(force=True)
        self.assertEqual([], manager.inspect("orders")["relations"])
        self.assertEqual("unresolved", manager.resolve("orders", ["user_id"])["status"])

    def test_cross_machine_restore_revalidates_but_unrelated_change_does_not(self):
        policy = VersionedPolicy()
        first = self.manager("first", policy)
        second = self.manager("second", policy)
        first.refresh(force=True)
        second.refresh(force=True)
        relation = relation_id("shared-dev", "orders", ["user_id"], "users", ["id"])
        first.reject("b" * 64)
        calls = second.repository.validation_calls
        self.assertEqual("data_verified", second.resolve("orders", ["user_id"])["status"])
        self.assertEqual(calls, second.repository.validation_calls)
        first.reject(relation)
        first.restore(relation)
        result = second.resolve("orders", ["user_id"], target_table="users", target_columns=["id"])
        self.assertEqual("live_verified", result["status"])
        self.assertEqual(calls + 1, second.repository.validation_calls)
        self.assertEqual("explicit_target", result["verification_scope"])

    def test_policy_preserves_restore_revision_across_rejection_and_repeats(self):
        store = RelationPolicyStore(self.root / "policy.json")
        store.create_scope("shared-dev")
        relation = "a" * 64
        store.reject("shared-dev", relation, "wrong_columns")
        restored = store.restore("shared-dev", relation)
        first = store.snapshot("shared-dev")
        self.assertEqual(2, first["protocol_version"])
        self.assertEqual(restored["revision"], first["restore_revisions"][relation])
        store.restore("shared-dev", relation)
        store.reject("shared-dev", relation, "wrong_columns")
        self.assertEqual(first["restore_revisions"], store.snapshot("shared-dev")["restore_revisions"])

    def test_policy_changed_during_validation_discards_result(self):
        policy = VersionedPolicy()
        relation = relation_id("shared-dev", "orders", ["user_id"], "users", ["id"])

        class RacingRepository(FakeRepository):
            def validate_relation(self, *args, **kwargs):
                policy.reject(relation, "wrong_columns")
                policy.restore(relation)
                return super().validate_relation(*args, **kwargs)

        manager = self.manager("racing", policy, RacingRepository())
        manager.refresh(force=True)
        self.assertEqual([], manager.inspect("orders")["relations"])
        self.assertEqual("unresolved", manager.resolve("orders", ["user_id"], target_table="users", target_columns=["id"], force_live=True)["status"])


if __name__ == "__main__":
    unittest.main()
