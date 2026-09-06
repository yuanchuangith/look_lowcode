from __future__ import annotations

import copy
import unittest

from gxp_core.canvas import CanvasInspector, node_facts
from gxp_core.canvas_references import expression_references
from gxp_core.conversation import conversation_context
from gxp_core.diagnostics import DiagnosticEngine


def node(key, element, inputs=None, outputs=None):
    return {"key": key, "title": key, "elementKey": element, "paramsValue": {"inputParams": inputs or {}, "outputParams": outputs or {}}}


def design(nodes, key="main", title="main"):
    return {"actionData": [{"key": key, "title": title, "data": nodes}]}


class Repository:
    def resolve_action(self, identifier):
        return [{"ref_id": identifier, "action_code": identifier}]

    def resolve_actions(self, tokens):
        return [self.resolve_action(token)[0] for token in tokens if token == "ACTION02"]

    def search_actions(self, query, **kwargs):
        return []

    def search_pages(self, query, **kwargs):
        return []

    def search_design_text(self, query, **kwargs):
        return []


class ConversationAccuracyTests(unittest.TestCase):
    def test_context_is_stateless_and_does_not_claim_verification(self):
        context = {"anchors": [{"action_code": "ACTION01"}], "findings": [{"id": "BUG-01", "status": "reported_fixed"}], "exclusions": ["hours"]}
        original = copy.deepcopy(context)
        result = DiagnosticEngine(Repository(), CanvasInspector()).diagnose_codex_input("改了再看看", context=context)
        self.assertEqual(original, context)
        self.assertTrue(result["context_anchor_reused"])
        self.assertEqual(["compare_designs", "inspect_action"], result["next_tools"])
        self.assertEqual("none", result["conversation_context"]["persistence"])
        self.assertFalse(result["recheck_target"]["reuse_old_canvas_lines"])

    def test_explicit_new_identity_wins_and_unknown_does_not_fallback(self):
        engine = DiagnosticEngine(Repository(), CanvasInspector())
        context = {"anchors": [{"action_code": "ACTION01"}]}
        self.assertEqual("ACTION02", engine.diagnose_codex_input("ACTION02 改了", context=context)["resolved_actions"][0]["action_code"])
        self.assertEqual([], engine.diagnose_codex_input("UNKNOWN9", context=context)["resolved_actions"])
        self.assertEqual([], engine.diagnose_codex_input("ABCDEFGH", context=context)["resolved_actions"])

    def test_field_correction_reuses_anchor_and_multiple_anchors_stay_ambiguous(self):
        engine = DiagnosticEngine(Repository(), CanvasInspector())
        context = {"anchors": [{"action_code": "ACTION01"}]}
        self.assertTrue(engine.diagnose_codex_input("member_id 要用", context=context)["context_anchor_reused"])
        context["anchors"].append({"action_code": "ACTION02"})
        self.assertTrue(engine.diagnose_codex_input("再看看", context=context)["requires_action_selection"])

    def test_context_validation(self):
        for value in ([], {"password": "x"}, {"anchors": [{}] * 9}, {"goal": "x" * 40000}, {"anchors": [{"ref_id": 5}]}):
            with self.subTest(value_type=type(value)), self.assertRaises(ValueError):
                conversation_context(value, "review")

    def test_field_read_condition_loop_and_return(self):
        nodes = [
            node("condition", "IfCondition", {"condition": {"Filters": [{"target": {"code": "trainingType"}, "equalTo": "Equal", "value": {"code": '"initial"'}}]}}),
            node("end", "IfEnd"),
            node("define", "SetVariable", {"variableValue": {"code": 'detail["file_ver_id"]'}}, {"variableName": {"code": "version"}}),
            node("assign", "SetVariableValue", {"attributeValue": {"code": "file_ver_id"}}),
            node("return", "ExitAction", {"returnValue": {"code": "file_ver_id"}}),
        ]
        inspected = CanvasInspector().inspect(design(nodes))
        self.assertEqual(1, len(CanvasInspector.focus_fields(inspected, ["trainingType"])))
        self.assertEqual(3, len(CanvasInspector.focus_fields(inspected, ["file_ver_id"])))
        references = node_facts(node("loop", "ForEachArray", {"list": {"code": "files"}}, {"item": {"code": "file"}}))["references"]
        self.assertTrue(any(item["symbol"] == "files" and item["role"] == "loop_source" for item in references))

    def test_literals_and_similar_identifiers_do_not_match(self):
        for expression in ('"file_ver_id"', '"file_ver_id is unused"', '/* file_ver_id */ file_ver_id_suffix'):
            refs = expression_references(expression, "read", "value")
            self.assertFalse(any(item["symbol"] == "file_ver_id" for item in refs))
        inspected = CanvasInspector().inspect(design([node("mapping", "AddNewData", {"params": [{"attribute": "message", "name": {"code": '"file_ver_id is mentioned"'}}]})]))
        self.assertEqual([], CanvasInspector.focus_fields(inspected, ["file_ver_id"]))

    def test_exact_group_and_ambiguity(self):
        data = {"actionData": [{"key": key, "title": "same", "data": [node(key, "SetVariable")]} for key in ("main", "main-copy")]}
        inspector = CanvasInspector()
        self.assertEqual(["main"], [item["group_key"] for item in inspector.inspect(data, group="main")])
        self.assertEqual([], inspector.inspect(data, group="same"))
        self.assertEqual("ambiguous", inspector.inspect_control_flow(data, group="same")["group_resolution"]["status"])

    def test_local_call_identity_is_not_display_name(self):
        data = design([node("call", "CallAction", {"actionName": {"value": "target", "label": "same"}})])
        data["actionData"].append({"key": "target", "title": "same", "data": []})
        called = CanvasInspector().inspect(data, group="main")[0]["facts"]["called_action"]
        self.assertEqual("target", called["target_group_key"])
        self.assertEqual("resolved", called["resolution_status"])
        dynamic = node_facts(node("call", "CallAction", {"actionName": {"value": 'row["target"]', "label": "same"}}))["called_action"]
        self.assertEqual("", dynamic["target_group_key"])


if __name__ == "__main__":
    unittest.main()
