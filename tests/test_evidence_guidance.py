import copy
import unittest

from gxp_core.evidence_guidance import guidance
from gxp_core.telemetry import traced_tool
from gxp_core.source_analysis import _base


class EvidenceGuidanceTests(unittest.TestCase):
    def test_error_guidance_does_not_turn_failure_into_success_or_mutate_result(self):
        original = {"blocked": True, "error_code": "DB_OFFLINE", "write_executed": False}
        expected = copy.deepcopy(original)
        wrapped = traced_tool(lambda: original)
        response = wrapped()
        self.assertTrue(response["blocked"])
        self.assertFalse(response["write_executed"])
        self.assertEqual("alternative_read_required", response["fallback"]["stop_reason"])
        self.assertEqual(3, response["fallback"]["max_additional_calls"])
        self.assertEqual(expected, original)

    def test_unhealthy_source_layer_keeps_healthy_work_without_closing_chain(self):
        status = {"repositories": {"frontend": {"stale": False}, "backend": {"stale": True}}}
        result = _base(status, ("frontend", "backend"))
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(["backend"], result["evidence_gaps"][0]["affects"])
        self.assertIn("frontend", result["evidence_gaps"][0]["can_continue"])
        self.assertTrue(result["index"]["stale"])

    def test_guidance_does_not_alias_executable_request(self):
        request = {"tool": "describe_table", "arguments": {"table": "orders"}}
        result = guidance("missing", "relation", next_read=request)
        request["arguments"]["table"] = "other"
        self.assertEqual("orders", result["evidence_gaps"][0]["next_read"]["arguments"]["table"])
