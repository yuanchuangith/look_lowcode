from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core.cpm_config import (
    CPM_CREDENTIAL_TARGET,
    CpmConfig,
    cpm_config_path,
    get_cpm_password,
    save_cpm_config,
    set_cpm_password,
    load_cpm_config,
    upgrade_cpm_runtime,
)


class CpmConfigTests(unittest.TestCase):
    def test_runtime_upgrade_retargets_managed_cli_and_preserves_access_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with patch.dict(os.environ, {"GXP_LOWCODE_CPM_CONFIG": str(root / "cpm.json")}), patch(
                "gxp_core.cpm_config.keyring.get_password"
            ) as getter, patch("gxp_core.cpm_config.keyring.set_password") as setter:
                original = CpmConfig(
                    platform_url="https://cpm.example", account="tester",
                    node_path=str(root / "node-old.exe"),
                    cli_path=str(root / "cpm-cli" / "old" / "dist" / "cli.js"),
                    snapshot_dir=str(root / "snapshot"), ttl_seconds=1234, concurrency=4,
                )
                save_cpm_config(original)
                new_cli = str(root / "cpm-cli" / "new" / "dist" / "cli.js")
                new_node = str(root / "node.exe")
                self.assertTrue(upgrade_cpm_runtime(str(root), new_node, new_cli))
                upgraded = load_cpm_config()
                self.assertEqual(upgraded.cli_path, new_cli)
                self.assertEqual(upgraded.node_path, new_node)
                for field in ("platform_url", "account", "snapshot_dir", "ttl_seconds", "timeout_seconds", "concurrency"):
                    self.assertEqual(getattr(upgraded, field), getattr(original, field))
                self.assertFalse(upgrade_cpm_runtime(str(root), new_node, new_cli))
                self.assertFalse(upgrade_cpm_runtime(str(root), new_node, str(root / "custom-cli.js")))
                getter.assert_not_called()
                setter.assert_not_called()

    def test_password_only_uses_fixed_credential_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ, {"APPDATA": directory}, clear=False
        ), patch("gxp_core.cpm_config.keyring.set_password") as setter, patch(
            "gxp_core.cpm_config.keyring.get_password", return_value="top-secret"
        ) as getter:
            root = Path(directory).resolve()
            config = CpmConfig(
                platform_url="https://cpm.example",
                account="tester",
                node_path=str(root / "node.exe"),
                cli_path=str(root / "dist" / "cli.js"),
                snapshot_dir=str(root / "snapshot"),
            )
            save_cpm_config(config)
            set_cpm_password(config.account, "top-secret")
            self.assertEqual(get_cpm_password(config), "top-secret")
            setter.assert_called_once_with(CPM_CREDENTIAL_TARGET, "tester", "top-secret")
            getter.assert_called_once_with(CPM_CREDENTIAL_TARGET, "tester")
            serialized = cpm_config_path().read_text(encoding="utf-8")
            self.assertNotIn("top-secret", serialized)
            self.assertFalse(any("password" in key.lower() for key in json.loads(serialized)))

    def test_password_fields_are_rejected_from_json_config(self) -> None:
        root = Path(tempfile.gettempdir()).resolve()
        with self.assertRaisesRegex(ValueError, "不得包含密码"):
            CpmConfig.from_dict(
                {
                    "platform_url": "https://cpm.example",
                    "account": "tester",
                    "node_path": str(root / "node.exe"),
                    "cli_path": str(root / "cli.js"),
                    "snapshot_dir": str(root / "snapshot"),
                    "password": "forbidden",
                }
            )


if __name__ == "__main__":
    unittest.main()
