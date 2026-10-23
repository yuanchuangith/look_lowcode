from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

from gxp_core import connection_settings as settings
from gxp_core.config import load_config
from gxp_core.schema_config import load_schema_config, save_schema_config


class DatabaseSettingsTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.look = self.root / "look.json"
        self.write = self.root / "write.json"
        self.shared = self.root / "connection.json"
        self.state = self.root / "state.sqlite3"
        self.enterContext(patch.dict(os.environ, {
            "GXP_LOWCODE_SHARED_CONFIG": str(self.shared), "GXP_LOWCODE_CONFIG": str(self.look),
            "GXP_LOWCODE_EDITOR_CONFIG": str(self.write), "GXP_LOWCODE_EDITOR_STATE": str(self.state),
            "GXP_LOWCODE_SCHEMA_CONFIG": str(self.root / "schema.json"),
        }))
        self.base = {"host": "old.example", "port": 3306, "database": "old_db", "user": "reader", "credential_target": "old.look", "pool_size": 2}
        self.look.write_text(json.dumps(self.base), encoding="utf-8")
        self.write_base = {"database": {**self.base, "user": "editor", "credential_target": "old.write", "account_mode": "shared_restricted", "expected_grants_sha256": "a" * 64},
                           "frontend_repo": str(self.root / "frontend"), "runtime_references": {"directory": str(self.root / "refs")}}
        self.write.write_text(json.dumps(self.write_base), encoding="utf-8")
        self.passwords = {("old.look", "reader"): "reader-secret", ("old.write", "editor"): "editor-secret"}
        self.enterContext(patch.object(settings, "_secure_keyring"))
        self.probe = self.enterContext(patch.object(settings, "_probe"))
        self.get = self.enterContext(patch.object(settings.keyring, "get_password", side_effect=lambda target, user: self.passwords.get((target, user))))
        self.set = self.enterContext(patch.object(settings.keyring, "set_password", side_effect=lambda target, user, password: self.passwords.__setitem__((target, user), password)))
        self.delete = self.enterContext(patch.object(settings.keyring, "delete_password", side_effect=lambda target, user: self.passwords.pop((target, user), None)))

    def update(self, changes=None, **kwargs):
        return settings.update_settings(changes or {"host": "new.example", "database": "new_db"}, settings.settings_status()["revision"], **kwargs)

    def test_status_reads_existing_values_without_credentials_or_database_connection(self):
        result = settings.settings_status()
        self.assertEqual("old.example", result["settings"]["host"])
        self.assertEqual("reader", result["settings"]["look_user"])
        self.assertEqual("editor", result["settings"]["write_user"])
        self.assertFalse(result["configured"])
        self.get.assert_not_called()
        self.probe.assert_not_called()
        self.assertFalse(self.shared.exists())

    def test_commit_is_shared_preserves_base_options_and_never_serializes_passwords(self):
        original_look, original_write = self.look.read_bytes(), self.write.read_bytes()
        result = self.update()
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["changed"])
        config = load_config()
        self.assertEqual("new.example", config.host)
        self.assertEqual("new_db", config.database)
        self.assertEqual(2, config.pool_size)
        self.assertEqual(original_look, self.look.read_bytes())
        self.assertEqual(original_write, self.write.read_bytes())
        self.assertEqual("old.example", load_config(self.look).host)
        for secret in self.passwords.values():
            self.assertNotIn(secret, self.shared.read_text(encoding="utf-8"))
        self.assertEqual("reader-secret", self.passwords[(config.credential_target, config.user)])
        self.assertEqual("reader-secret", self.passwords[("old.look", "reader")])
        overlay = settings.overlay_database(self.write_base["database"], "write")
        self.assertEqual("new_db", overlay["database"])
        self.assertEqual("a" * 64, overlay["expected_grants_sha256"])
        self.assertEqual("shared_restricted", overlay["account_mode"])

    def test_testing_changes_neither_configuration_nor_keyring(self):
        result = self.update(test_only=True, look_password="one", write_password="two")
        self.assertTrue(result["ok"])
        self.assertTrue(result["tested"])
        self.assertFalse(result["changed"])
        self.assertFalse(self.shared.exists())
        self.set.assert_not_called()

    def test_stale_revision_and_private_fields_are_rejected_before_connection(self):
        revision = settings.settings_status()["revision"]
        self.look.write_text(json.dumps({**self.base, "port": 3307}), encoding="utf-8")
        result = settings.update_settings({"host": "new.example"}, revision)
        self.assertEqual("SETTINGS_CONFLICT", result["error_code"])
        for changes in ({"password": "never-print-this"}, {"host": "mysql://bad"}, {"port": True}):
            result = self.update(changes)
            self.assertEqual("SETTINGS_FIELDS", result["error_code"])
            self.assertNotIn("never-print-this", json.dumps(result))
        self.probe.assert_not_called()

    def test_probe_failure_preserves_old_secrets_and_configuration(self):
        self.probe.side_effect = settings.SettingsError("SETTINGS_CONNECTION", "connection failed")
        result = self.update(look_password="new-secret")
        self.assertFalse(result["ok"])
        self.assertFalse(self.shared.exists())
        self.assertEqual("reader-secret", self.passwords[("old.look", "reader")])
        self.set.assert_not_called()

    def test_second_secret_write_failure_rolls_back_only_staged_secret(self):
        original = dict(self.passwords)
        def save(target, user, password):
            if target.endswith(".write"):
                raise RuntimeError("secret backend error")
            self.passwords[(target, user)] = password
        self.set.side_effect = save
        result = self.update()
        self.assertFalse(result["ok"])
        self.assertFalse(self.shared.exists())
        self.assertEqual(original, self.passwords)

    def test_file_failure_rolls_back_staged_secrets_and_keeps_previous_profile(self):
        self.assertTrue(self.update()["ok"])
        previous = self.shared.read_bytes()
        passwords = dict(self.passwords)
        with patch.object(settings, "_atomic_save", side_effect=OSError("no access")):
            result = self.update({"host": "another.example"})
        self.assertFalse(result["ok"])
        self.assertEqual(previous, self.shared.read_bytes())
        self.assertEqual(passwords, self.passwords)

    def test_active_session_blocks_changes_and_is_not_cancelled(self):
        with closing(sqlite3.connect(self.state)) as db:
            db.execute("CREATE TABLE sessions(id TEXT,state TEXT)")
            db.execute("INSERT INTO sessions VALUES('flow','awaiting_approval')")
            db.commit()
        result = self.update()
        self.assertEqual("SETTINGS_ACTIVE_SESSIONS", result["error_code"])
        self.assertEqual("flow", result["active_edit_sessions"][0]["id"])
        self.probe.assert_not_called()
        self.assertFalse(self.shared.exists())

    def test_new_session_during_probe_prevents_commit(self):
        def start_session(*args):
            with closing(sqlite3.connect(self.state)) as db:
                db.execute("CREATE TABLE sessions(id TEXT,state TEXT)")
                db.execute("INSERT INTO sessions VALUES('flow','locked')")
                db.commit()
        self.probe.side_effect = start_session
        previous = dict(self.passwords)
        result = self.update()
        self.assertEqual("SETTINGS_ACTIVE_SESSIONS", result["error_code"])
        self.assertEqual(previous, self.passwords)
        self.assertFalse(self.shared.exists())

    def test_new_user_needs_password_in_local_ui(self):
        result = self.update({"look_user": "other_reader"})
        self.assertEqual("SETTINGS_CREDENTIALS", result["error_code"])
        self.probe.assert_not_called()
        result = self.update({"look_user": "other_reader"}, look_password="local-only")
        self.assertTrue(result["ok"], result)
        self.assertNotIn("local-only", json.dumps(result))

    def test_schema_and_graph_namespace_tracks_environment_and_saves_base_preferences(self):
        legacy = load_schema_config()
        self.assertTrue(self.update()["ok"])
        first = load_schema_config()
        self.assertNotEqual(legacy.snapshot_dir, first.snapshot_dir)
        self.assertIn("|database:", first.policy_scope_id)
        save_schema_config(first)
        self.assertEqual(first, load_schema_config())
        saved = json.loads((self.root / "schema.json").read_text(encoding="utf-8"))
        self.assertEqual(legacy.policy_scope_id, saved["policy_scope_id"])
        self.assertEqual(legacy.snapshot_dir, saved["snapshot_dir"])
        self.assertTrue(self.update({"database": "different_db"})["ok"])
        second = load_schema_config()
        self.assertNotEqual(first.snapshot_dir, second.snapshot_dir)
        self.assertNotEqual(first.policy_scope_id, second.policy_scope_id)

    def test_corrupt_shared_settings_fail_closed(self):
        self.shared.write_text('{"password":"must-not-print"}', encoding="utf-8")
        result = settings.manage_settings("status")
        self.assertFalse(result["ok"])
        self.assertNotIn("must-not-print", json.dumps(result))

    def test_actual_probe_uses_only_read_only_connection_commands_and_redacts_errors(self):
        values = {"host": "test.example", "port": 3306, "database": "db", "look_user": "reader", "write_user": "editor"}
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        # Use the actual function rather than the fixture's no-network stub.
        from importlib import util
        spec = util.spec_from_file_location("settings_probe_fixture", Path(settings.__file__))
        module = util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with patch("pymysql.connect", return_value=connection) as connect:
            module._probe(values, {"look": "one", "write": "two"})
        self.assertEqual(2, connect.call_count)
        self.assertEqual(["SET SESSION TRANSACTION READ ONLY", "SELECT 1"] * 2, [call.args[0] for call in cursor.execute.call_args_list])
        with patch("pymysql.connect", side_effect=RuntimeError("password=one")):
            with self.assertRaises(module.SettingsError) as error:
                module._probe(values, {"look": "one", "write": "two"})
        self.assertNotIn("password=one", str(error.exception))


if __name__ == "__main__":
    unittest.main()
