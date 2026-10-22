"""Export bounded, current design evidence for a later guarded edit."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from .handoff_store import (
    HandoffError, HandoffStore, canonical_bytes, canonical_sha256, compare_targets,
    environment_scope, normalize_targets, snapshot_targets, validate_change_spec,
)
from .telemetry import stage

# Reserve room for the public tracing envelope and response flags.
READ_RESPONSE_BYTES = 63 * 1024


def _bounded_response(response: dict[str, Any]) -> dict[str, Any]:
    if len(canonical_bytes(response)) > READ_RESPONSE_BYTES:
        raise HandoffError("HANDOFF_RESPONSE_LIMIT", "Handoff response metadata exceeds 63 KiB; use an exact handoff ID or ordinary targeted inspection. The complete local record is retained.")
    return response


def fallback(exc: Exception) -> dict[str, Any]:
    return {
        "available": False, "error_code": getattr(exc, "code", "HANDOFF_UNAVAILABLE"),
        "error": str(exc) if isinstance(exc, HandoffError) else "Local handoff is unavailable; continue ordinary targeted design inspection.",
        "write_executed": False, "authorization_granted": False,
        "next_step": "Use the exact action code/RefId with ordinary inspect_action and inspect_control_flow; no session, approval or restart is required.",
    }


def _design_evidence(design: dict[str, Any]) -> dict[str, str]:
    if bool(design.get("is_deleted")) or design.get("version") not in {"draft", "published"}:
        raise HandoffError("HANDOFF_DESIGN", "Only a current nondeleted draft or published copy can be handed off")
    if not design.get("design_id") or not isinstance(design.get("data_json"), dict):
        raise HandoffError("HANDOFF_DESIGN", "Current design identity or JSON is unavailable")
    raw = design.get("data")
    checksum = hashlib.sha256(raw.encode("utf-8")).hexdigest() if isinstance(raw, str) else design.get("data_sha256")
    if not isinstance(checksum, str) or len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum):
        raise HandoffError("HANDOFF_DESIGN", "Current design content fingerprint is unavailable")
    return {"design_id": str(design["design_id"]), "data_sha256": checksum}


def export_handoff(service: Any, identifier: str, targets: list[dict[str, str]], change_spec: dict[str, Any], diagnosis_source: dict[str, str]) -> dict[str, Any]:
    try:
        targets = normalize_targets(targets)
        spec = validate_change_spec(change_spec)
        if (not isinstance(diagnosis_source, dict)
                or set(diagnosis_source) != {"version", "design_id", "data_sha256"}
                or diagnosis_source.get("version") not in {"draft", "published"}
                or not isinstance(diagnosis_source.get("design_id"), str)
                or not diagnosis_source["design_id"]
                or not isinstance(diagnosis_source.get("data_sha256"), str)
                or len(diagnosis_source["data_sha256"]) != 64
                or any(char not in "0123456789abcdef" for char in diagnosis_source["data_sha256"])):
            raise HandoffError("HANDOFF_DIAGNOSIS_SOURCE", "diagnosis_source requires the inspected current version (draft/published), exact design_id and data_sha256")
        selected = {(target["group_key"], target["node_key"]) for target in targets}
        for change in spec.get("changes", []):
            if (change.get("group_key"), change.get("node_key")) not in selected:
                raise HandoffError("HANDOFF_CHANGE_SPEC", "Each proposed change must reference an exported target")
        with stage("handoff.resolve_action"):
            matches = service.repository.resolve_action(identifier)
            if len(matches) != 1:
                raise HandoffError("HANDOFF_ACTION", "Use one exact action code or RefId; action-name search is not an edit identity")
            metadata = matches[0]
        with stage("draft.read"):
            draft = service.repository.load_design(metadata["ref_id"], version="draft", include_deleted=False)
            draft_evidence = _design_evidence(draft)
            if draft.get("version") != "draft":
                raise HandoffError("HANDOFF_DESIGN", "Editable current draft is unavailable")
        with stage("handoff.diagnosis_read"):
            source = draft if diagnosis_source["version"] == "draft" else service.repository.load_design(metadata["ref_id"], version="published", include_deleted=False)
            source_evidence = {"version": source.get("version"), **_design_evidence(source)}
            if source_evidence != diagnosis_source:
                return {
                    **fallback(HandoffError("HANDOFF_STALE_DIAGNOSIS", "The diagnosed copy changed or is historical; reverify the current copy before export")),
                    "diagnosis_source_observed": source_evidence, "draft_observed": draft_evidence,
                    "next_read": {"tool": "inspect_action", "arguments": {"identifier": metadata["ref_id"], "version": diagnosis_source["version"], "design_id": source_evidence["design_id"], "include_params": False}},
                }
        with stage("handoff.capture", count=len(targets)):
            snapshots = snapshot_targets(draft["data_json"], targets)
            diagnosed = snapshot_targets(source["data_json"], targets, allow_missing=True)
            differences = compare_targets(diagnosed, snapshots)
            config = service.database.config
            record = {
                "environment_scope": environment_scope(config),
                "action": {key: str(metadata.get(key) or "") for key in ("ref_id", "action_code", "action_name", "action_type", "page_id")},
                "draft": draft_evidence, "diagnosis_source": source_evidence,
                "targets": snapshots, "diagnosis_targets": diagnosed,
                "source_target_differences": differences, "change_spec": spec,
            }
        with stage("handoff.write", count=len(targets)):
            result = HandoffStore().write(record)
        return {
            "available": True, **result, "source_target_differences": differences,
            "diagnosis_matches_draft": source_evidence["data_sha256"] == draft_evidence["data_sha256"],
            "authorization_granted": False, "write_executed": False,
            "next_step": "Evidence was saved locally. The editor may optionally use handoff_ref or proceed with ordinary inspection. Check relevance and sufficiency first; analyze or call readonly Look tools for missing evidence. This record starts no editor session and grants no approval.",
        }
    except Exception as exc:
        return fallback(exc)


def read_handoff(handoff_id: str = "", identifier: str = "", sha256: str = "", *, target_index: int | None = None) -> dict[str, Any]:
    try:
        store = HandoffStore()
        with stage("handoff.read"):
            if not handoff_id:
                if sha256 or target_index is not None:
                    raise HandoffError("HANDOFF_ID", "Provide an exact handoff_id to read a checksum or target")
                candidates = store.list(identifier)
                return _bounded_response({"available": True, "candidates": candidates, "count": len(candidates), "selection_required": True, "authorization_granted": False, "next_step": "Choose an explicit handoff_id and sha256; do not automatically select the newest record."})
            record = store.read(handoff_id, sha256)
        checksum = canonical_sha256(record)
        if identifier and identifier not in {record["action"]["ref_id"], record["action"]["action_code"]}:
            raise HandoffError("HANDOFF_ACTION", "Handoff belongs to a different action")
        result = {"available": True, "handoff_ref": {"handoff_id": handoff_id, "sha256": checksum}, "authorization_granted": False, "requires_current_scope_confirmation": True}
        if target_index is not None:
            if type(target_index) is not int or not 0 <= target_index < len(record["targets"]):
                raise HandoffError("HANDOFF_TARGETS", "target_index is outside this record")
            result.update(target_index=target_index, target=record["targets"][target_index], diagnosis_target=record["diagnosis_targets"][target_index])
        else:
            result["record"] = record
        if len(canonical_bytes(result)) <= READ_RESPONSE_BYTES - 64:
            return {**result, "response_complete": True}
        # Preserve every byte on disk; return an explicit continuation, not a
        # silently shortened parameter record or generated-code dump.
        summary = store.summary(record, checksum)
        if target_index is None:
            return _bounded_response({"available": True, "handoff_ref": result["handoff_ref"], "summary": summary, "change_spec": record["change_spec"], "response_complete": False, "authorization_granted": False,
                    "omitted": ["targets", "diagnosis_targets"], "next_read": [{"tool": "read_edit_handoff", "arguments": {"handoff_id": handoff_id, "sha256": checksum, "target_index": index}} for index in range(len(record["targets"]))]})
        target = record["targets"][target_index]
        return _bounded_response({"available": True, "handoff_ref": result["handoff_ref"], "summary": summary, "target": {key: value for key, value in target.items() if key != "paramsValue"}, "response_complete": False, "authorization_granted": False,
                "omitted": ["target.paramsValue", "diagnosis_target"], "next_read": {"tool": "inspect_action", "arguments": {"identifier": record["action"]["ref_id"], "version": "draft", "design_id": record["draft"]["design_id"], "group": target["group_key"], "node_key": target["node_key"], "include_params": True}},
                "next_step": "Use the existing bounded inspect_action/node-value continuation and recheck the draft fingerprint; the stored full parameters have not been truncated."})
    except (HandoffError, ValueError, TypeError, OSError, KeyError) as exc:
        return fallback(exc)
