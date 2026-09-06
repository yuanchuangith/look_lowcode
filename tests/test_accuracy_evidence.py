from __future__ import annotations

import copy
import json
import importlib.util
import unittest
from pathlib import Path

from gxp_core.canvas import CanvasInspector
from gxp_core.canvas_budget import canvas_payload, node_value_page, payload_size
from gxp_core.canvas_evidence import _method_ranges, scoped_csharp
from gxp_core.call_flow import expand_calls
from gxp_core.service import GxpReadonlyService
from test_conversation_accuracy import design, node
import test_cpm_snapshot
from gxp_core.cpm_snapshot import get_cpm_knowledge


class Repository:
    def __init__(self, root, others=None):
        self.root = root
        self.others = others or {}
        self.reads = []

    def resolve_action(self, identifier):
        return [{"ref_id": identifier, "action_code": identifier}]

    def load_design(self, ref_id, **kwargs):
        self.reads.append((ref_id, kwargs))
        return copy.deepcopy(self.others.get(ref_id, self.root))


def snapshot(data, key="root", code=""):
    return {"design_id": key + "-design", "version": "published", "is_deleted": 0, "metadata": {"ref_id": key, "action_code": key}, "data_json": data, "csharp_code": code}


class AccuracyEvidenceTests(unittest.TestCase):
    def test_replay_rubric_accepts_semantic_equivalents_not_false_bugs(self):
        path = Path(__file__).resolve().parents[1] / "scripts/replay_accuracy.py"
        spec = importlib.util.spec_from_file_location("replay_accuracy", path)
        replay = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(replay)
        settings = replay.fallback_settings('model = "fixture-model"\n[mcp_servers.local]\nmodel = "not-root"\n[mcp_servers."quoted.name".env]\n[mcp_servers.\'literal-name\']')
        self.assertEqual("fixture-model", settings["model"])
        self.assertEqual({"local", "quoted.name", "literal-name"}, set(settings["mcp_servers"]))
        case = {"id": "shared-type", "expected": {"classification": "risk", "decision": "verify_type_before_cast"}}
        self.assertIsNone(replay.grade_case(case, {"classification": "clarification", "decision": "verify_type_before_cast"}))
        self.assertIsNotNone(replay.grade_case(case, {"classification": "bug", "decision": "verify_type_before_cast"}))
        cases = json.loads((path.parents[1] / "tests/accuracy_replay_cases.json").read_text(encoding="utf-8"))
        self.assertEqual(12, len({case["id"] for case in cases}))

    def test_method_scope_ignores_other_method_and_strings(self):
        code = 'class Generated {\nvoid Other() { var value = "file_ver_id"; }\nvoid target() { var value = detail["file_ver_id"]; var text = "} void Wrong() {"; }\n}'
        scoped, result = scoped_csharp(code, [{"group_key": "target"}])
        self.assertEqual("resolved_method", result["status"])
        matches = CanvasInspector.search_csharp(scoped, ["file_ver_id"], context=0)
        self.assertEqual([3], [item["requested_line"] for item in matches])
        self.assertFalse(result["exact_source_map"])

    def test_ambiguous_or_unknown_method_retains_candidate(self):
        code = 'class Generated { void target(int first) {} void target(string second) {} }'
        self.assertEqual("unresolved", scoped_csharp(code, [{"group_key": "target"}])[1]["status"])
        self.assertEqual("unresolved", scoped_csharp(code, [{"group_key": "unknown"}])[1]["status"])

    def test_code_changes_do_not_reuse_old_method_locations(self):
        _method_ranges.cache_clear()
        for design_id in ("first", "second"):
            scoped_csharp("class G { void target() {} }", [{"group_key": "target"}], design_id)
        self.assertEqual(2, _method_ranges.cache_info().misses)
        nodes = [{"group_key": "target"}]
        before = scoped_csharp('class G { void target() {} }', nodes)[1]
        after = scoped_csharp('class G {\n\nvoid target() {} }', nodes)[1]
        self.assertNotEqual(before["code_sha256"], after["code_sha256"])
        self.assertNotEqual(before["start_line"], after["start_line"])

    def test_budget_and_version_pinned_value_roundtrip(self):
        expression = "中文\"\\" * 10000
        original_node = node("large", "SetVariable", {"variableValue": {"code": expression}}, {"variableName": {"code": "value"}})
        root = snapshot(design([original_node]))
        service = object.__new__(GxpReadonlyService)
        service.repository = Repository(root)
        service.inspector = CanvasInspector()
        response = service.inspect_action("root", group="main", node_key="large", include_params=True, max_output_bytes=8192)
        self.assertLessEqual(payload_size(response), 8192)
        self.assertFalse(response["response_complete"])
        self.assertEqual("root-design", response["design"]["design_id"])
        chunks = []
        arguments = dict(identifier="root", group="main", node_key="large", value_path="/paramsValue/inputParams/variableValue/code", value_limit=2048)
        while arguments:
            page = service.inspect_action(**arguments)
            self.assertLessEqual(payload_size(page), 8192)
            chunks.append(page["value_page"]["text"])
            arguments = page["next_read"]
        self.assertEqual(expression, "".join(chunks))
        self.assertTrue(all(read[1].get("design_id") == "root-design" for read in service.repository.reads[2:]))

    def test_value_scope_rejects_unsafe_or_unpinned_reads(self):
        raw = node("value", "SetVariable")
        for pointer in ("/other", "/paramsValueExtra", "/paramsValue/../../secret"):
            with self.assertRaises(ValueError):
                node_value_page(raw, pointer, 0, 30)
        service = object.__new__(GxpReadonlyService)
        service.repository = Repository(snapshot(design([raw])))
        service.inspector = CanvasInspector()
        with self.assertRaises(ValueError):
            service.inspect_action("root", group="main", node_key="value", value_path="/paramsValue", value_offset=1)

    def test_small_payload_is_unchanged(self):
        result = {"nodes": [], "structure_status": "valid"}
        self.assertIs(result, canvas_payload(result, 8192, identifier="root", tool="inspect_action"))

    def test_ambiguous_identity_respects_budget(self):
        service = object.__new__(GxpReadonlyService)
        service.repository = Repository(snapshot(design([])))
        service.repository.resolve_action = lambda identifier: [{"ref_id": str(index), "name": "候选" * 4000} for index in range(40)]
        for method in (service.inspect_action, service.inspect_control_flow):
            result = method("ambiguous", max_output_bytes=8192)
            self.assertLessEqual(payload_size(result), 8192)
            self.assertEqual("ambiguous", result["resolution_status"])
            self.assertFalse(result["response_complete"])

    def test_two_calls_preserve_bindings_and_report_missing_argument(self):
        calls = [node("first", "CallAction", {"actionName": {"value": "child", "label": "same"}, "input": {"paramName": "records", "code": "firstRows"}}), node("second", "CallAction", {"actionName": {"value": "child", "label": "same"}})]
        data = design(calls)
        data["actionData"].append({"key": "child", "title": "same", "inputParams": [{"name": "records"}], "data": [node("define", "SetVariable", {"variableValue": {"code": "records"}}, {"variableName": {"code": "result"}})]})
        root = snapshot(data)
        result = expand_calls(Repository(root), CanvasInspector(), root, group="main", node_key=None, version="published", at_time=None)
        self.assertEqual(2, len([edge for edge in result["edges"] if edge["type"] == "calls"]))
        self.assertTrue(any(edge["type"] == "argument_to_parameter" for edge in result["edges"]))
        self.assertTrue(any(item["reason"] == "missing_arguments_candidate" and item["via"].endswith("second") for item in result["unresolved"]))
        self.assertFalse(result["runtime_verified"])

    def test_recursive_and_dynamic_calls_are_unresolved(self):
        data = design([node("cycle", "CallAction", {"actionName": {"value": "main"}}), node("dynamic", "CallAction", {"actionName": {"value": 'row["target"]'}})])
        root = snapshot(data)
        result = expand_calls(Repository(root), CanvasInspector(), root, group="main", node_key=None, version="published", at_time=None)
        reasons = {item["reason"] for item in result["unresolved"]}
        self.assertTrue({"recursive_call", "callee_group_unresolved"} <= reasons)

    def test_historical_public_calls_keep_version_and_time(self):
        root = snapshot(design([node("call", "CallPublicAction", {"actionName": {"code": "child"}})]))
        child = snapshot(design([]), "child")
        repo = Repository(root, {"child": child})
        result = expand_calls(repo, CanvasInspector(), root, group="main", node_key=None, version="published", at_time="2026-09-01", max_actions=2)
        self.assertEqual("2026-09-01", repo.reads[0][1]["at_time"])
        self.assertEqual("published", repo.reads[0][1]["version"])
        self.assertEqual(2, len(result["designs"]))
        root["version"] = "draft"
        with self.assertRaises(ValueError):
            expand_calls(repo, CanvasInspector(), root, group="main", node_key=None, version="draft", at_time="2026-09-01")

    def test_call_flow_limits(self):
        data = design([node("call", "CallPublicAction", {"actionName": {"code": "child"}})])
        root = snapshot(data)
        repo = Repository(root)
        result = expand_calls(repo, CanvasInspector(), root, group="main", node_key=None, version="published", at_time=None, max_actions=1)
        self.assertIn("actions", result["limits_reached"])
        self.assertEqual([], repo.reads)

    def test_call_range_and_optional_return_contracts(self):
        data = design([node("one", "CallAction", {"actionName": {"value": "child"}}, {"value": {"code": "answer", "paramName": "value"}}), node("outside", "CallAction", {"actionName": {"value": "missing"}})])
        data["actionData"].append({"key": "child", "title": "child", "inputParams": [{"name": "optional", "default": ""}], "outputParams": [{"name": "value"}], "data": [node("return", "ExitAction", {"returnValue": {"code": "optional"}})]})
        root = snapshot(data)
        result = expand_calls(Repository(root), CanvasInspector(), root, group="main", node_key=None, version="published", at_time=None, start=0, end=0)
        self.assertFalse(result["unresolved"])
        self.assertTrue({"returns", "return_to_caller"} <= {edge["type"] for edge in result["edges"]})
        self.assertFalse(any(item.get("node_key") == "outside" for item in result["nodes"]))


class KnowledgeCatalogTests(unittest.TestCase):
    setUp = test_cpm_snapshot.CpmSnapshotTests.setUp
    tearDown = test_cpm_snapshot.CpmSnapshotTests.tearDown
    def test_variable_alias_uses_actual_files(self):
        folder = self.snapshot / "skills/cpm-platform/references/elements/DataProcessing"
        folder.mkdir(parents=True)
        (folder / "SetVariable.md").write_text("# define", encoding="utf-8")
        (folder / "SetVariableValue.md").write_text("# assign", encoding="utf-8")
        result = get_cpm_knowledge("catalog", "main", query="全局数组声明", limit=1)
        self.assertTrue(result["ok"])
        self.assertEqual(2, result["matched_count"])
        self.assertEqual(1, len(result["entries"]))
        self.assertTrue(result["truncated"])
        entry = result["entries"][0]
        self.assertTrue(get_cpm_knowledge(**entry["next_call"])["ok"])
