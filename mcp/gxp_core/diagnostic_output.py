"""Bounded diagnostic pages, with cursors tied to the exact source evidence."""
from __future__ import annotations

import base64
import copy
import hashlib
import json

from .canvas_budget import payload_size, response_limit
from .source_budget import bounded_payload


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def diagnostic_page(records, *, identity, envelope, response_detail="summary", max_output_bytes=16384,
                    cursor=None, limit=10, summarize=lambda item: item, collection="records"):
    response_limit(max_output_bytes)
    if response_detail not in {"summary", "full"} or type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("response_detail must be summary/full; limit must be 1..50")
    snapshot = hashlib.sha256(_json(identity).encode("utf-8")).hexdigest()

    def token(offset, part=0, detail=response_detail):
        return base64.urlsafe_b64encode(json.dumps([1, snapshot, detail, offset, part], separators=(",", ":")).encode()).decode()

    offset = part = 0
    if cursor:
        try:
            version, expected, detail, offset, part = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
            if version != 1 or expected != snapshot or detail != response_detail:
                raise ValueError("DIAGNOSTIC_CURSOR_STALE")
            if type(offset) is not int or not 0 <= offset <= len(records) or type(part) is not int or part < 0:
                raise ValueError("DIAGNOSTIC_CURSOR_INVALID")
        except (TypeError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise ValueError("DIAGNOSTIC_CURSOR_STALE_OR_INVALID") from exc
    result = copy.deepcopy(envelope)
    result.update(response_detail=response_detail, snapshot_fingerprint=snapshot, total_count=len(records),
                  offset=offset, returned_count=0, next_cursor=None, has_more=False,
                  response_complete=False, evidence_complete=False,
                  conclusion_gate="read_required_details_and_all_relevant_pages_before_conclusion")
    # The envelope is metadata only; bound pathological names without sacrificing the page protocol.
    if payload_size(result) > max_output_bytes // 3:
        result = {**bounded_payload(envelope, max_output_bytes // 4), **{key: value for key, value in result.items() if key not in envelope}}
        result["envelope_complete"] = False
    result[collection] = []
    end = min(len(records), offset + limit)
    while offset < end:
        item = copy.deepcopy(records[offset]) if response_detail == "full" else summarize(copy.deepcopy(records[offset]))
        if response_detail == "summary":
            item["detail_cursor"] = token(offset, detail="full")
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
    result.update(returned_count=len(result[collection]), has_more=offset < len(records),
                  next_cursor=token(offset, part) if offset < len(records) else None,
                  response_complete=offset == len(records) and not cursor and "record_value_page" not in result,
                  evidence_complete=response_detail == "full" and offset == len(records) and not cursor and "record_value_page" not in result)
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
