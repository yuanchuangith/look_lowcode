from __future__ import annotations

import re
from typing import Any

from .source_lex import LexedSource, string_value


IDENTIFIER = re.compile(r"[A-Za-z_$][\w$]*\Z")
KEYWORDS = {"true", "false", "null", "new", "var", "return", "throw", "if", "else", "this", "base", "string", "object", "int", "bool", "void"}


def expression_references(expression: str, role: str, path: str) -> list[dict[str, Any]]:
    if not expression or len(expression.encode("utf-8")) > 131072:
        return []
    source = LexedSource(expression, language="csharp")
    tokens = source.tokens
    references = []
    for index, token in enumerate(tokens):
        if len(references) >= 64:
            break
        symbol = ""
        kind = "identifier"
        if token.kind == "code" and IDENTIFIER.fullmatch(token.value) and token.value not in KEYWORDS:
            symbol = token.value
        elif token.kind == "string" and index > 1 and index + 1 < len(tokens):
            if tokens[index - 1].value == "[" and tokens[index + 1].value == "]":
                symbol = string_value(token)
                kind = "indexed_field"
        if symbol and not any(item["symbol"] == symbol and item["kind"] == kind for item in references):
            references.append({
                "symbol": symbol, "role": role, "kind": kind,
                "expression": expression, "source_path": path,
                "confidence": "lexical_candidate" if source.errors else "syntactic_reference",
            })
    return references


def parameter_code(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("code") or value.get("value") or "")
    return str(value) if value is not None else ""


def node_references(node: dict[str, Any]) -> list[dict[str, Any]]:
    params = node.get("paramsValue") or {}
    inputs = params.get("inputParams") or {}
    outputs = params.get("outputParams") or {}
    references = []
    role_fields = {"variableValue": "read", "attributeValue": "read", "list": "loop_source", "returnValue": "return", "value": "return"}
    for key, role in role_fields.items():
        value = inputs.get(key)
        if value is not None:
            references.extend(expression_references(parameter_code(value), role, f"paramsValue.inputParams.{key}"))

    def visit_condition(value: Any, path: str) -> None:
        if isinstance(value, dict):
            if "Filters" in value:
                for index, child in enumerate(value.get("Filters") or []):
                    visit_condition(child, f"{path}.Filters[{index}]")
            else:
                for key in ("target", "value", "ParamInput"):
                    operand = value.get(key)
                    if isinstance(operand, dict):
                        references.extend(expression_references(parameter_code(operand), "condition", f"{path}.{key}"))
                if value.get("Field"):
                    references.append({"symbol": str(value["Field"]), "role": "condition", "kind": "field", "expression": str(value["Field"]), "source_path": f"{path}.Field", "confidence": "structural"})

    visit_condition(inputs.get("condition"), "paramsValue.inputParams.condition")
    for key, value in inputs.items():
        if key == "variableName":
            references.extend(expression_references(parameter_code(value), "write", f"paramsValue.inputParams.{key}"))
        elif isinstance(value, dict) and value.get("paramName"):
            references.extend(expression_references(parameter_code(value), "argument", f"paramsValue.inputParams.{key}"))
        elif key in {"params", "updateParams"} and isinstance(value, list):
            for index, mapping in enumerate(value):
                if isinstance(mapping, dict):
                    references.extend(expression_references(parameter_code(mapping.get("name")), "read", f"paramsValue.inputParams.{key}[{index}].name"))
    for key, value in outputs.items():
        if isinstance(value, dict):
            references.extend(expression_references(parameter_code(value), "return" if value.get("paramName") else "define", f"paramsValue.outputParams.{key}"))
    return references


def select_groups(groups: list[dict[str, Any]], selector: str | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not selector:
        return groups, {"status": "all", "candidates": []}
    exact_keys = [group for group in groups if str(group.get("key", "")) == selector]
    exact_titles = [group for group in groups if str(group.get("title", "")).casefold() == selector.casefold()]
    candidates = exact_keys or exact_titles or [group for group in groups if selector.casefold() in f"{group.get('key', '')} {group.get('title', '')}".casefold()]
    status = "unique" if len(candidates) == 1 else "ambiguous" if candidates else "not_found"
    return candidates if status == "unique" else [], {
        "status": status,
        "match_kind": "exact_key" if exact_keys else "exact_title" if exact_titles else "fuzzy",
        "candidates": [{"group_key": group.get("key"), "title": group.get("title")} for group in candidates][:20],
    }


def called_identity(action_name: dict[str, Any], element: str) -> dict[str, Any]:
    kind = "public" if element == "CallPublicAction" else "local"
    target = str(action_name.get("value") or "")
    if not re.fullmatch(r"[\w-]{1,128}", target):
        target = ""
    return {
        "kind": kind,
        "target_group_key": target if kind == "local" else "",
        "target_action_identifier": str(action_name.get("code") or action_name.get("id") or target) if kind == "public" else "",
        "resolution_status": "unresolved",
    }
