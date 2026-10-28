from __future__ import annotations

import base64
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import patch

from diagnostic_fixture import FixtureDatabase, STACK
from gxp_core.diagnostic_cache import DIAGNOSTIC_CACHE, DiagnosticCache, ReadManifest
from gxp_core.service import GxpReadonlyService
from gxp_core.canvas_budget import payload_size


class DiagnosticCacheTests(unittest.TestCase):
    def setUp(self):
        DIAGNOSTIC_CACHE.clear()
        self.addCleanup(DIAGNOSTIC_CACHE.clear)
        self.database = FixtureDatabase()

    def service(self):
        return GxpReadonlyService(self.database)

    def test_filter_pages_revalidate_actual_reads_without_transferring_or_analyzing_body(self):
        service = self.service()
        with patch.object(service.inspector, "inspect_component_filters", wraps=service.inspector.inspect_component_filters) as scan:
            first = service.inspect_component_filters("ACTION01", "picker", limit=1)
            self.assertEqual(scan.call_count, 1)
        reads, queries = self.database.body_reads, len(self.database.queries)
        service = self.service()  # MCP creates a fresh service/repository/DB wrapper.
        with patch.object(service.inspector, "inspect_component_filters", side_effect=AssertionError("must reuse pure analysis")):
            second = service.inspect_component_filters("ACTION01", "picker", cursor=first["next_cursor"], limit=1)
        self.assertEqual(reads, self.database.body_reads)
        self.assertGreater(len(self.database.queries), queries)
        self.assertEqual(first["snapshot_fingerprint"], second["snapshot_fingerprint"])
        self.assertEqual(second["writers"][0]["node_key"], "writer-1")

    def test_codex_exception_route_uses_bounded_cached_summary_and_restorable_continuation(self):
        context = {"goal": "preserve-context", "anchors": [{"action_code": "ACTION01"}]}
        service = self.service()
        first = service.diagnose_codex_input(STACK, context=context, max_output_bytes=8192, limit=1)
        self.assertEqual("dynamic_exception", first["input_kind"])
        self.assertEqual(context, first["conversation_context"]["record"])
        self.assertLessEqual(payload_size(first), 8192)
        page = first["diagnosis"]
        self.assertEqual("summary", page["response_detail"])
        self.assertNotIn("actions", page)
        self.assertNotIn("generated_csharp", page["runtime_published_candidates"][0])
        next_read = page["evidence_gaps"][0]["next_read"]
        self.assertEqual("diagnose_codex_input", next_read["tool"])
        self.assertTrue(next_read["reuse_original_arguments"])
        self.assertEqual(["text", "at_time", "context", "context_lines", "max_output_bytes", "limit"], next_read["inherit_arguments"])
        self.assertNotIn("text", next_read["arguments"])
        body_reads = self.database.body_reads
        service = self.service()
        with patch.object(service.diagnostics, "trace_dynamic_exception", side_effect=AssertionError("must reuse pure analysis")):
            second = service.diagnose_codex_input(STACK, context=context, max_output_bytes=8192, limit=1,
                **next_read["arguments"])
        self.assertEqual(body_reads, self.database.body_reads)
        self.assertEqual(page["snapshot_fingerprint"], second["diagnosis"]["snapshot_fingerprint"])
        self.assertLessEqual(payload_size(second), 8192)

    def test_codex_exception_large_context_and_stack_recover_via_envelope_pages(self):
        context = {"goal": "中文😀" * 2500}
        stack = STACK.replace("synthetic failure", "中文😀" * 2000)
        args = {"context": context, "max_output_bytes": 8192, "response_detail": "full", "limit": 1}
        result = self.service().diagnose_codex_input(stack, **args)
        chunks = []
        while True:
            self.assertLessEqual(payload_size(result), 8192)
            page = result["diagnosis"]
            self.assertFalse(page["evidence_complete"])
            if "envelope_value_page" in page:
                value = page["envelope_value_page"]
                self.assertEqual(sum(map(len, chunks)), value["offset"])
                chunks.append(value["text"])
            if not page["has_more"]:
                break
            result = self.service().diagnose_codex_input(stack, **args, cursor=page["next_cursor"])
        restored = json.loads("".join(chunks))
        self.assertEqual(context, restored["conversation_context"]["record"])
        self.assertEqual("中文😀" * 2000, restored["parsed"]["message"])

    def test_codex_exception_cursor_rejects_changed_context_and_design(self):
        first = self.service().diagnose_codex_input(STACK, context={"goal": "one"}, limit=1)
        cursor = first["diagnosis"]["next_cursor"]
        with self.assertRaisesRegex(ValueError, "CURSOR"):
            self.service().diagnose_codex_input(STACK, context={"goal": "two"}, cursor=cursor)
        self.database.versions[-1]["data"] += " "
        with self.assertRaisesRegex(ValueError, "CURSOR"):
            self.service().diagnose_codex_input(STACK, context={"goal": "one"}, cursor=cursor)

    def test_mutated_same_design_id_and_permission_denial_never_use_cached_evidence(self):
        first = self.service().inspect_component_filters("ACTION01", "picker", limit=1)
        self.database.denied = True
        with self.assertRaises(PermissionError):
            self.service().inspect_component_filters("ACTION01", "picker", cursor=first["next_cursor"])
        self.database.denied = False
        self.database.versions[-2]["data"] = self.database.versions[-2]["data"].replace("values0", "changed")
        with self.assertRaisesRegex(ValueError, "CURSOR"):
            self.service().inspect_component_filters("ACTION01", "picker", cursor=first["next_cursor"])

    def test_changed_publication_and_account_scope_force_fresh_analysis(self):
        first = self.service().inspect_component_filters("ACTION01", "picker", limit=1)
        self.database.config.user = "other-reader"
        service = self.service()
        with patch.object(service.inspector, "inspect_component_filters", wraps=service.inspector.inspect_component_filters) as scan:
            service.inspect_component_filters("ACTION01", "picker", cursor=first["next_cursor"])
            self.assertEqual(scan.call_count, 1)
        self.database.versions[-2]["is_deleted"] = 1
        self.database.versions[0]["is_deleted"] = 0
        with self.assertRaisesRegex(ValueError, "CURSOR"):
            self.service().inspect_component_filters("ACTION01", "picker", cursor=first["next_cursor"])

    def test_exception_manifest_includes_empty_call_selectors_and_current_draft(self):
        first = self.service().trace_dynamic_exception(STACK, limit=1)
        self.assertTrue(first["has_more"])
        reads = self.database.body_reads
        service = self.service()
        with patch.object(service.diagnostics, "trace_dynamic_exception", side_effect=AssertionError("must reuse")):
            service.trace_dynamic_exception(STACK, cursor=first["next_cursor"], limit=1)
        self.assertEqual(reads, self.database.body_reads)
        self.database.actions.append({"action_type": "public", "ref_id": "child", "action_code": "MISSING01", "action_name": "new", "page_id": None})
        with self.assertRaisesRegex(ValueError, "CURSOR"):
            self.service().trace_dynamic_exception(STACK, cursor=first["next_cursor"])

    def test_exception_rechecks_class_fallback_and_called_action_history(self):
        for row in self.database.versions:
            row["csharp_code"] = row["csharp_code"].replace("class ACTION01", "class GeneratedFixture")
        stack = STACK.replace("ACTION01", "GeneratedFixture")
        first = self.service().trace_dynamic_exception(stack, limit=1)
        self.assertTrue(any("LIKE %(needle)s" in sql for sql, _, _ in self.database.queries))
        self.database.actions.append({"action_type": "public", "ref_id": "new-root", "action_code": "GeneratedFixture", "action_name": "new", "page_id": None})
        with self.assertRaisesRegex(ValueError, "CURSOR"):
            self.service().trace_dynamic_exception(stack, cursor=first["next_cursor"])
        self.database.actions.pop()
        self.database.actions.append({"action_type": "public", "ref_id": "child", "action_code": "MISSING01", "action_name": "child", "page_id": None})
        self.database.versions.append({**self.database.versions[0], "ref_id": "child", "design_id": "child-history",
                                       "csharp_code": "// synthetic failure", "is_deleted": 1})
        first = self.service().trace_dynamic_exception(stack, limit=1)
        self.database.versions[-1]["csharp_code"] = "// historical content changed"
        with self.assertRaisesRegex(ValueError, "CURSOR"):
            self.service().trace_dynamic_exception(stack, cursor=first["next_cursor"])

    def test_envelope_fragments_reuse_analysis_and_unsigned_guidance_fits_budget(self):
        from gxp_core.canvas_budget import payload_size
        stack = STACK.replace("synthetic failure", "中文😀" * 3000)
        page = self.service().trace_dynamic_exception(stack, max_output_bytes=8192, limit=20)
        reads = self.database.body_reads
        saw_envelope = False
        while page["has_more"]:
            self.assertLessEqual(payload_size(page), 8192)
            self.assertIn("evidence_gaps", page)
            self.assertEqual(page["evidence_gaps"][0]["next_read"]["arguments"]["cursor"], page["next_cursor"])
            service = self.service()
            with patch.object(service.diagnostics, "trace_dynamic_exception", side_effect=AssertionError("analysis should be cached")):
                page = service.trace_dynamic_exception(stack, max_output_bytes=8192, limit=20, cursor=page["next_cursor"])
            saw_envelope |= "envelope_value_page" in page
        self.assertTrue(saw_envelope)
        self.assertFalse(page["evidence_complete"])
        self.assertEqual(self.database.body_reads, reads)
        DIAGNOSTIC_CACHE.clear()
        first = self.service().trace_dynamic_exception(STACK, limit=1)
        self.database.versions[-1]["data"] = self.database.versions[-1]["data"].replace("values0", "draft-changed")
        with self.assertRaisesRegex(ValueError, "CURSOR"):
            self.service().trace_dynamic_exception(STACK, cursor=first["next_cursor"])

    def test_eviction_rebuild_accepts_v1_and_v2_without_changing_fingerprint(self):
        first = self.service().inspect_component_filters("ACTION01", "picker", limit=1)
        state = json.loads(base64.urlsafe_b64decode(first["next_cursor"]))
        legacy = base64.urlsafe_b64encode(json.dumps([1, *state[1:5]]).encode()).decode()
        for cursor in (legacy, first["next_cursor"]):
            DIAGNOSTIC_CACHE.clear()
            second = self.service().inspect_component_filters("ACTION01", "picker", cursor=cursor, limit=1)
            self.assertEqual(first["snapshot_fingerprint"], second["snapshot_fingerprint"])
            self.assertEqual(second["writers"][0]["node_key"], "writer-1")

    def test_lru_idle_and_serialized_byte_limits(self):
        self.service().inspect_component_filters("ACTION01", "picker", limit=1)
        snapshot = next(iter(DIAGNOSTIC_CACHE._items.values()))[0]
        now = [0]
        cache = DiagnosticCache(max_entries=2, max_entry_bytes=snapshot.serialized_bytes + 1,
                                max_total_bytes=snapshot.serialized_bytes * 2, idle_seconds=300, clock=lambda: now[0])
        cache.put("first", snapshot)
        cache.put("second", snapshot)
        cache.get("first")
        cache.put("third", snapshot)
        self.assertIsNone(cache.get("second"))
        cache.put("oversized", replace(snapshot, serialized_bytes=snapshot.serialized_bytes + 2))
        self.assertIsNone(cache.get("oversized"))
        now[0] = 301
        self.assertIsNone(cache.get("first"))
        self.assertEqual(cache._bytes, 0)

    def test_concurrent_new_request_services_do_not_mutate_or_share_connections(self):
        first = self.service().inspect_component_filters("ACTION01", "picker", limit=1)
        inspector_type = type(self.service().inspector)
        def read(_):
            database = FixtureDatabase()
            result = GxpReadonlyService(database).inspect_component_filters(
                "ACTION01", "picker", cursor=first["next_cursor"], limit=1)
            self.assertGreater(len(database.queries), 0)
            self.assertEqual(0, database.body_reads)
            return result
        with patch.object(inspector_type, "inspect_component_filters", side_effect=AssertionError("unexpected reanalysis")):
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(read, range(8)))
            results[0]["writers"][0]["node_key"] = "caller-mutation"
            self.assertEqual("writer-1", read(None)["writers"][0]["node_key"])

    def test_truncated_read_does_not_enter_cache_and_proof_hashes_are_utf8(self):
        self.database.truncated = True
        self.service().inspect_component_filters("ACTION01", "picker", limit=1)
        self.assertFalse(DIAGNOSTIC_CACHE._items)
        manifest = ReadManifest()
        manifest.record("SELECT `data` AS `data` FROM fixture", None, 1, None, [{"data": "中文😀"}], False)
        self.assertIn("CONVERT(IFNULL(`data`,'') USING utf8mb4)", manifest.proofs[0].sql)
        unknown = ReadManifest()
        unknown.record("SELECT data FROM fixture", None, 1, None, [{"data": "value"}], False)
        self.assertFalse(unknown.complete)


if __name__ == "__main__":
    unittest.main()
