from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core.source_config import (
    SourceRepositoriesConfig,
    SourceRepositoryError,
    _git_bytes,
    load_source_config,
    resolve_repository,
    save_source_config,
)


class SourceConfigTests(unittest.TestCase):
    def test_git_metadata_detaches_mcp_stdin_and_bounds_wait(self) -> None:
        with patch("gxp_core.source_config.subprocess.run") as runner:
            runner.return_value.returncode = 0
            runner.return_value.stdout = b"metadata"
            self.assertEqual(b"metadata", _git_bytes(Path.cwd(), "rev-parse", "HEAD"))
        self.assertEqual(subprocess.DEVNULL, runner.call_args.kwargs.get("stdin"))
        self.assertGreater(runner.call_args.kwargs.get("timeout", 0), 0)
        self.assertLessEqual(runner.call_args.kwargs["timeout"], 10)

    def test_git_timeout_is_an_unavailable_repository(self) -> None:
        with patch("gxp_core.source_config.subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)):
            with self.assertRaises(SourceRepositoryError) as failure:
                _git_bytes(Path.cwd(), "rev-parse", "HEAD")
        self.assertEqual("GIT_METADATA_TIMEOUT", failure.exception.code)

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _repo(path: Path, content: str = "one") -> None:
        path.mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
        subprocess.run(["git", "remote", "add", "origin", "https://example.invalid/gxp.git"], cwd=path, check=True)
        (path / "source.txt").write_text(content, encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", content], cwd=path, check=True)

    def test_custom_config_round_trip_and_secret_rejection(self) -> None:
        frontend = self.root / "前端"
        backend = self.root / "backend"
        config_path = self.root / "source-repositories.json"
        config = SourceRepositoriesConfig(
            frontend=(str(frontend),),
            backend=(str(backend),),
            preferred_frontend=str(frontend),
        )
        with patch.dict("os.environ", {"GXP_LOWCODE_SOURCE_CONFIG": str(config_path)}):
            save_source_config(config)
            loaded = load_source_config()
        self.assertEqual(config.frontend, loaded.frontend)
        self.assertEqual(str(frontend), loaded.preferred_frontend)
        self.assertNotIn("token", config_path.read_text(encoding="utf-8").casefold())
        with self.assertRaises(ValueError):
            SourceRepositoriesConfig.from_dict({"frontend": [str(frontend)], "token": "bad"})

    def test_single_repository_selected_and_dirty_metadata_reported(self) -> None:
        frontend = self.root / "frontend"
        self._repo(frontend)
        (frontend / "dirty.ts").write_text("dirty", encoding="utf-8")
        config = SourceRepositoriesConfig(frontend=(str(frontend),))
        with patch("gxp_core.source_config.DEFAULT_REPOSITORIES", {"frontend": (), "backend": ()}):
            result = resolve_repository("frontend", config=config)
        self.assertEqual(str(frontend.resolve()), result["selected"]["path"])
        self.assertEqual(1, result["selected"]["dirty_file_count"])
        self.assertFalse(result["alternates_present"])

    def test_same_commit_mirrors_follow_order_and_different_commits_require_preferred(self) -> None:
        first = self.root / "first"
        second = self.root / "second"
        self._repo(first)
        subprocess.run(["git", "clone", "-q", str(first), str(second)], check=True)
        subprocess.run(["git", "remote", "set-url", "origin", "https://example.invalid/gxp.git"], cwd=second, check=True)
        config = SourceRepositoriesConfig(frontend=(str(first), str(second)))
        with patch("gxp_core.source_config.DEFAULT_REPOSITORIES", {"frontend": (), "backend": ()}):
            same = resolve_repository("frontend", config=config)
            self.assertEqual(str(first.resolve()), same["selected"]["path"])
            self.assertEqual(1, len(same["mirrors"]))
            (second / "source.txt").write_text("two", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=second, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=second, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=second, check=True)
            subprocess.run(["git", "commit", "-q", "-m", "two"], cwd=second, check=True)
            with self.assertRaises(SourceRepositoryError) as ambiguous:
                resolve_repository("frontend", config=config)
            self.assertEqual("REPOSITORY_AMBIGUOUS", ambiguous.exception.code)
            preferred = SourceRepositoriesConfig(
                frontend=(str(first), str(second)),
                preferred_frontend=str(second.resolve()),
            )
            selected = resolve_repository("frontend", config=preferred)
        self.assertEqual(str(second.resolve()), selected["selected"]["path"])
        self.assertTrue(selected["commits_differ"])

    def test_invalid_git_root_is_not_selected(self) -> None:
        root = self.root / "repo"
        self._repo(root)
        nested = root / "nested"
        nested.mkdir()
        config = SourceRepositoriesConfig(frontend=(str(nested),))
        with patch("gxp_core.source_config.DEFAULT_REPOSITORIES", {"frontend": (), "backend": ()}):
            with self.assertRaises(SourceRepositoryError) as failure:
                resolve_repository("frontend", config=config)
        self.assertEqual("REPOSITORY_NOT_FOUND", failure.exception.code)
        self.assertEqual("REPOSITORY_ROOT_MISMATCH", failure.exception.details["checked"][0]["error"]["code"])


if __name__ == "__main__":
    unittest.main()
