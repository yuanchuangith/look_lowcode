"""Local diagnostic metadata; never reads or writes a business database."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .cpm_config import _atomic_json
from .relation_policy import _PolicyFileLock, utc_now
from .schema_config import schema_runtime_root

GRAPH_VERSION = 2
MAX_GRAPH_BYTES = 16 * 1024 * 1024
MAX_RELATION_BYTES = 64 * 1024
MAX_RESPONSE_BYTES = 256 * 1024
CONFIRMED_STATUSES = {"confirmed_static", "confirmed_data", "runtime_verified"}
LIFECYCLE_STATUSES = {"superseded", "stale", "invalidated"}
REASON_CODES = {"user_confirmed_incorrect", "published_design_changed", "evidence_invalidated"}
HASH_RE = re.compile(r"^[a-f0-9]{64}$")
# Text is a short human-written summary, never a tool response, source or record.
UNSAFE_TEXT = re.compile(
    r"(?i)(?:password|passwd|pwd|token|secret|connectionstring|server|host|user id|uid)"
    r"\s*[=:]|bearer\s+\S+|://|-----BEGIN|\b(?:namespace|using)\s+[\w.]+[;{]"
    r"|\b(?:public|private|protected)\s+(?:static\s+)?\w+\s+\w+\s*[({]"
    r"|\b(?:return|var)\s+[^;]+;|[{}]|(?:密码|令牌|连接串|记录值)\s*[:：=]"
)
RELATION_FIELDS = {
    "relation_key", "environment", "conclusion", "business_keywords", "status",
    "anchors", "published_design_id", "tables", "views", "fields", "calls", "nodes", "edges",
    "evidence", "relation_id", "evidence_fingerprint",
}
ANCHOR_FIELDS = {"id", "action_code", "ref_id", "page", "group_key", "node_key",
                 "canvas_row", "published_design_id"}
NODE_FIELDS = {"id", "kind", "label", "anchor_id", "table", "view", "field"}
EDGE_FIELDS = {"source", "target", "kind", "label", "evidence_ids"}
EVIDENCE_FIELDS = {"id", "type", "fingerprint", "summary", "anchor_ids"}
EVIDENCE_TYPES = {"published_design", "control_flow", "schema", "readonly_data", "runtime"}


class BusinessLogicGraphError(RuntimeError):
    pass


class GraphValidationError(ValueError):
    pass


def default_graph_path() -> Path:
    return schema_runtime_root() / "business-logic-graph.json"


def _encoded(value: Any) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                           allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise GraphValidationError("GRAPH_INVALID_JSON") from exc


def _object(value: Any, allowed: set[str], required: set[str]) -> dict:
    if not isinstance(value, dict) or set(value) - allowed or required - set(value):
        # Never echo rejected keys/values (they may themselves contain secrets).
        raise GraphValidationError("GRAPH_UNSUPPORTED_OR_MISSING_FIELDS")
    return value


def _text(value: Any, max_chars: int = 256) -> str:
    if (not isinstance(value, str) or not value.strip() or len(value) > max_chars
            or any(ord(c) < 32 for c in value) or UNSAFE_TEXT.search(value)):
        raise GraphValidationError("GRAPH_UNSAFE_OR_INVALID_TEXT")
    return value.strip()


def _hash(value: Any) -> str:
    if not isinstance(value, str) or not HASH_RE.fullmatch(value):
        raise GraphValidationError("GRAPH_INVALID_FINGERPRINT")
    return value


def _list(value: Any, maximum: int, minimum: int = 0) -> list:
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise GraphValidationError("GRAPH_INVALID_COLLECTION")
    return value


def _strings(value: Any, maximum: int, minimum: int = 0) -> list[str]:
    return sorted({_text(x) for x in _list(value, maximum, minimum)})


def _digest(value: Any) -> str:
    return hashlib.sha256(_encoded(value)).hexdigest()


def _unique_ids(items: list[dict]) -> set[str]:
    ids = {item["id"] for item in items}
    if len(ids) != len(items):
        raise GraphValidationError("GRAPH_DUPLICATE_ID")
    return ids


def render_mermaid(nodes: list[dict], edges: list[dict]) -> str:
    # User-controlled IDs never enter Mermaid syntax. Encode every punctuation
    # character, including entity prefixes, quotes, pipes and angle brackets.
    def label(text: str) -> str:
        return "".join(c if c.isalnum() or c == " " else f"#{ord(c)};" for c in text)
    ids = {node["id"]: f"n{i}" for i, node in enumerate(nodes)}
    lines = ["flowchart TD"]
    lines.extend(f'  {ids[n["id"]]}["{label(n["label"])}"]' for n in nodes)
    lines.extend(f'  {ids[e["source"]]} -->|"{label(e["label"])}"| {ids[e["target"]]}'
                 for e in edges)
    return "\n".join(lines)


def validate_relation(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise GraphValidationError("GRAPH_UNSUPPORTED_OR_MISSING_FIELDS")
    if len(_encoded(raw)) > MAX_RELATION_BYTES:
        raise GraphValidationError("GRAPH_PAYLOAD_TOO_LARGE")
    _object(raw, RELATION_FIELDS, RELATION_FIELDS - {"relation_id", "evidence_fingerprint", "calls"})
    if _text(raw["status"]) not in CONFIRMED_STATUSES:
        raise GraphValidationError("GRAPH_CONFIRMED_STATUS_REQUIRED")
    if _text(raw["environment"]) not in {"development", "test", "production"}:
        raise GraphValidationError("GRAPH_ENVIRONMENT_REQUIRED")
    result = {key: _text(raw[key], 1000 if key == "conclusion" else 256)
              for key in ("relation_key", "environment", "conclusion", "status", "published_design_id")}
    for key in ("business_keywords", "tables", "views", "fields"):
        result[key] = _strings(raw[key], 50, 1 if key == "business_keywords" else 0)
    result["calls"] = _strings(raw.get("calls", []), 100)
    anchors = []
    for item in _list(raw["anchors"], 30, 1):
        _object(item, ANCHOR_FIELDS, ANCHOR_FIELDS)
        row = item["canvas_row"]
        if type(row) is not int or row < 1:
            raise GraphValidationError("GRAPH_INVALID_CANVAS_ROW")
        anchors.append({key: row if key == "canvas_row" else _text(item[key]) for key in ANCHOR_FIELDS})
    anchor_ids = _unique_ids(anchors)
    if result["published_design_id"] != anchors[0]["published_design_id"]:
        raise GraphValidationError("GRAPH_PRIMARY_DESIGN_MISMATCH")
    designs: dict[str, str] = {}
    for a in anchors:
        if a["ref_id"] in designs and designs[a["ref_id"]] != a["published_design_id"]:
            raise GraphValidationError("GRAPH_CONFLICTING_DESIGNS")
        designs[a["ref_id"]] = a["published_design_id"]
    nodes = []
    for item in _list(raw["nodes"], 60, 2):
        _object(item, NODE_FIELDS, {"id", "kind", "label"})
        node = {key: _text(value) for key, value in item.items()}
        if node["kind"] not in {"action", "node", "table", "view", "field", "report"}:
            raise GraphValidationError("GRAPH_INVALID_NODE_KIND")
        if "anchor_id" in node and node["anchor_id"] not in anchor_ids:
            raise GraphValidationError("GRAPH_UNKNOWN_ANCHOR")
        if node["kind"] in {"action", "node"} and "anchor_id" not in node:
            raise GraphValidationError("GRAPH_NODE_ANCHOR_REQUIRED")
        if node["kind"] in {"table", "view", "field"} and node["kind"] not in node:
            raise GraphValidationError("GRAPH_DATASET_ANCHOR_REQUIRED")
        nodes.append(node)
    node_ids = _unique_ids(nodes)
    evidence = []
    for item in _list(raw["evidence"], 60, 1):
        _object(item, EVIDENCE_FIELDS, EVIDENCE_FIELDS)
        proof = {"id": _text(item["id"]), "type": _text(item["type"]),
                 "fingerprint": _hash(item["fingerprint"]), "summary": _text(item["summary"], 1000),
                 "anchor_ids": _strings(item["anchor_ids"], 30, 1)}
        if proof["type"] not in EVIDENCE_TYPES or not set(proof["anchor_ids"]) <= anchor_ids:
            raise GraphValidationError("GRAPH_INVALID_EVIDENCE")
        evidence.append(proof)
    evidence_ids = _unique_ids(evidence)
    for anchor_id in anchor_ids:
        kinds = {e["type"] for e in evidence if anchor_id in e["anchor_ids"]}
        required = {"published_design", "control_flow"}
        if result["status"] in {"confirmed_data", "runtime_verified"}:
            required.add("readonly_data")
        if result["status"] == "runtime_verified":
            required.add("runtime")
        if not required <= kinds or not kinds & {"schema", "readonly_data"}:
            raise GraphValidationError("GRAPH_INSUFFICIENT_EVIDENCE")
    edges = []
    for item in _list(raw["edges"], 120, 1):
        _object(item, EDGE_FIELDS, EDGE_FIELDS)
        edge = {key: _text(item[key]) for key in EDGE_FIELDS - {"evidence_ids"}}
        edge["evidence_ids"] = _strings(item["evidence_ids"], 60, 1)
        if (edge["source"] not in node_ids or edge["target"] not in node_ids
                or not set(edge["evidence_ids"]) <= evidence_ids):
            raise GraphValidationError("GRAPH_DANGLING_EDGE")
        if edge["kind"] not in {"calls", "writes", "reads", "displays", "flows_to"}:
            raise GraphValidationError("GRAPH_INVALID_EDGE_KIND")
        endpoint_anchors = {n["anchor_id"] for n in nodes
                            if n["id"] in {edge["source"], edge["target"]} and "anchor_id" in n}
        supported = {a for e in evidence if e["id"] in edge["evidence_ids"] for a in e["anchor_ids"]}
        if not endpoint_anchors <= supported:
            raise GraphValidationError("GRAPH_EDGE_EVIDENCE_MISMATCH")
        edges.append(edge)
    if {e[k] for e in edges for k in ("source", "target")} != node_ids:
        raise GraphValidationError("GRAPH_UNCONNECTED_NODE")
    # Anchor order identifies the primary action; other collections are sets.
    anchors = anchors[:1] + sorted(anchors[1:], key=lambda x: x["id"])
    result.update(anchors=anchors, nodes=sorted(nodes, key=lambda x: x["id"]),
                  edges=sorted(edges, key=lambda x: _encoded(x)),
                  evidence=sorted(evidence, key=lambda x: x["id"]))
    relation_id = _digest([result["environment"], result["relation_key"], anchors[0]["ref_id"]])
    fingerprint = _digest({k: result[k] for k in (
        "published_design_id", "anchors", "nodes", "edges", "calls", "evidence")})
    if "relation_id" in raw and _hash(raw["relation_id"]) != relation_id:
        raise GraphValidationError("GRAPH_RELATION_ID_MISMATCH")
    if "evidence_fingerprint" in raw and _hash(raw["evidence_fingerprint"]) != fingerprint:
        raise GraphValidationError("GRAPH_FINGERPRINT_MISMATCH")
    result.update(relation_id=relation_id, evidence_fingerprint=fingerprint,
                  mermaid=render_mermaid(result["nodes"], result["edges"]))
    if len(_encoded(result)) > MAX_RELATION_BYTES:
        raise GraphValidationError("GRAPH_PAYLOAD_TOO_LARGE")
    return result


def _empty_document() -> dict:
    return {"version": GRAPH_VERSION, "relations": [], "audit": [],
            "migration": {"attempted": False, "imported": 0, "skipped": 0, "rejected": 0}}


class BusinessLogicGraphStore:
    def __init__(self, path: Path | None = None, *, lock_timeout_seconds: float = 5):
        self.path = (path or default_graph_path()).resolve()
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.lock_timeout_seconds = lock_timeout_seconds

    def _write(self, document: dict) -> None:
        if (len(_encoded(document)) > MAX_GRAPH_BYTES or len(document["relations"]) > 10000
                or len(document["audit"]) > 100000):
            raise BusinessLogicGraphError("GRAPH_TOO_LARGE")
        _atomic_json(self.path, document)

    @staticmethod
    def _audit(document: dict, action: str, relation: dict, reason: str = "") -> None:
        document["audit"].append({"action": action, "relation_id": relation["relation_id"],
                                  "revision": relation["revision"], "reason": reason,
                                  "created_at": utc_now()})

    def _upsert(self, document: dict, relation: dict) -> dict:
        prior = [r for r in document["relations"] if r["relation_id"] == relation["relation_id"]]
        active = next((r for r in reversed(prior) if r["lifecycle"] == "active"), None)
        if active and all(active.get(k) == v for k, v in relation.items()):
            return {"written": False, "idempotent": True, "relation": copy.deepcopy(active)}
        for old in prior:
            if old["lifecycle"] == "active":
                old["lifecycle"] = "superseded"
                self._audit(document, "superseded", old, "new_confirmed_evidence")
        # One confirmed publication change also stales other conclusions that
        # depend on that same action, including a callee in a multi-action chain.
        designs = {a["ref_id"]: a["published_design_id"] for a in relation["anchors"]}
        for old in document["relations"]:
            if (old["lifecycle"] == "active" and old["environment"] == relation["environment"]
                    and any(a["ref_id"] in designs and designs[a["ref_id"]] != a["published_design_id"]
                            for a in old["anchors"])):
                old["lifecycle"] = "stale"
                self._audit(document, "stale", old, "published_design_changed")
        new = {**relation, "revision": max((r["revision"] for r in prior), default=0) + 1,
               "lifecycle": "active", "created_at": utc_now()}
        document["relations"].append(new)
        self._audit(document, "upsert", new)
        return {"written": True, "idempotent": False, "relation": copy.deepcopy(new)}

    def _migrate(self, legacy: Any) -> dict:
        if isinstance(legacy, list):
            records = legacy
        elif isinstance(legacy, dict) and legacy.get("version") in (None, 0, 1):
            records = legacy.get("relations", legacy.get("records"))
        else:
            raise BusinessLogicGraphError("GRAPH_UNSUPPORTED_VERSION")
        if not isinstance(records, list):
            raise BusinessLogicGraphError("GRAPH_MIGRATION_FAILED")
        document = _empty_document()
        migration = document["migration"]
        migration["attempted"] = True
        for item in records:
            if (not isinstance(item, dict) or not isinstance(item.get("status"), str)
                    or item["status"] not in CONFIRMED_STATUSES):
                migration["skipped"] += 1
                continue
            try:
                # Legacy record must meet today's evidence/sensitive-data gates.
                relation = validate_relation(item)
            except (GraphValidationError, TypeError):
                migration["rejected"] += 1
                continue
            migration["imported"] += int(self._upsert(document, relation)["written"])
        self._write(document)  # atomic; failed migration leaves the original untouched
        return document

    def _read(self) -> dict:
        try:
            with self.path.open("rb") as stream:
                data = stream.read(MAX_GRAPH_BYTES + 1)
        except FileNotFoundError:
            return _empty_document()
        if len(data) > MAX_GRAPH_BYTES:
            raise BusinessLogicGraphError("GRAPH_TOO_LARGE")
        try:
            document = json.loads(data.decode("utf-8-sig"))
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise BusinessLogicGraphError("GRAPH_CORRUPT") from exc
        if not isinstance(document, dict) or document.get("version") != GRAPH_VERSION:
            return self._migrate(document)
        # Validate every saved record before returning anything from disk.
        try:
            _object(document, {"version", "relations", "audit", "migration"},
                    {"version", "relations", "audit", "migration"})
            _list(document["audit"], 100000)
            _object(document["migration"], {"attempted", "imported", "skipped", "rejected"},
                    {"attempted", "imported", "skipped", "rejected"})
            migration = document["migration"]
            if (type(migration["attempted"]) is not bool
                    or any(type(migration[k]) is not int or migration[k] < 0
                           for k in ("imported", "skipped", "rejected"))):
                raise GraphValidationError("GRAPH_INVALID_MIGRATION")
            seen: set[tuple[str, int]] = set()
            active: set[str] = set()
            for record in _list(document["relations"], 10000):
                _object(record, RELATION_FIELDS | {"mermaid", "revision", "lifecycle", "created_at"},
                        RELATION_FIELDS | {"mermaid", "revision", "lifecycle", "created_at"})
                clean = validate_relation({k: record[k] for k in RELATION_FIELDS})
                if any(record[k] != v for k, v in clean.items()):
                    raise GraphValidationError("GRAPH_RECORD_MISMATCH")
                if type(record["revision"]) is not int or record["revision"] < 1:
                    raise GraphValidationError("GRAPH_INVALID_REVISION")
                _text(record["created_at"])
                if record["lifecycle"] not in LIFECYCLE_STATUSES | {"active"}:
                    raise GraphValidationError("GRAPH_INVALID_LIFECYCLE")
                key = (record["relation_id"], record["revision"])
                if key in seen or record["lifecycle"] == "active" and key[0] in active:
                    raise GraphValidationError("GRAPH_DUPLICATE_REVISION")
                seen.add(key)
                if record["lifecycle"] == "active":
                    active.add(key[0])
            for entry in document["audit"]:
                _object(entry, {"action", "relation_id", "revision", "reason", "created_at"},
                        {"action", "relation_id", "revision", "reason", "created_at"})
                _hash(entry["relation_id"])
                if (_text(entry["action"]) not in {"upsert", "superseded", "stale", "invalidated"}
                        or entry["reason"] not in REASON_CODES | {"", "new_confirmed_evidence"}
                        or type(entry["revision"]) is not int or entry["revision"] < 1):
                    raise GraphValidationError("GRAPH_INVALID_AUDIT")
                _text(entry["created_at"])
        except (ValueError, TypeError, KeyError) as exc:
            raise BusinessLogicGraphError("GRAPH_CORRUPT") from exc
        return document

    def _transaction(self, operation):
        try:
            with _PolicyFileLock(self.lock_path, self.lock_timeout_seconds):
                return operation(self._read())
        except TimeoutError as exc:
            raise BusinessLogicGraphError("GRAPH_LOCK_TIMEOUT") from exc
        except OSError as exc:
            raise BusinessLogicGraphError("GRAPH_IO_ERROR") from exc

    def read(self) -> dict:
        """Read and validate the cache under the same lock used for writes."""
        return self._transaction(copy.deepcopy)

    def upsert(self, relation: dict) -> dict:
        clean = validate_relation(relation)
        def operation(document):
            result = self._upsert(document, clean)
            if result["written"]:
                self._write(document)
            return result
        return self._transaction(operation)

    def invalidate(self, relation_id: str, *, reason: str) -> dict:
        _hash(relation_id)
        if _text(reason) not in REASON_CODES:
            raise GraphValidationError("GRAPH_INVALID_REASON")
        def operation(document):
            changed = 0
            for record in document["relations"]:
                if record["relation_id"] == relation_id and record["lifecycle"] == "active":
                    record["lifecycle"] = "invalidated" if reason == "user_confirmed_incorrect" else "stale"
                    self._audit(document, record["lifecycle"], record, reason)
                    changed += 1
            if changed:
                self._write(document)
            return {"relation_id": relation_id, "changed": changed}
        return self._transaction(operation)

    def search(self, *, query: str | None = None, action: str | None = None,
               page: str | None = None, table: str | None = None, field: str | None = None,
               status: str | None = None, environment: str = "development", limit: int = 20,
               current_published_designs: dict[str, str] | None = None,
               relation_id: str | None = None,
               current_evidence_fingerprints: dict[str, str] | None = None) -> dict:
        filters = {k: _text(v).casefold() for k, v in (
            ("query", query), ("action", action), ("page", page), ("table", table),
            ("field", field)) if v is not None}
        if (status is not None and _text(status) not in CONFIRMED_STATUSES | LIFECYCLE_STATUSES
                or _text(environment) not in {"development", "test", "production"}
                or type(limit) is not int or not 1 <= limit <= 50):
            raise GraphValidationError("GRAPH_INVALID_SEARCH")
        designs = {} if current_published_designs is None else current_published_designs
        fingerprints = {} if current_evidence_fingerprints is None else current_evidence_fingerprints
        for mapping in (designs, fingerprints):
            if not isinstance(mapping, dict) or len(mapping) > 60:
                raise GraphValidationError("GRAPH_INVALID_CURRENT_EVIDENCE")
            for k, v in mapping.items():
                _text(k)
                _text(v)
        if relation_id is not None:
            _hash(relation_id)
        if fingerprints and relation_id is None:
            raise GraphValidationError("GRAPH_RELATION_ID_REQUIRED")
        for fingerprint in fingerprints.values():
            _hash(fingerprint)
        def operation(document):
            changed = False
            matches = []
            for record in reversed(document["relations"]):
                if record["environment"] != environment:
                    continue
                if record["lifecycle"] == "active":
                    design_changed = any(a["ref_id"] in designs and designs[a["ref_id"]] != a["published_design_id"]
                                         for a in record["anchors"])
                    proof_changed = record["relation_id"] == relation_id and any(
                        e["id"] in fingerprints and fingerprints[e["id"]] != e["fingerprint"]
                        for e in record["evidence"])
                    if design_changed or proof_changed:
                        record["lifecycle"] = "stale"
                        self._audit(document, "stale", record,
                                    "published_design_changed" if design_changed else "evidence_invalidated")
                        changed = True
                if relation_id and record["relation_id"] != relation_id:
                    continue
                if status in LIFECYCLE_STATUSES:
                    if record["lifecycle"] != status:
                        continue
                elif record["lifecycle"] != "active" or status and record["status"] != status:
                    continue
                searchable = {
                    "query": " ".join([record["conclusion"], *record["business_keywords"],
                                      *record["tables"], *record["views"], *record["fields"],
                                      *[str(v) for a in record["anchors"] for v in a.values()]]),
                    "action": " ".join(a["action_code"] + " " + a["ref_id"] for a in record["anchors"]),
                    "page": " ".join(a["page"] for a in record["anchors"]),
                    "table": " ".join(record["tables"] + record["views"]),
                    "field": " ".join(record["fields"]),
                }
                if all(all(term in searchable[k].casefold() for term in v.split())
                       for k, v in filters.items()):
                    matches.append(record)
            if changed:
                self._write(document)
            result = {"available": True, "source": "local_diagnostic_cache",
                      "must_reverify_current_published_copy": True,
                      "reverification": "必须重新核对当前发布副本、动作身份、控制流及当前只读证据；历史图不能直接作为本次结论。",
                      "migration": document["migration"], "matched_count": len(matches),
                      "relations": [], "count": 0, "truncated": False}
            for record in matches[:limit]:
                result["relations"].append(record)
                if len(_encoded(result)) > MAX_RESPONSE_BYTES:
                    result["relations"].pop()
                    break
            result["count"] = len(result["relations"])
            result["truncated"] = result["count"] < len(matches)
            return copy.deepcopy(result)
        return self._transaction(operation)
