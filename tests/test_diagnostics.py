from __future__ import annotations

import unittest

from gxp_core.canvas import CanvasInspector
from gxp_core.diagnostics import (
    DiagnosticEngine,
    action_name_queries,
    page_name_queries,
    parse_dynamic_exception,
)
from gxp_core.config import DatabaseConfig
from gxp_core.db import _redacted_connection_error
from gxp_core.repository import _json_value


class DiagnosticParserTests(unittest.TestCase):
    def test_prefers_repeated_generated_class_frame(self) -> None:
        text = """System.Exception: sample
at GxP2.Services.DynamicActionService.InvokeDynamicMethod(Object value) in x:line 383
at GTEoZQNMJ.GTEoZQNMJ.main(String periodic_id) in :line 213"""
        result = parse_dynamic_exception(text)
        self.assertTrue(result["matched"])
        self.assertEqual("GTEoZQNMJ", result["generated_class"])
        self.assertEqual("main", result["method"])
        self.assertEqual(213, result["generated_csharp_line"])

    def test_mysql_bit_bytes_become_numbers(self) -> None:
        self.assertEqual(0, _json_value(b"\x00"))
        self.assertEqual(1, _json_value(b"\x01"))

    def test_connection_errors_redact_configured_values(self) -> None:
        config = DatabaseConfig(
            host="private-host",
            port=3306,
            database="private-db",
            user="private-user",
        )
        message = _redacted_connection_error(
            RuntimeError("private-user cannot access private-db at private-host"), config
        )
        self.assertNotIn("private-host", message)
        self.assertNotIn("private-db", message)
        self.assertNotIn("private-user", message)

    def test_action_tokens_allow_digit_prefix_and_name_queries(self) -> None:
        class Repository:
            def resolve_actions(self, tokens):
                self.tokens = tokens
                return [
                    {"action_code": "24qf4ene", "ref_id": "ref-24"}
                ] if "24qf4ene" in tokens else []

            def search_actions(self, query, *, limit=20):
                return []

            def search_design_text(self, text, *, max_rows=20):
                return []

        repository = Repository()
        engine = DiagnosticEngine(repository, CanvasInspector())

        result = engine.diagnose_codex_input(
            "请排查公共动作周期培训自动推送，调用 24qf4ene 后失败"
        )

        self.assertIn("24qf4ene", repository.tokens)
        self.assertEqual("24qf4ene", result["resolved_actions"][0]["action_code"])
        self.assertEqual("unique", result["action_resolution_status"])
        self.assertFalse(result["requires_action_selection"])
        self.assertIn("周期培训自动推送", action_name_queries("公共动作周期培训自动推送没有执行"))

    def test_page_semantics_fall_back_to_page_candidates(self) -> None:
        pages = {
            "岗位矩阵申请": "peixunjuzhenshenqingliucheng",
            "岗位矩阵修订": "peixunjuzhenbiangengliucheng",
            "岗位培训申请": "gangweipeixunshenqingliucheng",
        }

        class Repository:
            def resolve_actions(self, tokens):
                return []

            def search_actions(self, query, *, limit=20):
                return []

            def search_pages(self, query, *, limit=20):
                route = pages.get(query)
                return (
                    [{"page_id": route, "route": route, "display_name": query}]
                    if route
                    else []
                )

            def search_design_text(self, text, *, max_rows=20):
                raise AssertionError("page fallback must avoid broad design-text search")

        text = (
            "岗位矩阵申请/修订、岗位培训申请时下拉只能选择文件对应字段，"
            "如果没有就选择不了"
        )
        engine = DiagnosticEngine(Repository(), CanvasInspector())
        result = engine.diagnose_codex_input(text)

        self.assertEqual(
            ["岗位矩阵申请", "岗位矩阵修订", "岗位培训申请"],
            page_name_queries(text),
        )
        self.assertEqual(3, len(result["page_candidates"]))
        self.assertEqual("list_page_actions", result["next_tools"][0])
        self.assertIn("Route/Id/OutId", result["page_next_step"])

    def test_page_queries_are_not_limited_to_training_domains(self) -> None:
        self.assertEqual(
            ["采购订单审批", "供应商变更页面", "质量事件详情页面"],
            page_name_queries(
                "请检查采购订单审批、供应商变更页面，"
                "质量事件详情页面也需要定位"
            ),
        )

    def test_exception_history_uses_published_snapshot_but_current_sync_uses_active_copies(self) -> None:
        empty_data = '{"actionData": []}'
        history_csharp = "ABC12345\nhistory failure\nreturn;"
        current_csharp = "ABC12345\ncurrent line\nreturn;"

        class Repository:
            def resolve_action(self, identifier):
                return [{"action_code": "ABC12345", "ref_id": "ref-1"}]

            def get_design_versions(self, ref_id, *, include_deleted, include_content):
                if not include_deleted:
                    return [
                        {
                            "design_id": "published-current",
                            "version": "published",
                            "is_deleted": False,
                            "created_time": "2026-02-01 00:00:00",
                            "data": empty_data,
                            "csharp_code": current_csharp,
                            "data_sha256": "data-current",
                            "csharp_sha256": "code-current",
                        },
                        {
                            "design_id": "draft-current",
                            "version": "draft",
                            "is_deleted": False,
                            "created_time": "2025-12-01 00:00:00",
                            "modified_time": "2026-02-01 00:00:00",
                            "data": empty_data,
                            "csharp_code": current_csharp,
                            "data_sha256": "data-current",
                            "csharp_sha256": "code-current",
                        },
                    ]
                return [
                    {
                        "design_id": "published-current",
                        "version": "published",
                        "is_deleted": False,
                        "created_time": "2026-02-01 00:00:00",
                        "data": empty_data,
                        "csharp_code": current_csharp,
                        "data_sha256": "data-current",
                        "csharp_sha256": "code-current",
                    },
                    {
                        "design_id": "published-history",
                        "version": "published",
                        "is_deleted": True,
                        "created_time": "2026-01-01 00:00:00",
                        "data": empty_data,
                        "csharp_code": history_csharp,
                        "data_sha256": "data-history",
                        "csharp_sha256": "code-history",
                    },
                    {
                        "design_id": "draft-history",
                        "version": "draft",
                        "is_deleted": True,
                        "created_time": "2025-12-01 00:00:00",
                        "data": empty_data,
                        "csharp_code": history_csharp,
                        "data_sha256": "draft-history",
                        "csharp_sha256": "draft-history",
                    },
                ]

            def resolve_actions(self, tokens):
                return []

        result = DiagnosticEngine(Repository(), CanvasInspector()).trace_dynamic_exception(
            "System.Exception: failure\nat ABC12345.ABC12345.main() in :line 2",
            at_time="2026-01-15 00:00:00",
        )
        action = result["actions"][0]

        self.assertEqual(
            ["published-history"],
            [item["design_id"] for item in action["runtime_published_candidates"]],
        )
        self.assertEqual("synchronized", action["current_copy_sync"]["sync_status"])
        self.assertFalse(action["current_copy_sync"]["has_unpublished_changes"])
        self.assertEqual(
            "published-current",
            action["current_copy_sync"]["current_published"]["design_id"],
        )


if __name__ == "__main__":
    unittest.main()
