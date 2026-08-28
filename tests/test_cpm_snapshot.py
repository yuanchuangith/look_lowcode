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
