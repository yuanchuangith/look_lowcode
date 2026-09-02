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


def _operand(value: Any, *, source_path: str, fallback: str = "") -> dict[str, Any]:
    """Preserve an expression operand without executing it."""
    if isinstance(value, dict):
        return {
            "kind": str(value.get("paramTypes", "") or "expression"),
            "code": str(value.get("code", "") or ""),
            "label": _compact(value.get("label")),
            "value": value.get("value"),
            "data_type": str(value.get("dataType", "") or value.get("type", "")),
            "object_attribute": str(value.get("objectAttribute", "") or ""),
            "source_path": source_path,
        }
    return {
        "kind": "field" if fallback else "literal",
        "code": fallback or str(value or ""),
        "label": fallback,
        "value": value if not fallback else fallback,
        "data_type": "",
        "object_attribute": "",
        "source_path": source_path,
    }


def condition_ast(condition: Any, *, source_path: str = "condition") -> dict[str, Any] | None:
    """Convert both canvas and database condition shapes to one recursive AST."""
    if not isinstance(condition, dict):
        return None
    nested_where = condition.get("whereConditions")
    if isinstance(nested_where, dict) and not isinstance(condition.get("Filters"), list):
        return condition_ast(nested_where, source_path=f"{source_path}.whereConditions")
    filters = condition.get("Filters")
    if not isinstance(filters, list):
        return None
    children: list[dict[str, Any]] = []
    for index, item in enumerate(filters):
        if not isinstance(item, dict):
            continue
        item_path = f"{source_path}.Filters[{index}]"
        if isinstance(item.get("Filters"), list):
            nested = condition_ast(item, source_path=item_path)
            if nested:
                children.append(nested)
            continue
        field = str(item.get("Field", "") or "")
        left_value = item.get("target") if item.get("target") is not None else field
        right_key = next(
            (
                key
                for key in ("value", "ParamInput", "source", "valueTarget")
                if item.get(key) is not None
            ),
            "value",
        )
        operator = str(item.get("equalTo", "") or item.get("Operator", ""))
        if not operator and not field and item.get("target") is None:
            continue
        left = _operand(
            left_value,
            source_path=f"{item_path}.{'target' if not field else 'Field'}",
            fallback=field,
        )
        right = _operand(item.get(right_key), source_path=f"{item_path}.{right_key}")
        children.append(
            {
                "type": "predicate",
                "left": left,
                "operator": operator,
                "right": right,
                "data_type": str(
                    item.get("type", "")
                    or left.get("data_type", "")
                    or right.get("data_type", "")
                ),
                "source_path": item_path,
            }
        )
    return {
        "type": "condition_group",
        "logic": str(condition.get("Logic", "") or "AND").upper(),
        "children": children,
        "source_path": source_path,
    }


def _operand_text(operand: dict[str, Any] | None) -> str:
    operand = operand or {}
    value = operand.get("code") or operand.get("label") or operand.get("value")
    return _compact(value)


def condition_ast_summary(ast: dict[str, Any] | None) -> str:
    if not ast:
        return ""
    if ast.get("type") == "predicate":
        return " ".join(
            part
            for part in (
                _operand_text(ast.get("left")),
                str(ast.get("operator", "")),
                _operand_text(ast.get("right")),
            )
            if part
        )
    parts = [condition_ast_summary(child) for child in ast.get("children", []) or []]
    parts = [part for part in parts if part]
    if not parts:
        return ""
    joined = f" {str(ast.get('logic', 'AND')).upper()} ".join(parts)
    return f"({joined})" if len(parts) > 1 else joined


def condition_summary(condition: Any) -> str:
    return condition_ast_summary(condition_ast(condition))


def _literal(text: Any) -> tuple[bool, Any]:
    if text is None:
        return True, None
    if isinstance(text, (bool, int, float)):
        return True, text
    value = str(text).strip()
    if not value:
        return False, None
    if (value.startswith("\"") and value.endswith("\"")) or (
        value.startswith("'") and value.endswith("'")
    ):
        return True, value[1:-1]
    if value.lower() == "null":
        return True, None
    if value.lower() in {"true", "false"}:
        return True, value.lower() == "true"
    if re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        return True, float(value) if "." in value else int(value)
    return False, None


def _resolve_operand(operand: dict[str, Any], inputs: dict[str, Any]) -> tuple[bool, Any, str]:
    candidates = []
    for key in ("code", "value", "label"):
        candidate = operand.get(key)
        if candidate not in (None, ""):
            candidates.append(str(candidate))
    for candidate in candidates:
        if candidate in inputs:
            return True, inputs[candidate], candidate
        simple = candidate.strip("()")
        if simple in inputs:
            return True, inputs[simple], simple
        tail = re.search(r"(?:\[['\"]([^'\"]+)['\"]\]|\.([A-Za-z_]\w*))$", simple)
        if tail:
            name = tail.group(1) or tail.group(2)
            if name in inputs:
                return True, inputs[name], name
    kind = str(operand.get("kind", "")).lower()
    if kind in {"custom", "literal"}:
        for candidate in candidates:
            resolved, value = _literal(candidate)
            if resolved:
                return True, value, "literal"
    return False, None, ""


def evaluate_condition_ast(
    ast: dict[str, Any] | None, inputs: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate supported, side-effect-free predicates with three-state logic."""
    if not ast:
        return {"result": "unknown", "unresolved_inputs": []}
    if ast.get("type") == "condition_group":
        evaluations = [evaluate_condition_ast(child, inputs) for child in ast.get("children", [])]
        values = [item["result"] for item in evaluations]
        logic = str(ast.get("logic", "AND")).upper()
        if not values:
            result = "unknown"
        elif logic == "OR":
            result = "true" if "true" in values else "false" if all(v == "false" for v in values) else "unknown"
        else:
            result = "false" if "false" in values else "true" if all(v == "true" for v in values) else "unknown"
        return {
            "result": result,
            "logic": logic,
            "children": evaluations,
            "unresolved_inputs": list(
                dict.fromkeys(
                    unresolved
                    for item in evaluations
                    for unresolved in item.get("unresolved_inputs", [])
                )
            ),
        }
    left_ok, left, left_source = _resolve_operand(ast.get("left") or {}, inputs)
    right_ok, right, right_source = _resolve_operand(ast.get("right") or {}, inputs)
    operator = str(ast.get("operator", ""))
    op = re.sub(r"[^a-z]", "", operator.lower())
    unary_null = op in {"equalnull", "isnull", "notequalnull", "isnotnull"}
    matched: bool | None = None
    if left_ok and (right_ok or unary_null):
        try:
            if op in {"equal", "equalto"}:
                matched = left == right
            elif op in {"notequal", "notequalto"}:
                matched = left != right
            elif op == "greaterthan":
                matched = left > right
            elif op == "greaterthanorequal":
                matched = left >= right
            elif op == "lessthan":
                matched = left < right
            elif op == "lessthanorequal":
                matched = left <= right
            elif op == "contains":
                matched = right in left
            elif op == "notcontains":
                matched = right not in left
            elif op in {"equalnull", "isnull"}:
                matched = left is None
            elif op in {"notequalnull", "isnotnull"}:
                matched = left is not None
        except (TypeError, ValueError):
            matched = None
    unresolved = []
    if not left_ok:
        unresolved.append(_operand_text(ast.get("left")) or "left_operand")
    if not right_ok and not unary_null:
        unresolved.append(_operand_text(ast.get("right")) or "right_operand")
    return {
        "result": "true" if matched is True else "false" if matched is False else "unknown",
        "operator": operator,
        "left_resolved": left_ok,
        "right_resolved": right_ok or unary_null,
        "left_value": left if left_ok else None,
        "right_value": right if right_ok else None,
        "left_source": left_source,
        "right_source": right_source,
        "unresolved_inputs": unresolved,
    }


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
    component = _component_identity(node)
    if any(component.values()):
        facts["component"] = component
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
    parsed_condition = condition_ast(
        input_params.get("condition", {}),
        source_path="paramsValue.inputParams.condition",
    )
    condition = condition_ast_summary(parsed_condition)
    if condition:
        facts["condition"] = condition
        facts["condition_ast"] = parsed_condition
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
    api_routes: list[str] = []
    service_symbols: list[str] = []

    def collect_source_signals(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                collect_source_signals(nested_value, str(nested_key))
            return
        if isinstance(value, list):
            for nested_value in value:
                collect_source_signals(nested_value, key)
            return
        candidate = _compact(value)
        if not candidate or len(candidate) > 200:
            return
        normalized_key = key.lower().replace("_", "")
        if normalized_key in {"url", "requesturl", "apiurl", "endpoint", "route", "path"}:
            if candidate.startswith("/") or "/api/" in candidate.lower():
                api_routes.append(candidate)
        if normalized_key in {
            "service",
            "servicename",
            "controller",
            "controllername",
            "classname",
            "methodname",
        }:
            if re.search(r"(?:Service|ServiceBase|Controller)(?:\.[A-Za-z_]\w*)?$", candidate):
                service_symbols.append(candidate)

    collect_source_signals(input_params)
    if api_routes:
        facts["api_routes"] = list(dict.fromkeys(api_routes))[:8]
    if service_symbols:
        facts["service_symbols"] = list(dict.fromkeys(service_symbols))[:8]
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


class ControlFlowAnalyzer:
    """Replay ActionDesign block markers into an auditable control-flow model."""

    IF_BRANCHES = {"ElseIf", "ElseIfCondition", "Else"}
    LOOP_OPENERS = {
        "WhileLoop",
        "ForLoop",
        "ForEachArray",
        "ForEachDynamicArray",
        "ForEachObject",
    }
    TRY_BRANCHES = {"Catch", "Finally"}
    END_FAMILY = {"IfEnd": "if", "LoopEnd": "loop", "EndTry": "try"}
    READ_NODES = {
        "SelectData",
        "SelectModelData",
        "SelectOrgData",
        "SelectProcessFinalApprover",
        "QueryData",
    }
    WRITE_NODES = {
        "AddNewData",
        "AddNewDataByDict",
        "UpdateData",
        "UpdateDataByDict",
        "DeleteData",
    }

    @classmethod
    def _opener_family(cls, element: str) -> str | None:
        if element in cls.LOOP_OPENERS or element.startswith("ForEach"):
            return "loop"
        if element == "Try":
            return "try"
        if element in cls.IF_BRANCHES or element in cls.END_FAMILY:
            return None
        if element in {
            "IfCondition",
            "NullCondition",
            "FlowIsComplate",
            "FlowTaskIsComplate",
            "CurrentTaskIsComplate",
        } or (element.startswith("Flow") and element.endswith(("Condition", "Complate"))):
            return "if"
        return None

    @staticmethod
    def _has_marker(node: dict[str, Any], marker: str) -> bool:
        for container in (node, node.get("config"), node.get("props"), node.get("meta")):
            if isinstance(container, dict) and container.get(marker) is True:
                return True
        return False

    @staticmethod
    def _warning(
        code: str,
        message: str,
        index: int | None = None,
        node: dict[str, Any] | None = None,
        *,
        severity: str = "error",
    ) -> dict[str, Any]:
        result: dict[str, Any] = {"code": code, "severity": severity, "message": message}
        if index is not None:
            result["canvas_line"] = index + 1
            result["internal_index"] = index
        if node is not None:
            result["node_key"] = str(node.get("key", ""))
            result["node_type"] = str(node.get("elementKey", ""))
        return result

    @staticmethod
    def _role(element: str, family: str | None = None) -> str:
        return {
            "ElseIf": "else_if",
            "ElseIfCondition": "else_if",
            "Else": "else",
            "IfEnd": "if_end",
            "LoopEnd": "loop_end",
            "Try": "try",
            "Catch": "catch",
            "Finally": "finally",
            "EndTry": "end_try",
        }.get(element, f"{family}_root" if family else "statement")

    def analyze_group(self, group: dict[str, Any], group_index: int = 0) -> dict[str, Any]:
        nodes = list(group.get("data", []) or [])
        group_key = str(group.get("key", ""))
        group_title = str(group.get("title", ""))
        warnings: list[dict[str, Any]] = []
        metadata: list[dict[str, Any]] = []
        blocks: list[dict[str, Any]] = []
        stack: list[dict[str, Any]] = []
        key_counts: dict[str, int] = {}
        block_by_id: dict[str, dict[str, Any]] = {}

        for node in nodes:
            key = str(node.get("key", ""))
            if key:
                key_counts[key] = key_counts.get(key, 0) + 1
        for key, count in key_counts.items():
            if count > 1:
                warnings.append(
                    self._warning(
                        "duplicate_node_key",
                        f"Node key {key!r} occurs {count} times in the group.",
                    )
                )

        for index, node in enumerate(nodes):
            element = str(node.get("elementKey", ""))
            key = str(node.get("key", ""))
            expected_depth = [str(frame["active"]["node_key"]) for frame in stack]
            if "depth" in node:
                stored_depth = [str(item) for item in (node.get("depth") or [])]
                if stored_depth != expected_depth:
                    warnings.append(
                        self._warning(
                            "depth_drift",
                            f"Stored depth {stored_depth!r} differs from replayed depth {expected_depth!r}.",
                            index,
                            node,
                        )
                    )

            opener_family = self._opener_family(element)
            current_frame = stack[-1] if stack else None
            meta: dict[str, Any] = {
                "structure_status": "valid",
                "role": self._role(element, opener_family),
                "nesting_level": len(stack),
                "root_block": current_frame["root"] if current_frame else None,
                "active_branch": current_frame["active"] if current_frame else None,
                "matched_branch": None,
                "matched_end": None,
                "enclosing_path": list(expected_depth),
            }

            if opener_family:
                root = _node_ref(index, node)
                block_id = f"block:{group_key or group_index}:{key or index}"
                block = {
                    "block_id": block_id,
                    "family": opener_family,
                    "root": root,
                    "branches": [
                        {
                            **root,
                            "role": self._role(element, opener_family),
                            "condition": (node_facts(node).get("condition") or ""),
                            "condition_ast": node_facts(node).get("condition_ast"),
                            "body_start": index + 1,
                            "body_end": None,
                        }
                    ],
                    "end": None,
                    "span": {"start": index, "end": None},
                    "nesting_level": len(stack),
                    "parent_block": stack[-1]["block"]["block_id"] if stack else None,
                    "children": [],
                }
                if stack:
                    stack[-1]["block"]["children"].append(block_id)
                blocks.append(block)
                block_by_id[block_id] = block
                meta.update({"root_block": root, "active_branch": root})
                stack.append({"family": opener_family, "root": root, "active": root, "block": block})
            elif element in self.IF_BRANCHES or element in self.TRY_BRANCHES:
                expected_family = "if" if element in self.IF_BRANCHES else "try"
                if not stack or stack[-1]["family"] != expected_family:
                    warnings.append(
                        self._warning(
                            "orphan_branch",
                            f"{element} has no open {expected_family} block to attach to.",
                            index,
                            node,
                        )
                    )
                    meta["role"] = self._role(element)
                else:
                    frame = stack[-1]
                    if element == "Else" and any(
                        branch.get("role") == "else" for branch in frame["block"]["branches"]
                    ):
                        warnings.append(
                            self._warning(
                                "duplicate_else",
                                "An IF chain contains more than one Else branch.",
                                index,
                                node,
                            )
                        )
                    if frame["block"]["branches"]:
                        frame["block"]["branches"][-1]["body_end"] = index - 1
                    branch = _node_ref(index, node)
                    facts = node_facts(node)
                    frame["block"]["branches"].append(
                        {
                            **branch,
                            "role": self._role(element),
                            "condition": facts.get("condition", ""),
                            "condition_ast": facts.get("condition_ast"),
                            "body_start": index + 1,
                            "body_end": None,
                        }
                    )
                    meta.update(
                        {
                            "role": self._role(element),
                            "nesting_level": max(0, len(stack) - 1),
                            "root_block": frame["root"],
                            "active_branch": branch,
                            "matched_branch": frame["active"],
                            "enclosing_path": expected_depth[:-1],
                        }
                    )
                    frame["active"] = branch
            elif element in self.END_FAMILY:
                expected_family = self.END_FAMILY[element]
                if not stack:
                    warnings.append(
                        self._warning(
                            "orphan_end",
                            f"{element} has no open block to close.",
                            index,
                            node,
                        )
                    )
                elif stack[-1]["family"] != expected_family:
                    warnings.append(
                        self._warning(
                            "mismatched_end",
                            f"{element} cannot close the open {stack[-1]['family']} block.",
                            index,
                            node,
                        )
                    )
                else:
                    frame = stack.pop()
                    end_ref = _node_ref(index, node)
                    block = frame["block"]
                    block["end"] = end_ref
                    block["span"]["end"] = index
                    block["branches"][-1]["body_end"] = index - 1
                    meta.update(
                        {
                            "role": self._role(element),
                            "nesting_level": len(stack),
                            "root_block": frame["root"],
                            "active_branch": frame["active"],
                            "matched_branch": frame["active"],
                            "matched_end": end_ref,
                            "enclosing_path": expected_depth,
                        }
                    )
                    participant_keys = {
                        str(branch.get("node_key", "")) for branch in block["branches"]
                    }
                    for prior_index, prior in enumerate(metadata):
                        if str((prior.get("root_block") or {}).get("node_key", "")) == str(
                            frame["root"].get("node_key", "")
                        ) or str(nodes[prior_index].get("key", "")) in participant_keys:
                            prior["matched_end"] = end_ref
            elif (self._has_marker(node, "levelMarker") or self._has_marker(node, "endMarker")):
                warnings.append(
                    self._warning(
                        "unknown_plugin_block",
                        f"Unknown block marker element {element!r}; pairing is only a candidate.",
                        index,
                        node,
                        severity="warning",
                    )
                )
            metadata.append(meta)

        for frame in stack:
            block = frame["block"]
            block["branches"][-1]["body_end"] = len(nodes) - 1
            warnings.append(
                self._warning(
                    "missing_end",
                    f"Open {frame['family']} block is missing its closing marker.",
                    int(block["root"]["internal_index"]),
                    nodes[int(block["root"]["internal_index"])],
                )
            )

        status = (
            "invalid"
            if any(item.get("severity") == "error" for item in warnings)
            else "partial"
            if warnings
            else "valid"
        )
        for item in metadata:
            item["structure_status"] = status
            item["pairing_definitive"] = status == "valid"
            item["pairing_kind"] = "definitive" if status == "valid" else "candidate"
        for block in blocks:
            block["structure_status"] = status
            block["pairing_definitive"] = status == "valid"
            block["pairing_kind"] = "definitive" if status == "valid" else "candidate"
        return {
            "group_key": group_key,
            "group_title": group_title,
            "group_index": group_index,
            "structure_status": status,
            "node_count": len(nodes),
            "nodes": nodes,
            "node_control_flow": metadata,
            "blocks": blocks,
            "warnings": warnings,
        }

    def analyze(self, data: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(data, str):
            data = json.loads(data)
        groups = [
            self.analyze_group(group, index)
            for index, group in enumerate(data.get("actionData", []) or [])
        ]
        statuses = [group["structure_status"] for group in groups]
        status = "invalid" if "invalid" in statuses else "partial" if "partial" in statuses else "valid"
        return {
            "schema_version": "1.0",
            "structure_status": status,
            "groups": groups,
            "warnings": [warning for group in groups for warning in group["warnings"]],
        }

    @staticmethod
    def _safe_id(value: str) -> str:
        return "n_" + hashlib.sha1(value.encode("utf-8")).hexdigest()[:14]

    @staticmethod
    def _label(value: Any, limit: int = 80) -> str:
        text = _compact(value).replace("\\", "\\\\").replace('"', "'")
        text = text.replace("[", "(").replace("]", ")").replace("\n", " ")
        return text[:limit] + ("…" if len(text) > limit else "")

    @staticmethod
    def _scenario_items(scenarios: Any) -> list[tuple[str, dict[str, Any]]]:
        if scenarios is None:
            return []
        if isinstance(scenarios, dict):
            items = [(str(name), values) for name, values in scenarios.items()]
        elif isinstance(scenarios, list):
            items = [
                (str(item.get("name", f"scenario_{index + 1}")), item.get("inputs") or {})
                for index, item in enumerate(scenarios)
                if isinstance(item, dict)
            ]
        else:
            raise ValueError("scenarios must be an object or a list of named input objects")
        if len(items) > 20:
            raise ValueError("scenarios accepts at most 20 named inputs")
        if any(not isinstance(values, dict) for _, values in items):
            raise ValueError("each scenario value must be an input object")
        return items

    def _evaluate_scenarios(
        self,
        groups: list[dict[str, Any]],
        scenarios: Any,
        selected: dict[str, set[int]] | None = None,
    ) -> list[dict[str, Any]]:
        result = []
        for name, inputs in self._scenario_items(scenarios):
            block_results = []
            reachable: list[dict[str, Any]] = []
            unresolved: list[str] = []
            for group in groups:
                nodes = group["nodes"]
                active_branch_results: dict[str, str] = {}
                for block in group["blocks"]:
                    selected_indices = (selected or {}).get(group["group_key"])
                    block_end = block["span"].get("end")
                    block_end = int(block_end) if block_end is not None else len(nodes) - 1
                    if selected_indices is not None and (
                        int(block["span"]["start"]) not in selected_indices
                        or block_end not in selected_indices
                    ):
                        continue
                    if block["family"] not in {"if", "loop"}:
                        continue
                    root_index = int(block["root"]["internal_index"])
                    ancestor_path = group["node_control_flow"][root_index].get("enclosing_path", [])
                    ancestor_states = [
                        active_branch_results.get(str(key), "unknown") for key in ancestor_path
                    ]
                    block_activation = (
                        "false"
                        if "false" in ancestor_states
                        else "unknown"
                        if "unknown" in ancestor_states
                        else "true"
                    )
                    prior_no_match = "true"
                    branch_results = []
                    for branch in block["branches"]:
                        ast = branch.get("condition_ast")
                        if branch.get("role") == "else":
                            branch_result = prior_no_match
                            evaluation = {"result": branch_result, "unresolved_inputs": []}
                        else:
                            evaluation = evaluate_condition_ast(ast, inputs)
                            condition_result = evaluation["result"]
                            if prior_no_match == "false" or condition_result == "false":
                                branch_result = "false"
                            elif prior_no_match == "true":
                                branch_result = condition_result
                            else:
                                branch_result = "unknown"
                            if prior_no_match == "true":
                                prior_no_match = (
                                    "false" if condition_result == "true" else "true" if condition_result == "false" else "unknown"
                                )
                            elif prior_no_match == "unknown" and condition_result == "true":
                                prior_no_match = "false"
                        if block_activation == "false":
                            branch_result = "false"
                        elif block_activation == "unknown" and branch_result == "true":
                            branch_result = "unknown"
                        active_branch_results[str(branch.get("node_key", ""))] = branch_result
                        unresolved.extend(evaluation.get("unresolved_inputs", []))
                        branch_results.append(
                            {
                                "branch": {key: branch.get(key) for key in ("node_key", "canvas_line", "role")},
                                "condition": branch.get("condition", ""),
                                "result": branch_result,
                                "evaluation": evaluation,
                            }
                        )
                        if branch_result == "true":
                            start = max(0, int(branch.get("body_start", 0)))
                            end = int(branch.get("body_end", start - 1))
                            branch_key = str(branch.get("node_key", ""))
                            reachable.extend(
                                _node_ref(index, nodes[index])
                                for index in range(start, end + 1)
                                if (group["node_control_flow"][index].get("enclosing_path") or [None])[-1]
                                == branch_key
                            )
                    hits = [item["branch"] for item in branch_results if item["result"] == "true"]
                    block_results.append(
                        {
                            "group_key": group["group_key"],
                            "block_id": block["block_id"],
                            "family": block["family"],
                            "branches": branch_results,
                            "hit_branch": hits[0] if len(hits) == 1 else None,
                            "path_result": "resolved" if len(hits) == 1 else "unknown",
                        }
                    )
            result.append(
                {
                    "name": name,
                    "inputs": inputs,
                    "blocks": block_results,
                    "unresolved_inputs": list(dict.fromkeys(unresolved)),
                    "statically_reachable_nodes": reachable,
                    "execution_claim": "static_three_state_evaluation_only",
                }
            )
        return result

    def _tree_text(self, groups: list[dict[str, Any]], selected: dict[str, set[int]]) -> str:
        lines: list[str] = []
        for group in groups:
            indices = selected.get(group["group_key"], set())
            if not indices:
                continue
            lines.append(f"group {group['group_title'] or group['group_key']} {{")
            for index in sorted(indices):
                node = group["nodes"][index]
                meta = group["node_control_flow"][index]
                role = meta["role"]
                facts = node_facts(node)
                condition = facts.get("condition", "")
                indent = "  " * (int(meta["nesting_level"]) + 1)
                suffix = f" // line {index + 1}, {str(node.get('key', ''))}"
                if role in {"if_root", "loop_root"}:
                    keyword = "if" if role == "if_root" else "loop"
                    lines.append(f"{indent}{keyword} ({condition or '?'}) {{{suffix}")
                elif role == "else_if":
                    lines.append(f"{indent}}} else if ({condition or '?'}) {{{suffix}")
                elif role == "else":
                    lines.append(f"{indent}}} else {{{suffix}")
                elif role == "try":
                    lines.append(f"{indent}try {{{suffix}")
                elif role in {"catch", "finally"}:
                    lines.append(f"{indent}}} {role} {{{suffix}")
                elif role in {"if_end", "loop_end", "end_try"}:
                    lines.append(f"{indent}}}{suffix}")
                else:
                    title = self._label(node.get("title") or node.get("elementKey"), 60)
                    lines.append(f"{indent}{title};{suffix}")
            lines.append("}")
        return "\n".join(lines)

    def _build_graph(
        self,
        groups: list[dict[str, Any]],
        selected: dict[str, set[int]],
        *,
        include_relations: bool,
        relation_types: list[str] | None,
        max_nodes: int,
        max_edges: int,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        allowed = set(relation_types or [])
        nodes_by_id: dict[str, dict[str, Any]] = {}
        edges: list[dict[str, Any]] = []
        control_ids: set[str] = set()

        def add_node(identifier: str, kind: str, label: str, **extra: Any) -> None:
            nodes_by_id.setdefault(identifier, {"id": identifier, "type": kind, "label": self._label(label), **extra})

        def add_edge(source: str, target: str, relation: str, **extra: Any) -> None:
            if allowed and relation not in allowed:
                return
            edge_id = f"{relation}:{source}:{target}:{len(edges)}"
            edges.append({"id": edge_id, "source": source, "target": target, "type": relation, **extra})

        for group in groups:
            indices = selected.get(group["group_key"], set())
            if not indices:
                continue
            canvas_ids: dict[int, str] = {}
            for index in sorted(indices):
                node = group["nodes"][index]
                canvas_id = f"canvas:{group['group_key']}:{str(node.get('key', '')) or index}"
                canvas_ids[index] = canvas_id
                control_ids.add(canvas_id)
                add_node(
                    canvas_id,
                    "canvas",
                    f"{index + 1}. {node.get('title') or node.get('elementKey')}",
                    group_key=group["group_key"],
                    canvas_line=index + 1,
                    node_key=str(node.get("key", "")),
                    node_type=str(node.get("elementKey", "")),
                )
            ordered = sorted(canvas_ids)
            for left, right in zip(ordered, ordered[1:]):
                if right == left + 1:
                    add_edge(canvas_ids[left], canvas_ids[right], "sequence")
            for block in group["blocks"]:
                span_start = int(block["span"]["start"])
                span_end = block["span"].get("end")
                span_end = int(span_end) if span_end is not None else len(group["nodes"]) - 1
                contained = [index for index in indices if span_start <= index <= span_end]
                if span_start not in indices or span_end not in indices:
                    continue
                block_id = block["block_id"]
                control_ids.add(block_id)
                add_node(block_id, "block", f"{block['family']} block line {span_start + 1}", family=block["family"])
                for index in contained:
                    add_edge(block_id, canvas_ids[index], "contains")
                for branch in block["branches"]:
                    index = int(branch["internal_index"])
                    if index in canvas_ids:
                        add_edge(canvas_ids[index], block_id, "branch_of", role=branch["role"])
                if block.get("end"):
                    index = int(block["end"]["internal_index"])
                    if index in canvas_ids:
                        add_edge(canvas_ids[index], block_id, "closes")

            if include_relations:
                for index, canvas_id in canvas_ids.items():
                    node = group["nodes"][index]
                    element = str(node.get("elementKey", ""))
                    facts = node_facts(node)
                    called = facts.get("called_action") or {}
                    if called:
                        identity = str(called.get("code") or called.get("id") or called.get("name"))
                        target = f"action:{identity}"
                        add_node(target, "action", identity)
                        add_edge(canvas_id, target, "calls")
                    model = str(facts.get("model_or_table", ""))
                    if model:
                        target = f"model:{model}"
                        add_node(target, "model", model)
                        if element in self.WRITE_NODES:
                            add_edge(canvas_id, target, "writes")
                        elif element in self.READ_NODES or element.startswith("Select"):
                            add_edge(canvas_id, target, "reads")
                    component = facts.get("component") or {}
                    component_key = str(component.get("component_key") or component.get("model_key") or "")
                    if element == "DataFilter" and component_key:
                        target = f"component:{component_key}"
                        add_node(target, "component", component.get("label") or component_key)
                        add_edge(canvas_id, target, "filters")
                    for mapping in facts.get("field_mappings", []) or []:
                        field = str(mapping.get("field", ""))
                        if not field:
                            continue
                        target = f"field:{model}:{field}" if model else f"field:{field}"
                        add_node(target, "field", f"{model + '.' if model else ''}{field}")
                        add_edge(canvas_id, target, "maps_field")
                    defined = str(facts.get("defined_variable", ""))
                    if defined:
                        target = f"variable:{defined}"
                        add_node(target, "variable", defined)
                        add_edge(canvas_id, target, "defines")
                    assigned = str(facts.get("assignment_target", ""))
                    if assigned:
                        target = f"variable:{assigned}"
                        add_node(target, "variable", assigned)
                        add_edge(canvas_id, target, "assigns")

        all_nodes = list(nodes_by_id.values())
        control_nodes = [item for item in all_nodes if item["id"] in control_ids]
        truncated = {"nodes": False, "edges": False, "control_tree_omitted": False}
        if len(control_nodes) > max_nodes:
            return {"nodes": [], "edges": []}, {
                "nodes": True,
                "edges": bool(edges),
                "control_tree_omitted": True,
                "reason": "control scope exceeds max_nodes; narrow to one group or block",
            }
        kept_nodes = control_nodes + [item for item in all_nodes if item["id"] not in control_ids][: max_nodes - len(control_nodes)]
        kept_ids = {item["id"] for item in kept_nodes}
        candidate_edges = [edge for edge in edges if edge["source"] in kept_ids and edge["target"] in kept_ids]
        control_edges = [edge for edge in candidate_edges if edge["type"] in {"sequence", "contains", "branch_of", "closes"}]
        other_edges = [edge for edge in candidate_edges if edge not in control_edges]
        if len(control_edges) > max_edges:
            return {"nodes": [], "edges": []}, {
                "nodes": len(all_nodes) > max_nodes,
                "edges": True,
                "control_tree_omitted": True,
                "reason": "control scope exceeds max_edges; narrow to one group or block",
            }
        kept_edges = control_edges + other_edges[: max_edges - len(control_edges)]
        truncated["nodes"] = len(kept_nodes) < len(all_nodes)
        truncated["edges"] = len(kept_edges) < len(candidate_edges) or len(candidate_edges) < len(edges)
        return {"nodes": kept_nodes, "edges": kept_edges}, truncated

    def _mermaid(self, graph: dict[str, Any], relations: set[str]) -> str:
        lines = ["flowchart TD"]
        matching_edges = [
            edge for edge in graph.get("edges", []) if edge.get("type") in relations
        ]
        included_ids = {
            str(endpoint)
            for edge in matching_edges
            for endpoint in (edge.get("source"), edge.get("target"))
        }
        if relations <= {"sequence", "contains", "branch_of", "closes"}:
            included_ids.update(
                str(node.get("id"))
                for node in graph.get("nodes", [])
                if node.get("type") in {"canvas", "block"}
            )
        for node in graph.get("nodes", []):
            if str(node.get("id")) not in included_ids:
                continue
            node_id = self._safe_id(str(node["id"]))
            lines.append(f'  {node_id}["{self._label(node.get("label", ""))}"]')
        for edge in matching_edges:
            source = self._safe_id(str(edge["source"]))
            target = self._safe_id(str(edge["target"]))
            lines.append(f'  {source} -->|{self._label(edge.get("type", ""), 24)}| {target}')
        return "\n".join(lines)

    def inspect(
        self,
        data: dict[str, Any] | str,
        *,
        group: str | None = None,
        node_key: str | None = None,
        start: int | None = None,
        end: int | None = None,
        scope: str = "auto",
        include_relations: bool = True,
        relation_types: list[str] | None = None,
        render: str | list[str] | None = None,
        scenarios: Any = None,
        max_nodes: int = 120,
        max_edges: int = 240,
    ) -> dict[str, Any]:
        if scope not in {"auto", "group", "action"}:
            raise ValueError("scope must be auto, group or action")
        max_nodes = max(1, min(int(max_nodes), 300))
        max_edges = max(1, min(int(max_edges), 600))
        analysis = self.analyze(data)
        groups = [
            item
            for item in analysis["groups"]
            if not group or group.lower() in f"{item['group_title']} {item['group_key']}".lower()
        ]
        summaries = [
            {
                key: item[key]
                for key in ("group_key", "group_title", "group_index", "structure_status", "node_count")
            }
            | {"block_count": len(item["blocks"]), "warning_count": len(item["warnings"])}
            for item in groups
        ]
        summary_only = scope == "auto" and not any((group, node_key, start is not None, end is not None))
        selected: dict[str, set[int]] = {}
        if not summary_only:
            for item in groups:
                count = len(item["nodes"])
                if scope == "action" or (group and node_key is None and start is None and end is None):
                    selected[item["group_key"]] = set(range(count))
                    continue
                targets = {
                    index
                    for index, node in enumerate(item["nodes"])
                    if (not node_key or str(node.get("key", "")) == node_key)
                    and (start is None or index >= start)
                    and (end is None or index <= end)
                }
                chosen: set[int] = set()
                for target in targets:
                    containing = []
                    for block in item["blocks"]:
                        block_end = block["span"].get("end")
                        block_end = int(block_end) if block_end is not None else count - 1
                        if int(block["span"]["start"]) <= target <= block_end:
                            containing.append((block_end - int(block["span"]["start"]), block, block_end))
                    if containing:
                        _, block, block_end = min(containing, key=lambda value: value[0])
                        chosen.update(range(int(block["span"]["start"]), block_end + 1))
                    else:
                        chosen.add(target)
                selected[item["group_key"]] = chosen
        selected_groups = [item for item in groups if selected.get(item["group_key"])]
        scope_warnings: list[dict[str, Any]] = []
        if group and not groups:
            scope_warnings.append(
                {
                    "code": "group_not_found",
                    "severity": "warning",
                    "message": f"No action group matched {group!r}.",
                }
            )
        elif node_key and not selected_groups:
            scope_warnings.append(
                {
                    "code": "node_not_found",
                    "severity": "warning",
                    "message": f"No canvas node matched {node_key!r} in the selected groups.",
                }
            )
        graph, truncation = self._build_graph(
            selected_groups,
            selected,
            include_relations=include_relations,
            relation_types=relation_types,
            max_nodes=max_nodes,
            max_edges=max_edges,
        ) if not summary_only else ({"nodes": [], "edges": []}, {"nodes": False, "edges": False, "control_tree_omitted": False})
        selected_statuses = [item["structure_status"] for item in selected_groups or groups]
        status = "invalid" if "invalid" in selected_statuses else "partial" if "partial" in selected_statuses else "valid"
        tree_text = "" if truncation.get("control_tree_omitted") else self._tree_text(selected_groups, selected)
        control_relations = {"sequence", "contains", "branch_of", "closes"}
        dependency_relations = {"calls", "reads", "writes", "filters", "maps_field", "defines", "assigns"}
        views = {
            "tree_text": tree_text,
            "control_mermaid": "" if truncation.get("control_tree_omitted") else self._mermaid(graph, control_relations),
            "dependency_mermaid": self._mermaid(graph, dependency_relations),
        }
        if render:
            requested = {render} if isinstance(render, str) else set(render)
            aliases = {"tree": "tree_text", "control": "control_mermaid", "dependency": "dependency_mermaid"}
            requested = {aliases.get(item, item) for item in requested}
            views = {key: value for key, value in views.items() if key in requested}
        return {
            "schema_version": analysis["schema_version"],
            "structure_status": status,
            "scope": {
                "mode": "summary" if summary_only else scope,
                "group": group,
                "node_key": node_key,
                "start": start,
                "end": end,
            },
            "group_summaries": summaries,
            "blocks": [
                block
                for item in selected_groups
                for block in item["blocks"]
                if int(block["span"]["start"]) in selected.get(item["group_key"], set())
                and int(
                    block["span"].get("end")
                    if block["span"].get("end") is not None
                    else len(item["nodes"]) - 1
                ) in selected.get(item["group_key"], set())
            ],
            "graph": graph,
            "views": views,
            "scenario_matrix": self._evaluate_scenarios(selected_groups, scenarios, selected),
            "warnings": [warning for item in groups for warning in item["warnings"]] + scope_warnings + ([{
                "code": "scope_required",
                "severity": "info",
                "message": "Specify group/node/range, or scope='action', to generate an action graph.",
            }] if summary_only else []),
            "truncation": truncation | {"max_nodes": max_nodes, "max_edges": max_edges},
        }


class CanvasInspector:
    def __init__(self) -> None:
        self.control_flow = ControlFlowAnalyzer()

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
        for group_index, action_group in enumerate(data.get("actionData", []) or []):
            group_title = str(action_group.get("title", ""))
            group_key = str(action_group.get("key", ""))
            if group and group.lower() not in f"{group_title} {group_key}".lower():
                continue
            nodes = action_group.get("data", []) or []
            control = self.control_flow.analyze_group(action_group, group_index)
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
                    "control_flow": control["node_control_flow"][index],
                }
                if include_params:
                    item["paramsValue"] = node.get("paramsValue", {})
                result.append(item)
        return result

    def inspect_control_flow(
        self,
        data: dict[str, Any] | str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.control_flow.inspect(data, **kwargs)

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
            control = self.control_flow.analyze_group(action_group, group_index)
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
                flow = control["node_control_flow"][index]
                for parent_key in flow.get("enclosing_path", []) or []:
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
                        "NullCondition": "if",
                        "ElseIf": "else_if",
                        "ElseIfCondition": "else_if",
                        "Else": "else",
                    }.get(parent_type, "parent")
                    if parent_facts.get("condition"):
                        parent["condition"] = parent_facts["condition"]
                        parent["condition_ast"] = parent_facts.get("condition_ast")
                    parent["structure_status"] = flow.get("structure_status")
                    parent["pairing_definitive"] = flow.get("pairing_definitive")
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
                    "control_flow": flow,
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
        analyzer = ControlFlowAnalyzer()
        left_flow = analyzer.analyze(left)
        right_flow = analyzer.analyze(right)

        def flow_map(analysis: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
            result: dict[tuple[str, str], dict[str, Any]] = {}
            for action_group in analysis.get("groups", []):
                for index, node in enumerate(action_group.get("nodes", [])):
                    result[(action_group["group_key"], str(node.get("key", "")))] = (
                        action_group["node_control_flow"][index]
                    )
            return result

        left_flow_nodes = flow_map(left_flow)
        right_flow_nodes = flow_map(right_flow)
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
        common_keys = sorted(set(left_nodes) & set(right_nodes))

        def ref_key(value: Any) -> str | None:
            return str((value or {}).get("node_key", "")) or None

        condition_changes = []
        branch_changes = []
        pairing_changes = []
        for key in common_keys:
            left_facts = node_facts(left_nodes[key]["node"])
            right_facts = node_facts(right_nodes[key]["node"])
            if left_facts.get("condition_ast") != right_facts.get("condition_ast"):
                condition_changes.append(
                    {
                        "group_key": key[0],
                        "node_key": key[1],
                        "published": left_facts.get("condition_ast"),
                        "draft": right_facts.get("condition_ast"),
                    }
                )
            left_meta = left_flow_nodes.get(key, {})
            right_meta = right_flow_nodes.get(key, {})
            left_branch = (
                ref_key(left_meta.get("root_block")),
                ref_key(left_meta.get("active_branch")),
            )
            right_branch = (
                ref_key(right_meta.get("root_block")),
                ref_key(right_meta.get("active_branch")),
            )
            if left_branch != right_branch:
                branch_changes.append(
                    {
                        "group_key": key[0],
                        "node_key": key[1],
                        "published_root_block": left_branch[0],
                        "published_active_branch": left_branch[1],
                        "draft_root_block": right_branch[0],
                        "draft_active_branch": right_branch[1],
                    }
                )
            left_pair = (ref_key(left_meta.get("matched_branch")), ref_key(left_meta.get("matched_end")))
            right_pair = (ref_key(right_meta.get("matched_branch")), ref_key(right_meta.get("matched_end")))
            if left_pair != right_pair:
                pairing_changes.append(
                    {
                        "group_key": key[0],
                        "node_key": key[1],
                        "published_matched_branch": left_pair[0],
                        "published_matched_end": left_pair[1],
                        "draft_matched_branch": right_pair[0],
                        "draft_matched_end": right_pair[1],
                    }
                )
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
            "semantic": {
                "published_structure_status": left_flow["structure_status"],
                "draft_structure_status": right_flow["structure_status"],
                "structure_status_changed": left_flow["structure_status"] != right_flow["structure_status"],
                "condition_changes": condition_changes,
                "node_branch_changes": branch_changes,
                "pairing_changes": pairing_changes,
            },
        }
