"""The shared settings UI can read status without a Look installation."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_project_context import settings


class StandaloneProjectSettingsTests(unittest.TestCase):
    def test_original_metadata_paths_honor_the_existing_environment_overrides(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            with patch.dict(os.environ, {"GXP_LOWCODE_CONFIG_ROOT": str(base / "config"),
                                         "GXP_LOWCODE_RUNTIME_ROOT": str(base / "data"),
                                         "GXP_LOWCODE_CPM_CONFIG": str(base / "cpm.json"),
                                         "GXP_LOWCODE_SCHEMA_CONFIG": str(base / "schema.json"),
                                         "GXP_FORM_EDITOR_CONFIG": str(base / "form.json")}):
                self.assertEqual(base / "cpm.json", settings._legacy_cpm_config_path())
                self.assertEqual((base / "schema.json").resolve(), settings._legacy_schema_config_path())
                self.assertEqual((base / "data").resolve(), settings._legacy_schema_runtime_root())
                self.assertEqual((base / "form.json").resolve(), settings._legacy_form_config_path())

    def test_write_style_installation_reads_status_without_core_credentials_or_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            package_root = root / "write" / "mcp"
            source = Path(settings.__file__).resolve().parent
            destination = package_root / "gxp_project_context"
            destination.mkdir(parents=True)
            # Only the shared settings modules are installed, never gxp_core.
            for name in ("__init__.py", "_compat.py", "context.py", "settings.py", "refresh.py", "local_sessions.py"):
                shutil.copyfile(source / name, destination / name)
            database = {"host": "fixture.invalid", "port": 3306, "database": "fixture", "user": "fixture-user"}
            configs = {
                "look.json": database,
                "write.json": {"database": database},
                "cpm.json": {"platform_url": "https://fixture.invalid", "account": "fixture-platform",
                             "app_id": "fixture-app", "site_out_id": "fixture-site"},
                "schema.json": {"policy_scope_id": "fixture-development"},
                "form.json": {"base_url": "https://fixture.invalid", "platform": "web", "environment": "development"},
            }
            for name, value in configs.items():
                (root / name).write_text(json.dumps(value), encoding="utf-8")
            environment = dict(os.environ)
            for key, relative in (("APPDATA", "roaming"), ("LOCALAPPDATA", "local"),
                                  ("GXP_LOWCODE_SHARED_CONFIG", "connection.json"),
                                  ("GXP_PROJECT_CONFIG_ROOT", "projects"), ("GXP_PROJECT_RUNTIME_ROOT", "projects-runtime"),
                                  ("GXP_LOWCODE_CONFIG", "look.json"), ("GXP_LOWCODE_EDITOR_CONFIG", "write.json"),
                                  ("GXP_LOWCODE_CPM_CONFIG", "cpm.json"), ("GXP_LOWCODE_SCHEMA_CONFIG", "schema.json"),
                                  ("GXP_FORM_EDITOR_CONFIG", "form.json"), ("GXP_LOWCODE_RUNTIME_ROOT", "legacy-runtime"),
                                  ("GXP_LOWCODE_EDITOR_STATE", "missing-action.sqlite3"), ("GXP_FORM_CONFIG_ROOT", "missing-forms")):
                environment[key] = str(root / relative)
            dependencies = [str(Path(path).resolve()) for path in sys.path if path and "site-packages" in Path(path).parts]
            environment["PYTHONPATH"] = os.pathsep.join([str(package_root), *dependencies])
            environment["PYTHONIOENCODING"] = "utf-8"
            script = r'''
import importlib.abc,json,socket,sys
class NoLook(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname == 'gxp_core' or fullname.startswith('gxp_core.'):
            raise AssertionError('Standalone Write must not import Look core')
sys.meta_path.insert(0,NoLook())
def forbidden(*args,**kwargs):raise AssertionError('No credentials or network permitted in status')
socket.socket.connect=forbidden
import keyring
keyring.get_password=keyring.set_password=keyring.delete_password=forbidden
from gxp_project_context import settings
status=settings.settings_status()
assert status['settings']['database']=='fixture'
assert status['platform_defaults']['configured'] is True
assert not status['active_edit_sessions']
settings._backup_legacy()
assert not any(name=='gxp_core' or name.startswith('gxp_core.') for name in sys.modules)
print(json.dumps({'ok':status['ok'],'configured':status['configured']}))
'''
            result = subprocess.run([sys.executable, "-c", script], env=environment, cwd=root,
                                    capture_output=True, text=True, encoding="utf-8", timeout=20)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual({"ok": True, "configured": True}, json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
