from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from scripts import install_claude, run_tests, setup, verify_mcp


class TestRunnerTests(unittest.TestCase):
    def test_runtime_selection_and_missing_runtime_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            python = setup._venv_python(root)
            with patch.object(run_tests, "runtime_root", return_value=root):
                self.assertEqual(run_tests.select_python(), Path(sys.executable))
                python.parent.mkdir(parents=True)
                python.touch()
                self.assertEqual(run_tests.select_python(), python)

    def test_relaunch_propagates_arguments_and_failure(self) -> None:
        with patch.object(run_tests, "select_python", return_value=Path("other-python")), patch.object(
            run_tests.subprocess, "run", return_value=SimpleNamespace(returncode=7)
        ) as launch:
            self.assertEqual(run_tests.main(["-p", "test_canvas.py", "-v"]), 7)
        self.assertEqual(launch.call_args.args[0][2:], ["--current-python", "-p", "test_canvas.py", "-v"])
        self.assertEqual(launch.call_args.kwargs["cwd"], run_tests.REPO_ROOT)

    def test_paths_live_opt_in_and_test_exit_codes(self) -> None:
        for arguments, success, expected_live in (([], True, "0"), (["--live"], False, "1")):
            with self.subTest(arguments=arguments):
                original_path = sys.path[:]
                suite = Mock()
                suite.countTestCases.return_value = 1
                result = Mock()
                result.wasSuccessful.return_value = success
                try:
                    with patch.dict(os.environ, {"PYTHONPATH": "inherited", "GXP_LIVE_TEST": "1"}), patch.object(
                        run_tests.os, "chdir"
                    ), patch.object(run_tests.unittest, "TestLoader") as loader, patch.object(
                        run_tests.unittest, "TextTestRunner"
                    ) as runner, contextlib.redirect_stdout(io.StringIO()):
                        loader.return_value.discover.return_value = suite
                        runner.return_value.run.return_value = result
                        self.assertEqual(run_tests.main(["--current-python", *arguments]), 0 if success else 1)
                        self.assertEqual(os.environ["GXP_LIVE_TEST"], expected_live)
                        expected = [str(run_tests.REPO_ROOT / "mcp"), str(run_tests.REPO_ROOT / "tests"), str(run_tests.REPO_ROOT)]
                        self.assertEqual(sys.path[:3], expected)
                        self.assertEqual(os.environ["PYTHONPATH"], os.pathsep.join([*expected, "inherited"]))
                        loader.return_value.discover.assert_called_once_with(str(run_tests.REPO_ROOT / "tests"), pattern="test_*.py")
                finally:
                    sys.path[:] = original_path

    def test_empty_suite_fails(self) -> None:
        original_path = sys.path[:]
        try:
            with patch.dict(os.environ), patch.object(run_tests.os, "chdir"), patch.object(
                run_tests.unittest, "TestLoader"
            ) as loader, contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                loader.return_value.discover.return_value.countTestCases.return_value = 0
                self.assertEqual(run_tests.main(["--current-python"]), 1)
        finally:
            sys.path[:] = original_path

    def test_runtime_override_and_platform_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"GXP_LOWCODE_RUNTIME_ROOT": directory}):
            self.assertEqual(setup.runtime_root(), Path(directory).resolve())
            for platform_name, suffix in (("nt", "Scripts/python.exe"), ("posix", "bin/python")):
                with patch.object(setup, "os", SimpleNamespace(name=platform_name)):
                    self.assertEqual(setup._venv_python(Path(directory)), Path(directory) / ".venv" / suffix)


class SkillLinkTests(unittest.TestCase):
    def test_refuses_real_files_and_directories_without_deleting_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            for name, is_directory in (("file", False), ("directory", True)):
                destination = root / name
                if is_directory:
                    destination.mkdir()
                    payload = destination / "keep.txt"
                else:
                    payload = destination
                payload.write_text("keep", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    install_claude.ensure_link(target, destination)
                self.assertEqual(payload.read_text(encoding="utf-8"), "keep")

    def test_native_link_creation_idempotence_and_retargeting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "目标 & %LOOK%"
            replacement = root / "replacement"
            target.mkdir()
            replacement.mkdir()
            payload = target / "keep.txt"
            payload.write_text("keep", encoding="utf-8")
            destination = root / "skill links" / "链接"
            install_claude.ensure_link(target, destination)
            self.assertEqual(destination.resolve(), target.resolve())
            with patch.object(install_claude.subprocess, "run") as launch:
                install_claude.ensure_link(target, destination)
                launch.assert_not_called()
            install_claude.ensure_link(replacement, destination)
            self.assertEqual(destination.resolve(), replacement.resolve())
            self.assertEqual(payload.read_text(encoding="utf-8"), "keep")

    def test_non_windows_branch_uses_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            destination = root / "link"
            platform_os = SimpleNamespace(name="posix", path=os.path, environ=os.environ)
            with patch.object(install_claude, "os", platform_os), patch.object(Path, "symlink_to") as symlink:
                install_claude.ensure_link(target, destination)
            symlink.assert_called_once_with(target.resolve(), target_is_directory=True)

    def test_missing_target_does_not_touch_existing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "keep"
            destination.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileNotFoundError):
                install_claude.ensure_link(Path(directory) / "missing", destination)
            self.assertEqual(destination.read_text(encoding="utf-8"), "keep")


class ProtocolVerificationTests(unittest.IsolatedAsyncioTestCase):
    def session(self, names: list[str], cursor: str | None = None):
        session = SimpleNamespace(initialize=AsyncMock(), send_ping=AsyncMock(), list_tools=AsyncMock())
        session.list_tools.return_value = SimpleNamespace(tools=[SimpleNamespace(name=name) for name in names], nextCursor=cursor)
        return session

    async def test_initialize_ping_and_public_registry(self) -> None:
        session = self.session(["one", "two"])
        self.assertEqual(await verify_mcp.check_session(session, 2), ["one", "two"])
        session.initialize.assert_awaited_once()
        session.send_ping.assert_awaited_once()
        session.list_tools.assert_awaited_once()

    async def test_count_mismatch_and_duplicates_fail(self) -> None:
        for names in (["one"], ["one", "one"]):
            with self.assertRaisesRegex(RuntimeError, "Expected 2 unique"):
                await verify_mcp.check_session(self.session(names), 2)

    async def test_pagination_and_repeated_cursor(self) -> None:
        session = self.session(["one"], "next")
        first = session.list_tools.return_value
        session.list_tools.side_effect = [first, SimpleNamespace(tools=[SimpleNamespace(name="two")], nextCursor=None)]
        self.assertEqual(await verify_mcp.check_session(session, 2), ["one", "two"])
        session.list_tools.assert_awaited_with(cursor="next")
        with self.assertRaisesRegex(RuntimeError, "repeated"):
            await verify_mcp.check_session(self.session(["one"], "same"), 2)

    async def test_ping_failure_is_not_reported_as_success(self) -> None:
        session = self.session(["one"])
        session.send_ping.side_effect = RuntimeError("ping failed")
        with self.assertRaisesRegex(RuntimeError, "ping failed"):
            await verify_mcp.check_session(session, 1)
        session.list_tools.assert_not_awaited()

    async def test_protocol_timeout(self) -> None:
        session = self.session(["one"])
        async def stalled():
            await asyncio.sleep(60)
        session.initialize.side_effect = stalled
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(verify_mcp.check_session(session, 1), timeout=0.01)

    async def test_timeout_survives_transport_cleanup_error(self) -> None:
        import mcp
        import mcp.client.stdio

        @contextlib.asynccontextmanager
        async def broken_transport(*args, **kwargs):
            yield None, None
            raise RuntimeError("cleanup failed")

        @contextlib.asynccontextmanager
        async def session_context(*args, **kwargs):
            yield self.session(["one"])

        with patch.object(mcp.client.stdio, "stdio_client", broken_transport), patch.object(
            mcp, "ClientSession", session_context
        ), patch.object(verify_mcp.shutil, "which", return_value="node"), patch.object(
            verify_mcp, "check_session", new=AsyncMock(side_effect=asyncio.TimeoutError)
        ):
            with self.assertRaises(asyncio.TimeoutError):
                await verify_mcp.verify(Path.cwd(), 0.01)


class ClaudeVerificationTests(unittest.TestCase):
    def test_verify_only_does_not_install_or_change_configuration(self) -> None:
        with patch.object(install_claude, "verify_mcp_tools", return_value=True) as verify, patch.object(
            install_claude, "install_runtime"
        ) as runtime, patch.object(install_claude, "ensure_link") as link, patch.object(
            install_claude, "configure_mcp_json"
        ) as config:
            self.assertEqual(install_claude.main(["--verify-only", "--verify-timeout", "2"]), 0)
        verify.assert_called_once_with(2)
        runtime.assert_not_called()
        link.assert_not_called()
        config.assert_not_called()

    def test_install_failure_exit_and_skip_verification(self) -> None:
        for arguments, expected, verify_calls in ((["--verify"], 1, 1), (["--no-verify"], 0, 0)):
            with patch.object(install_claude, "verify_mcp_tools", return_value=False) as verify, patch.object(
                install_claude, "ensure_link"
            ), patch.object(install_claude, "configure_mcp_json"), patch.object(
                install_claude, "update_gitignore"
            ), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(install_claude.main(["--skip-runtime", *arguments]), expected)
            self.assertEqual(verify.call_count, verify_calls)
            self.assertEqual("[SUCCESS]" in output.getvalue(), expected == 0)

    def test_verifier_subprocess_contract_and_failures(self) -> None:
        good = json.dumps({"tools": 35, "initialize": True, "ping": True})
        outcomes = [(SimpleNamespace(stdout=good), True), (SimpleNamespace(stdout="{}"), False),
                    (SimpleNamespace(stdout="not-json"), False), (subprocess.TimeoutExpired("verify", 20), False),
                    (subprocess.CalledProcessError(1, "verify", stderr="failed"), False)]
        for outcome, expected in outcomes:
            with self.subTest(outcome=outcome), patch.object(install_claude, "_venv_python", return_value=Path(sys.executable)), patch.object(
                install_claude.subprocess, "run"
            ) as launch, patch.dict(os.environ, {"PYTHONPATH": "existing"}), contextlib.redirect_stdout(io.StringIO()):
                if isinstance(outcome, Exception):
                    launch.side_effect = outcome
                else:
                    launch.return_value = outcome
                self.assertEqual(install_claude.verify_mcp_tools(5), expected)
                self.assertIn("verify_mcp.py", launch.call_args.args[0][1])
                self.assertEqual(launch.call_args.kwargs["timeout"], 20)
                self.assertEqual(launch.call_args.kwargs["encoding"], "utf-8")
                self.assertEqual(launch.call_args.kwargs["env"]["PYTHONPATH"], "existing")

    def test_missing_runtime_fails_without_launching(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch.object(
            install_claude, "_venv_python", return_value=Path(directory) / "missing"
        ), patch.object(install_claude.subprocess, "run") as launch, contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(install_claude.verify_mcp_tools())
        launch.assert_not_called()

    def test_invalid_timeout_and_conflicting_options(self) -> None:
        for arguments in (["--verify-timeout", "0"], ["--verify-timeout", "nan"], ["--verify-timeout", "inf"],
                          ["--verify", "--no-verify"], ["--verify-only", "--no-verify"]):
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                install_claude.main(arguments)
            self.assertEqual(raised.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
