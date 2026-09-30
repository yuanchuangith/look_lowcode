from __future__ import annotations

import re

from .business_logic_graph import (
    CONFIRMED_STATUSES, GraphValidationError, _digest, _encoded, _hash,
    _list, _object, _strings, _text, validate_relation,
)

IDENTITIES = {
    "action": {"ref_id"}, "node": {"ref_id", "group_key", "node_key"},
    "page": {"platform_id"}, "workflow": {"platform_id"},
    "business_object": {"business_key"}, "report": {"page_id", "component_id"},
    "table": {"datasource", "schema", "name"}, "view": {"datasource", "schema", "name"},
    "field": {"datasource", "schema", "owner_kind", "owner", "column"},
    "api": {"repository", "method", "route"}, "service": {"repository", "symbol"},
}
FACT_KINDS = {"calls", "triggers", "references", "generates", "writes", "reads",
              "transforms", "displays", "depends_on", "associated_with", "flows_to",
              "contains", "belongs_to"}
STRUCTURAL_KINDS = {"contains", "belongs_to"}
DATA_KINDS = {"generates", "writes", "reads", "transforms", "displays", "flows_to"}
PROOF_TYPES = {"published_design", "control_flow", "schema", "readonly_data", "runtime",
               "source_static", "cpm_catalog", "schema_catalog"}
DEPENDENCY_KINDS = {"action", "schema", "source", "catalog"}
MAX_OBSERVATION_BYTES = 128 * 1024


def stable_identity(value: str) -> str:
    value = _text(value)
    return value.lower() if re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", value) else value


def route_identity(value: str) -> str:
    if not isinstance(value, str) or len(value) > 256:
        raise GraphValidationError("GRAPH_INVALID_ROUTE")
    placeholder = r"\{\*{0,2}[A-Za-z_][\w]*(?::[A-Za-z_][\w]*(?:\([0-9,]+\))?)*\??\}"
    checked = re.sub(placeholder, "parameter", value)
    _text(checked)
    if not re.fullmatch(r"[\w./\[\]-]+", checked):
        raise GraphValidationError("GRAPH_INVALID_ROUTE")
    return "/" + value.lstrip("/")


def namespace(scope: str, environment: str) -> tuple[str, str]:
    scope = _text(scope)
    environment = _text(environment)
    if environment not in {"development", "test", "production"}:
        raise GraphValidationError("GRAPH_ENVIRONMENT_REQUIRED")
    return scope, environment


def entity(raw: dict, scope: str, environment: str) -> dict:
    _object(raw, {"id", "kind", "key", "label", "boundary"}, {"id", "kind", "key", "label"})
    kind = _text(raw["kind"])
    if kind not in IDENTITIES:
        raise GraphValidationError("GRAPH_INVALID_ENTITY_KIND")
    _object(raw["key"], IDENTITIES[kind], IDENTITIES[kind])
    key = {name: route_identity(value) if kind == "api" and name == "route" else _text(value)
           for name, value in raw["key"].items()}
    for name in ("ref_id", "platform_id", "page_id", "component_id"):
        if name in key:
            key[name] = stable_identity(key[name])
    if kind == "field" and key["owner_kind"] not in {"table", "view"}:
        raise GraphValidationError("GRAPH_INVALID_FIELD_OWNER")
    if kind == "api":
        key["method"] = key["method"].upper()
        if key["method"] not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            raise GraphValidationError("GRAPH_INVALID_METHOD")
    boundary = raw.get("boundary", "unknown")
    if boundary not in {"unknown", "source", "sink", "independent"}:
        raise GraphValidationError("GRAPH_INVALID_BOUNDARY")
    return {"id": _digest([scope, environment, kind, key]), "kind": kind, "key": key,
            "label": _text(raw["label"]), "boundary": boundary}


def signature(raw: dict | None, mapping: bool = False) -> dict:
    raw = {} if raw is None else raw
    allowed = {"kind", "fingerprint"} if mapping else {"branch_keys", "fingerprint"}
    _object(raw, allowed, set())
    result = {}
    if "fingerprint" in raw:
        result["fingerprint"] = _hash(raw["fingerprint"])
    if mapping:
        kind = raw.get("kind", "unknown")
        if kind not in {"unknown", "copy", "derive", "aggregate", "constant", "binding"}:
            raise GraphValidationError("GRAPH_INVALID_MAPPING")
        result["kind"] = kind
    else:
        result["branch_keys"] = _strings(raw.get("branch_keys", []), 30)
    return result


def proof(raw: dict) -> dict:
    _object(raw, {"id", "type", "fingerprint", "summary", "dependencies", "anchors"},
            {"id", "type", "fingerprint", "summary", "dependencies"})
    kind = _text(raw["type"])
    if kind not in PROOF_TYPES:
        raise GraphValidationError("GRAPH_INVALID_EVIDENCE")
    dependencies = []
    for item in _list(raw["dependencies"], 40, 1):
        _object(item, {"kind", "key", "version"}, {"kind", "key", "version"})
        dependency = {key: _text(value) for key, value in item.items()}
        if dependency["kind"] not in DEPENDENCY_KINDS:
            raise GraphValidationError("GRAPH_INVALID_DEPENDENCY")
        if dependency["kind"] == "action":
            dependency["key"], dependency["version"] = stable_identity(dependency["key"]), stable_identity(dependency["version"])
        dependencies.append(dependency)
    anchors = []
    for anchor in _list(raw.get("anchors", []), 40):
        _object(anchor, {"ref_id", "design_id", "group_key", "node_key", "page_id", "component_id",
                         "repository", "file", "symbol", "line", "canvas_index"}, set())
        location = {}
        for name, value in anchor.items():
            if name in {"line", "canvas_index"}:
                if type(value) is not int or value < 0 or value > 10000000:
                    raise GraphValidationError("GRAPH_INVALID_ANCHOR")
                location[name] = value
            else:
                location[name] = _text(value)
        anchors.append(location)
    return {"id": _text(raw["id"]), "type": kind, "fingerprint": _hash(raw["fingerprint"]),
            "summary": _text(raw["summary"], 1000),
            "dependencies": sorted(dependencies, key=_encoded), "anchors": sorted(anchors, key=_encoded)}


def validate_support(fact: dict, entities: dict, evidence: list[dict], status: str) -> None:
    kinds = {item["type"] for item in evidence}
    dependencies = {(dep["kind"], dep["key"]) for item in evidence for dep in item["dependencies"]}
    endpoints = [entities[fact[key]] for key in ("source", "target")]
    if fact["kind"] == "calls" and any(item["kind"] not in {"action", "node", "api", "service"} for item in endpoints):
        raise GraphValidationError("GRAPH_INVALID_CALL_ENDPOINT")
    for item in evidence:
        expected = {"published_design": "action", "control_flow": "action",
                    "schema": "schema", "source_static": "source",
                    "schema_catalog": "catalog", "cpm_catalog": "catalog"}.get(item["type"])
        if expected and not any(dep["kind"] == expected for dep in item["dependencies"]):
            raise GraphValidationError("GRAPH_EVIDENCE_DEPENDENCY_MISMATCH")
    if status in {"confirmed_data", "runtime_verified"} and "readonly_data" not in kinds:
        raise GraphValidationError("GRAPH_INSUFFICIENT_EVIDENCE")
    if status == "runtime_verified" and "runtime" not in kinds:
        raise GraphValidationError("GRAPH_INSUFFICIENT_EVIDENCE")
    if fact["kind"] in STRUCTURAL_KINDS:
        if not kinds & {"schema", "schema_catalog", "cpm_catalog", "source_static"}:
            raise GraphValidationError("GRAPH_INSUFFICIENT_EVIDENCE")
        return
    actions = {item["key"]["ref_id"] for item in endpoints if item["kind"] in {"action", "node"}}
    if actions:
        if not {"published_design", "control_flow"} <= kinds:
            raise GraphValidationError("GRAPH_INSUFFICIENT_EVIDENCE")
        if any(("action", action) not in dependencies for action in actions):
            raise GraphValidationError("GRAPH_ACTION_DEPENDENCY_REQUIRED")
        for proof_type in ("published_design", "control_flow"):
            covered = {dependency["key"] for item in evidence if item["type"] == proof_type
                       for dependency in item["dependencies"] if dependency["kind"] == "action"}
            if not actions <= covered:
                raise GraphValidationError("GRAPH_ACTION_EVIDENCE_INCOMPLETE")
    elif not kinds & {"source_static", "published_design", "readonly_data"} and not (
            fact["kind"] in {"references", "associated_with", "depends_on"} and kinds & {"schema", "schema_catalog"}):
        raise GraphValidationError("GRAPH_INSUFFICIENT_EVIDENCE")
    if fact["kind"] in DATA_KINDS and not kinds & {"schema", "readonly_data"}:
        raise GraphValidationError("GRAPH_INSUFFICIENT_EVIDENCE")
    if fact["data_binding"] and not kinds & {"schema", "readonly_data"}:
        raise GraphValidationError("GRAPH_BINDING_EVIDENCE_REQUIRED")
    data_objects = {"table", "view", "field"}
    if fact["kind"] == "writes" and endpoints[1]["kind"] not in data_objects:
        raise GraphValidationError("GRAPH_INVALID_DATA_DIRECTION")
    if fact["kind"] == "reads" and endpoints[0]["kind"] not in data_objects:
        raise GraphValidationError("GRAPH_INVALID_DATA_DIRECTION")


def normalize_v3(raw: dict, default_scope: str) -> dict:
    allowed = {"format_version", "scope_id", "environment", "case_key", "conclusion", "status",
               "entities", "facts", "evidence", "request_id"}
    required = allowed - {"scope_id", "request_id", "environment"}
    _object(raw, allowed, required)
    if type(raw["format_version"]) is not int or raw["format_version"] != 3:
        raise GraphValidationError("GRAPH_UNSUPPORTED_VERSION")
    if len(_encoded(raw)) > MAX_OBSERVATION_BYTES:
        raise GraphValidationError("GRAPH_PAYLOAD_TOO_LARGE")
    if re.search(r"(?i)\b(?:select\s+.+?\s+from|insert\s+into|update\s+\w+\s+set|delete\s+from)\b", _encoded(raw).decode("utf-8")):
        raise GraphValidationError("GRAPH_RAW_QUERY_NOT_ALLOWED")
    scope, environment = namespace(raw.get("scope_id", default_scope), raw.get("environment", "development"))
    status = _text(raw["status"])
    if status not in CONFIRMED_STATUSES:
        raise GraphValidationError("GRAPH_CONFIRMED_STATUS_REQUIRED")
    aliases, entities, declared, unresolved = {}, {}, set(), []
    for item in _list(raw["entities"], 200, 1):
        _object(item, {"id", "kind", "key", "label", "boundary"}, {"id", "kind", "key", "label"})
        local_id = _text(item["id"])
        if local_id in declared:
            raise GraphValidationError("GRAPH_DUPLICATE_ID")
        declared.add(local_id)
        kind = _text(item["kind"])
        if kind not in IDENTITIES:
            raise GraphValidationError("GRAPH_INVALID_ENTITY_KIND")
        _object(item["key"], IDENTITIES[kind], set())
        for name, value in item["key"].items():
            route_identity(value) if kind == "api" and name == "route" else _text(value)
        if IDENTITIES[kind] - item["key"].keys():
            unresolved.append({"reason": "identity_unresolved", "local_id": local_id,
                               "kind": kind, "label": _text(item["label"])})
            continue
        normalized = entity(item, scope, environment)
        aliases[local_id] = normalized["id"]
        entities[normalized["id"]] = normalized
    proofs = sorted([proof(item) for item in _list(raw["evidence"], 100, 1)], key=lambda item: item["id"])
    evidence = {item["id"]: item for item in proofs}
    if len(evidence) != len(proofs):
        raise GraphValidationError("GRAPH_DUPLICATE_ID")
    all_versions = {}
    for item in proofs:
        for dependency in item["dependencies"]:
            key = dependency["kind"], dependency["key"]
            if key in all_versions and all_versions[key] != dependency["version"]:
                raise GraphValidationError("GRAPH_CONFLICTING_DEPENDENCIES")
            all_versions[key] = dependency["version"]
    facts, fact_ids = [], set()
    for item in _list(raw["facts"], 400):
        _object(item, {"id", "source", "target", "kind", "label", "evidence_ids", "condition",
                       "mapping", "granularity", "data_binding"},
                {"id", "source", "target", "kind", "label", "evidence_ids"})
        if _text(item["id"]) in fact_ids:
            raise GraphValidationError("GRAPH_DUPLICATE_ID")
        fact_ids.add(item["id"])
        source_alias, target_alias = _text(item["source"]), _text(item["target"])
        if source_alias not in declared or target_alias not in declared:
            raise GraphValidationError("GRAPH_DANGLING_EDGE")
        kind = _text(item["kind"])
        if kind not in FACT_KINDS:
            raise GraphValidationError("GRAPH_INVALID_EDGE_KIND")
        if source_alias not in aliases or target_alias not in aliases:
            unresolved.append({"reason": "identity_unresolved", "local_id": item["id"], "label": _text(item["label"])})
            continue
        binding = item.get("data_binding", False)
        if type(binding) is not bool:
            raise GraphValidationError("GRAPH_INVALID_BINDING")
        condition, mapping = signature(item.get("condition")), signature(item.get("mapping"), True)
        if binding and (mapping["kind"] != "binding" or "fingerprint" not in mapping):
            raise GraphValidationError("GRAPH_BINDING_EVIDENCE_REQUIRED")
        if mapping["kind"] == "binding" and not binding:
            raise GraphValidationError("GRAPH_BINDING_EVIDENCE_REQUIRED")
        granularity = item.get("granularity", "dataset_level")
        if granularity not in {"dataset_level", "field_level"}:
            raise GraphValidationError("GRAPH_INVALID_GRANULARITY")
        source, target = aliases[item["source"]], aliases[item["target"]]
        if granularity == "field_level" and not all(entities[key]["kind"] == "field" for key in (source, target)):
            raise GraphValidationError("GRAPH_FIELD_IDENTITY_REQUIRED")
        if (mapping["kind"] != "unknown" or kind == "transforms" or granularity == "field_level") and "fingerprint" not in mapping:
            raise GraphValidationError("GRAPH_MAPPING_FINGERPRINT_REQUIRED")
        proof_ids = _strings(item["evidence_ids"], 100, 1)
        if not set(proof_ids) <= evidence.keys():
            raise GraphValidationError("GRAPH_INVALID_EVIDENCE")
        fact = {"id": _digest([scope, environment, source, target, kind, condition, mapping]),
                "source": source, "target": target, "kind": kind, "label": _text(item["label"]),
                "condition": condition, "mapping": mapping, "granularity": granularity,
                "data_binding": binding, "evidence": [evidence[key] for key in proof_ids]}
        validate_support(fact, entities, fact["evidence"], status)
        facts.append(fact)
    case_key = _text(raw["case_key"])
    unique_facts = {}
    for fact in facts:
        prior = unique_facts.get(fact["id"])
        if prior:
            combined = {item["id"]: item for item in prior["evidence"] + fact["evidence"]}
            prior["evidence"] = [combined[key] for key in sorted(combined)]
            prior["label"] = min(prior["label"], fact["label"])
            if fact["granularity"] == "dataset_level":
                prior["granularity"] = "dataset_level"
        else:
            unique_facts[fact["id"]] = fact
    result = {"scope_id": scope, "environment": environment, "case_key": case_key,
              "case_id": _digest([scope, environment, case_key]), "status": status,
              "conclusion": _text(raw["conclusion"], 1000), "entities": sorted(entities.values(), key=lambda item: item["id"]),
              "facts": [unique_facts[key] for key in sorted(unique_facts)], "evidence": proofs,
              "unresolved": sorted(unresolved, key=_encoded), "legacy": None,
              "request_id": _text(raw["request_id"]) if raw.get("request_id") else None}
    for fact in result["facts"]:
        fact["evidence_ids"] = [item["id"] for item in fact.pop("evidence")]
    result["fingerprint"] = _digest({key: value for key, value in result.items() if key != "request_id"})
    return result


def adapt_legacy(raw: dict, scope: str) -> dict:
    clean = validate_relation(raw)
    scope, environment = namespace(scope, clean["environment"])
    anchors = {item["id"]: item for item in clean["anchors"]}
    entities, aliases, unresolved = [], {}, []
    for node in clean["nodes"]:
        kind, key = node["kind"], None
        anchor = anchors.get(node.get("anchor_id"))
        if kind in {"action", "node"} and anchor:
            names = IDENTITIES[kind]
            key = {name: anchor[name] for name in names}
        if key is None:
            unresolved.append({"reason": "identity_unresolved", "label": node["label"]})
            continue
        normalized = entity({"id": node["id"], "kind": kind, "key": key, "label": node["label"]}, scope, environment)
        entities.append(normalized)
        aliases[node["id"]] = normalized["id"]
    evidence = []
    for item in clean["evidence"]:
        dependencies = [{"kind": "action", "key": stable_identity(anchors[key]["ref_id"]),
                         "version": stable_identity(anchors[key]["published_design_id"])} for key in item["anchor_ids"]]
        if item["type"] == "schema":
            dependencies.append({"kind": "schema", "key": "legacy-" + clean["relation_id"], "version": item["fingerprint"]})
        evidence.append({"id": item["id"], "type": item["type"], "fingerprint": item["fingerprint"],
                         "summary": item["summary"], "dependencies": dependencies,
                         "anchors": [{"ref_id": anchors[key]["ref_id"], "design_id": anchors[key]["published_design_id"],
                                      "group_key": anchors[key]["group_key"], "node_key": anchors[key]["node_key"]}
                                     for key in item["anchor_ids"]]})
    facts = []
    indexed = {item["id"]: item for item in entities}
    for edge in clean["edges"]:
        if edge["source"] not in aliases or edge["target"] not in aliases:
            unresolved.append({"reason": "identity_unresolved", "label": edge["label"]})
            continue
        source, target = aliases[edge["source"]], aliases[edge["target"]]
        branch_keys = sorted({anchors[node["anchor_id"]]["group_key"] + "/" + anchors[node["anchor_id"]]["node_key"]
                              for node in clean["nodes"] if node["id"] in {edge["source"], edge["target"]}
                              and node.get("anchor_id") in anchors})
        condition, mapping = {"branch_keys": branch_keys}, {"kind": "unknown"}
        fact = {"id": _digest([scope, environment, source, target, edge["kind"], condition, mapping]),
                "source": source, "target": target, "kind": edge["kind"], "label": edge["label"],
                "condition": condition, "mapping": mapping, "data_binding": False,
                "granularity": "field_level" if indexed[source]["kind"] == indexed[target]["kind"] == "field" else "dataset_level",
                "evidence_ids": [item["id"] for item in evidence]}
        facts.append(fact)
    result = {"scope_id": scope, "environment": environment, "case_key": clean["relation_id"],
              "case_id": _digest([scope, environment, clean["relation_id"]]), "status": clean["status"],
              "conclusion": clean["conclusion"], "entities": entities, "facts": facts,
              "evidence": evidence, "unresolved": unresolved, "legacy": clean, "request_id": None,
              "fingerprint": clean["evidence_fingerprint"]}
    return result
