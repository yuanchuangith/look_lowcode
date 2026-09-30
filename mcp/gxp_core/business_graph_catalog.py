from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from .business_logic_graph import GraphValidationError, _digest, _text
from .schema_config import load_schema_config


def _read(root: Path, relative: str, deadline: float):
    if time.monotonic() >= deadline:
        raise GraphValidationError("GRAPH_CATALOG_BUDGET_EXHAUSTED")
    root = root.resolve()
    path = root / relative
    path.resolve().relative_to(root)
    if path.is_symlink():
        raise GraphValidationError("GRAPH_UNSAFE_CATALOG_PATH")
    with path.open("rb") as stream:
        data = stream.read(2 * 1024 * 1024 + 1)
    if len(data) > 2 * 1024 * 1024:
        raise GraphValidationError("GRAPH_CATALOG_TOO_LARGE")
    return json.loads(data.decode("utf-8-sig"))


def _fresh(completed: str, ttl: int) -> bool:
    try:
        timestamp = datetime.fromisoformat(completed.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            return False
        age = datetime.now(timezone.utc).timestamp() - timestamp.timestamp()
        return 0 <= age < ttl
    except (AttributeError, TypeError, ValueError):
        return False


def _result(scope: str, environment: str, source: str, version: str, entities: list[dict],
            facts: list[dict], seed: dict, proof_type: str = "schema_catalog", dependency_kind: str = "catalog") -> dict:
    proof = {"id": "catalog-proof", "type": proof_type, "fingerprint": _digest([source, version, entities, facts]),
             "summary": "Bounded identities from an existing local snapshot; not runtime verification",
             "dependencies": [{"kind": dependency_kind, "key": source, "version": version}]}
    return {"source": source, "version": version, "observation": {
        "format_version": 3, "scope_id": scope, "environment": environment,
        "case_key": "catalog-" + _digest([source, seed["key"]]),
        "conclusion": "On-demand catalog identities", "status": "confirmed_static",
        "entities": entities, "facts": facts, "evidence": [proof]}}


def _schema(node: dict, scope: str, environment: str, deadline: float) -> dict:
    config = load_schema_config()
    if config.policy_scope_id != scope or node["key"]["datasource"] != scope:
        return {"reason": "catalog_scope_unresolved"}
    root = Path(config.snapshot_dir)
    manifest = _read(root, "manifest.json", deadline)
    if manifest.get("policy", {}).get("scope_id") != scope or not _fresh(manifest.get("completed_at"), config.ttl_seconds):
        return {"reason": "catalog_missing_or_stale"}
    owner = node["key"].get("owner", node["key"].get("name"))
    index = _read(root, "indexes/tables.json", deadline)
    candidates = [item for item in index if item.get("table_name") == owner]
    if len(candidates) != 1:
        return {"reason": "identity_unresolved"}
    indexed = candidates[0]
    kind = "view" if str(indexed.get("table_type", "")).upper() == "VIEW" else "table"
    expected = node["key"].get("owner_kind", node["kind"])
    schema_name = _text(manifest["database"])
    if expected != kind or node["key"]["schema"] != schema_name:
        return {"reason": "identity_unresolved"}
    table = _read(root, indexed["file"], deadline)
    columns = table.get("columns", [])
    requested = node["key"].get("column")
    if requested is not None and not any(item.get("column_name") == requested for item in columns):
        return {"reason": "identity_unresolved"}
    selected = ([item for item in columns if item.get("column_name") == requested] if requested is not None
                else sorted(columns, key=lambda item: str(item.get("column_name")))[:20])
    entities = [{"id": "owner", "kind": kind, "label": _text(owner),
                 "key": {"datasource": scope, "schema": schema_name, "name": owner}}]
    facts = []
    for index, column in enumerate(selected):
        name = _text(column["column_name"])
        local_id = f"column-{index}"
        entities.append({"id": local_id, "kind": "field", "label": name,
                         "key": {"datasource": scope, "schema": schema_name, "owner_kind": kind,
                                 "owner": owner, "column": name}})
        facts.append({"id": f"contains-{index}", "source": "owner", "target": local_id,
                      "kind": "contains", "label": "catalog column", "evidence_ids": ["catalog-proof"]})
    for index, constraint in enumerate(table.get("foreign_keys", [])[:20]):
        if not isinstance(constraint, dict) or not constraint.get("referenced_table_name"):
            continue
        if requested is not None and requested not in constraint.get("columns", []):
            continue
        candidate = f"unresolved-fk-{index}"
        entities.append({"id": candidate, "kind": "table", "label": _text(constraint["referenced_table_name"]),
                         "key": {"name": _text(constraint["referenced_table_name"])}})
        facts.append({"id": f"fk-{index}", "source": "column-0" if requested is not None else "owner", "target": candidate,
                      "kind": "references", "label": "FK target needs datasource and Schema verification",
                      "evidence_ids": ["catalog-proof"]})
    version = _text(manifest["schema_fingerprint"])
    result = _result(scope, environment, "schema-" + scope, version, entities, facts, node)
    result["observation"]["evidence"][0]["anchors"] = [{"file": _text(indexed["file"])}]
    return result


def _cpm(node: dict, scope: str, environment: str, deadline: float) -> dict:
    from .cpm_config import load_cpm_config
    from .cpm_runner import _is_fresh, _read_status
    config = load_cpm_config()
    if not _is_fresh(config, _read_status(), None):
        return {"reason": "catalog_missing_or_stale"}
    root = Path(config.snapshot_dir)
    page_id = node["key"].get("platform_id", node["key"].get("page_id"))
    found = None
    for path in sorted((root / "pages").glob("*/page-meta.json"))[:200]:
        meta = _read(root, path.relative_to(root).as_posix(), deadline)
        if meta.get("id") == page_id:
            if found is not None:
                return {"reason": "identity_unresolved"}
            found = path, meta
    if found is None:
        return {"reason": "identity_unresolved"}
    path, meta = found
    entities = [{"id": "page", "kind": "page", "label": _text(meta["name"]), "key": {"platform_id": _text(meta["id"])}}]
    facts = []
    relative = (path.parent / "components.json").relative_to(root).as_posix()
    content = _read(root, relative, deadline)
    components = content.get("componentList", []) if isinstance(content, dict) else content
    if isinstance(components, list):
        if node["kind"] == "report":
            components = [item for item in components if isinstance(item, dict) and item.get("id") == node["key"]["component_id"]]
            if len(components) != 1:
                return {"reason": "identity_unresolved"}
        for item in components[:20]:
            component_type = item.get("componentType") if isinstance(item, dict) else None
            if component_type not in {"Table", "FormTables", "GxpSmartTables", "CardTables", "TestPaper", "TreeTable", "SubTable"}:
                continue
            component_id = _text(item["id"])
            local_id = "component-" + component_id
            entities.append({"id": local_id, "kind": "report", "label": _text(item.get("title") or component_type),
                             "key": {"page_id": meta["id"], "component_id": component_id}})
            facts.append({"id": "contains-" + component_id, "source": "page", "target": local_id,
                          "kind": "contains", "label": "catalog display component", "evidence_ids": ["catalog-proof"]})
    status = _read_status()
    if node["kind"] == "report" and not any(item["key"].get("component_id") == node["key"]["component_id"] for item in entities):
        return {"reason": "identity_unresolved"}
    page_versions = {key: value.get("last_completed_at") for key, value in status.get("pages", {}).items() if isinstance(value, dict)}
    version = _digest([status.get("full", {}).get("last_completed_at"), page_versions])
    result = _result(scope, environment, "cpm-" + scope, version, entities, facts, node, "cpm_catalog")
    result["observation"]["evidence"][0]["anchors"] = [{"page_id": _text(meta["id"])}]
    return result


def _source(node: dict, scope: str, environment: str, deadline: float) -> dict:
    from .source_config import source_index_root
    from .source_index import source_index_status
    repository = node["key"]["repository"]
    if repository not in {"frontend", "backend"}:
        return {"reason": "repository_identity_unresolved"}
    status = source_index_status(layers=(repository,))
    selected = status.get("repositories", {}).get(repository)
    if not selected or selected.get("stale") or selected.get("parse_incomplete") or status.get("errors"):
        return {"reason": "catalog_missing_stale_or_ambiguous"}
    root = source_index_root()
    symbols = _read(root, repository + "/symbols.json", deadline)
    entities = [{"id": "root", "kind": node["kind"], "key": node["key"], "label": node["label"]}]
    facts = []
    source_symbol = node["key"].get("symbol")
    if node["kind"] == "api":
        routes = _read(root, repository + "/routes.json", deadline)
        matches = [item for item in routes if item.get("route") == node["key"]["route"] and item.get("method") == node["key"]["method"]]
        if len(matches) != 1:
            return {"reason": "identity_unresolved"}
        source_symbol = matches[0].get("symbol_id")
    matches = [item for item in symbols if item.get("symbol_id") == source_symbol]
    if len(matches) != 1:
        return {"reason": "identity_unresolved"}
    edges = _read(root, "graph/" + repository + "-call-edges.json", deadline)
    destinations = sorted({item["target_ids"][0] for item in edges if item.get("caller_id") == source_symbol
                           and item.get("category") == "business" and item.get("confidence") == "structural"
                           and len(item.get("target_ids", [])) == 1})[:20]
    for index, target in enumerate(destinations):
        target_symbols = [item for item in symbols if item.get("symbol_id") == target]
        if len(target_symbols) != 1:
            continue
        local_id = f"callee-{index}"
        entities.append({"id": local_id, "kind": "service", "label": _text(target_symbols[0]["name"]),
                         "key": {"repository": repository, "symbol": _text(target)}})
        facts.append({"id": f"call-{index}", "source": "root", "target": local_id, "kind": "calls",
                      "label": "source-static possible call", "condition": {"branch_keys": ["execution_condition_unresolved"]},
                      "evidence_ids": ["catalog-proof"]})
    version = _text(selected["index"]["fingerprint"])
    result = _result(scope, environment, "source-" + repository, version, entities, facts, node, "source_static", "source")
    result["observation"]["evidence"][0]["anchors"] = [{"repository": repository, "symbol": _text(source_symbol),
        "file": _text(item["path"]), "line": item["line"]} for item in edges
        if item.get("caller_id") == source_symbol and item.get("path") and type(item.get("line")) is int][:40]
    return result


def lookup(node: dict, scope: str, environment: str, *, deadline: float) -> dict:
    if environment != "development" or scope != load_schema_config().policy_scope_id:
        return {"reason": "catalog_scope_unresolved"}
    if node["kind"] in {"table", "view", "field"}:
        return _schema(node, scope, environment, deadline)
    if node["kind"] in {"page", "report"}:
        return _cpm(node, scope, environment, deadline)
    if node["kind"] in {"api", "service"}:
        return _source(node, scope, environment, deadline)
    return {"reason": "precise_published_evidence_required"}
