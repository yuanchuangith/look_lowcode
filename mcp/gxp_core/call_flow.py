from __future__ import annotations

import json
from typing import Any

from .canvas_references import expression_references, select_groups


def expand_calls(repository, inspector, root_design: dict[str, Any], *, group: str | None, node_key: str | None, version: str, at_time: str | None, max_depth: int = 2, max_actions: int = 8, max_nodes: int = 120, max_edges: int = 240, start: int | None = None, end: int | None = None) -> dict[str, Any]:
    for value, maximum in ((max_depth, 5), (max_actions, 8), (max_nodes, 300), (max_edges, 600)):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
            raise ValueError("call-flow limits must be positive and within depth=5/actions=8/nodes=300/edges=600")
    nodes: dict[str, Any] = {}
    edges = []
    unresolved = []
    designs = {}
    loaded = {}
    visited = set()
    limits = set()

    def data(design):
        value = design["data_json"]
        return json.loads(value) if isinstance(value, str) else value

    def identity(design):
        metadata = design.get("metadata") or {}
        return str(metadata.get("ref_id") or design.get("ref_id") or "root") + "@" + str(design["design_id"])

    def add_node(key, kind, **values):
        if key not in nodes and len(nodes) >= max_nodes:
            limits.add("nodes")
            return False
        nodes.setdefault(key, {"id": key, "kind": kind, **values})
        return True

    def add_edge(source, target, kind, via, branch):
        if source not in nodes or target not in nodes:
            return
        if len(edges) >= max_edges:
            limits.add("edges")
            return
        edge = {"source": source, "target": target, "type": kind, "via": via, "branch_path": branch, "evidence": "static_relation_not_runtime_path"}
        if edge not in edges:
            edges.append(edge)

    def contract(action_group, name):
        values = action_group.get(name)
        if isinstance(values, list):
            return {str(item.get("name") or item.get("paramName") or ""): item.get("required", True) and not any(key in item for key in ("default", "defaultValue")) for item in values if isinstance(item, dict)}
        if isinstance(values, dict):
            return {key: not isinstance(value, dict) or value.get("required", True) and not any(field in value for field in ("default", "defaultValue")) for key, value in values.items()}
        return None

    def visit(design, selected_group, depth, ancestry, only_node=None):
        design_key = identity(design)
        scope = design_key + "/" + str(selected_group["key"])
        if scope in ancestry:
            unresolved.append({"scope": scope, "reason": "recursive_call"})
            return
        if scope in visited:
            return
        visited.add(scope)
        designs[design_key] = {key: design.get(key) for key in ("design_id", "version", "data_sha256", "csharp_sha256", "modified_time")}
        designs[design_key]["ref_id"] = (design.get("metadata") or {}).get("ref_id")
        inspected = inspector.inspect(data(design), group=str(selected_group["key"]))
        for item in inspected:
            if depth == 0 and (start is not None and item["internal_index"] < start or end is not None and item["internal_index"] > end):
                continue
            if only_node and item["node_key"] != only_node:
                continue
            if item.get("control_flow", {}).get("structure_status") != "valid":
                unresolved.append({"scope": scope, "reason": "invalid_control_structure"})
                return
            location = scope + "/node/" + item["node_key"]
            if not add_node(location, "canvas", group_key=item["group_key"], node_key=item["node_key"], canvas_line=item["canvas_line"], design=design_key):
                return
            branch = item.get("control_flow", {}).get("enclosing_path", [])
            facts = item["facts"]
            for reference in facts.get("references", []):
                variable = scope + "/variable/" + reference["symbol"]
                if not add_node(variable, "variable", name=reference["symbol"], scope=scope):
                    continue
                if reference["role"] in {"define", "write"}:
                    add_edge(location, variable, "defines", location, branch)
                else:
                    add_edge(variable, location, reference["role"], location, branch)
            for mapping in facts.get("field_mappings", []):
                target = scope + "/field/" + str(facts.get("model_or_table", "")) + "/" + mapping["field"]
                add_node(target, "field", name=mapping["field"], model=facts.get("model_or_table"))
                add_edge(location, target, "writes_field", location, branch)
            outputs = contract(selected_group, "outputParams")
            raw = (selected_group.get("data") or [])[item["internal_index"]]
            return_value = ((raw.get("paramsValue") or {}).get("inputParams") or {}).get("returnValue")
            if isinstance(return_value, dict) and outputs:
                return_name = return_value.get("paramName") or (next(iter(outputs)) if len(outputs) == 1 else None)
                if return_name in outputs:
                    returned = scope + "/return/" + return_name
                    add_node(returned, "return", name=return_name, scope=scope)
                    add_edge(location, returned, "returns", location, branch)
            if facts.get("loop_source") and facts.get("loop_item"):
                target = scope + "/variable/" + facts["loop_item"]
                add_node(target, "variable", name=facts["loop_item"], scope=scope)
                for reference in expression_references(facts["loop_source"], "loop_source", "list"):
                    source = scope + "/variable/" + reference["symbol"]
                    add_node(source, "variable", name=reference["symbol"], scope=scope)
                    add_edge(source, target, "query_result_to_item", location, branch)
            called = facts.get("called_action")
            if not called:
                continue
            target_design = design
            if called["kind"] == "public":
                target_identifier = called.get("target_action_identifier")
                matches = repository.resolve_action(target_identifier) if target_identifier else []
                if len(matches) != 1:
                    unresolved.append({"via": location, "reason": "ambiguous_or_dynamic_public_target"})
                    continue
                ref_id = str(matches[0]["ref_id"])
                if ref_id not in loaded:
                    if depth >= max_depth or len(loaded) >= max_actions:
                        limits.add("depth" if depth >= max_depth else "actions")
                        continue
                    try:
                        loaded[ref_id] = repository.load_design(ref_id, version=version, at_time=at_time, include_deleted=bool(at_time))
                    except Exception:
                        unresolved.append({"via": location, "reason": "callee_design_unavailable"})
                        continue
                target_design = loaded[ref_id]
                target_groups, resolution = select_groups(data(target_design).get("actionData", []), "main")
            else:
                target_key = called.get("target_group_key")
                target_groups = [candidate for candidate in data(design).get("actionData", []) if target_key and candidate.get("key") == target_key]
            if len(target_groups) != 1:
                unresolved.append({"via": location, "reason": "callee_group_unresolved"})
                continue
            target_group = target_groups[0]
            target_scope = identity(target_design) + "/" + str(target_group["key"])
            add_node(target_scope, "action_group", group_key=target_group["key"], design=identity(target_design))
            add_edge(location, target_scope, "calls", location, branch)
            declared = contract(target_group, "inputParams")
            arguments = facts.get("call_parameters", [])
            if declared is None:
                unresolved.append({"via": location, "reason": "parameter_declarations_unavailable"})
            else:
                supplied = {argument["name"] for argument in arguments}
                missing = [name for name, required in declared.items() if name and required and name not in supplied]
                if missing:
                    unresolved.append({"via": location, "reason": "missing_arguments_candidate", "parameters": missing})
            for argument in arguments:
                target = target_scope + "/variable/" + argument["name"]
                add_node(target, "parameter", name=argument["name"], scope=target_scope, declaration_verified=declared is not None and argument["name"] in declared)
                for reference in expression_references(argument["expression"], "argument", argument["source_path"]):
                    source = scope + "/variable/" + reference["symbol"]
                    add_node(source, "variable", name=reference["symbol"], scope=scope)
                    add_edge(source, target, "argument_to_parameter", location, branch)
            raw = (selected_group.get("data") or [])[item["internal_index"]]
            returns = contract(target_group, "outputParams")
            for key, output in ((raw.get("paramsValue") or {}).get("outputParams") or {}).items():
                if not isinstance(output, dict):
                    continue
                name = output.get("paramName") or key
                if returns is None or name not in returns:
                    unresolved.append({"via": location, "reason": "return_binding_unresolved", "parameter": name})
                    continue
                source = target_scope + "/return/" + name
                target = scope + "/variable/" + str(output.get("code") or output.get("value") or "")
                add_node(source, "return", name=name, scope=target_scope)
                add_node(target, "variable", scope=scope)
                add_edge(source, target, "return_to_caller", location, branch)
            if depth >= max_depth:
                limits.add("depth")
            elif "nodes" not in limits and "edges" not in limits:
                visit(target_design, target_group, depth + 1, ancestry | {scope})

    version = str(root_design.get("version") or version)
    if root_design.get("is_deleted") and not at_time and version == "published":
        at_time = str(root_design.get("created_time") or root_design.get("modified_time") or "") or None
        if not at_time:
            raise ValueError("historical root needs an explicit at_time for call expansion")
    if at_time and version != "published":
        raise ValueError("historical call expansion accepts published snapshots only")
    root_ref = str((root_design.get("metadata") or {}).get("ref_id") or "root")
    loaded[root_ref] = root_design
    root_groups, resolution = select_groups(data(root_design).get("actionData", []), group or "main")
    if len(root_groups) == 1:
        visit(root_design, root_groups[0], 0, set(), node_key)
    else:
        unresolved.append({"reason": "entry_group_required", "resolution": resolution})
    return {"schema_version": "2.0", "status": "partial" if unresolved or limits else "ok", "nodes": list(nodes.values()), "edges": edges, "designs": designs, "unresolved": unresolved[:40], "limits_reached": sorted(limits), "runtime_verified": False, "database_relation_verified": False}
