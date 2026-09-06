from __future__ import annotations

import json

from gxp_core.canvas import CanvasInspector
from gxp_core.diagnostics import DiagnosticEngine
from gxp_core.service import GxpReadonlyService


def node(key, element, inputs, outputs=None):
    return {
        "key": key, "title": key, "elementKey": element,
        "paramsValue": {"inputParams": inputs, "outputParams": outputs or {}},
    }


def design_for(nodes):
    return {"actionData": [{"key": "main", "title": "main", "data": nodes}]}


class FixtureRepository:
    def __init__(self, data):
        self.data = data

    def resolve_action(self, identifier):
        return [{"ref_id": "fixture-ref", "action_code": "fixture-action"}]

    def load_design(self, ref_id, **kwargs):
        return {
            "design_id": "fixture-design", "version": "published", "is_deleted": 0,
            "metadata": self.resolve_action(ref_id)[0], "data_json": self.data,
            "csharp_code": "",
        }

    def resolve_actions(self, tokens):
        return []

    def search_actions(self, query, **kwargs):
        return []

    def search_pages(self, query, **kwargs):
        return []

    def search_design_text(self, text, **kwargs):
        return []


def main():
    inspector = CanvasInspector()
    condition = node("condition", "IfCondition", {
        "condition": {"Logic": "And", "Filters": [{
            "target": {"code": "trainingType", "paramTypes": "inputParam"},
            "equalTo": "Equal", "value": {"code": '"initial"'},
        }]},
    })
    variable = node("variable", "SetVariable", {
        "variableType": "string", "variableValue": {"code": 'detail["file_ver_id"]'},
    }, {"variableName": {"code": "selectedVersion", "dataType": "string"}})
    data = design_for([condition, node("end", "IfEnd", {}), variable])
    nodes = inspector.inspect(data)
    result = {}
    for label, field in (("condition_lookup", "trainingType"), ("variable_read_lookup", "file_ver_id")):
        result[label] = {
            "focus_count": len(inspector.focus_fields(nodes, [field])),
            "text_count": len(inspector.inspect(data, terms=[field])),
        }
    calls = [node("call-" + target, "CallAction", {
        "actionName": {"value": target, "label": "Same label", "actionType": "csharp"},
    }) for target in ("group-a", "group-b")]
    result["local_call_identity"] = {
        "source_targets": ["group-a", "group-b"],
        "reported_targets": [entry["facts"]["called_action"] for entry in inspector.inspect(design_for(calls))],
    }
    alias_data = {"actionData": [
        {"key": "main", "title": "main", "data": [variable]},
        {"key": "main-copy", "title": "main copy", "data": [variable]},
    ]}
    result["exact_group_lookup"] = {
        "returned_groups": [entry["group_key"] for entry in inspector.inspect(alias_data, group="main")],
    }
    generated = '\n'.join([
        'void Other' + str(index) + '() { var wrong = detail["file_ver_id"]; }' for index in range(25)
    ] + ['void Wanted() { var selectedVersion = detail["file_ver_id"]; }'])
    evidence = inspector.generated_csharp_node_evidence([nodes[-1]], generated, context=0)
    result["node_csharp_lookup"] = {
        "expected_target_line": 26,
        "returned_lines": [match["requested_line"] for match in evidence[0]["matches"]],
        "exact_source_map": evidence[0]["exact_source_map"],
    }
    oversized = node("large", "SetVariable", {
        "variableType": "string", "variableValue": {"code": '"' + 'x' * 50000 + '"'},
    }, {"variableName": {"code": "payload", "dataType": "string"}})
    service = object.__new__(GxpReadonlyService)
    service.repository = FixtureRepository(design_for([oversized]))
    service.inspector = inspector
    response = service.inspect_action("fixture-action", node_key="large", include_params=True, max_nodes=1)
    result["one_node_response"] = {
        "serialized_bytes": len(json.dumps(response, ensure_ascii=False).encode("utf-8")),
        "nodes_truncated": response["nodes_truncated"],
        "too_broad_for_params": response["too_broad_for_params"],
    }
    engine = DiagnosticEngine(FixtureRepository(data), inspector)
    followup = engine.diagnose_codex_input("\u6539\u4e86\u4f60\u518d\u770b\u770b")
    result["context_free_followup"] = {
        "action_resolution_status": followup["action_resolution_status"],
        "next_tools": followup["next_tools"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
