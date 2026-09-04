from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from gxp_core.schema_config import SchemaSnapshotConfig, load_schema_config


class SchemaConfigTests(unittest.TestCase):
    def test_remote_policy_requires_https_and_localhost_allows_http(self) -> None:
        base = {
            "snapshot_dir": "C:/schema-snapshot",
            "policy_scope_id": "dev",
        }
        with self.assertRaises(ValueError):
            SchemaSnapshotConfig.from_dict({**base, "policy_url": "http://policy.example"})
        local = SchemaSnapshotConfig.from_dict({**base, "policy_url": "http://127.0.0.1:8890"})
        self.assertEqual("http://127.0.0.1:8890", local.policy_url)

    def test_config_rejects_secret_fields(self) -> None:
        with self.assertRaises(ValueError):
            SchemaSnapshotConfig.from_dict({
                "snapshot_dir": "C:/schema-snapshot",
                "policy_url": "https://policy.example",
                "policy_scope_id": "dev",
                "policy_token": "must-not-be-in-json",
            })

    def test_missing_config_uses_portable_public_policy_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"GXP_LOWCODE_SCHEMA_CONFIG": f"{directory}/missing.json"}
        ):
            config = load_schema_config()
        self.assertEqual("https://43-135-137-212.sslip.io:8892", config.policy_url)
        self.assertEqual("gxp-development", config.policy_scope_id)


if __name__ == "__main__":
    unittest.main()
