from __future__ import annotations

import os
import json
import unittest

from gxp_core.service import GxpReadonlyService


@unittest.skipUnless(
    os.environ.get("GXP_LIVE_TEST") == "1",
    "set GXP_LIVE_TEST=1 to run read-only live checks",
)
class LiveReadOnlyIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = GxpReadonlyService()

    def test_action_name_and_natural_language_resolve_periodic_push(self) -> None:
        resolved = self.service.resolve_action("周期培训自动推送")
        diagnosed = self.service.diagnose_codex_input(
            "公共动作周期培训自动推送没有执行，请排查"
        )

        self.assertIn(
            "sPNfFfCL", [item.get("action_code") for item in resolved["matches"]]
        )
        self.assertIn(
            "sPNfFfCL",
            [item.get("action_code") for item in diagnosed["resolved_actions"]],
        )

    def test_focus_field_limits_output_to_matching_nodes(self) -> None:
        result = self.service.inspect_action(
            "sPNfFfCL",
            version="published",
            focus_fields=["push_status"],
            include_generated_csharp=True,
        )

        self.assertGreater(result["scanned_node_count"], result["node_count"])
        self.assertEqual(result["field_match_count"], result["node_count"])
        self.assertTrue(result["node_generated_csharp_evidence"])

    def test_golden_page_routes_and_component_filters_stay_compact(self) -> None:
        expected_pages = {
            "岗位矩阵申请": "peixunjuzhenshenqingliucheng",
            "岗位矩阵修订": "peixunjuzhenbiangengliucheng",
            "岗位培训申请": "gangweipeixunshenqingliucheng",
        }
        responses = []
        for query, route in expected_pages.items():
            page_result = self.service.search_pages(query, limit=5)
            self.assertEqual(route, page_result["matches"][0]["route"])
            responses.append(page_result)
            action_result = self.service.list_page_actions(route)
            self.assertEqual("unique", action_result["resolution_status"])
            responses.append(action_result)

        for action, component in (
            ("PQDL0QlL", "testpaper"),
            ("MP8fqQTL", "testpaper_id"),
        ):
            filter_result = self.service.inspect_component_filters(action, component)
            component_filters = filter_result["component_filters"]
            self.assertEqual("unique", component_filters["resolution_status"])
            self.assertGreater(component_filters["writer_count"], 1)
            self.assertFalse(filter_result["generated_csharp_included"])
            responses.append(filter_result)

        sizes = [
            len(json.dumps(item, ensure_ascii=False, default=str).encode("utf-8"))
            for item in responses
        ]
        self.assertTrue(all(size < 64 * 1024 for size in sizes))
        self.assertLess(sum(sizes), 120 * 1024)


if __name__ == "__main__":
    unittest.main()
