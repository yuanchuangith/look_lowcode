from __future__ import annotations

import json
from typing import Any

from .source_budget import bounded_payload


def response_limit(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 8192 <= value <= 65536:
        raise ValueError("max_output_bytes must be 8192..65536")
    return value


def payload_size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))


def canvas_payload(result: dict[str, Any], limit: int, *, identifier: str, tool: str) -> dict[str, Any]:
    response_limit(limit)
    if payload_size(result) <= limit:
        return result
    bounded = bounded_payload(result, max(4096, limit // 2))
    envelope = {key: result[key] for key in ("action", "design", "version_semantics", "structure_status", "group_resolution", "generated_csharp_scope", "reference_coverage") if key in result}
    if payload_size(envelope) < limit // 3:
        bounded.update(envelope)
    if "generated_csharp" in result and payload_size(result["generated_csharp"]) < limit // 4:
        bounded["generated_csharp"] = result["generated_csharp"]
    reads = []
    for node in result.get("nodes", [])[:8]:
        reads.append({"tool": "inspect_action", "arguments": {
            "identifier": identifier, "design_id": (result.get("design") or {}).get("design_id"),
            "version": (result.get("design") or {}).get("version", "published"),
            "group": node.get("group_key"), "node_key": node.get("node_key"),
            "value_path": "/paramsValue", "value_offset": 0, "value_limit": 2048,
        }})
    bounded["next_read"] = reads or [{"tool": tool, "arguments": {"identifier": identifier, "design_id": (result.get("design") or {}).get("design_id")}, "instruction": "Narrow to an exact group and node, then read its paramsValue with inspect_action.value_path."}]
    bounded["evidence_complete"] = False
    bounded["response_complete"] = False
    bounded["response_truncated"] = True
    bounded["conclusion_gate"] = "candidate_only_until_omitted_evidence_is_read"
    bounded["response_budget"] = {"bytes": limit, "encoding": "utf-8", "serialization": "json_indent_2"}
    if isinstance(bounded.get("nodes"), list):
        bounded["node_count"] = len(bounded["nodes"])
        bounded["nodes_truncated"] = len(bounded["nodes"]) < len(result.get("nodes", [])) or result.get("nodes_truncated", False)
    if payload_size(bounded) > limit:
        bounded = bounded_payload(bounded, limit)
    return bounded


def node_value_page(node: dict[str, Any], path: str, offset: int, count: int) -> dict[str, Any]:
    if not path.startswith("/paramsValue") or path.split("/")[1] != "paramsValue":
        raise ValueError("value_path must be a JSON pointer within this node's /paramsValue")
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0 or isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 8192:
        raise ValueError("value_offset must be nonnegative and value_limit must be 1..8192")
    value: Any = node
    for part in path.split("/")[1:]:
        part = part.replace("~1", "/").replace("~0", "~")
        try:
            value = value[int(part)] if isinstance(value, list) and part.isdecimal() else value[part]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError("value_path was not found in the selected node") from exc
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    if offset > len(text):
        raise ValueError("value_offset exceeds the value length")
    chunk = text[offset:offset + count]
    while payload_size(chunk) > 4096 and len(chunk) > 1:
        chunk = chunk[:len(chunk) // 2]
    next_offset = offset + len(chunk)
    return {"value_path": path, "value_offset": offset, "text": chunk, "total_characters": len(text), "encoding": "text" if isinstance(value, str) else "json", "complete": next_offset == len(text), "next_offset": next_offset if next_offset < len(text) else None}
