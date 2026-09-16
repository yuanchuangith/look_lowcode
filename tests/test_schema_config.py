from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from gxp_core.schema_config import SchemaSnapshotConfig, load_schema_config


class SchemaConfigTests(unittest.TestCase):
    def test_legacy_remote_url_is_ignored_and_not_saved(self) -> None:
        from dataclasses import asdict
        with tempfile.TemporaryDirectory() as directory:
            config = SchemaSnapshotConfig.from_dict({
                "snapshot_dir": directory, "policy_scope_id": "dev",
                "policy_url": "http://retired-server.invalid",
            })
        self.assertNotIn("policy_url", asdict(config))
        self.assertEqual("dev", config.policy_scope_id)

    def test_config_rejects_secret_fields(self) -> None:
        with self.assertRaises(ValueError):
            SchemaSnapshotConfig.from_dict({
                "snapshot_dir": "C:/schema-snapshot",
                "policy_url": "https://policy.example",
                "policy_scope_id": "dev",
                "policy_token": "must-not-be-in-json",
            })

    def test_missing_config_uses_local_policy_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"GXP_LOWCODE_SCHEMA_CONFIG": f"{directory}/missing.json"}
        ):
            config = load_schema_config()
        self.assertFalse(hasattr(config, "policy_url"))
        self.assertEqual("gxp-development", config.policy_scope_id)


if __name__ == "__main__":
    unittest.main()
