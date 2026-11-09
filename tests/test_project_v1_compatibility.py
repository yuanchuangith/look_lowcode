"""Compatible project activation uses only temporary files and a fake keyring."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_project_context import context, settings
from gxp_core import connection_settings as legacy


class ProjectV1CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.enterContext(patch.dict(os.environ, {
            "APPDATA": str(self.root / "roaming"), "LOCALAPPDATA": str(self.root / "local"),
            "GXP_LOWCODE_SHARED_CONFIG": str(self.root / "connection.json"),
            "GXP_PROJECT_CONFIG_ROOT": str(self.root / "projects"),
            "GXP_PROJECT_RUNTIME_ROOT": str(self.root / "runtime"),
            "GXP_LOWCODE_EDITOR_CONFIG": str(self.root / "write.json"),
            "GXP_LOWCODE_CONFIG": str(self.root / "look.json"),
            "GXP_LOWCODE_SCHEMA_CONFIG": str(self.root / "schema.json"),
        }))
        context.atomic_json(self.root / "write.json", {"database": {"account_mode": "dedicated", "expected_grants_sha256": ""}})
        database = {"host": "fixture.invalid", "port": 3306, "database": "fixture"}
        scope = context.database_scope(database)
        profile = {"schema_version": 2, "project_id": scope, "name": "Synthetic", "environment": "development",
                   "database": database, "business_scope_id": "development|database:" + scope,
                   "accounts": {"look": {"user": "reader", "credential_target": "Original.Read.Reference"},
                                "write": {"user": "writer", "credential_target": "Original.Write.Reference",
                                          "account_mode": "dedicated", "expected_grants_sha256": ""}},
                   "platform_binding": {}, "platform_version": {}, "refresh": {}}
        profile["revision"] = context.digest(profile)
        self.profile = profile
        self.profile_path = context.config_root() / "profiles" / scope / (profile["revision"] + ".json")
        context.atomic_json(self.profile_path, profile)
        context.atomic_json(context.config_root() / "projects.json", {"schema_version": 2, "projects": {
            scope: {"name": profile["name"], "revision": profile["revision"]}}})
        self.pointer = {"schema_version": 2, "project_id": scope, "profile_revision": profile["revision"],
                        "activation_id": "a" * 32, "refresh_generation": "b" * 32,
                        "revision": "c" * 32, "switch_id": "fixture", "refresh_state": "pending"}
        self.secrets = {("Original.Read.Reference", "reader"): "synthetic-read-value",
                        ("Original.Write.Reference", "writer"): "synthetic-write-value"}
        self.enterContext(patch.object(settings, "_secure_keyring"))
        self.enterContext(patch.object(settings.keyring, "get_password", side_effect=lambda target, user: self.secrets.get((target, user))))
        self.enterContext(patch.object(settings.keyring, "set_password", side_effect=lambda target, user, value: self.secrets.__setitem__((target, user), value)))
        self.enterContext(patch.object(settings.keyring, "delete_password", side_effect=lambda target, user: self.secrets.pop((target, user), None)))

    def publish(self):
        return settings.publish_active(self.profile, self.pointer)

    def test_strict_v1_readers_and_managed_context_use_one_committed_destination(self):
        original_profile = self.profile_path.read_bytes()
        connection = self.publish()
        self.assertEqual({"schema_version", "revision", "host", "port", "database", "accounts"}, set(connection))
        self.assertEqual(1, connection["schema_version"])
        for role, account in connection["accounts"].items():
            self.assertEqual({"user", "credential_target"}, set(account))
            self.assertTrue(account["credential_target"].startswith("GxpLowcode.Connection."))
            original = self.profile["accounts"][role]
            self.assertEqual(self.secrets[(original["credential_target"], original["user"])],
                             self.secrets[(account["credential_target"], account["user"])])
        self.assertEqual(connection, legacy.active_settings())
        self.assertEqual(self.pointer, context.project_active_settings())
        current = context.get_context(role="write")
        self.assertTrue(current.managed)
        self.assertEqual(self.profile["accounts"]["write"]["credential_target"], current.database_configs["write"]["credential_target"])
        self.assertEqual(original_profile, self.profile_path.read_bytes())

    def test_mismatched_sidecar_never_overrides_a_new_v1_connection(self):
        original = self.publish()
        for key, replacement in (("revision", "d" * 32), ("host", "other.invalid"), ("database", "other")):
            changed = {**original, key: replacement}
            context.atomic_json(context.active_path(), changed)
            self.assertEqual(changed, context.project_active_settings())
        for key, replacement in (("user", "other-user"), ("credential_target", "GxpLowcode.Connection.other.look")):
            changed = copy.deepcopy(original)
            changed["accounts"]["look"][key] = replacement
            context.atomic_json(context.active_path(), changed)
            self.assertEqual(changed, context.project_active_settings())
            self.assertFalse(context.get_context(role="look").managed)

    def test_refresh_metadata_changes_neither_v1_bytes_nor_credentials(self):
        self.publish()
        before, secrets = context.active_path().read_bytes(), dict(self.secrets)
        old_revision = settings.revision()
        pointer = {**self.pointer, "refresh_generation": "d" * 32, "revision": "e" * 32}
        settings.publish_metadata(pointer)
        self.assertEqual(before, context.active_path().read_bytes())
        self.assertEqual(secrets, self.secrets)
        self.assertEqual(pointer, context.project_active_settings())
        self.assertNotEqual(old_revision, settings.revision())

    def test_old_v2_pointer_remains_readable(self):
        context.atomic_json(context.active_path(), self.pointer)
        self.assertEqual(self.pointer, context.project_active_settings())
        self.assertTrue(context.get_context(role="write").managed)

    def test_write_policy_mismatch_is_rejected_without_commit_or_new_credentials(self):
        self.publish()
        before, secrets = context.active_path().read_bytes(), dict(self.secrets)
        profile = copy.deepcopy(self.profile)
        profile["accounts"]["write"]["account_mode"] = "shared_unrestricted"
        with self.assertRaises(context.ProjectError) as unsafe:
            settings.publish_active(profile, self.pointer)
        self.assertEqual("PROJECT_WRITE_POLICY_INCOMPATIBLE", unsafe.exception.code)
        self.assertEqual(before, context.active_path().read_bytes())
        self.assertEqual(secrets, self.secrets)

    def test_commit_failure_cleans_only_staged_aliases_and_preserves_v1(self):
        self.publish()
        before, secrets = context.active_path().read_bytes(), dict(self.secrets)
        previous_project = context.project_active_settings()
        atomic = settings.atomic_json
        def fail_connection(path, value):
            if path == context.active_path():
                raise OSError("synthetic commit failure")
            return atomic(path, value)
        with patch.object(settings, "atomic_json", side_effect=fail_connection), self.assertRaises(OSError):
            self.publish()
        self.assertEqual(before, context.active_path().read_bytes())
        self.assertEqual(secrets, self.secrets)
        self.assertEqual(1, legacy.active_settings()["schema_version"])
        self.assertEqual(previous_project, context.project_active_settings())


if __name__ == "__main__":
    unittest.main()
