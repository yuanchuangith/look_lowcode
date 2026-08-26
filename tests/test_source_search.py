from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "skills" / "gxp-lowcode-debug" / "scripts" / "search_source_evidence.py"
SPEC = importlib.util.spec_from_file_location("search_source_evidence", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class SourceSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        if not shutil.which("rg") or not shutil.which("git"):
            self.skipTest("rg and git are required")
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.frontend = root / "frontend"
        self.backend = root / "backend"
        self._init_repo(self.frontend)
        self._init_repo(self.backend)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _init_repo(path: Path) -> None:
        path.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=path, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
        (path / ".keep").write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", ".keep"], cwd=path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=path, check=True)

    def test_exact_frontend_backend_hits_and_generated_exclusions(self) -> None:
        (self.frontend / "src").mkdir()
        (self.frontend / "src" / "DataFilter.tsx").write_text(
            "export const DataFilter = 'TestPaper document_code revision_no';\n", encoding="utf-8"
        )
        (self.frontend / "dist").mkdir()
        (self.frontend / "dist" / "DataFilter.js").write_text("TestPaper document_code revision_no", encoding="utf-8")
        (self.backend / "Services").mkdir()
        (self.backend / "Services" / "DynamicActionService.cs").write_text(
            "class DynamicActionService {}\n", encoding="utf-8"
        )
        (self.backend / "Services" / "BizflowsCsharpServiceBase.cs").write_text(
            "class BizflowsCsharpServiceBase {}\n", encoding="utf-8"
        )

        frontend = MODULE.search_source_evidence(
            layer="frontend",
            terms=["DataFilter", "TestPaper"],
            pairs=[["document_code", "revision_no"]],
            frontend_repo=self.frontend,
            backend_repo=self.backend,
        )
        backend = MODULE.search_source_evidence(
            layer="backend",
            terms=["DynamicActionService", "BizflowsCsharpServiceBase"],
            pairs=[],
            frontend_repo=self.frontend,
            backend_repo=self.backend,
        )

        self.assertEqual("ok", frontend["status"])
        self.assertEqual(["src/DataFilter.tsx"], [item["path"] for item in frontend["files"]])
        self.assertEqual(
            ["Services/BizflowsCsharpServiceBase.cs", "Services/DynamicActionService.cs"],
            [item["path"] for item in backend["files"]],
        )

    def test_pair_boost_does_not_hide_independent_exact_component_hits(self) -> None:
        (self.frontend / "DataFilter.tsx").write_text("export const DataFilter = true;\n", encoding="utf-8")
        (self.frontend / "TestPaper.tsx").write_text("export const TestPaper = true;\n", encoding="utf-8")
        (self.frontend / "mapping.ts").write_text("document_code + revision_no\n", encoding="utf-8")

        result = MODULE.search_source_evidence(
            layer="frontend",
            terms=["DataFilter", "TestPaper"],
            pairs=[["document_code", "revision_no"]],
            frontend_repo=self.frontend,
            backend_repo=self.backend,
        )

        self.assertEqual(
            ["mapping.ts", "DataFilter.tsx", "TestPaper.tsx"],
            [item["path"] for item in result["files"]],
        )
        self.assertEqual([["document_code", "revision_no"]], result["files"][0]["matched_pairs"])

    def test_file_context_and_response_limits(self) -> None:
        for index in range(25):
            (self.frontend / f"source-{index:02}.tsx").write_text(
                ("line\n" * 20) + "BoundedToken\n" + ("tail\n" * 20),
                encoding="utf-8",
            )

        result = MODULE.search_source_evidence(
            layer="frontend",
            terms=["BoundedToken"],
            pairs=[],
            frontend_repo=self.frontend,
            backend_repo=self.backend,
        )
        encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        self.assertEqual(20, result["returned_file_count"])
        self.assertTrue(result["files_truncated"])
        self.assertEqual(5, sum("context" in item for item in result["files"]))
        self.assertLessEqual(len(encoded), 32 * 1024)

    def test_missing_repo_rg_unavailable_and_no_match_do_not_widen_scope(self) -> None:
        with self.assertRaises(MODULE.SourceSearchError) as missing:
            MODULE.search_source_evidence(
                layer="frontend",
                terms=["Token"],
                pairs=[],
                frontend_repo=self.frontend / "missing",
                backend_repo=self.backend,
            )
        self.assertEqual("repository_not_found", missing.exception.code)

        with patch.object(MODULE.shutil, "which", return_value=None):
            with self.assertRaises(MODULE.SourceSearchError) as unavailable:
                MODULE.search_source_evidence(
                    layer="frontend",
                    terms=["Token"],
                    pairs=[],
                    frontend_repo=self.frontend,
                    backend_repo=self.backend,
                )
        self.assertEqual("rg_unavailable", unavailable.exception.code)

        no_match = MODULE.search_source_evidence(
            layer="both",
            terms=["DefinitelyNotPresent"],
            pairs=[],
            frontend_repo=self.frontend,
            backend_repo=self.backend,
        )
        self.assertEqual("no_matches", no_match["status"])
        self.assertFalse(no_match["scope_expanded"])
        self.assertEqual([], no_match["files"])


if __name__ == "__main__":
    unittest.main()
