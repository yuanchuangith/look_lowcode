from __future__ import annotations

import hashlib
import json
import re
from typing import Any


def _compact(value: Any) -> str:
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _parameter(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    for key in ("code", "label", "value"):
        candidate = value.get(key)
        if candidate not in (None, ""):
            return _compact(candidate)
    return ""


def _model_name(input_params: dict[str, Any]) -> str:
    model = input_params.get("modelName", {})
    if isinstance(model, dict):
        return str(model.get("modelName", "") or model.get("value", ""))
    return str(model or "")


def condition_summary(condition: Any) -> str:
    if not isinstance(condition, dict):
        return ""
    logic = str(condition.get("Logic", "") or "AND").upper()
    parts: list[str] = []
    filters = condition.get("Filters", []) or []
    for item in filters if isinstance(filters, list) else []:
        if not isinstance(item, dict):
            continue
        nested = condition_summary(item)
        if nested:
            parts.append(nested)
            continue
        left = _parameter(item.get("target")) or str(item.get("Field", ""))
        operator = str(item.get("equalTo", "") or item.get("Operator", ""))
        right = (
            _parameter(item.get("ParamInput"))
            or _parameter(item.get("source"))
            or _parameter(item.get("valueTarget"))
        )
        if not right and item.get("value") not in (None, ""):
            right = str(item.get("value"))
        expression = " ".join(part for part in (left, operator, right) if part)
        if expression:
            parts.append(expression)
    if not parts:
        return ""
    joined = f" {logic} ".join(parts)
    return f"({joined})" if len(parts) > 1 else joined


def _where_filters(input_params: dict[str, Any]) -> list[dict[str, Any]]:
    select_config = input_params.get("selectDataConfig", {}) or {}
    where = (
        select_config.get("whereConditions")
        or input_params.get("whereConditions")
        or {}
    )
    result: list[dict[str, Any]] = []

    def visit(condition: Any, logic_path: list[str]) -> None:
        if not isinstance(condition, dict):
            return
        logic = str(condition.get("Logic", "") or "AND").upper()
        filters = condition.get("Filters", []) or []
        for item in filters if isinstance(filters, list) else []:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("Filters"), list):
                visit(item, [*logic_path, logic])
                continue
            field = str(item.get("Field", ""))
            if not field:
                continue
            result.append(
                {
                    "field": field,
                    "operator": str(item.get("Operator", "")),
                    "expression": _parameter(item.get("ParamInput"))
                    or str(item.get("value", "")),
                    "data_type": str(item.get("type", "")),
                    "logic_path": [*logic_path, logic],
                    "source_path": "paramsValue.inputParams.*whereConditions.Filters",
                }
            )

    visit(where, [])
    return result


def _contains_identifier(value: Any, identifier: str) -> bool:
    if not identifier:
        return False
    return bool(
        re.search(
            rf"(?<![A-Za-z0-9_]){re.escape(identifier)}(?![A-Za-z0-9_])",
            str(value or ""),
            re.IGNORECASE,
        )
    )


def node_facts(node: dict[str, Any]) -> dict[str, Any]:
    params = node.get("paramsValue", {}) or {}
    input_params = params.get("inputParams", {}) or {}
    output_params = params.get("outputParams", {}) or {}
    facts: dict[str, Any] = {}
    model = _model_name(input_params)
    if model:
        facts["model_or_table"] = model
    element_key = str(node.get("elementKey", ""))
    if element_key == "SetVariable":
        facts["defined_variable"] = _parameter(output_params.get("variableName"))
        facts["defined_variable_type"] = str(
            (output_params.get("variableName") or {}).get("dataType", "")
        )
        facts["variable_value"] = _parameter(input_params.get("variableValue"))
    elif element_key == "SetVariableValue":
        facts["assignment_target"] = _parameter(input_params.get("variableName"))
        facts["assignment_target_type"] = str(
            (input_params.get("variableName") or {}).get("dataType", "")
        )
        facts["assignment_value"] = _parameter(input_params.get("attributeValue"))
    elif element_key in {"ForEachArray", "ForEachDynamicArray"}:
        facts["loop_source"] = _parameter(input_params.get("list"))
        facts["loop_item"] = _parameter(output_params.get("item"))
    condition = condition_summary(input_params.get("condition", {}))
    if condition:
        facts["condition"] = condition
    filters = _where_filters(input_params)
    if filters:
        facts["filters"] = filters
    mapping_name = "params" if input_params.get("params") is not None else "updateParams"
    mappings = input_params.get(mapping_name) or []
    if isinstance(mappings, list):
        mapped = []
        for mapping in mappings:
            if not isinstance(mapping, dict) or not mapping.get("attribute"):
                continue
            mapped.append(
                {
                    "field": str(mapping.get("attribute")),
                    "expression": _parameter(mapping.get("name")),
                    "data_type": str(
                        (mapping.get("modelAttribute") or {}).get("DataType", "")
                        or mapping.get("dataType", "")
                    ),
                    "map_type": str(
                        (mapping.get("modelAttribute") or {}).get("MapType", "")
                    ),
                    "source_path": f"paramsValue.inputParams.{mapping_name}",
                }
            )
        if mapped:
            facts["field_mappings"] = mapped
    outputs = []
    output_parameters = []
    if isinstance(output_params, dict):
        for output_key, output in output_params.items():
            value = _parameter(output)
            if value:
                outputs.append(value)
                output_parameters.append(
                    {
                        "name": value,
                        "data_type": str((output or {}).get("dataType", "")),
                        "source_path": f"paramsValue.outputParams.{output_key}",
                    }
                )
    if outputs:
        facts["output_variables"] = list(dict.fromkeys(outputs))
        facts["output_parameters"] = output_parameters
    action_name = input_params.get("actionName", {})
    if isinstance(action_name, dict) and any(action_name.get(k) for k in ("code", "id", "name", "label")):
        facts["called_action"] = {
            "code": str(action_name.get("code", "")),
            "id": str(action_name.get("id", "")),
            "name": str(action_name.get("name", "") or action_name.get("label", "")),
        }
        call_params = []
        for value in input_params.values():
            if isinstance(value, dict) and value.get("paramName"):
                call_params.append(
                    {
                        "name": str(value.get("paramName")),
                        "expression": _parameter(value),
                        "data_type": str(value.get("dataType", "")),
                        "source_path": "paramsValue.inputParams",
                    }
                )
        if call_params:
            facts["call_parameters"] = call_params
    return {key: value for key, value in facts.items() if value not in (None, "", [], {})}


def _node_ref(index: int, node: dict[str, Any]) -> dict[str, Any]:
    return {
        "canvas_line": index + 1,
        "internal_index": index,
        "node_key": str(node.get("key", "")),
        "node_name": str(node.get("title", "")),
        "node_type": str(node.get("elementKey", "")),
    }


def _component_identity(node: dict[str, Any]) -> dict[str, str]:
    params = node.get("paramsValue", {}) or {}
    input_params = params.get("inputParams", {}) or {}
    name = input_params.get("name", {}) or {}
    if not isinstance(name, dict):
        name = {"value": name}
    return {
        "component_key": _compact(name.get("value") or name.get("code")),
        "label": _compact(name.get("label")),
        "component_type": _compact(
            name.get("componentType") or input_params.get("componentType")
        ),
        "model_key": _compact(name.get("modelkey") or name.get("modelKey")),
    }


def _execution_stage(group_title: str) -> tuple[int, str]:
    title = (group_title or "").lower()
    if any(term in title for term in ("变更", "变化", "change", "onchange")):
        return 40, "field_change"
    if any(term in title for term in ("选择事件", "点击事件", "component event")):
        return 50, "component_event"
    if any(term in title for term in ("事件绑定", "event binding")):
        return 30, "event_binding"
    if any(term in title for term in ("默认值", "default")):
        return 20, "default_value"
    if any(term in title for term in ("主动作", "初始化", "initial")):
        return 10, "initialization"
    return 90, "other"


class CanvasInspector:
    def inspect(
        self,
        data: dict[str, Any] | str,
        *,
        group: str | None = None,
        terms: list[str] | None = None,
        node_key: str | None = None,
        start: int | None = None,
        end: int | None = None,
        include_params: bool = False,
    ) -> list[dict[str, Any]]:
        if isinstance(data, str):
            data = json.loads(data)
        terms = [term.lower() for term in (terms or []) if term]
        result = []
        for action_group in data.get("actionData", []) or []:
            group_title = str(action_group.get("title", ""))
            group_key = str(action_group.get("key", ""))
            if group and group.lower() not in f"{group_title} {group_key}".lower():
                continue
            nodes = action_group.get("data", []) or []
            locations = {
                str(node.get("key")): (index, node)
                for index, node in enumerate(nodes)
                if node.get("key")
            }
            for index, node in enumerate(nodes):
                if start is not None and index < start:
                    continue
                if end is not None and index > end:
                    continue
                if node_key and str(node.get("key")) != node_key:
                    continue
                if terms:
                    blob = json.dumps(node, ensure_ascii=False).lower()
                    if not any(term in blob for term in terms):
                        continue
                parents = []
                for parent_key in node.get("depth", []) or []:
                    location = locations.get(str(parent_key))
                    parents.append(
                        _node_ref(*location)
                        if location
                        else {"node_key": str(parent_key), "unresolved": True}
                    )
                item = {
                    "action_group": group_title,
                    "group_key": group_key,
                    **_node_ref(index, node),
                    "description": _compact(node.get("description")),
                    "parent_path": parents,
                    "previous_node": _node_ref(index - 1, nodes[index - 1]) if index else None,
                    "next_node": _node_ref(index + 1, nodes[index + 1])
                    if index + 1 < len(nodes)
                    else None,
                    "facts": node_facts(node),
                }
                if include_params:
                    item["paramsValue"] = node.get("paramsValue", {})
                result.append(item)
        return result

    def inspect_component_filters(
        self,
        data: dict[str, Any] | str,
        component: str,
        *,
        include_params: bool = False,
    ) -> dict[str, Any]:
        if isinstance(data, str):
            data = json.loads(data)
        component = (component or "").strip()
        if not component or len(component) > 200:
            raise ValueError("Component identifier must be 1-200 characters")

        all_writers: list[dict[str, Any]] = []
        for group_index, action_group in enumerate(data.get("actionData", []) or []):
            group_title = str(action_group.get("title", ""))
            group_key = str(action_group.get("key", ""))
            stage_order, stage = _execution_stage(group_title)
            nodes = action_group.get("data", []) or []
            locations = {
                str(node.get("key")): (index, node)
                for index, node in enumerate(nodes)
                if node.get("key")
            }
            for index, node in enumerate(nodes):
                if str(node.get("elementKey", "")) != "DataFilter":
                    continue
                identity = _component_identity(node)
                parents = []
                for parent_key in node.get("depth", []) or []:
                    location = locations.get(str(parent_key))
                    if not location:
                        parents.append({"node_key": str(parent_key), "unresolved": True})
                        continue
                    parent_index, parent_node = location
                    parent_type = str(parent_node.get("elementKey", ""))
                    parent_facts = node_facts(parent_node)
                    parent = _node_ref(parent_index, parent_node)
                    parent["branch"] = {
                        "IfCondition": "if",
                        "ElseIfCondition": "else_if",
                        "Else": "else",
                    }.get(parent_type, "parent")
                    if parent_facts.get("condition"):
                        parent["condition"] = parent_facts["condition"]
                    parents.append(parent)
                input_params = ((node.get("paramsValue") or {}).get("inputParams") or {})
                where = (
                    (input_params.get("selectDataConfig") or {}).get("whereConditions")
                    or input_params.get("whereConditions")
                    or {}
                )
                writer = {
                    "action_group": group_title,
                    "group_key": group_key,
                    "group_index": group_index,
                    "execution_stage": stage,
                    "stage_order": stage_order,
                    **_node_ref(index, node),
                    "component": identity,
                    "filter_facts": {
                        "logic": str(where.get("Logic", "") or "AND").upper()
                        if isinstance(where, dict)
                        else "",
                        "summary": condition_summary(where),
                        "filters": _where_filters(input_params),
                    },
                    "parent_conditions": parents,
                    "previous_node": _node_ref(index - 1, nodes[index - 1])
                    if index
                    else None,
                    "next_node": _node_ref(index + 1, nodes[index + 1])
                    if index + 1 < len(nodes)
                    else None,
                }
                if include_params:
                    writer["paramsValue"] = node.get("paramsValue", {})
                all_writers.append(writer)

        query = component.lower()
        exact_by_key = [
            item
            for item in all_writers
            if query == item["component"]["component_key"].lower()
        ]
        exact_by_model = [
            item
            for item in all_writers
            if query == item["component"]["model_key"].lower()
        ]
        exact_by_label = [
            item
            for item in all_writers
            if query == item["component"]["label"].lower()
        ]
        if exact_by_key:
            matching = exact_by_key
            match_mode = "exact_component_key"
        elif exact_by_model:
            matching = exact_by_model
            match_mode = "exact_model_key"
        elif exact_by_label:
            matching = exact_by_label
            match_mode = "exact_label"
        else:
            matching = [
                item
                for item in all_writers
                if any(
                    query in value.lower()
                    for value in item["component"].values()
                    if value
                )
            ]
            match_mode = "component_contains" if matching else "not_found"

        candidate_map: dict[tuple[str, str, str], dict[str, Any]] = {}
        for item in matching:
            identity = item["component"]
            signature = (
                identity["component_key"],
                identity["model_key"],
                identity["label"],
            )
            candidate = candidate_map.setdefault(
                signature, {**identity, "writer_count": 0}
            )
            candidate["writer_count"] += 1
        candidates = list(candidate_map.values())

        identity_field = {
            "exact_component_key": "component_key",
            "exact_model_key": "model_key",
        }.get(match_mode)
        if identity_field:
            identities = {
                item["component"][identity_field].lower() for item in matching
            }
        else:
            identities = {
                (
                    item["component"]["component_key"].lower(),
                    item["component"]["model_key"].lower(),
                )
                for item in matching
            }
        ambiguous = len(identities) > 1
        if ambiguous:
            return {
                "component_query": component,
                "resolution_status": "ambiguous",
                "match_mode": match_mode,
                "component_candidates": candidates,
                "writer_count": 0,
                "writers": [],
                "next_step": "Retry with one exact component key or model key.",
            }

        matching.sort(
            key=lambda item: (
                item["stage_order"],
                item["group_index"],
                item["internal_index"],
            )
        )
        for execution_order, item in enumerate(matching, start=1):
            item["execution_order"] = execution_order
            item["may_overwrite_earlier_filter"] = execution_order > 1
        stages = list(dict.fromkeys(item["execution_stage"] for item in matching))
        return {
            "component_query": component,
            "resolution_status": "unique" if matching else "not_found",
            "match_mode": match_mode,
            "component": matching[0]["component"] if matching else None,
            "component_candidates": candidates,
            "writer_count": len(matching),
            "execution_stages": stages,
            "writers": matching,
            "overwrite_warning": (
                "A later DataFilter writer can replace an earlier filter when its branch/event executes; "
                "evaluate every writer and parent condition before deciding the final dropdown scope."
                if len(matching) > 1
                else ""
            ),
        }

    @staticmethod
    def csharp_context(csharp: str, line: int, context: int = 3) -> dict[str, Any]:
        lines = (csharp or "").splitlines()
        if line < 1:
            raise ValueError("Generated C# line must be 1 or greater")
        if line > len(lines):
            return {"requested_line": line, "line_count": len(lines), "lines": []}
        radius = max(0, min(int(context), 20))
        start = max(1, line - radius)
        end = min(len(lines), line + radius)
        return {
            "requested_line": line,
            "line_count": len(lines),
            "lines": [CanvasInspector._csharp_line(lines[number - 1], number, line)
                      for number in range(start, end + 1)],
        }

    @staticmethod
    def _csharp_line(text: str, number: int, target: int) -> dict[str, Any]:
        max_length = 500
        item = {
            "line": number,
            "text": text if len(text) <= max_length else text[:max_length] + "...",
            "target": number == target,
        }
        if len(text) > max_length:
            item["text_truncated"] = True
            item["original_length"] = len(text)
        return item

    @staticmethod
    def search_csharp(
        csharp: str,
        terms: list[str],
        context: int = 2,
        max_matches: int = 20,
    ) -> list[dict[str, Any]]:
        return CanvasInspector.search_csharp_with_metadata(
            csharp, terms, context=context, max_matches=max_matches
        )["matches"]

    @staticmethod
    def search_csharp_with_metadata(
        csharp: str,
        terms: list[str],
        context: int = 2,
        max_matches: int = 20,
    ) -> dict[str, Any]:
        normalized: list[tuple[str, str]] = []
        seen: set[str] = set()
        for term in terms:
            original = str(term or "").strip()
            lowered = original.lower()
            if not original or lowered in seen:
                continue
            seen.add(lowered)
            normalized.append((original, lowered))
        lines = (csharp or "").splitlines()
        matches = []
        matched_line_count = 0
        safe_limit = max(1, min(int(max_matches), 20))
        for index, line in enumerate(lines):
            matched_terms = [
                original
                for original, lowered in normalized
                if lowered in line.lower()
            ]
            if not matched_terms:
                continue
            matched_line_count += 1
            if len(matches) < safe_limit:
                item = CanvasInspector.csharp_context(csharp, index + 1, context)
                item["matched_terms"] = matched_terms
                matches.append(item)
        return {
            "matches": matches,
            "matched_line_count": matched_line_count,
            "matches_truncated": matched_line_count > len(matches),
            "max_matches": safe_limit,
        }

    @staticmethod
    def focus_fields(nodes: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
        requested = {field.strip().lower() for field in fields if field and field.strip()}
        if not requested:
            return []
        evidence = []
        for node in nodes:
            facts = node.get("facts") or {}
            matches: dict[str, Any] = {}
            for fact_name in ("field_mappings", "filters", "call_parameters"):
                fact_items = facts.get(fact_name) or []
                selected = []
                for item in fact_items:
                    identity = str(
                        item.get("field", item.get("name", ""))
                    ).strip().lower()
                    if identity in requested:
                        selected.append(item)
                if selected:
                    matches[fact_name] = selected
                expression_matches = [
                    item
                    for item in fact_items
                    if any(
                        _contains_identifier(item.get("expression"), field)
                        for field in requested
                    )
                ]
                if expression_matches:
                    matches[f"{fact_name}_expression_references"] = expression_matches
            for fact_name in (
                "defined_variable",
                "assignment_target",
                "output_variables",
            ):
                value = facts.get(fact_name)
                values = value if isinstance(value, list) else [value]
                if any(str(item).strip().lower() in requested for item in values if item):
                    matches[fact_name] = value
            if matches:
                evidence.append(
                    {
                        "action_group": node.get("action_group"),
                        "group_key": node.get("group_key"),
                        "canvas_line": node.get("canvas_line"),
                        "internal_index": node.get("internal_index"),
                        "node_key": node.get("node_key"),
                        "node_name": node.get("node_name"),
                        "node_type": node.get("node_type"),
                        "matches": matches,
                    }
                )
        return evidence

    @staticmethod
    def node_csharp_terms(
        nodes: list[dict[str, Any]], focus_fields: list[str] | None = None
    ) -> list[str]:
        requested = {
            field.strip().lower()
            for field in (focus_fields or [])
            if field and field.strip()
        }
        terms: list[str] = []
        for node in nodes:
            facts = node.get("facts") or {}
            field_items = [
                *(facts.get("field_mappings") or []),
                *(facts.get("filters") or []),
                *(facts.get("call_parameters") or []),
            ]
            for item in field_items:
                field = str(item.get("field", item.get("name", "")))
                expression = str(item.get("expression", ""))
                matches_focus = not requested or field.lower() in requested or any(
                    _contains_identifier(expression, requested_field)
                    for requested_field in requested
                )
                if not matches_focus:
                    continue
                if field:
                    terms.extend((field, f'Add("{field}"'))
            for requested_field in requested:
                if any(
                    _contains_identifier(item.get("expression"), requested_field)
                    or str(item.get("field", item.get("name", ""))).lower()
                    == requested_field
                    for item in field_items
                ):
                    terms.append(requested_field)
            called = facts.get("called_action") or {}
            if not requested:
                terms.extend(
                    str(called.get(key, ""))
                    for key in ("id", "code")
                    if called.get(key)
                )
            model = str(facts.get("model_or_table", ""))
            if model and not requested:
                terms.append(model)
            for value_name in ("variable_value", "assignment_value"):
                value = str(facts.get(value_name, ""))
                for literal in re.findall(r'"([^"\\]{4,120})"', value):
                    terms.append(literal)
        return list(dict.fromkeys(term for term in terms if term))[:20]

    @staticmethod
    def generated_csharp_node_evidence(
        nodes: list[dict[str, Any]],
        csharp: str,
        *,
        focus_fields: list[str] | None = None,
        context: int = 2,
        max_nodes: int = 20,
    ) -> list[dict[str, Any]]:
        evidence = []
        for node in nodes[: max(1, min(int(max_nodes), 50))]:
            terms = CanvasInspector.node_csharp_terms([node], focus_fields)
            matches = CanvasInspector.search_csharp(
                csharp, terms, context=context, max_matches=10
            )
            if not matches:
                continue
            evidence.append(
                {
                    "action_group": node.get("action_group"),
                    "group_key": node.get("group_key"),
                    "canvas_line": node.get("canvas_line"),
                    "internal_index": node.get("internal_index"),
                    "node_key": node.get("node_key"),
                    "node_name": node.get("node_name"),
                    "node_type": node.get("node_type"),
                    "search_terms": terms,
                    "matches": matches,
                    "evidence_kind": "generated_csharp_term_match_candidate",
                    "exact_source_map": False,
                }
            )
        return evidence

    @staticmethod
    def compare(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        def flatten(value: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
            result = {}
            for group in value.get("actionData", []) or []:
                group_key = str(group.get("key", ""))
                group_title = str(group.get("title", ""))
                for index, node in enumerate(group.get("data", []) or []):
                    result[(group_key, str(node.get("key", "")))] = {
                        "group_title": group_title,
                        "index": index,
                        "node": node,
                    }
            return result

        def locator(item: dict[str, Any]) -> dict[str, Any]:
            node = item["node"]
            return {
                "group_key": str(node.get("groupKey", "")) or None,
                "group_title": item["group_title"],
                "canvas_line": item["index"] + 1,
                "internal_index": item["index"],
                "node_key": str(node.get("key", "")),
                "node_name": str(node.get("title", "")),
                "node_type": str(node.get("elementKey", "")),
            }

        left_nodes = flatten(left)
        right_nodes = flatten(right)
        added = sorted(set(right_nodes) - set(left_nodes))
        removed = sorted(set(left_nodes) - set(right_nodes))
        changed = []
        for key in sorted(set(left_nodes) & set(right_nodes)):
            left_node = left_nodes[key]["node"]
            right_node = right_nodes[key]["node"]
            left_json = json.dumps(left_node, ensure_ascii=False, sort_keys=True)
            right_json = json.dumps(right_node, ensure_ascii=False, sort_keys=True)
            if left_json != right_json:
                relevant_sections = (
                    "title",
                    "elementKey",
                    "depth",
                    "paramsValue",
                    "description",
                )
                changed.append(
                    {
                        "group_key": key[0],
                        "group_title": right_nodes[key]["group_title"]
                        or left_nodes[key]["group_title"],
                        "node_key": key[1],
                        "published_locator": {
                            **locator(left_nodes[key]),
                            "group_key": key[0],
                        },
                        "draft_locator": {
                            **locator(right_nodes[key]),
                            "group_key": key[0],
                        },
                        "changed_sections": [
                            section
                            for section in relevant_sections
                            if left_node.get(section) != right_node.get(section)
                        ],
                    }
                )
        left_raw = json.dumps(left, ensure_ascii=False, sort_keys=True)
        right_raw = json.dumps(right, ensure_ascii=False, sort_keys=True)
        return {
            "same": left_raw == right_raw,
            "left_sha256": hashlib.sha256(left_raw.encode()).hexdigest(),
            "right_sha256": hashlib.sha256(right_raw.encode()).hexdigest(),
            "added": [
                {
                    **locator(right_nodes[item]),
                    "group_key": item[0],
                }
                for item in added
            ],
            "removed": [
                {
                    **locator(left_nodes[item]),
                    "group_key": item[0],
                }
                for item in removed
            ],
            "changed": changed,
        }
