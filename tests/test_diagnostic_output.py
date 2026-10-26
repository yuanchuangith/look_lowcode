from __future__ import annotations

import copy
import json
import unittest

from gxp_core.canvas import CanvasInspector
from gxp_core.diagnostic_output import diagnostic_page, filter_summary
from gxp_core.service import GxpReadonlyService
from gxp_core.canvas_budget import payload_size


class DiagnosticOutputTests(unittest.TestCase):
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
