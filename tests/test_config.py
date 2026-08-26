from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core.config import DatabaseConfig, load_password


class PasswordFileTests(unittest.TestCase):
    def test_password_file_precedes_windows_keyring(self) -> None:
        config = DatabaseConfig(host="db", port=3306, database="gxp", user="readonly")
        with tempfile.TemporaryDirectory() as directory:
            password_file = Path(directory) / "db-password"
            password_file.write_text("server-secret\n", encoding="utf-8")
            with patch.dict(os.environ, {"GXP_LOWCODE_DB_PASSWORD_FILE": str(password_file)}), patch(
                "gxp_core.config.keyring.get_password",
                side_effect=AssertionError("keyring must not be used"),
            ):
                self.assertEqual(load_password(config), "server-secret")


if __name__ == "__main__":
    unittest.main()
