"""Installer updates preserve running runtimes and the previous plugin payload."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
spec = importlib.util.spec_from_file_location("codex_installer_fixture", SCRIPTS / "install_codex_plugin.py")
installer = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules), patch.object(sys, "path", [str(SCRIPTS), *sys.path]):
    setup_spec = importlib.util.spec_from_file_location("setup", SCRIPTS / "setup.py")
    setup_module = importlib.util.module_from_spec(setup_spec)
    sys.modules["setup"] = setup_module
    setup_spec.loader.exec_module(setup_module)
    spec.loader.exec_module(installer)


class CodexInstallerTests(unittest.TestCase):
    def test_replacing_plugin_keeps_previous_and_older_backups(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            target, staged = parent / "plugin", parent / "staged"
            target.mkdir()
            staged.mkdir()
            (target / "old.txt").write_text("old")
            (staged / "new.txt").write_text("new")
            previous = parent / ".plugin.previous"
            previous.mkdir()
            backup = installer._replace_plugin(staged, target, parent)
            self.assertTrue((backup / "old.txt").is_file())
            self.assertTrue((target / "new.txt").is_file())
            self.assertTrue(previous.is_dir())

    def test_skip_runtime_does_not_run_setup_and_keeps_plugin_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            python.parent.mkdir(parents=True)
            python.touch()
            target = root / "codex-marketplace/plugins" / installer.PLUGIN_NAME
            target.mkdir(parents=True)
            (target / "old.txt").write_text("old")
            with patch.object(installer, "runtime_root", return_value=root), patch.object(
                installer, "install_runtime"
            ) as setup, patch.object(installer.subprocess, "run") as probe, patch.object(
                installer, "_codex_command", return_value="codex"
            ), patch.object(installer, "_marketplace_roots", return_value={}), patch.object(
                installer, "_plugin_payload", side_effect=lambda path: (path / "new.txt").write_text("new")
            ), patch.object(installer, "_run_codex", return_value=SimpleNamespace(stdout="{}")), contextlib.redirect_stdout(io.StringIO()):
                result = installer.install_plugin(skip_runtime=True)
            setup.assert_not_called()
            self.assertEqual([str(python), "-c", "import mcp, keyring, pymysql"], probe.call_args.args[0])
            self.assertTrue(result["runtime_reused"])
            self.assertTrue((Path(result["previous_plugin_backup"]) / "old.txt").is_file())

    def test_conflicting_marketplace_is_rejected_before_payload_replacement(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            installer, "runtime_root", return_value=Path(directory)
        ), patch.object(installer, "install_runtime"), patch.object(
            installer, "_codex_command", return_value="codex"
        ), patch.object(installer, "_marketplace_roots", return_value={installer.MARKETPLACE_NAME: Path(directory) / "other"}), patch.object(
            installer, "_replace_plugin"
        ) as replace:
            with self.assertRaisesRegex(RuntimeError, "already points"):
                installer.install_plugin()
            replace.assert_not_called()


if __name__ == "__main__":
    unittest.main()
