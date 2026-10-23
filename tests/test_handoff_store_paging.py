from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gxp_core.handoff_store import (
    HandoffError, HandoffStore, canonical_bytes, design_content_sha256,
)
from tests.test_edit_handoff import evidence_only_spec, make_record


class EvidencePagingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = HandoffStore(Path(temporary.name))

    def collect(self, identifier="code", environment="", **kwargs):
        candidates, pages, cursor = [], [], ""
        while True:
            page = self.store.list_page(identifier, environment, cursor=cursor, **kwargs)
            pages.append(page)
            candidates.extend(page["candidates"])
            if not page["has_more"]:
                self.assertEqual("", page["next_cursor"])
                return candidates, pages
            self.assertNotEqual(cursor, page["next_cursor"])
            cursor = page["next_cursor"]

    def test_pages_preserve_all_matches_and_filter_exact_environment(self):
        references = [self.store.write(make_record())["handoff_id"] for _ in range(53)]
        other = make_record()
        other["environment_scope"] = "b" * 64
        self.store.write(other)
        environment = make_record()["environment_scope"]
        candidates, pages = self.collect(environment=environment, limit=7)
        self.assertEqual(set(references), {item["handoff_id"] for item in candidates})
        self.assertEqual(len(references), len(candidates))
        self.assertGreater(len(pages), 1)
        self.assertTrue(all(page["count"] <= 7 for page in pages))
        self.assertTrue(all(item["environment_scope"] == environment for item in candidates))

    def test_byte_budget_returns_continuation_without_losing_first_unreturned_record(self):
        record = make_record()
        record["change_spec"] = evidence_only_spec()
        record["change_spec"]["summary"] = "字" * 650
        record["change_spec"]["diagnosis"]["issues"][0]["symptom"] = "症" * 1000
        references = [self.store.write(record)["handoff_id"] for _ in range(8)]
        candidates, pages = self.collect(limit=50, max_bytes=7 * 1024)
        self.assertEqual(set(references), {item["handoff_id"] for item in candidates})
        self.assertEqual(len(references), len(candidates))
        self.assertGreater(len(pages), 1)
        self.assertTrue(all(len(canonical_bytes(page["candidates"])) <= 7 * 1024 for page in pages))
        self.assertTrue(all(item["summary_truncated"] for item in candidates))
        self.assertEqual(record["change_spec"], self.store.read(references[0])["change_spec"])

    def test_more_than_one_thousand_files_can_be_traversed_in_bounded_windows(self):
        # Corrupt local records must not make later valid records undiscoverable.
        for index in range(1001):
            (self.store.root / (f"{index:032x}.json")).write_text("{}", encoding="utf-8")
        with patch("gxp_core.handoff_store.secrets.token_hex", side_effect=["f" * 32, "a" * 16]):
            reference = self.store.write(make_record())
        original_read = self.store.read
        with patch.object(self.store, "read", wraps=original_read) as read:
            first = self.store.list_page("code")
        self.assertEqual(200, read.call_count)
        self.assertEqual([], first["candidates"])
        self.assertTrue(first["has_more"])
        candidates, pages = self.collect()
        self.assertEqual([reference["handoff_id"]], [item["handoff_id"] for item in candidates])
        self.assertGreaterEqual(len(pages), 6)

    def test_cursor_is_bound_to_lookup_and_rejects_paths(self):
        for _ in range(2):
            self.store.write(make_record())
        first = self.store.list_page("code", limit=1)
        for identifier, environment, cursor in [
            ("ref", "", first["next_cursor"]),
            ("code", "a" * 64, first["next_cursor"]),
            ("code", "", "../record.json"),
        ]:
            with self.subTest(identifier=identifier, environment=environment), self.assertRaises(HandoffError):
                self.store.list_page(identifier, environment, cursor=cursor)
        for limit in (0, 51, True):
            with self.subTest(limit=limit), self.assertRaises(HandoffError):
                self.store.list_page("code", limit=limit)

    def test_summary_reports_source_and_finding_status_without_promoting_candidates(self):
        record = make_record()
        record["change_spec"] = evidence_only_spec()
        saved = self.store.write(record)
        summary = saved["summary"]
        self.assertEqual("edit_snapshot", summary["record_kind"])
        self.assertEqual(record["environment_scope"], summary["environment_scope"])
        self.assertEqual(record["diagnosis_source"], summary["diagnosis_source"])
        self.assertEqual(1, summary["diagnosis_status"]["confirmed_count"])
        self.assertEqual(1, summary["diagnosis_status"]["candidate_count"])
        self.assertEqual(1, summary["diagnosis_status"]["verification_counts"]["pending"])
        self.assertEqual(1, summary["diagnosis_status"]["unresolved_count"])
        self.assertEqual("candidate", summary["issue_summaries"][1]["status"])

    def test_diagnosis_only_has_no_editable_snapshot_and_preserves_unresolved_evidence(self):
        record = make_record()
        record.update(record_kind="diagnosis_only", draft=None, targets=[], diagnosis_targets=[], source_target_differences=[])
        record["change_spec"] = evidence_only_spec()
        saved = self.store.write(record)
        restored = self.store.read(**saved["handoff_ref"])
        self.assertIsNone(restored["draft"])
        self.assertEqual(record["change_spec"], restored["change_spec"])
        self.assertEqual(0, saved["summary"]["target_count"])
        mutations = [
            lambda item: item.update(targets=make_record()["targets"]),
            lambda item: item.update(draft=make_record()["draft"]),
            lambda item: item["change_spec"].update(changes=make_record()["change_spec"]["changes"]),
            lambda item: item["change_spec"].pop("diagnosis"),
            lambda item: item.update(record_kind="unknown"),
        ]
        for mutate in mutations:
            invalid = copy.deepcopy(record)
            mutate(invalid)
            with self.subTest(record=invalid), self.assertRaises(HandoffError):
                self.store.write(invalid)
        legacy = make_record()
        legacy.update(targets=[], diagnosis_targets=[])
        with self.assertRaises(HandoffError):
            self.store.write(legacy)

    def test_semantic_fingerprint_ignores_formatting_but_retains_all_design_content(self):
        data = {"actionData": [], "globalVariables": [{"key": "variable", "value": 1}], "js_code": "hash only"}
        self.assertEqual(design_content_sha256(data), design_content_sha256(json.dumps(data, indent=4)))
        changed = copy.deepcopy(data)
        changed["globalVariables"][0]["value"] = 2
        self.assertNotEqual(design_content_sha256(data), design_content_sha256(changed))


if __name__ == "__main__":
    unittest.main()
