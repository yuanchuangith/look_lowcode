from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any

from .source_backend import parse_backend_file


@lru_cache(maxsize=8)
def _method_ranges(design_id: str, code_hash: str, csharp: str) -> tuple[list[dict[str, Any]], bool]:
    parsed, lexed = parse_backend_file(csharp, "generated.cs")
    return parsed["methods"], bool(lexed.errors)


def scoped_csharp(csharp: str, nodes: list[dict[str, Any]], design_id: str = "") -> tuple[str, dict[str, Any]]:
    code_hash = hashlib.sha256(csharp.encode("utf-8")).hexdigest()
    methods, incomplete = _method_ranges(design_id, code_hash, csharp)
    groups = {str(node.get("group_key", "")) for node in nodes}
    candidates = [method for method in methods if method.get("member") in groups]
    if len(groups) != 1 or len(candidates) != 1 or incomplete:
        return csharp, {"status": "unresolved", "search_scope": "whole_action_candidate", "code_sha256": code_hash, "exact_source_map": False}
    method = candidates[0]
    begin, end = method["body_start"], method["body_end"] + 1
    masked = "".join(char if begin <= index < end or char in "\r\n" else " " for index, char in enumerate(csharp))
    return masked, {
        "status": "resolved_method", "search_scope": "group_method",
        "method": method["member"], "code_sha256": code_hash,
        "start_line": csharp.count("\n", 0, begin) + 1,
        "end_line": csharp.count("\n", 0, end) + 1,
        "exact_source_map": False,
    }
