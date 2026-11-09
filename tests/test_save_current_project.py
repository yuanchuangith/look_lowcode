"""Save the current synthetic connection without activating or retrieving secrets."""
from __future__ import annotations

import copy
import os
import tempfile
import unittest
from contextvars import ContextVar
from pathlib import Path
from unittest.mock import patch

from gxp_project_context import settings
from gxp_project_context.context import active_path, atomic_json, database_scope, get_context, load_profile


class SaveCurrentProjectTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.look_path, self.write_path = self.root / "look.json", self.root / "write.json"
        self.enterContext(patch.dict(os.environ, {
            "GXP_LOWCODE_SHARED_CONFIG": str(self.root / "active.json"),
            "GXP_LOWCODE_CONFIG": str(self.look_path),
            "GXP_LOWCODE_EDITOR_CONFIG": str(self.write_path),
            "GXP_LOWCODE_SCHEMA_CONFIG": str(self.root / "schema.json"),
            "GXP_LOWCODE_CPM_CONFIG": str(self.root / "cpm.json"),
            "GXP_FORM_EDITOR_CONFIG": str(self.root / "form.json"),
            "GXP_PROJECT_CONFIG_ROOT": str(self.root / "projects"),
            "GXP_PROJECT_RUNTIME_ROOT": str(self.root / "runtime"),
            "GXP_LOWCODE_EDITOR_STATE": str(self.root / "editor.sqlite3"),
            "GXP_FORM_CONFIG_ROOT": str(self.root / "forms"),
        }))
        self.enterContext(patch("gxp_project_context.context._PINNED", ContextVar("save-current-test-context", default=None)))
        self.enterContext(patch("gxp_project_context.context._PIN_SET", ContextVar("save-current-test-pinned", default=False)))
        self.look = {"host": "old-look.invalid", "port": 3306, "database": "look-old", "user": "original-reader", "credential_target": "fixture.look.original"}
        self.write = {"host": "old-write.invalid", "port": 3307, "database": "write-old", "user": "original-editor",
                      "credential_target": "fixture.write.original", "account_mode": "shared_unrestricted", "expected_grants_sha256": "a" * 64}
        atomic_json(self.look_path, self.look)
        atomic_json(self.write_path, {"database": self.write, "frontend_repo": "synthetic-front", "runtime_references": {"directory": "synthetic-refs"}})
        self.defaults = {"configured": True,
            "platform_binding": {"platform_url": "https://original-platform.invalid", "app_id": "old-app", "site_out_id": "old-site", "account": "original-actor", "credential_target": "fixture.platform.original", "form_config": {"api_prefix": "/gxp2"}},
            "platform_version": {"cpm": {"node_path": "synthetic-node"}}}
        self.enterContext(patch.object(settings, "legacy_platform_defaults", side_effect=lambda: copy.deepcopy(self.defaults)))
        self.get_password = self.enterContext(patch("keyring.get_password", side_effect=AssertionError("No password/token reads while saving current metadata")))
        self.set_password = self.enterContext(patch("keyring.set_password", side_effect=AssertionError("Do not duplicate secret values")))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("No connection test while only saving")))
        self.probe = self.enterContext(patch.object(settings, "probe_database", side_effect=AssertionError("Saving must not connect to a database")))

    def saved_profile(self, result):
        return load_profile(result["project_id"], result["profile_revision"])

    def test_saving_original_connection_preserves_legacy_files_and_does_not_activate(self):
        before = {path: path.read_bytes() for path in (self.look_path, self.write_path)}
        scope = get_context().database_scope
        result = settings.save_current_project(settings.revision())
        self.assertTrue(result["ok"])
        self.assertEqual(scope, result["project_id"])
        self.assertFalse(active_path().exists())
        self.assertEqual(scope, get_context().database_scope)
        self.assertFalse(get_context().managed)
        for path, contents in before.items():
            self.assertEqual(contents, path.read_bytes())
        name = self.saved_profile(result)["name"]
        self.assertIn("原配置", name)
        for part in (self.look["host"], str(self.look["port"]), self.look["database"]):
            self.assertIn(part, name)
        self.get_password.assert_not_called()
        self.set_password.assert_not_called()
        self.probe.assert_not_called()

    def test_original_role_policy_and_all_credential_references_are_retained(self):
        result = settings.save_current_project(settings.revision(), name="Original connection")
        profile = self.saved_profile(result)
        for role, original in (("look", self.look), ("write", self.write)):
            self.assertEqual(original["user"], profile["accounts"][role]["user"])
            self.assertEqual(original["credential_target"], profile["accounts"][role]["credential_target"])
        self.assertEqual(self.write["account_mode"], profile["accounts"]["write"]["account_mode"])
        self.assertEqual(self.write["expected_grants_sha256"], profile["accounts"]["write"]["expected_grants_sha256"])
        self.assertEqual(self.defaults["platform_binding"]["credential_target"], profile["platform_binding"]["credential_target"])
        self.assertEqual("Original connection", profile["name"])
        self.get_password.assert_not_called()
        self.set_password.assert_not_called()

    def test_missing_legacy_write_account_identifies_original_connection_without_saving(self):
        self.write_path.unlink()
        original = self.look_path.read_bytes()
        with self.assertRaises(settings.ProjectError) as caught:
            settings.save_current_project(settings.revision())
        self.assertEqual("PROJECT_CURRENT_ACCOUNTS_MISSING", caught.exception.code)
        self.assertIn("原连接缺少 Write 账号", str(caught.exception))
        self.assertIn("保存项目", str(caught.exception))
        self.assertEqual(original, self.look_path.read_bytes())
        self.assertFalse(active_path().exists())
        self.assertEqual({}, settings.registry()["projects"])
        self.get_password.assert_not_called()
        self.set_password.assert_not_called()
        self.probe.assert_not_called()

    def test_existing_targets_are_not_overwritten_and_repeated_save_has_no_duplicate_project(self):
        targets = []
        for number in (1, 2):
            value = {"name": "Saved target " + str(number), "database": {"host": "target.invalid", "port": 3306, "database": "target" + str(number)},
                     "accounts": {"look": {"user": "target-reader", "credential_target": "fixture.target.look"}, "write": {"user": "target-editor", "credential_target": "fixture.target.write"}},
                     "platform_binding": {"platform_url": "https://target.invalid", "app_id": "target-app", "site_out_id": "target-site"}}
            targets.append(settings.save_project(value, settings.revision()))
        before = {result["project_id"]: self.saved_profile(result) for result in targets}
        first = settings.save_current_project(settings.revision())
        second = settings.save_current_project(settings.revision())
        self.assertEqual(first["project_id"], second["project_id"])
        self.assertEqual(3, len(settings.list_projects()["projects"]))
        entries = settings.registry()["projects"]
        for project_id, original in before.items():
            self.assertEqual(original["revision"], entries[project_id]["revision"])
            self.assertEqual(original, load_profile(project_id, entries[project_id]["revision"]))
        self.assertFalse(active_path().exists())

    def test_login_link_is_saved_for_native_login_and_form_configuration(self):
        result = settings.save_current_project(settings.revision())
        original = self.saved_profile(result)
        fields = ("name", "environment", "database", "accounts", "platform_binding", "platform_version", "refresh")
        profile = {key: copy.deepcopy(original[key]) for key in fields}
        url = "https://original-platform.invalid/custom/auth"
        profile["platform_binding"]["login_url"] = url
        saved = settings.save_project(profile, settings.revision())
        binding = self.saved_profile(saved)["platform_binding"]
        self.assertEqual(url, binding["login_url"])
        self.assertEqual(url, binding["form_config"]["login_url"])
        profile["platform_binding"]["form_config"]["login_url"] = url
        profile["platform_binding"]["login_url"] = ""
        cleared = self.saved_profile(settings.save_project(profile, settings.revision()))
        self.assertEqual("", cleared["platform_binding"]["login_url"])
        self.assertEqual("", cleared["platform_binding"]["form_config"]["login_url"])
        self.get_password.assert_not_called()
        self.set_password.assert_not_called()

    def test_existing_legacy_active_pointer_is_byte_identical_after_saving(self):
        pointer = {"schema_version": 1, "revision": "b" * 32,
                   **{key: self.look[key] for key in ("host", "port", "database")},
                   "accounts": {role: {"user": config["user"], "credential_target": config["credential_target"]}
                                for role, config in (("look", self.look), ("write", self.write))}}
        atomic_json(active_path(), pointer)
        original = active_path().read_bytes()
        result = settings.save_current_project(settings.revision())
        self.assertEqual(original, active_path().read_bytes())
        self.assertEqual(database_scope(self.look), result["project_id"])
        self.assertEqual(self.write["account_mode"], self.saved_profile(result)["accounts"]["write"]["account_mode"])
        self.assertFalse(get_context().managed)


if __name__ == "__main__":
    unittest.main()
