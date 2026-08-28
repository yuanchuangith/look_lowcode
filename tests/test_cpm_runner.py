from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core.cpm_config import CpmConfig
from gxp_core.cpm_runner import CpmRefreshManager, _FileLock


def completed(args: list[str], payload: dict, code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, code, stdout=json.dumps(payload, ensure_ascii=False) + "\n", stderr="")


class CpmRunnerTests(unittest.TestCase):
    def _fixture(self, root: Path) -> CpmConfig:
        cli_root = root / "cpm-cli" / "0.3.1"
        cli = cli_root / "dist" / "cli.js"
        cli.parent.mkdir(parents=True)
        cli.write_text("", encoding="utf-8")
        (cli_root / "package.json").write_text('{"version":"0.3.1"}', encoding="utf-8")
        node = root / "node.exe"
        node.write_text("", encoding="utf-8")
        snapshot = root / "snapshot"
        page = snapshot / "pages" / "page-a"
        (snapshot / ".cpm").mkdir(parents=True)
        (snapshot / ".cpm" / "config.json").write_text("{}", encoding="utf-8")
        page.mkdir(parents=True)
        (snapshot / "manifest.json").write_text("{}", encoding="utf-8")
        (page / "page-meta.json").write_text(
            json.dumps({"version": 1, "route": "/a", "id": "id-a", "outId": "out-a", "name": "A", "dir": "pages/page-a", "componentTypes": [], "eventSubscriptions": []}),
            encoding="utf-8",
        )
        (snapshot / "old-marker.txt").write_text("old", encoding="utf-8")
        return CpmConfig(
            platform_url="https://cpm.example",
            account="tester",
            node_path=str(node.resolve()),
            cli_path=str(cli.resolve()),
            snapshot_dir=str(snapshot.resolve()),
            timeout_seconds=3,
        )

    def test_auth_expiry_logs_in_once_and_password_never_enters_arguments_or_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._fixture(root)
            calls: list[tuple[list[str], dict[str, str]]] = []
            success = {"ok": True, "mode": "page", "page": {"route": "/a"}, "counts": {}, "changes": {}, "failures": [], "health": {}, "durationMs": 1, "error": None}

            def fake_run(args: list[str], env: dict[str, str], timeout: float):
                calls.append((args, env))
                if "login" in args:
                    return subprocess.CompletedProcess(args, 0, stdout="logged in", stderr="")
                pulls = sum(1 for previous, _ in calls if "pull" in previous)
                if pulls == 1:
                    return completed(args, {"ok": False, "error": {"code": "AUTH_EXPIRED", "message": "expired"}}, 1)
                return completed(args, success)

            with patch.dict(os.environ, {"LOCALAPPDATA": str(root / "local")}, clear=False), patch(
                "gxp_core.cpm_runner.get_cpm_password", return_value="top-secret"
            ), patch.object(CpmRefreshManager, "_run", side_effect=fake_run):
                report = CpmRefreshManager(config).refresh(force=True, page_identifier="/a")

            self.assertTrue(report["ok"], report)
            self.assertEqual(["pull", "login", "pull"], ["login" if "login" in args else "pull" for args, _ in calls])
            for args, env in calls:
                self.assertNotIn("top-secret", args)
                self.assertEqual(env["CPM_PASSWORD"], "top-secret")
                self.assertEqual(env["CPM_ACCOUNT"], "tester")
            status_text = (root / "local" / "GxpLowcodeReadonly" / "cpm-refresh-status.json").read_text(encoding="utf-8")
            self.assertNotIn("top-secret", status_text)

    def test_timeout_keeps_old_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._fixture(root)
            with patch.dict(os.environ, {"LOCALAPPDATA": str(root / "local")}, clear=False), patch(
                "gxp_core.cpm_runner.get_cpm_password", return_value="top-secret"
            ), patch.object(
                CpmRefreshManager,
                "_run",
                side_effect=subprocess.TimeoutExpired(cmd="node", timeout=3),
            ):
                report = CpmRefreshManager(config).refresh(force=True, page_identifier="/a")
            self.assertFalse(report["ok"])
            self.assertEqual("REFRESH_TIMEOUT", report["error"]["code"])
            self.assertEqual("old", (Path(config.snapshot_dir) / "old-marker.txt").read_text(encoding="utf-8"))

    def test_success_timestamp_drives_ttl_without_using_manifest_pulled_at(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._fixture(root)
            status_path = root / "local" / "GxpLowcodeReadonly" / "cpm-refresh-status.json"
            status_path.parent.mkdir(parents=True)
            status_path.write_text(
                json.dumps({"version": 1, "full": {"last_completed_at": "2999-01-01T00:00:00Z", "report": {"failures": []}}, "pages": {}}),
                encoding="utf-8",
            )
            # manifest time is deliberately unrelated; status success time is the TTL authority.
            (Path(config.snapshot_dir) / "manifest.json").write_text('{"pulledAt":"2000-01-01T00:00:00Z"}', encoding="utf-8")
            with patch.dict(os.environ, {"LOCALAPPDATA": str(root / "local")}, clear=False), patch.object(
                CpmRefreshManager, "refresh", side_effect=AssertionError("fresh snapshot must not refresh")
            ):
                result = CpmRefreshManager(config).ensure_fresh("/a")
            self.assertTrue(result["skipped"])

    def test_missing_page_metadata_selects_full_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._fixture(root)
            (Path(config.snapshot_dir) / "pages" / "page-a" / "page-meta.json").unlink()
            calls: list[list[str]] = []
            success = {"ok": True, "mode": "full", "page": None, "counts": {}, "changes": {}, "failures": [], "health": {}, "durationMs": 1, "error": None}

            def fake_run(args: list[str], env: dict[str, str], timeout: float):
                calls.append(args)
                return completed(args, success)

            with patch.dict(os.environ, {"LOCALAPPDATA": str(root / "local")}, clear=False), patch(
                "gxp_core.cpm_runner.get_cpm_password", return_value="top-secret"
            ), patch.object(CpmRefreshManager, "_run", side_effect=fake_run):
                report = CpmRefreshManager(config).refresh(force=True, page_identifier="/a")
            self.assertTrue(report["ok"])
            pull_args = next(args for args in calls if "pull" in args)
            self.assertNotIn("--page", pull_args)
            self.assertEqual("full", report["refresh_mode"])

    def test_cross_process_lock_has_bounded_wait(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "refresh.lock"
            with _FileLock(lock_path, 1):
                started = time.monotonic()
                with self.assertRaises(TimeoutError):
                    with _FileLock(lock_path, 0.1):
                        pass
                self.assertLess(time.monotonic() - started, 1)

    def test_online_token_validation_uses_whoami_without_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._fixture(root)
            result = subprocess.CompletedProcess(
                [config.node_path, config.cli_path, "whoami"],
                0,
                stdout="token valid\n",
                stderr="",
            )
            with patch.object(CpmRefreshManager, "_run", return_value=result) as runner:
                report = CpmRefreshManager(config).validate_token()
            self.assertTrue(report["token_valid"])
            args, env, timeout = runner.call_args.args
            self.assertIn("whoami", args)
            self.assertNotIn("CPM_PASSWORD", env)
            self.assertLessEqual(timeout, 30)

    def test_online_token_validation_reports_invalid_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self._fixture(root)
            result = subprocess.CompletedProcess(
                [config.node_path, config.cli_path, "whoami"],
                1,
                stdout="token expired\n",
                stderr="",
            )
            with patch.object(CpmRefreshManager, "_run", return_value=result):
                report = CpmRefreshManager(config).validate_token()
            self.assertFalse(report["token_valid"])
            self.assertEqual("TOKEN_INVALID", report["error"]["code"])


if __name__ == "__main__":
    unittest.main()
