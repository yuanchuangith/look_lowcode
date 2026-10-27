from __future__ import annotations

import copy
import base64
import hashlib
import json
import unittest

from gxp_core.canvas import CanvasInspector
from gxp_core.diagnostic_output import diagnostic_page, filter_summary
from gxp_core.service import GxpReadonlyService
from gxp_core.canvas_budget import payload_size


class DiagnosticOutputTests(unittest.TestCase):
    def test_truncated_action_candidates_can_be_recovered_without_false_completeness(self):
        matches = [{"ref_id": f"candidate-{index}", "display_name": "name-" + "x" * 240}
                   for index in range(40)]

        class Repository:
            def resolve_action(self, identifier):
                return matches

        service = object.__new__(GxpReadonlyService)
        service.repository = Repository()
        args = dict(response_detail="full", max_output_bytes=16384)
        first = service.inspect_component_filters("common-name", "component", **args)
        self.assertEqual(first["count"], 40)
        self.assertLess(len(first["matches"]), 40)
        self.assertFalse(first["envelope_complete"])
        self.assertTrue(first["response_truncated"])
        self.assertTrue(first["has_more"])
        chunks = []
        page = first
        while page["has_more"]:
            self.assertFalse(page["response_complete"])
            self.assertFalse(page["evidence_complete"])
            page = service.inspect_component_filters("common-name", "component", **args, cursor=page["next_cursor"])
            self.assertLessEqual(payload_size(page), 16384)
            self.assertEqual(page["snapshot_fingerprint"], first["snapshot_fingerprint"])
            value = page["envelope_value_page"]
            self.assertEqual(value["offset"], sum(map(len, chunks)))
            chunks.append(value["text"])
        self.assertFalse(page["response_complete"])
        self.assertFalse(page["evidence_complete"])
        self.assertTrue(value["continuation_complete"])
        restored_text = "".join(chunks)
        self.assertEqual(len(restored_text), value["total_characters"])
        self.assertEqual(hashlib.sha256(restored_text.encode("utf-8")).hexdigest(), value["envelope_sha256"])
        self.assertEqual(json.loads(restored_text)["matches"], matches)

    def test_record_pages_continue_into_unicode_envelope_without_losing_evidence(self):
        envelope = {"parsed": {"message": "中文😀" * 5000}}
        rows = [{"node_key": str(index)} for index in range(7)]
        args = dict(identity=["fixture", envelope], envelope=envelope, response_detail="full",
                    max_output_bytes=8192, limit=2)
        page = diagnostic_page(rows, **args)
        fingerprint = page["snapshot_fingerprint"]
        records, chunks = [], []
        while True:
            self.assertLessEqual(payload_size(page), 8192)
            self.assertFalse(page["response_complete"])
            self.assertFalse(page["evidence_complete"])
            self.assertEqual(page["snapshot_fingerprint"], fingerprint)
            records.extend(page["records"])
            if "envelope_value_page" in page:
                value = page["envelope_value_page"]
                self.assertEqual(value["offset"], sum(map(len, chunks)))
                chunks.append(value["text"])
            if not page["has_more"]:
                break
            cursor = page["next_cursor"]
            page = diagnostic_page(rows, **args, cursor=cursor)
        self.assertEqual(records, rows)
        self.assertEqual(json.loads("".join(chunks)), envelope)
        self.assertTrue(value["continuation_complete"])
        changed = {"parsed": {"message": "changed"}}
        with self.assertRaisesRegex(ValueError, "CURSOR"):
            diagnostic_page(rows, **{**args, "identity": ["fixture", changed], "envelope": changed}, cursor=cursor)

    def test_small_full_response_remains_complete_and_accepts_legacy_record_cursor(self):
        rows = [{"node_key": "first"}, {"node_key": "second"}]
        args = dict(identity=["fixture"], envelope={"writer_count": 2}, response_detail="full")
        complete = diagnostic_page(rows, **args)
        self.assertTrue(complete["response_complete"])
        self.assertTrue(complete["evidence_complete"])
        self.assertFalse(complete["has_more"])
        first = diagnostic_page(rows, **args, limit=1)
        state = json.loads(base64.urlsafe_b64decode(first["next_cursor"]))
        legacy = base64.urlsafe_b64encode(json.dumps([1, *state[1:5]]).encode()).decode()
        second = diagnostic_page(rows, **args, limit=1, cursor=legacy)
        self.assertEqual(second["records"], rows[1:])
        self.assertFalse(second["has_more"])

    def test_changed_response_budget_keeps_envelope_recoverable(self):
        envelope = {"parsed": {"message": "x" * 7000}}
        rows = [{"node_key": "first"}, {"node_key": "second"}]
        args = dict(identity=[envelope], envelope=envelope, response_detail="full", limit=1)
        for initial_budget, continuation_budget in ((65536, 8192), (8192, 65536)):
            with self.subTest(initial_budget=initial_budget):
                page = diagnostic_page(rows, **args, max_output_bytes=initial_budget)
                records = list(page["records"])
                chunks = []
                while page["has_more"]:
                    page = diagnostic_page(rows, **args, max_output_bytes=continuation_budget, cursor=page["next_cursor"])
                    self.assertLessEqual(payload_size(page), continuation_budget)
                    records.extend(page["records"])
                    if "envelope_value_page" in page:
                        chunks.append(page["envelope_value_page"]["text"])
                        self.assertFalse(page["envelope_complete"])
                        self.assertFalse(page["evidence_complete"])
                self.assertEqual(records, rows)
                self.assertEqual(json.loads("".join(chunks)), envelope)

    def test_detail_cursor_survives_summary_full_envelope_budget_boundary(self):
        envelope = {"parsed": {"message": "x" * 2317}}
        rows = [{"node_key": "one"}]
        args = dict(identity=[envelope], envelope=envelope, max_output_bytes=8192, summarize=filter_summary)
        summary = diagnostic_page(rows, **args)
        self.assertFalse(summary["envelope_complete"])
        full = diagnostic_page(rows, **args, response_detail="full", cursor=summary["records"][0]["detail_cursor"])
        self.assertEqual(full["records"], rows)

    def test_all_pages_keep_order_and_reject_changed_source_or_query(self):
        records = [{"node_key": str(index), "filter_facts": {"filters": ["safe"]}} for index in range(23)]
        args = dict(identity=["draft", "hash"], envelope={"writer_count": 23}, limit=4,
                    max_output_bytes=8192, summarize=filter_summary)
        cursor, actual = None, []
        while True:
            page = diagnostic_page(records, **args, cursor=cursor)
            self.assertLessEqual(payload_size(page), 8192)
            self.assertEqual(page["total_count"], 23)
            self.assertFalse(page["evidence_complete"])
            actual.extend(item["node_key"] for item in page["records"])
            if not page["has_more"]:
                break
            cursor = page["next_cursor"]
        self.assertEqual(actual, [str(index) for index in range(23)])
        with self.assertRaisesRegex(ValueError, "CURSOR"):
            diagnostic_page(records, **{**args, "identity": ["draft", "changed"]}, cursor=cursor)
        with self.assertRaisesRegex(ValueError, "CURSOR"):
            diagnostic_page(records, **args, response_detail="full", cursor=cursor)

    def test_oversized_full_record_roundtrips_without_loss(self):
        record = {"node_key": "one", "paramsValue": {"code": "中文" * 20000}}
        args = dict(identity=["same"], envelope={}, response_detail="full", max_output_bytes=8192, limit=1)
        cursor, chunks = None, []
        while True:
            page = diagnostic_page([record], **args, cursor=cursor)
            self.assertLessEqual(payload_size(page), 8192)
            self.assertFalse(page["evidence_complete"])
            chunks.append(page["record_value_page"]["text"])
            if not page["has_more"]:
                break
            cursor = page["next_cursor"]
        self.assertEqual(json.loads("".join(chunks)), record)

    def test_summary_detail_cursor_retrieves_original_record(self):
        rows = [{"node_key": "first", "paramsValue": {"code": "value"}}, {"node_key": "second"}]
        args = dict(identity=["same"], envelope={}, limit=1, summarize=filter_summary)
        summary = diagnostic_page(rows, **args)
        full = diagnostic_page(rows, **args, response_detail="full", cursor=summary["records"][0]["detail_cursor"])
        self.assertEqual(full["records"], rows[:1])

    def test_filter_service_summary_and_parameter_pointer_pin_design(self):
        class Repository:
            def resolve_action(self, identifier):
                return [{"ref_id": "ref"}]

            def load_design(self, ref_id, **kwargs):
                return {"design_id": "draft-id", "version": "draft", "data_sha256": "hash", "metadata": {},
                        "data_json": {"actionData": [{"key": "main", "title": "main", "data": []}]}}

        class Inspector:
            def inspect_component_filters(self, *args, **kwargs):
                return {"writer_count": 1, "writers": [{"group_key": "main", "node_key": "filter", "paramsValue": {"large": "x" * 30000}}]}

        service = object.__new__(GxpReadonlyService)
        service.repository, service.inspector = Repository(), Inspector()
        page = service.inspect_component_filters("ref", "component", version="draft")
        self.assertNotIn("paramsValue", page["writers"][0])
        self.assertEqual(page["writers"][0]["params_read"]["arguments"]["design_id"], "draft-id")
        self.assertEqual(page["component_filters"]["writer_count"], 1)

    def test_exception_service_returns_one_candidate_collection_and_budget(self):
        class Diagnostics:
            def trace_dynamic_exception(self, *args, **kwargs):
                candidate = {"design_id": "published-id", "version": "published", "generated_csharp": {"lines": ["x" * 30000]}}
                return {"parsed": {}, "actions": [{"action": {"ref_id": "ref"}, "runtime_published_candidates": [candidate],
                    "candidate_versions": [candidate], "current_copy_sync": {"sync_status": "synchronized"}}]}

        service = object.__new__(GxpReadonlyService)
        service.diagnostics = Diagnostics()
        page = service.trace_dynamic_exception("stack", max_output_bytes=8192)
        self.assertLessEqual(payload_size(page), 8192)
        self.assertNotIn("actions", page)
        self.assertEqual(page["runtime_published_candidates"][0]["design_id"], "published-id")
        self.assertNotIn("generated_csharp", page["runtime_published_candidates"][0])
        self.assertNotIn("candidate_versions", json.dumps(page))
