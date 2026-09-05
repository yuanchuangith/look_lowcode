from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core import source_analysis, source_index
from gxp_core.source_config import SOURCE_INDEX_VERSION


class SourceFreshnessContracts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.enterContext(patch.object(source_index, "source_index_root", return_value=self.root / "index"))
        self.enterContext(patch.object(source_index, "source_index_lock_path", return_value=self.root / "index.lock"))

    def tearDown(self):
        self.temporary.cleanup()

    def test_generation_change_retries_once_then_returns_unresolved(self):
        status = {"index": {"exists": True}, "repositories": {"frontend": {"stale": False}}}
        with patch.object(source_analysis, "ensure_source_index", return_value=status), patch.object(source_analysis, "source_index_generation", side_effect=["a", "b", "c", "d"]), patch.object(source_analysis, "load_index_file", return_value=[]):
            result = source_analysis.inspect_component_source("Test")
        self.assertEqual("unresolved", result["status"])
        self.assertEqual("SOURCE_INDEX_CHANGED_DURING_READ", result["errors"][0]["code"])

    def test_backend_failure_preserves_frontend_without_closing_chain(self):
        root = self.root / "index/frontend"
        root.mkdir(parents=True)
        (root / "requests.json").write_text(json.dumps([{"route": "/api/test", "method": "GET", "function": "test", "path": "service.ts", "line": 1}]), encoding="utf-8")
        status = {"index": {"exists": True}, "repositories": {"frontend": {"stale": False}, "backend": {"stale": True}}, "errors": [{"layer": "backend", "code": "REPOSITORY_NOT_FOUND"}]}
        with patch.object(source_analysis, "ensure_source_index", return_value=status):
            result = source_analysis.trace_api_contract("/api/test")
        self.assertEqual("partial", result["status"])
        self.assertEqual(1, len(result["frontend_callers"]))
        self.assertEqual([], result["backend_endpoints"])
        self.assertEqual("unresolved", result["contract_status"])

    def test_component_requests_frontend_only_and_hot_index_does_not_rebuild(self):
        status = {"index": {"exists": True}, "repositories": {"frontend": {"stale": False}}}
        with patch.object(source_analysis, "ensure_source_index", return_value=status) as ensure, patch.object(source_analysis, "load_index_file", return_value=[]):
            source_analysis.inspect_component_source("Test")
        self.assertEqual(("frontend",), ensure.call_args_list[0].args[0])
        with patch.object(source_index, "source_index_status", return_value=status), patch.object(source_index, "refresh_source_index") as refresh:
            source_index.ensure_source_index(("frontend",))
        refresh.assert_not_called()

    def test_changed_source_during_build_is_not_published_as_current(self):
        calls = 0
        def resolution(layer):
            nonlocal calls
            calls += 1
            return {"selected": {"path": str(self.root), "fingerprint": str(calls)}}
        data = {"components": [], "component_contracts": [], "requests": [], "symbols": [], "call_edges": [], "file_count": 0}
        with patch.object(source_index, "resolve_repository", side_effect=resolution), patch.object(source_index, "_scan_frontend", return_value=(data, [])):
            result = source_index.refresh_source_index(force=True, layers=("frontend",))
        self.assertEqual("partial", result["status"])
        manifest = json.loads((self.root / "index/manifest.json").read_text(encoding="utf-8"))
        self.assertNotIn("frontend", manifest["repositories"])

    def test_old_layer_version_is_stale_even_when_fingerprint_matches(self):
        root = self.root / "index"
        root.mkdir()
        (root / "manifest.json").write_text(json.dumps({"version": SOURCE_INDEX_VERSION, "repositories": {"frontend": {"fingerprint": "same", "index_version": 1}}}), encoding="utf-8")
        with patch.object(source_index, "resolve_repository", return_value={"selected": {"fingerprint": "same"}}):
            result = source_index.source_index_status(("frontend",))
        self.assertTrue(result["repositories"]["frontend"]["stale"])


if __name__ == "__main__":
    unittest.main()

