from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core.cpm_config import CpmConfig
from gxp_core.cpm_snapshot import get_cpm_knowledge, inspect_page_snapshot, search_platform_snapshot


class CpmSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name).resolve()
        self.snapshot = root / "snapshot"
        page = self.snapshot / "pages" / "page-a"
        page.mkdir(parents=True)
        (self.snapshot / "manifest.json").write_text("{}", encoding="utf-8")
        indexes = self.snapshot / "indexes"
        indexes.mkdir()
        for name in ("pages.md", "model-usage.md", "component-usage.md", "event-usage.md"):
            (indexes / name).write_text("# index", encoding="utf-8")
        meta = {"version": 1, "route": "/a", "id": "id-a", "outId": "out-a", "name": "页面A", "dir": "pages/page-a", "componentTypes": ["DataFilter"], "eventSubscriptions": []}
        (page / "page-meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        (page / "tree.md").write_text("# 页面A\nDataFilter", encoding="utf-8")
        (page / "components.json").write_text("[]", encoding="utf-8")
        (page / "bindings.md").write_text("主模型 ModelA", encoding="utf-8")
        skill = self.snapshot / "skills" / "cpm-platform"
        (skill / "references" / "components").mkdir(parents=True)
        (skill / "references" / "components" / "DataFilter.md").write_text("# DataFilter\n安全知识", encoding="utf-8")
        (skill / "SKILL.md").write_text("# CPM", encoding="utf-8")
        self.config = CpmConfig(
            platform_url="https://cpm.example",
            account="tester",
            node_path=str(root / "node.exe"),
            cli_path=str(root / "dist" / "cli.js"),
            snapshot_dir=str(self.snapshot),
        )
        self.config_patch = patch("gxp_core.cpm_snapshot.load_cpm_config", return_value=self.config)
        self.config_patch.start()

    def tearDown(self) -> None:
        self.config_patch.stop()
        self.temp.cleanup()

    def test_search_and_page_inspection_are_bounded(self) -> None:
        found = search_platform_snapshot("DataFilter", ["components"], limit=999, refresh_if_stale=False)
        self.assertTrue(found["ok"])
        self.assertEqual(100, found["limit"])
        inspected = inspect_page_snapshot("out-a", sections=["meta", "tree"], limit=5, refresh_if_stale=False)
        self.assertTrue(inspected["ok"])
        self.assertEqual("/a", inspected["page"]["route"])
        self.assertEqual("cpm_snapshot", inspected["source"])

    def test_search_reports_result_and_scan_limits_without_claiming_zero_hits(self) -> None:
        models = self.snapshot / "models"
        models.mkdir()
        paths = [models / f"{index}.json" for index in range(3)]
        for path in paths:
            path.write_text("needle", encoding="utf-8")
        with patch("gxp_core.cpm_snapshot.Path.rglob", return_value=paths):
            limited = search_platform_snapshot("needle", ["models"], limit=1, refresh_if_stale=False)
        self.assertEqual(1, limited["count"])
        self.assertFalse(limited["search_complete"])
        self.assertFalse(limited["scan_complete"])
        self.assertEqual("result_limit", limited["stop_reason"])
        self.assertEqual(1, limited["scanned_count"])
        self.assertEqual("CPM_SEARCH_INCOMPLETE", limited["evidence_gaps"][-1]["code"])
        for path in paths[:2]:
            path.write_text("absent", encoding="utf-8")
        with patch("gxp_core.cpm_snapshot.Path.rglob", return_value=paths), patch("gxp_core.cpm_snapshot.MAX_SCAN_FILES", 2):
            capped = search_platform_snapshot("needle", ["models"], refresh_if_stale=False)
        self.assertTrue(capped["ok"])
        self.assertEqual(0, capped["count"])
        self.assertEqual(2, capped["scanned_count"])
        self.assertFalse(capped["search_complete"])
        self.assertEqual("scan_file_limit", capped["stop_reason"])
        with patch("gxp_core.cpm_snapshot.Path.rglob", return_value=paths), patch("gxp_core.cpm_snapshot.MAX_SCAN_FILES", 3):
            exact_boundary = search_platform_snapshot("needle", ["models"], limit=1, refresh_if_stale=False)
        self.assertEqual(1, exact_boundary["count"])
        self.assertFalse(exact_boundary["search_complete"])
        with patch("gxp_core.cpm_snapshot.Path.rglob", return_value=paths), patch("gxp_core.cpm_snapshot.MAX_SCAN_FILES", 4):
            complete = search_platform_snapshot("needle", ["models"], limit=2, refresh_if_stale=False)
        self.assertTrue(complete["search_complete"])
        self.assertEqual("completed", complete["stop_reason"])

    def test_search_stops_before_walking_an_unrelated_tail_at_the_boundary(self) -> None:
        models = self.snapshot / "models"
        models.mkdir()
        path = models / "one.json"
        path.write_text("needle", encoding="utf-8")

        def paths():
            yield path
            raise AssertionError("must stop before iterating unrelated tail")

        with patch("gxp_core.cpm_snapshot.Path.rglob", return_value=paths()):
            result = search_platform_snapshot("needle", ["models"], limit=1, refresh_if_stale=False)
        self.assertTrue(result["ok"])
        self.assertEqual(1, result["scanned_count"])
        self.assertFalse(result["scan_complete"])
        self.assertEqual("result_limit", result["stop_reason"])

    def test_search_reports_unread_file_tails_and_read_failures(self) -> None:
        models = self.snapshot / "models"
        models.mkdir()
        long_file = models / "long.json"
        long_file.write_text("x" * 64000 + "needle", encoding="utf-8")
        result = search_platform_snapshot("needle", ["models"], refresh_if_stale=False)
        self.assertEqual(0, result["count"])
        self.assertTrue(result["scan_complete"])
        self.assertFalse(result["search_complete"])
        self.assertEqual("file_content_limit", result["stop_reason"])
        self.assertEqual(1, result["truncated_file_count"])
        self.assertEqual(["models/long.json"], result["truncated_files"])
        long_file.write_bytes(b"\xff")
        result = search_platform_snapshot("needle", ["models"], refresh_if_stale=False)
        self.assertEqual(1, result["read_failure_count"])
        self.assertFalse(result["search_complete"])
        self.assertEqual("file_read_failed", result["stop_reason"])

    def test_complete_zero_hit_search_and_stale_context_remain_distinct(self) -> None:
        result = search_platform_snapshot("definitely-absent", ["models"], refresh_if_stale=False)
        self.assertTrue(result["search_complete"])
        self.assertEqual(0, result["count"])
        self.assertEqual(0, result["scanned_count"])
        self.assertEqual([], result["stop_reasons"])
        # Freshness remains an independent gate even when search scans all files.
        self.assertEqual("snapshot_candidates_only", result["evidence_scope"])

    def test_failed_refresh_returns_only_explicitly_stale_candidates(self):
        with patch("gxp_core.cpm_snapshot.CpmRefreshManager") as manager:
            manager.return_value.ensure_fresh.return_value = {"ok": False, "error": {"code": "TOKEN_INVALID"}}
            manager.return_value.snapshot_status.return_value = {"stale": True, "refreshed_at": "old"}
            result = search_platform_snapshot("DataFilter", ["components"])
            self.assertTrue(result["ok"])
            self.assertTrue(result["stale"])
            self.assertEqual("TOKEN_INVALID", result["stale_reason"])
            self.assertFalse(result["current_runtime_verified"])
            self.assertEqual("snapshot_candidates_only", result["evidence_scope"])
            self.assertEqual(1, manager.return_value.ensure_fresh.call_count)

    def test_failed_refresh_without_usable_snapshot_remains_an_error(self):
        (self.snapshot / "manifest.json").unlink()
        with patch("gxp_core.cpm_snapshot.CpmRefreshManager") as manager:
            manager.return_value.ensure_fresh.return_value = {"ok": False, "error": {"code": "REFRESH_FAILED"}}
            result = search_platform_snapshot("DataFilter")
            self.assertFalse(result["ok"])

    def test_knowledge_rejects_path_traversal_and_reads_allowlisted_component(self) -> None:
        denied = get_cpm_knowledge("component", "../DataFilter")
        self.assertFalse(denied["ok"])
        self.assertEqual("KNOWLEDGE_NOT_ALLOWED", denied["error"]["code"])
        allowed = get_cpm_knowledge("component", "DataFilter", max_chars=20)
        self.assertTrue(allowed["ok"])
        self.assertIn("安全知识", allowed["content"])

    def test_non_utf8_page_section_fails_safely(self) -> None:
        (self.snapshot / "pages" / "page-a" / "tree.md").write_bytes(b"\xff\xfe")
        result = inspect_page_snapshot("/a", sections=["tree"], refresh_if_stale=False)
        self.assertFalse(result["ok"])
        self.assertEqual("NON_UTF8_FILE", result["error"]["code"])

    def test_malformed_manifest_and_missing_indexes_fail_safely(self) -> None:
        (self.snapshot / "manifest.json").write_text("{", encoding="utf-8")
        malformed = search_platform_snapshot("页面", refresh_if_stale=False)
        self.assertFalse(malformed["ok"])
        self.assertEqual("MALFORMED_JSON", malformed["error"]["code"])
        (self.snapshot / "manifest.json").write_text("{}", encoding="utf-8")
        (self.snapshot / "indexes" / "pages.md").unlink()
        missing = search_platform_snapshot("页面", refresh_if_stale=False)
        self.assertFalse(missing["ok"])
        self.assertEqual("SNAPSHOT_INDEX_MISSING", missing["error"]["code"])


if __name__ == "__main__":
    unittest.main()
