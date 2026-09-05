from __future__ import annotations

import itertools
import json
from typing import Any


PRIORITY_FIELDS = ("status", "errors", "error", "unresolved", "contract_status", "runtime_verified", "index", "repository")


def bounded_payload(result: dict[str, Any], limit: int) -> dict[str, Any]:
    def encoded_size(value):
        return len(json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8"))

    try:
        if encoded_size(result) <= limit:
            return result
    except (RecursionError, ValueError):
        pass
    for item_limit, string_limit, depth_limit in ((10, 512, 8), (6, 256, 6), (3, 128, 4), (1, 64, 2)):
        omitted = []
        omissions = 0

        def note(location, count, reason):
            nonlocal omissions
            omissions += 1
            if len(omitted) < 24:
                omitted.append({"path": location[:160], "count": count, "reason": reason})

        def clip(value, location, depth):
            if isinstance(value, str):
                if len(value) > string_limit:
                    note(location, len(value) - string_limit, "string_characters")
                    return value[:string_limit] + "…"
                return value
            if isinstance(value, (dict, list, tuple)) and depth >= depth_limit:
                note(location, len(value), "depth_limit")
                return {} if isinstance(value, dict) else []
            if isinstance(value, (list, tuple)):
                if len(value) > item_limit:
                    note(location, len(value) - item_limit, "list_items")
                return [clip(child, f"{location}[{index}]", depth + 1) for index, child in enumerate(value[:item_limit])]
            if isinstance(value, dict):
                before = omissions
                preferred = [key for key in PRIORITY_FIELDS if key in value]
                remaining = (key for key in value if key not in preferred)
                keys = preferred + list(itertools.islice(remaining, max(item_limit * 2 - len(preferred), 0)))
                if len(value) > len(keys):
                    note(location, len(value) - len(keys), "object_fields")
                bounded = {}
                for key in keys:
                    if len(str(key)) > string_limit:
                        note(location, 1, "oversized_key")
                        continue
                    bounded[key] = clip(value[key], f"{location}.{key}", depth + 1)
                if omissions > before:
                    bounded["evidence_complete"] = False
                    if "confidence" in bounded:
                        bounded["confidence"] = "candidate"
                    if "contract_status" in bounded:
                        bounded["contract_status"] = "unresolved"
                return bounded
            return value

        bounded = clip(result, "$", 0)
        previous_status = result.get("status", "ok")
        bounded["status"] = previous_status if previous_status in {"error", "unresolved", "ambiguous", "not_found"} else "partial"
        bounded["response_truncated"] = True
        bounded["response_complete"] = False
        bounded["omitted"] = omitted
        bounded["omission_count"] = omissions
        bounded["response_budget"] = {"bytes": limit, "encoding": "utf-8", "serialization": "json_indent_2", "scope": "structured_payload"}
        if "contract_status" in result:
            bounded["contract_status"] = "unresolved"
        unresolved = bounded.get("unresolved")
        bounded["unresolved"] = (unresolved if isinstance(unresolved, list) else []) + ["响应预算已裁剪证据，完整性未确认"]
        if encoded_size(bounded) <= limit:
            return bounded
    return {"status": "unresolved", "response_truncated": True, "response_complete": False,
            "unresolved": ["响应超过预算，仅返回有界摘要"]}
