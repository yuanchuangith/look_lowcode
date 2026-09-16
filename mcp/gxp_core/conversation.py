from __future__ import annotations

import copy
import json
import re
from typing import Any


CONTEXT_FIELDS = {"goal", "anchors", "rules", "exclusions", "field_meanings", "chosen_approach", "findings", "corrections"}
RECHECK = re.compile(r"改了|修改|发布|复核|再看|解决了|recheck|review again|published|fixed", re.IGNORECASE)


def conversation_context(value: dict[str, Any] | None, text: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(
            "context must be a JSON object, not " + type(value).__name__
            + "; put the current request in text and omit context on a first call"
        )
    unknown = set(value) - CONTEXT_FIELDS
    if unknown:
        raise ValueError(
            "context has unsupported fields: " + ", ".join(sorted(map(str, unknown)))
            + ". Allowed fields: " + ", ".join(sorted(CONTEXT_FIELDS))
            + ". For follow-ups, pass conversation_context.record, not the whole response"
        )
    try:
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValueError("context must be finite JSON") from exc
    if len(encoded.encode("utf-8")) > 32768:
        raise ValueError("context exceeds 32 KiB")
    anchors = value.get("anchors", [])
    if not isinstance(anchors, list) or len(anchors) > 8 or any(not isinstance(anchor, dict) for anchor in anchors):
        raise ValueError("context.anchors must contain at most eight objects")
    for anchor in anchors:
        if any(not isinstance(anchor.get(key, ""), str) for key in ("action_code", "ref_id", "page", "group_key", "node_key", "design_id")):
            raise ValueError("anchor identities must be strings")
    return {
        "record": copy.deepcopy(value),
        "evidence_level": "user_supplied_context_not_database_evidence",
        "persistence": "none",
        "refresh_required": bool(RECHECK.search(text)),
        "precedence": "current_explicit_identity_and_corrections_before_context",
        "finding_policy": "reported_fixed_is_pending_review; static_and_runtime_verification_are_separate",
    }


def anchor_identifiers(context: dict[str, Any] | None) -> list[str]:
    return list(dict.fromkeys(
        anchor.get("ref_id") or anchor.get("action_code")
        for anchor in ((context or {}).get("record", {}).get("anchors") or [])
        if anchor.get("ref_id") or anchor.get("action_code")
    ))
