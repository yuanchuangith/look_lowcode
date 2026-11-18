from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections import Counter, defaultdict
from typing import Any

from .canvas_budget import NodeValueNotFound, node_value_page, payload_size


def validate_batch_request(
    identifier: str,
    targets: list[dict[str, Any]] | None,
    *,
    design_id: str | None,
    expected_data_sha256: str | None,
    batch_cursor: str | None,
    legacy_selectors: bool,
) -> None:
    if targets is None:
        if expected_data_sha256 is not None or batch_cursor is not None:
            raise ValueError("expected_data_sha256 and batch_cursor require targets")
        return
    if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 128:
        raise ValueError("batch identifier must be an exact action code or RefId of 1..128 characters")
    if legacy_selectors:
        raise ValueError("targets cannot be combined with legacy node, time, or C# selectors")
    if (design_id is None) != (expected_data_sha256 is None) or batch_cursor is not None and not design_id:
        raise ValueError("a batch continuation requires both design_id and expected_data_sha256")
    if design_id is not None and (not isinstance(design_id, str) or not design_id.strip() or len(design_id) > 200):
        raise ValueError("batch design_id must be 1..200 characters")
    if expected_data_sha256 is not None and (
        not isinstance(expected_data_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_data_sha256)
    ):
        raise ValueError("expected_data_sha256 must be the lowercase SHA-256 returned by the batch")
    if batch_cursor is not None:
        _read_cursor(batch_cursor)
    if not isinstance(targets, list) or not 1 <= len(targets) <= 10:
        raise ValueError("targets must contain 1..10 exact nodes")
    keys = set()
    for item in targets:
        if not isinstance(item, dict) or set(item) - {"group_key", "node_key", "value_paths"}:
            raise ValueError("batch targets accept group_key, node_key and optional value_paths")
        coordinate = (item.get("group_key"), item.get("node_key"))
        if not all(isinstance(key, str) and 1 <= len(key) <= 128 and key.strip() for key in coordinate):
            raise ValueError("each batch target requires exact group_key and node_key of 1..128 characters")
        if coordinate in keys:
            raise ValueError("duplicate batch target; combine its value_paths in one target")
        keys.add(coordinate)
        paths = item.get("value_paths", [])
        if not isinstance(paths, list) or len(paths) > 8:
            raise ValueError("value_paths must contain at most 8 parameter paths per target")
        if not all(isinstance(path, str) and len(path) <= 512 and _valid_path(path) for path in paths):
            raise ValueError("batch paths must be JSON pointers under /paramsValue of at most 512 characters")
        if len(set(paths)) != len(paths):
            raise ValueError("duplicate value path in a batch target")


def _valid_path(path: str) -> bool:
    return (path == "/paramsValue" or path.startswith("/paramsValue/")) and not re.search(r"~(?![01])", path)


def _cursor(index: int, offset: int, fingerprint: str) -> str:
    raw = json.dumps([index, offset, fingerprint], separators=(",", ":")).encode("ascii")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _read_cursor(value: str) -> tuple[int, int, str]:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", value):
        raise ValueError("invalid inspect_action batch_cursor")
    try:
        positions = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
    except (ValueError, binascii.Error) as exc:
        raise ValueError("invalid inspect_action batch_cursor") from exc
    if (not isinstance(positions, list) or len(positions) != 3
        or type(positions[0]) is not int or not 0 <= positions[0] < 80
        or type(positions[1]) is not int or positions[1] < 0
        or not isinstance(positions[2], str) or not re.fullmatch(r"[a-f0-9]{64}", positions[2])):
        raise ValueError("invalid inspect_action batch_cursor")
    return positions[0], positions[1], positions[2]


def batch_version_drift(*, target_count: int, design=None, action=None) -> dict[str, Any]:
    return {
        "action": action, "design": design, "target_count": target_count, "runtime_verified": False,
        "batch_status": "version_drift", "targets": [], "response_complete": False,
        "evidence_complete": False, "response_truncated": False, "has_more": False,
        "next_step": "Re-anchor the exact targets on the current requested copy before reading more evidence.",
    }


def inspect_action_batch(
    design: dict[str, Any],
    *,
    identifier: str,
    version: str,
    expected_design_id: str | None,
    expected_data_sha256: str | None,
    targets: list[dict[str, Any]],
    batch_cursor: str | None,
    max_output_bytes: int,
    value_limit: int,
) -> dict[str, Any]:
    identity = {key: design.get(key) for key in ("design_id", "version", "data_sha256")}
    action = {
        key: str(value)[:160] for key, value in (design.get("metadata") or {}).items()
        if key in {"ref_id", "action_code", "action_name", "action_type"} and value is not None
    }
    outer = {
        "action": action, "design": identity, "target_count": len(targets),
        "runtime_verified": False, "response_budget": {"bytes": max_output_bytes, "encoding": "utf-8"},
    }
    pin_changed = expected_design_id is not None and (
        identity["design_id"] != expected_design_id or identity["data_sha256"] != expected_data_sha256
    )
    if (identity["version"] != version or design.get("is_deleted") or not identity["design_id"]
        or not identity["data_sha256"] or pin_changed):
        return batch_version_drift(target_count=len(targets), design=identity, action=action)

    selectors = [[item["group_key"], item["node_key"], item.get("value_paths", [])] for item in targets]
    request = [identifier, action.get("ref_id"), identity, selectors]
    fingerprint = hashlib.sha256(json.dumps(request, ensure_ascii=True, sort_keys=True).encode("ascii")).hexdigest()
    start, value_offset = 0, 0
    if batch_cursor is not None:
        start, value_offset, bound = _read_cursor(batch_cursor)
        if bound != fingerprint:
            raise ValueError("batch_cursor does not match these targets or design fingerprint")

    data = design["data_json"]
    if isinstance(data, str):
        data = json.loads(data)
    groups = data.get("actionData", []) or []
    group_counts = Counter(str(group.get("key", "")) for group in groups)
    exact_target_keys = defaultdict(set)
    for group_key, node_key, _ in selectors:
        if group_counts[group_key] == 1:
            exact_target_keys[group_key].add(node_key)
    found = defaultdict(list)
    for group in groups:
        group_key = str(group.get("key", ""))
        if group_key not in exact_target_keys:
            continue
        for index, raw_node in enumerate(group.get("data", []) or []):
            node_key = str(raw_node.get("key", ""))
            if node_key in exact_target_keys[group_key]:
                found[group_key, node_key].append({
                    "canvas_line": index + 1, "element_key": str(raw_node.get("elementKey", ""))[:128],
                    "paramsValue": raw_node.get("paramsValue", {}),
                })

    entries = []
    metadata = []
    for index, (group_key, node_key, paths) in enumerate(selectors):
        matches = found[group_key, node_key]
        node = matches[0] if len(matches) == 1 else None
        status = (
            "group_not_found" if group_counts[group_key] == 0 else
            "group_ambiguous" if group_counts[group_key] > 1 else
            "node_not_found" if not matches else "node_ambiguous" if node is None else "found"
        )
        metadata.append({"target_index": index, "group_key": group_key, "node_key": node_key, "status": status})
        if node is not None:
            metadata[-1]["node"] = {key: node[key] for key in ("canvas_line", "element_key")}
        entries.extend((index, node, path) for path in (paths if node is not None and paths else [None]))
    if start >= len(entries):
        raise ValueError("batch_cursor points outside the requested targets")

    stop = start + 1 if value_offset else len(entries)

    def page(rows, next_index: int):
        more_targets = next_index < stop
        results = {}
        for target_index, detail in rows:
            target = results.setdefault(target_index, {**metadata[target_index], "values": []})
            if detail is not None:
                target["values"].append(detail)
        more_values = any(detail is not None and detail["status"] == "truncated" for _, detail in rows)
        has_more = more_targets or more_values
        result = {**outer, "batch_status": "ok", "targets": list(results.values()), "has_more": has_more,
                  "response_complete": not has_more and start == 0 and not value_offset, "response_truncated": has_more}
        result["evidence_complete"] = result["response_complete"] and all(
            item["status"] == "found" and all(value["status"] == "complete" for value in item["values"])
            for item in result["targets"]
        )
        if more_targets:
            result["next_read"] = {
                "tool": "inspect_action", "reuse_arguments": ["identifier", "version", "targets", "max_output_bytes", "value_limit"],
                "arguments": {
                    "design_id": identity["design_id"], "expected_data_sha256": identity["data_sha256"],
                    "batch_cursor": _cursor(next_index, 0, fingerprint),
                },
            }
        return result

    rows = []
    next_index = start
    for entry_index in range(start, stop):
        target_index, node, path = entries[entry_index]
        offset = value_offset if entry_index == start else 0
        count = value_limit
        while True:
            detail = None
            if offset and path is None:
                raise ValueError("batch_cursor value offset requires a parameter path")
            if path is not None:
                try:
                    value = node_value_page(node, path, offset, count)
                except NodeValueNotFound:
                    detail = {"value_path": path, "status": "path_not_found"}
                else:
                    detail = {**value, "status": "complete" if value["complete"] else "truncated"}
                    if not value["complete"]:
                        detail["value_cursor"] = _cursor(entry_index, value["next_offset"], fingerprint)
            candidate = rows + [(target_index, detail)]
            result = page(candidate, entry_index + 1)
            if payload_size(result) <= max_output_bytes:
                rows = candidate
                next_index = entry_index + 1
                break
            if rows:
                return page(rows, next_index)
            if path is None or count <= 1:
                raise ValueError("target metadata exceeds max_output_bytes")
            count = max(1, count // 2)
    return page(rows, next_index)
