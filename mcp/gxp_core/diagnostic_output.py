"""Bounded diagnostic pages, with cursors tied to the exact source evidence."""
from __future__ import annotations

import base64
import copy
import hashlib
import json

from .canvas_budget import payload_size, response_limit
from .source_budget import bounded_payload
from .evidence_guidance import guidance


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def _continuation_guidance(result, tool, collection):
    if not tool or result["evidence_complete"]:
        return
    arguments = {"response_detail": result["response_detail"]}
    cursor = result["next_cursor"]
    if not cursor and result["response_detail"] == "summary":
        arguments["response_detail"] = "full"
        cursor = next((item.get("detail_cursor") for item in result.get(collection, []) if item.get("detail_cursor")), None)
    if cursor:
        arguments["cursor"] = cursor
    next_read = {"tool": tool, "arguments": arguments, "reuse_original_arguments": True} if cursor or result["response_detail"] == "summary" else None
    result.update(guidance("DIAGNOSTIC_EVIDENCE_INCOMPLETE", "diagnostic_completeness", next_read=next_read,
                           can_continue=("returned_locations_and_counts",), stop_reason="required_details_unread"))


def diagnostic_page(records, *, identity, envelope, response_detail="summary", max_output_bytes=16384,
                    cursor=None, limit=10, summarize=lambda item: item, collection="records", snapshot_fingerprint=None,
                    continuation_tool=None):
    response_limit(max_output_bytes)
    if response_detail not in {"summary", "full"} or type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("response_detail must be summary/full; limit must be 1..50")
    snapshot = snapshot_fingerprint or hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()

    def token(offset, part=0, detail=response_detail, envelope_part=-1):
        state = [2, snapshot, detail, offset, part, envelope_part]
        return base64.urlsafe_b64encode(json.dumps(state, separators=(",", ":")).encode()).decode()

    offset = part = 0
    envelope_part = None
    if cursor:
        try:
            state = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
            if not isinstance(state, list):
                raise ValueError("DIAGNOSTIC_CURSOR_INVALID")
            if len(state) == 5 and state[0] == 1:
                version, expected, detail, offset, part = state
            elif len(state) == 6 and state[0] == 2:
                version, expected, detail, offset, part, envelope_part = state
                if type(envelope_part) is not int or envelope_part < -1:
                    raise ValueError("DIAGNOSTIC_CURSOR_INVALID")
            else:
                raise ValueError("DIAGNOSTIC_CURSOR_INVALID")
            if expected != snapshot or detail != response_detail:
                raise ValueError("DIAGNOSTIC_CURSOR_STALE")
            if type(offset) is not int or not 0 <= offset <= len(records) or type(part) is not int or part < 0:
                raise ValueError("DIAGNOSTIC_CURSOR_INVALID")
            if offset == len(records) and part:
                raise ValueError("DIAGNOSTIC_CURSOR_INVALID")
        except (TypeError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("DIAGNOSTIC_CURSOR_STALE_OR_INVALID") from exc
    protocol = dict(response_detail=response_detail, snapshot_fingerprint=snapshot, total_count=len(records),
                    offset=offset, returned_count=0, next_cursor=None, has_more=False,
                    response_complete=False, evidence_complete=False,
                    conclusion_gate="read_required_details_and_all_relevant_pages_before_conclusion")
    metadata = copy.deepcopy(envelope)
    if payload_size({**metadata, **protocol}) > max_output_bytes // 3:
        metadata = bounded_payload(metadata, max_output_bytes // 4)
    envelope_truncated = metadata != envelope
    if envelope_part is None or envelope_truncated and envelope_part == -1:
        envelope_part = 0 if envelope_truncated else -1
    protocol["envelope_complete"] = not envelope_truncated

    # Once the records are exhausted, the same continuation recovers all omitted
    # metadata. A last fragment ends collection, not the completeness gate.
    if cursor and offset == len(records) and envelope_part >= 0:
        envelope_text = _json(envelope)
        if envelope_part >= len(envelope_text):
            raise ValueError("DIAGNOSTIC_CURSOR_STALE_OR_INVALID")
        result = {**protocol, collection: [], "response_truncated": True, "envelope_complete": False}
        chunk = envelope_text[envelope_part:envelope_part + max_output_bytes // 4]
        value_page = {"offset": envelope_part, "text": chunk, "total_characters": len(envelope_text),
                      "encoding": "json", "offset_unit": "unicode_code_points",
                      "envelope_sha256": hashlib.sha256(envelope_text.encode("utf-8")).hexdigest(),
                      "continuation_complete": False}
        result["envelope_value_page"] = value_page
        while payload_size(result) > max_output_bytes - 1024 and len(chunk) > 1:
            chunk = chunk[:len(chunk) // 2]
            value_page["text"] = chunk
        envelope_part += len(chunk)
        more = envelope_part < len(envelope_text)
        value_page["continuation_complete"] = not more
        result.update(has_more=more, next_cursor=token(offset, envelope_part=envelope_part) if more else None)
        _continuation_guidance(result, continuation_tool, collection)
        if payload_size(result) > max_output_bytes:
            raise ValueError("DIAGNOSTIC_ENVELOPE_TOO_LARGE")
        return result

    result = {**metadata, **protocol}
    result[collection] = []
    end = min(len(records), offset + limit)
    while offset < end:
        item = copy.deepcopy(records[offset]) if response_detail == "full" else summarize(copy.deepcopy(records[offset]))
        if response_detail == "summary":
            item["detail_cursor"] = token(offset, detail="full", envelope_part=envelope_part)
        candidate = {**result, collection: result[collection] + [item]}
        if part == 0 and payload_size(candidate) <= max_output_bytes - 1024:
            result[collection].append(item)
            offset += 1
            continue
        if result[collection]:
            break
        text = _json(item)
        if part >= len(text):
            raise ValueError("DIAGNOSTIC_CURSOR_INVALID")
        size = min(len(text) - part, max_output_bytes // 4)
        chunk = text[part:part + size]
        result["record_value_page"] = {"record_index": offset, "offset": part, "text": chunk,
                                       "total_characters": len(text), "encoding": "json"}
        while payload_size(result) > max_output_bytes - 1024 and len(chunk) > 1:
            chunk = chunk[:len(chunk) // 2]
            result["record_value_page"]["text"] = chunk
        part += len(chunk)
        if part == len(text):
            offset += 1
            part = 0
        break
    more = offset < len(records) or envelope_part >= 0
    complete = not envelope_truncated and offset == len(records) and not cursor and "record_value_page" not in result
    result.update(returned_count=len(result[collection]), has_more=more,
                  next_cursor=token(offset, part, envelope_part=envelope_part) if more else None,
                  response_complete=complete,
                  evidence_complete=response_detail == "full" and complete)
    _continuation_guidance(result, continuation_tool, collection)
    if payload_size(result) > max_output_bytes:
        raise ValueError("DIAGNOSTIC_ENVELOPE_TOO_LARGE")
    return result


def filter_summary(item):
    result = {key: item[key] for key in ("group_key", "node_key", "canvas_row", "internal_index", "component",
              "execution_stage", "execution_order", "may_overwrite_earlier_filter", "params_read") if key in item}
    result["parent_count"] = len(item.get("parent_conditions", []))
    result["filter_count"] = len((item.get("filter_facts") or {}).get("filters", []))
    result["details_omitted"] = True
    return result


def exception_summary(item):
    result = {key: item[key] for key in ("action", "design_id", "version", "published_at", "runtime_snapshot_role",
              "eligible_runtime_evidence", "is_deleted", "evidence_score", "data_sha256", "csharp_sha256") if key in item}
    result["matching_canvas_nodes"] = [{key: node[key] for key in ("group_key", "node_key", "canvas_row") if key in node}
                                        for node in item.get("matching_canvas_nodes", [])[:10]]
    result["matching_node_count"] = len(item.get("matching_canvas_nodes", []))
    result["sync_status"] = (item.get("current_copy_sync") or {}).get("sync_status")
    result["called_history_count"] = len(item.get("called_action_exception_history", []))
    result["details_omitted"] = True
    return result
