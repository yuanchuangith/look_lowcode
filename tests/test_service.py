from __future__ import annotations

import json
import unittest

from gxp_core.canvas import CanvasInspector
from gxp_core.service import GxpReadonlyService


class ServiceVersionTests(unittest.TestCase):
    @staticmethod
    def service_with_versions(versions):
        class Repository:
            def get_design_versions(self, ref_id, *, include_deleted, include_content):
                return [dict(item) for item in versions]

            def action_metadata(self, ref_id):
                return {"ref_id": ref_id, "action_code": "action-1"}

        service = object.__new__(GxpReadonlyService)
        service.repository = Repository()
        service.inspector = CanvasInspector()
        return service

    def test_current_copies_are_synchronized_when_both_hashes_match(self) -> None:
        service = self.service_with_versions(
            [
                {
                    "design_id": "published",
                    "version": "published",
                    "is_deleted": False,
                    "data_sha256": "same-data",
                    "csharp_sha256": "same-code",
                },
                {
                    "design_id": "draft",
                    "version": "draft",
                    "is_deleted": False,
                    "data_sha256": "same-data",
                    "csharp_sha256": "same-code",
                },
            ]
        )

        result = service.get_design_versions("ref-1")

        self.assertEqual("synchronized", result["sync_status"])
        self.assertFalse(result["has_unpublished_changes"])
        self.assertTrue(result["current_published"]["used_by_runtime"])
        self.assertFalse(result["current_draft"]["used_by_runtime"])

    def test_current_copies_report_unpublished_draft_changes(self) -> None:
        service = self.service_with_versions(
            [
                {
                    "design_id": "published",
                    "version": "published",
                    "is_deleted": False,
                    "data_sha256": "published-data",
                    "csharp_sha256": "published-code",
                },
                {
                    "design_id": "draft",
                    "version": "draft",
                    "is_deleted": False,
                    "data_sha256": "draft-data",
                    "csharp_sha256": "draft-code",
                },
            ]
        )

        result = service.get_design_versions("ref-1")

        self.assertEqual("unpublished_draft_changes", result["sync_status"])
        self.assertTrue(result["has_unpublished_changes"])
        self.assertFalse(result["version_semantics"].get("draft_edits_affect_runtime", False))


class ServiceInspectionLimitTests(unittest.TestCase):
    @staticmethod
    def make_service(node_count=25, csharp_line_count=30):
        design = {
            "actionData": [
                {
                    "key": "main",
                    "title": "主动作",
                    "data": [
                        {
                            "key": f"node-{index}",
                            "title": f"needle node {index}",
                            "elementKey": "SetVariableValue",
                            "paramsValue": {
                                "inputParams": {
                                    "variableName": {"code": f"target_{index}"},
                                    "attributeValue": {"code": "needle"},
                                }
                            },
                        }
                        for index in range(node_count)
                    ],
                }
            ]
        }
        csharp = "\n".join(f"// needle generated line {index}" for index in range(csharp_line_count))

        class Repository:
            def resolve_action(self, identifier):
                return [{"ref_id": "ref-1", "action_code": identifier}]

            def search_actions(self, identifier):
                return []

            def load_design(self, ref_id, **kwargs):
                return {
                    "design_id": "design-1",
                    "version": "published",
                    "is_deleted": False,
                    "modified_time": "2026-08-26 00:00:00",
                    "data_sha256": "data-hash",
                    "csharp_sha256": "code-hash",
                    "data_json": design,
                    "csharp_code": csharp,
                    "metadata": {
                        "ref_id": ref_id,
                        "action_code": "PQDL0QlL",
                        "action_name": "培训主题",
                    },
                }

        service = object.__new__(GxpReadonlyService)
        service.repository = Repository()
        service.inspector = CanvasInspector()
        return service

    def test_terms_do_not_return_csharp_without_explicit_opt_in(self) -> None:
        result = self.make_service().inspect_action(
            "PQDL0QlL", terms=["needle"], include_generated_csharp=False
        )

        self.assertFalse(any(key.startswith("generated_csharp") for key in result))
        self.assertEqual(25, result["matched_node_count"])
        self.assertEqual(20, result["node_count"])
        self.assertTrue(result["nodes_truncated"])

    def test_generated_csharp_is_capped_and_reports_truncation(self) -> None:
        result = self.make_service().inspect_action(
            "PQDL0QlL",
            terms=["needle"],
            include_generated_csharp=True,
            max_nodes=5,
        )

        self.assertEqual(30, result["generated_csharp_match_count"])
        self.assertEqual(20, len(result["generated_csharp_matches"]))
        self.assertTrue(result["generated_csharp_matches_truncated"])
        self.assertLess(len(json.dumps(result).encode("utf-8")), 64 * 1024)

    def test_exact_csharp_line_works_without_opt_in(self) -> None:
        result = self.make_service().inspect_action(
            "PQDL0QlL", csharp_line=3, include_generated_csharp=False
        )

        self.assertEqual(3, result["generated_csharp"]["requested_line"])

    def test_broad_params_return_compact_preview(self) -> None:
        result = self.make_service().inspect_action(
            "PQDL0QlL", terms=["needle"], include_params=True, max_nodes=5
        )

        self.assertTrue(result["too_broad_for_params"])
        self.assertTrue(result["params_omitted"])
        self.assertEqual(25, result["matched_node_count"])
        self.assertEqual(5, result["node_count"])
        self.assertTrue(all("paramsValue" not in node for node in result["nodes"]))
        self.assertIn("group", result["params_next_step"])

    def test_narrow_params_are_returned(self) -> None:
        result = self.make_service().inspect_action(
            "PQDL0QlL", node_key="node-3", include_params=True
        )

        self.assertFalse(result["too_broad_for_params"])
        self.assertEqual(1, result["node_count"])
        self.assertIn("paramsValue", result["nodes"][0])
        self.assertIn("control_flow", result["nodes"][0])

    def test_control_flow_tool_returns_summary_then_explicit_action_graph(self) -> None:
        service = self.make_service(node_count=3)
        summary = service.inspect_control_flow("PQDL0QlL")
        self.assertEqual("summary", summary["scope"]["mode"])
        self.assertEqual([], summary["graph"]["nodes"])
        action = service.inspect_control_flow("PQDL0QlL", scope="action")
        self.assertEqual(3, len([node for node in action["graph"]["nodes"] if node["type"] == "canvas"]))
        self.assertIn("tree_text", action["views"])

    def test_page_action_ambiguity_requires_exact_identifier(self) -> None:
        class Repository:
            def resolve_pages(self, page_identifier):
                return [{"route": "one"}, {"route": "two"}]

        service = object.__new__(GxpReadonlyService)
        service.repository = Repository()
        result = service.list_page_actions("duplicate")

        self.assertEqual("ambiguous", result["resolution_status"])
        self.assertEqual([], result["actions"])


if __name__ == "__main__":
    unittest.main()
