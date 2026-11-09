"""Synthetic legacy role configs; password values and live endpoints are never read."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from contextvars import ContextVar

from gxp_project_context import settings
from gxp_project_context.context import atomic_json, database_scope, load_profile


class LegacyProjectCredentialTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.enterContext(patch.dict(os.environ, {
            "GXP_LOWCODE_SHARED_CONFIG": str(root / "active.json"),
            "GXP_LOWCODE_CONFIG": str(root / "look.json"),
            "GXP_LOWCODE_EDITOR_CONFIG": str(root / "write.json"),
            "GXP_LOWCODE_SCHEMA_CONFIG": str(root / "schema.json"),
            "GXP_PROJECT_CONFIG_ROOT": str(root / "profiles"),
            "GXP_PROJECT_RUNTIME_ROOT": str(root / "runtime"),
            "GXP_LOWCODE_EDITOR_STATE": str(root / "editor.sqlite3"),
            "GXP_FORM_CONFIG_ROOT": str(root / "forms"),
        }))
        self.enterContext(patch("gxp_project_context.context._PINNED", ContextVar("legacy-test-context", default=None)))
        self.enterContext(patch("gxp_project_context.context._PIN_SET", ContextVar("legacy-test-pinned", default=False)))
        self.look = {"host": "old-look.invalid", "port": 3306, "database": "look-old", "user": "original-reader", "credential_target": "fixture.look.original"}
        self.write = {"host": "different-write.invalid", "port": 3307, "database": "write-old", "user": "original-editor",
                      "credential_target": "fixture.write.original", "account_mode": "shared_restricted", "expected_grants_sha256": "a" * 64}
        atomic_json(Path(os.environ["GXP_LOWCODE_CONFIG"]), self.look)
        atomic_json(Path(os.environ["GXP_LOWCODE_EDITOR_CONFIG"]), {"database": self.write})
        # Every secret/network boundary is an assertion so status/copy cannot silently retrieve credentials.
        self.get_password = self.enterContext(patch.object(settings.keyring, "get_password", side_effect=AssertionError("Never read a password when copying references")))
        self.set_password = self.enterContext(patch.object(settings.keyring, "set_password", side_effect=AssertionError("Never duplicate password values")))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("No network")))

    def candidate(self):
        return {"name": "New project", "database": {"host": "new-project.invalid", "port": 3306, "database": "new-db"},
                "accounts": {"look": {"user": self.look["user"]}, "write": {"user": self.write["user"],
                    "account_mode": self.write["account_mode"], "expected_grants_sha256": self.write["expected_grants_sha256"]}},
                "reuse_credentials_from": database_scope(self.look),
                "platform_binding": {"platform_url": "https://new-project.invalid", "app_id": "app", "site_out_id": "site"}}

    def test_status_includes_both_original_role_users_when_legacy_endpoints_differ(self):
        result = settings.settings_status()
        self.assertEqual(self.look["user"], result["settings"]["look_user"])
        self.assertEqual(self.write["user"], result["settings"]["write_user"])
        self.assertEqual(self.write["account_mode"], result["settings"]["account_mode"])
        self.assertEqual(self.write["expected_grants_sha256"], result["settings"]["expected_grants_sha256"])
        self.get_password.assert_not_called()

    def test_explicit_legacy_source_reuses_each_roles_original_reference_across_endpoints(self):
        source = settings._credential_source(database_scope(self.look), settings.registry())
        self.assertEqual(self.write["user"], source["accounts"]["write"]["user"])
        self.assertEqual(self.write["credential_target"], source["accounts"]["write"]["credential_target"])
        saved = settings.save_project(self.candidate(), settings.revision())
        profile = load_profile(saved["project_id"], saved["profile_revision"])
        for role, original in (("look", self.look), ("write", self.write)):
            self.assertEqual(original["user"], profile["accounts"][role]["user"])
            self.assertEqual(original["credential_target"], profile["accounts"][role]["credential_target"])
        self.assertEqual(self.write["account_mode"], profile["accounts"]["write"]["account_mode"])
        self.assertEqual(self.write["expected_grants_sha256"], profile["accounts"]["write"]["expected_grants_sha256"])
        self.assertNotEqual(database_scope(self.look), profile["project_id"])
        self.assertNotEqual(database_scope(self.write), profile["project_id"])
        self.get_password.assert_not_called()
        self.set_password.assert_not_called()

    def test_changed_username_cannot_inherit_other_roles_or_projects_reference(self):
        candidate = self.candidate()
        candidate["accounts"]["write"]["user"] = "different-editor"
        with self.assertRaises(settings.ProjectError) as caught:
            settings.save_project(candidate, settings.revision())
        self.assertEqual("PROJECT_CREDENTIAL_USER_MISMATCH", caught.exception.code)
        self.get_password.assert_not_called()
        self.set_password.assert_not_called()

    def test_unselected_legacy_or_registered_project_is_never_found_by_username(self):
        candidate = self.candidate()
        candidate.pop("reuse_credentials_from")
        for role in ("look", "write"):
            candidate["accounts"][role]["credential_target"] = "unselected." + role
        settings.save_project(candidate, settings.revision())
        # Even though another saved project uses exactly the same usernames,
        # an absent explicit source must fail instead of scanning its references.
        with self.assertRaises(settings.ProjectError) as caught:
            settings._credential_source("f" * 64, settings.registry())
        self.assertEqual("PROJECT_CREDENTIAL_SOURCE_NOT_FOUND", caught.exception.code)
        self.get_password.assert_not_called()


if __name__ == "__main__":
    unittest.main()
