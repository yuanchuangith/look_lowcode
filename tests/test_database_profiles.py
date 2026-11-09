"""Saved connection compatibility, with temporary files and mocked keyring/DB."""
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core import connection_settings as settings
from gxp_project_context import current_database_scope, database_scope, load_profile, profiles_root, _digest
import test_database_settings as baseline


class DatabaseProfileTests(unittest.TestCase):
    def setUp(self):
        baseline.DatabaseSettingsTests.setUp(self)
        self.enterContext(patch.dict(os.environ, {"GXP_PROJECT_CONFIG_ROOT": str(self.root / "profiles"),
                                                  "GXP_FORM_CONFIG_ROOT": str(self.root / "forms")}))

    def save(self, name="original", **changes):
        result = settings.save_project(name, settings.settings_status()["revision"], changes)
        self.assertTrue(result["ok"], result)
        return result["project"]

    def switch(self, project):
        return settings.switch_project(project["project_id"], settings.settings_status()["revision"])

    def test_save_old_config_keeps_credentials_and_write_policy_without_connecting(self):
        before = self.look.read_bytes(), self.write.read_bytes()
        project = self.save()
        profile = load_profile(self.shared, project["project_id"])
        self.assertEqual("old.look", profile["accounts"]["look"]["credential_target"])
        self.assertEqual("old.write", profile["accounts"]["write"]["credential_target"])
        self.assertEqual("shared_restricted", profile["accounts"]["write"]["account_mode"])
        self.assertEqual("a" * 64, profile["accounts"]["write"]["expected_grants_sha256"])
        self.assertEqual(before, (self.look.read_bytes(), self.write.read_bytes()))
        self.assertFalse(self.shared.exists())
        self.get.assert_not_called()
        self.probe.assert_not_called()
        self.set.assert_not_called()

    def test_saved_other_endpoint_reuses_each_original_account_and_password_reference(self):
        project = self.save("second", host="second.example", database="second_db")
        self.assertTrue(self.switch(project)["ok"])
        values, passwords = self.probe.call_args.args
        self.assertEqual("second.example", values["host"])
        self.assertEqual("reader", values["look_user"])
        self.assertEqual("editor", values["write_user"])
        self.assertEqual({"look": "reader-secret", "write": "editor-secret"}, passwords)
        self.assertEqual("shared_restricted", settings.overlay_database(self.write_base["database"], "write")["account_mode"])
        self.assertEqual("reader-secret", self.passwords[("old.look", "reader")])
        self.assertEqual("editor-secret", self.passwords[("old.write", "editor")])
        self.assertEqual(1, json.loads(self.shared.read_text(encoding="utf-8"))["schema_version"])

    def test_switch_uses_the_existing_v1_reader_contract(self):
        project = self.save("second", host="second.example", database="second_db")
        self.assertTrue(self.switch(project)["ok"])
        active = json.loads(self.shared.read_text(encoding="utf-8"))
        self.assertEqual({"schema_version", "revision", "host", "port", "database", "accounts"}, set(active))
        self.assertRegex(active["revision"], r"^[0-9a-f]{32}$")
        for account in active["accounts"].values():
            self.assertEqual({"user", "credential_target"}, set(account))
            self.assertTrue(account["credential_target"].startswith("GxpLowcode.Connection."))
        self.assertEqual("second_db", settings.active_settings()["database"])

    def test_failed_save_keeps_active_connection_and_original_credentials(self):
        project = self.save()
        before = dict(self.passwords)
        with patch.object(settings, "_atomic_save", side_effect=OSError("fixture failure")):
            self.assertFalse(self.switch(project)["ok"])
        self.assertEqual(before, self.passwords)
        self.assertFalse(self.shared.exists())

    def test_switch_back_reuses_database_identity_and_preserves_saved_history(self):
        first = self.save()
        second = self.save("second", database="second_db")
        for project in (first, second, first):
            self.assertTrue(self.switch(project)["ok"])
            self.assertEqual(project["project_id"], current_database_scope())
        self.assertEqual(2, len(settings.list_projects()["projects"]))
        self.assertTrue((profiles_root(self.shared) / "profiles" / second["project_id"] / (second["revision"] + ".json")).exists())

    def test_existing_full_profile_and_pointer_remain_readable(self):
        project = self.save()
        profile = load_profile(self.shared, project["project_id"])
        profile.update(platform_binding={"platform_url": "https://platform.example"},
                       platform_version={"source": "shared"}, refresh={"timeout_seconds": 900})
        profile.pop("revision")
        profile["revision"] = _digest(profile)
        path = profiles_root(self.shared) / "profiles" / project["project_id"] / (profile["revision"] + ".json")
        path.write_text(json.dumps(profile), encoding="utf-8")
        pointer = {"schema_version": 2, "project_id": project["project_id"], "profile_revision": profile["revision"],
                   "revision": "c" * 32, "activation_id": "a" * 32, "refresh_generation": "b" * 32,
                   "refresh_state": "pending", "switch_id": "d" * 32}
        self.shared.write_text(json.dumps(pointer), encoding="utf-8")
        before = self.shared.read_bytes()
        self.assertEqual("old.example", settings.active_settings()["host"])
        self.assertEqual(before, self.shared.read_bytes())
        self.get.assert_not_called()
        self.probe.assert_not_called()

    def test_failed_switch_and_stale_save_preserve_active_config(self):
        project = self.save()
        revision = settings.settings_status()["revision"]
        self.look.write_text(json.dumps({**self.base, "host": "changed.example"}), encoding="utf-8")
        self.assertEqual("SETTINGS_CONFLICT", settings.save_project("stale", revision)["error_code"])
        self.probe.side_effect = settings.SettingsError("SETTINGS_CONNECTION", "connection failed")
        self.assertEqual("SETTINGS_CONNECTION", self.switch(project)["error_code"])
        self.assertFalse(self.shared.exists())

    def test_tampered_or_missing_profile_revision_is_rejected(self):
        project = self.save()
        profile_path = profiles_root(self.shared) / "profiles" / project["project_id"] / (project["revision"] + ".json")
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["database"]["host"] = "tampered.example"
        profile_path.write_text(json.dumps(profile), encoding="utf-8")
        self.assertFalse(self.switch(project)["ok"])
        self.shared.write_text(json.dumps({"schema_version": 2, "project_id": project["project_id"]}), encoding="utf-8")
        self.assertFalse(settings.manage_settings("status")["ok"])
        self.probe.assert_not_called()

    def test_database_identity_ignores_accounts_and_matches_both_plugins(self):
        from gxp_core.handoff_store import environment_scope
        self.assertEqual(environment_scope(self.base), database_scope(self.base))
        self.assertEqual(database_scope(self.base), database_scope({**self.base, "user": "other", "credential_target": "other", "host": " OLD.EXAMPLE "}))
        root = Path(__file__).resolve().parents[2]
        self.assertEqual((root / "look/mcp/gxp_project_context/__init__.py").read_bytes(),
                         (root / "write/mcp/gxp_project_context/__init__.py").read_bytes())


if __name__ == "__main__":
    unittest.main()
