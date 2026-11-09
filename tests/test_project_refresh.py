"""Isolated worker fixtures; no database, password store or external HTTP requests."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_project_context import ProjectContext
from gxp_project_context._collectors import project_refresh as worker
from gxp_project_context._collectors.cpm_config import CpmConfig


class ProjectRefreshTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.enterContext(patch.dict(os.environ, {
            "GXP_PROJECT_RUNTIME_ROOT": str(self.root / "runtime"),
            "GXP_PROJECT_CONFIG_ROOT": str(self.root / "profiles"),
            "GXP_LOWCODE_SHARED_CONFIG": str(self.root / "connection.json"),
            "GXP_LOWCODE_CONFIG": str(self.root / "look.json"),
            "GXP_LOWCODE_EDITOR_CONFIG": str(self.root / "write.json"),
            "GXP_LOWCODE_SCHEMA_CONFIG": str(self.root / "schema.json"),
            "GXP_LOWCODE_CPM_CONFIG": str(self.root / "cpm.json"),
        }))
        self.enterContext(patch("keyring.get_password", side_effect=AssertionError("No real secret reads")))
        self.enterContext(patch("keyring.set_password", side_effect=AssertionError("No credential writes")))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("No network")))
        self.ctx = ProjectContext(project_id="a" * 64, database_scope="a" * 64, business_scope_id="test",
            activation_id="b" * 32, refresh_generation="c" * 32, managed=True,
            database_configs={"look": {"host": "synthetic.invalid", "port": 3306, "database": "fixture", "user": "reader", "credential_target": "test"}},
            platform_binding={"platform_url": "https://fixture.invalid", "app_id": "app", "site_out_id": "site", "account": "actor", "credential_target": "fixture-platform-reference"})

    def test_schema_reads_only_metadata_and_writes_standard_manifest_with_context(self):
        schema = {"database": "fixture", "tables": [{"table_name": "training", "table_type": "BASE TABLE", "columns": [{"column_name": "id"}], "foreign_keys": []}]}
        with patch.object(worker, "_database", return_value=object()), \
             patch("gxp_project_context._collectors.schema_repository.SchemaMetadataRepository") as repository:
            repository.return_value.load_schema.return_value = schema
            result = worker.collect_schema(self.ctx, time.monotonic() + 5)
            repository.return_value.validate_relation.assert_not_called()
        manifest = json.loads((self.ctx.snapshot_root("schema") / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual("ready", result["status"])
        self.assertEqual(self.ctx.binding(), manifest["project_binding"])
        self.assertTrue(manifest["metadata_only"])
        self.assertEqual([], json.loads((self.ctx.snapshot_root("schema") / "relations/verified.json").read_text(encoding="utf-8")))
        self.assertEqual(1, result["counts"]["tables"])

    def test_old_cli_ok_without_completeness_is_not_reported_as_ready(self):
        cpm_root = self.ctx.snapshot_root("cpm")
        page = cpm_root / "pages/a"
        page.mkdir(parents=True)
        (cpm_root / "manifest.json").write_text('{"platform":{"url":"https://fixture.invalid"}}', encoding="utf-8")
        (page / "page-meta.json").write_text(json.dumps({"route": "form", "id": "page", "designSource": {"version": "draft", "appId": "app", "siteOutId": "site"}}), encoding="utf-8")
        base = CpmConfig("https://old.invalid", "old-account", str(self.root / "node"), str(self.root / "cli"), str(cpm_root))
        with patch("gxp_project_context._collectors.cpm_config.load_cpm_config", return_value=base), \
             patch("gxp_project_context._collectors.cpm_runner.CpmRefreshManager") as manager:
            manager.return_value.refresh.return_value = {"ok": True, "failures": [], "counts": {"pages": 1}}
            result = worker.collect_cpm(self.ctx, time.monotonic() + 5)
            bound = manager.call_args.args[0]
        self.assertEqual("partial", result["status"])
        self.assertFalse(result["complete"])
        self.assertEqual("ready", result["objects"]["page:form"]["status"])
        self.assertEqual("fixture-platform-reference", bound.credential_target)
        self.assertTrue(bound.fresh_pull)

    def test_failed_only_selection_does_not_replace_successful_resource_classes(self):
        successful = self.ctx.snapshot_root("schema") / "manifest.json"
        successful.parent.mkdir(parents=True)
        successful.write_bytes(b'{"previous-success":true}')
        callbacks = []
        with patch.object(worker, "collect_schema") as schema, patch.object(worker, "collect_actions") as actions, \
             patch.object(worker, "collect_cpm", return_value={"status": "unavailable", "complete": False}):
            result = worker.run_collectors(self.ctx, lambda name, value: callbacks.append(name), resource_names=["cpm"])
            schema.assert_not_called()
            actions.assert_not_called()
        self.assertEqual(["cpm"], callbacks)
        self.assertEqual({"cpm"}, set(result["resources"]))
        self.assertEqual(b'{"previous-success":true}', successful.read_bytes())

    def test_cpm_fresh_pull_preserves_explicit_application_binding_without_old_business_files(self):
        from gxp_project_context._collectors.cpm_runner import CpmRefreshManager
        snapshot = self.ctx.snapshot_root("cpm")
        snapshot.mkdir(parents=True)
        (snapshot / "old-page.json").write_text('{"old":true}', encoding="utf-8")
        config = CpmConfig("https://fixture.invalid", "actor", str(self.root / "node"), str(self.root / "cli"), str(snapshot),
                           cache_scope=self.ctx.database_scope, credential_target="fixture-reference",
                           app_id="app", site_out_id="site", fresh_pull=True)
        calls = []
        def fake_run(args, env, timeout):
            calls.append(args)
            work = Path(args[args.index("--out") + 1])
            native = json.loads((work / ".cpm/config.json").read_text(encoding="utf-8"))
            self.assertEqual(("app", "site"), (native["appId"], native["siteOutId"]))
            self.assertFalse((work / "old-page.json").exists())
            report = {"ok": True, "failures": []}
            (work / "manifest.json").write_text('{}', encoding="utf-8")
            return subprocess.CompletedProcess(args, 0, json.dumps(report), "")
        with patch("gxp_project_context._collectors.cpm_runner.get_cpm_password", return_value="fixture-only"), \
             patch.object(CpmRefreshManager, "_run", side_effect=fake_run):
            result = CpmRefreshManager(config).refresh(force=True)
        self.assertTrue(result["ok"])
        self.assertEqual(["login", "pull"], ["login" if "login" in args else "pull" for args in calls])
        self.assertFalse((snapshot / "old-page.json").exists())

    def test_core_collector_mirror_is_exact_and_does_not_need_a_look_server_import(self):
        from gxp_project_context._collectors import CORE_SOURCES
        root = Path(__file__).resolve().parents[1]
        for name in CORE_SOURCES:
            self.assertEqual((root / "mcp/gxp_core" / name).read_bytes(), (root / "mcp/gxp_project_context/_collectors" / name).read_bytes(), name)
        write = root.parent / "write/mcp"
        env = {**os.environ, "PYTHONPATH": str(write)}
        result = subprocess.run([sys.executable, "-c", "import sys; from gxp_project_context._collectors.project_refresh import run_collectors; assert 'gxp_core' not in sys.modules; print('independent')"],
                                cwd=self.root, env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("independent", result.stdout)


if __name__ == "__main__":
    unittest.main()
