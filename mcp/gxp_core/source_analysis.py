from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from functools import wraps
from pathlib import Path
from typing import Any, Iterable

from .source_scope import EXCLUDED_PARTS
from .source_lex import LexedSource
from .cpm_config import load_cpm_config
from .service import GxpReadonlyService
from .source_hints import BACKEND_STACK_FRAME
from .source_index import bounded_result, ensure_source_index, load_index_file, refresh_source_index as _refresh_source_index, source_index_status, source_read_view, source_index_generation


MODEL_TERM = re.compile(r"\b(?:props\.)?([A-Za-z_$][\w$]*(?:Model|model|Dataset|dataset)[A-Za-z0-9_$]*)\b")
MAX_LIVE_FILES = 200


def _index_contract(status: dict[str, Any], layers: Iterable[str]) -> dict[str, Any]:
    repositories = status.get("repositories") or {}
    fingerprints = {
        layer: ((repositories.get(layer) or {}).get("index") or {}).get("fingerprint")
        for layer in layers
    }
    return {
        "version": status.get("index", {}).get("version"),
        "fingerprint": fingerprints,
        "stale": any((repositories.get(layer) or {}).get("stale", True) for layer in layers),
    }


def _repository_contract(status: dict[str, Any], layers: Iterable[str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for layer in layers:
        selected = ((status.get("repositories") or {}).get(layer) or {}).get("selected") or {}
        result[layer] = {
            key: selected.get(key) for key in ("path", "branch", "commit", "dirty_file_count")
        }
    return result


def _base(status: dict[str, Any], layers: Iterable[str]) -> dict[str, Any]:
    selected_layers = tuple(layers)
    return {
        "repository": _repository_contract(status, selected_layers),
        "index": _index_contract(status, selected_layers),
        "evidence": [],
        "runtime_verified": False,
        "unresolved": [],
    }


def _source_layers(*layers: str):
    def decorate(function):
        @wraps(function)
        def guarded(*args, **kwargs):
            for attempt in range(2):
                status = ensure_source_index(layers)
                errors = list(status.get("errors") or [])
                failed = [layer for layer in layers if ((status.get("repositories") or {}).get(layer) or {}).get("stale", True) or ((status.get("repositories") or {}).get(layer) or {}).get("parse_incomplete")]
                for layer in failed:
                    if not any(item.get("layer") == layer for item in errors):
                        errors.append({"layer": layer, "code": "SOURCE_LAYER_UNRESOLVED"})
                if len(failed) == len(layers):
                    return bounded_result({**_base(status, layers), "status": "unresolved", "errors": errors,
                            "unresolved": ["请求的源码层缺少当前可验证索引"]})
                generation = source_index_generation()
                expected_generation = (status.get("index") or {}).get("generation")
                if expected_generation and expected_generation != generation:
                    if attempt == 0:
                        continue
                    return bounded_result({**_base(status, layers), "status": "unresolved", "errors": [{"code": "SOURCE_INDEX_CHANGED_DURING_READ"}]})
                with source_read_view(status):
                    result = function(*args, **kwargs)
                if source_index_generation() != generation:
                    if attempt == 0:
                        continue
                    return bounded_result({**_base(status, layers), "status": "unresolved", "errors": [{"code": "SOURCE_INDEX_CHANGED_DURING_READ"}],
                            "unresolved": ["索引在读取期间连续变化"]})
                result["errors"] = errors
                if failed:
                    result["lookup_status"] = result.get("status")
                    result["status"] = "partial"
                    result.setdefault("unresolved", []).append("部分源码层未确认，不形成跨层确定结论")
                    if "contract_status" in result:
                        result["contract_status"] = "unresolved"
                return bounded_result(result)
        return guarded
    return decorate


def source_repository_status() -> dict[str, Any]:
    """Return bounded local source candidates, Git identities, and source-index freshness."""
    return bounded_result(source_index_status())


def refresh_source_index(force: bool = False) -> dict[str, Any]:
    """Refresh the local metadata-only source index using atomic replacement."""
    try:
        return bounded_result(_refresh_source_index(force=bool(force)))
    except (TimeoutError, OSError, RuntimeError) as exc:
        return bounded_result({"status": "error", "error": {"code": "SOURCE_INDEX_REFRESH_FAILED", "message": str(exc)}, "runtime_verified": False})


def _selected_root(status: dict[str, Any], layer: str) -> Path | None:
    repository = (status.get("repositories") or {}).get(layer) or {}
    if repository.get("stale", True) or repository.get("parse_incomplete"):
        return None
    path = (repository.get("selected") or {}).get("path")
    return Path(path) if path else None


def _evidence(layer: str, kind: str, path: str, line: int, symbol: str, confidence: str) -> dict[str, Any]:
    return {"layer": layer, "kind": kind, "path": path, "line": line, "symbol": symbol, "confidence": confidence}


def _live_model_bindings(root: Path | None, files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if root is None:
        return []
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for file in files[:MAX_LIVE_FILES]:
        relative = str(file.get("path") or "")
        try:
            lexed = LexedSource((root / relative).read_text(encoding="utf-8", errors="replace"))
            lines = lexed.code.splitlines() if not lexed.errors else []
        except OSError:
            continue
        for line_number, line in enumerate(lines, 1):
            for match in MODEL_TERM.finditer(line):
                value = match.group(1)
                key = (value.casefold(), relative, line_number)
                if key not in seen:
                    seen.add(key)
                    result.append({"name": value, "path": relative, "line": line_number})
                    if len(result) >= 100:
                        return result
    return result


@_source_layers("frontend")
def inspect_component_source(component_type: str, platform: str = "web", focus: str | None = None) -> dict[str, Any]:
    """Inspect one exact frontend component identity and its static source contract."""
    if not isinstance(component_type, str) or not component_type.strip() or len(component_type) > 160:
        return {"status": "error", "error": {"code": "INVALID_ARGUMENT", "message": "component_type 无效"}, "runtime_verified": False}
    if platform not in {"web", "wap"}:
        return {"status": "error", "error": {"code": "INVALID_ARGUMENT", "message": "platform 仅支持 web 或 wap"}, "runtime_verified": False}
    status = ensure_source_index()
    result = _base(status, ("frontend",))
    components = load_index_file("frontend/components.json", [])
    contracts = load_index_file("frontend/component-contracts.json", [])
    needle = component_type.strip().casefold()
    candidates = [
        item for item in components
        if needle == str(item.get("component_type", "")).casefold()
        or any(needle == str(value.get("value", "")).casefold() for value in item.get("behavior_names", []))
        or any(needle == str(value.get("value", "")).casefold() for value in item.get("selectors", []))
    ]
    if len(candidates) != 1:
        result.update({"status": "ambiguous" if candidates else "not_found", "candidates": candidates[:20]})
        result["unresolved"].append("组件身份未唯一命中" if candidates else "源码索引中没有该组件身份")
        return bounded_result(result)
    component = candidates[0]
    contract = next((item for item in contracts if item.get("component_type") == component.get("component_type")), {})
    files = component.get("files", [])
    platform_roles = {"designer", "api", "source", "locale", f"runtime_{platform}"}
    selected_files = [item for item in files if item.get("role") in platform_roles]
    result["evidence"].extend(
        _evidence("frontend", "definition", item["path"], 1, component["component_type"], "candidate")
        for item in selected_files
    )
    for item in [*component.get("behavior_names", []), *component.get("selectors", [])]:
        result["evidence"].append(_evidence("frontend", "definition", item["path"], item["line"], item["value"], "exact"))
    anchors = contract.get("anchors", [])
    if focus:
        anchors = [item for item in anchors if focus.casefold() in item["term"].casefold()]
    result["evidence"].extend(
        _evidence("frontend", "binding", item["path"], item["line"], item["term"], "structural")
        for item in anchors[:100]
    )
    model_bindings = _live_model_bindings(_selected_root(status, "frontend"), files)
    component_paths = {item.get("path") for item in files}
    registrations = [
        item for item in load_index_file("frontend/symbols.json", [])
        if item.get("path") in component_paths
    ][:100]
    result.update(
        {
            "status": "ok",
            "component": {
                **component,
                "platform": platform,
                "platform_available": any(item.get("role") == f"runtime_{platform}" for item in files),
            },
            "model_bindings": model_bindings,
            "registrations": registrations,
            "routes": contract.get("routes", []),
            "filter_contract": [item for item in anchors if item["term"] in {"dynamicFilter", "conditionFilter", "setFilter", "setConditionFilter", "filterInfo", "conditions"}],
        }
    )
    if not result["component"]["platform_available"]:
        result["unresolved"].append(f"没有找到 {platform} runtime 实现")
    return bounded_result(result)


def _normalize_route(route: str) -> str:
    value = route.strip().split("?", 1)[0]
    value = re.sub(r"^https?://[^/]+", "", value, flags=re.IGNORECASE)
    return "/" + value.strip("/")


@_source_layers("frontend", "backend")
def trace_api_contract(route: str, method: str | None = None, frontend_symbol: str | None = None) -> dict[str, Any]:
    """Trace a static frontend request through an ASP.NET endpoint, DTO, and service implementation."""
    if not isinstance(route, str) or not route.strip() or len(route) > 500:
        return {"status": "error", "error": {"code": "INVALID_ARGUMENT", "message": "route 无效"}, "runtime_verified": False}
    status = ensure_source_index()
    result = _base(status, ("frontend", "backend"))
    normalized = _normalize_route(route)
    wanted_method = method.upper() if method else None
    frontend = [
        item for item in load_index_file("frontend/requests.json", [])
        if _normalize_route(str(item.get("route", ""))) == normalized
        and (not wanted_method or item.get("method") == wanted_method)
        and (not frontend_symbol or str(item.get("function") or "").casefold() == frontend_symbol.casefold())
    ]
    backend = [
        item for item in load_index_file("backend/routes.json", [])
        if _normalize_route(str(item.get("route", ""))) == normalized
        and (not wanted_method or item.get("method") == wanted_method)
    ]
    candidate_routes = [item for item in load_index_file("frontend/route-candidates.json", []) if _normalize_route(str(item.get("route", ""))) == normalized][:30]
    for item in frontend:
        result["evidence"].append(_evidence("frontend", "route", item["path"], item["line"], f"{item.get('method') or '?'} {item['route']}", "structural" if not item.get("dynamic") else "candidate"))
    for item in backend:
        result["evidence"].append(_evidence("backend", "route", item["path"], item["line"], f"{item['controller']}.{item['action']}", "exact"))
    dto_names = {name for item in backend for name in item.get("dto_symbol_ids", item.get("dto_types", []))}
    all_dtos = load_index_file("backend/dto-contracts.json", [])
    dto_contracts = [_expand_dto(name, all_dtos) for name in sorted(dto_names)]
    dto_contracts = [item for item in dto_contracts if item]
    for dto in dto_contracts:
        result["evidence"].append(_evidence("backend", "dto", dto["path"], dto["line"], dto["name"], "exact"))
    backend_edges = load_index_file("graph/backend-call-edges.json", [])
    endpoint_calls = [
        edge for edge in backend_edges
        if any(edge.get("caller_id") == endpoint.get("symbol_id") for endpoint in backend if endpoint.get("symbol_id"))
    ]
    symbols = load_index_file("backend/symbols.json", [])
    bindings = load_index_file("backend/service-bindings.json", [])
    implementation_ids = {item.get("implementation_id") for item in bindings if item.get("implementation_id")}
    service_calls = [edge for edge in endpoint_calls if any(
        symbol.get("symbol_id") in edge.get("target_ids", []) and symbol.get("type_id") in implementation_ids
        for symbol in symbols
    )]
    implementations = [symbol for symbol in symbols if symbol.get("kind") == "method" and any(
        symbol.get("symbol_id") in call.get("target_ids", []) for call in service_calls
    )]
    unique_impl = {(item["name"], item["path"], item["line"]): item for item in implementations}.values()
    implementations = list(unique_impl)
    for item in service_calls:
        result["evidence"].append(_evidence("backend", "call", item["path"], item["line"], f"{item['caller']} → {item['callee_member']}", "structural" if len(item.get("target_ids", [])) == 1 else "candidate"))
    for item in implementations:
        result["evidence"].append(_evidence("backend", "definition", item["path"], item["line"], item["name"], "exact"))
    dynamic = any(item.get("path_confidence") == "candidate" or ("path_confidence" not in item and item.get("dynamic")) for item in frontend)
    query_dynamic = any(item.get("query_dynamic") for item in frontend)
    if query_dynamic:
        result["unresolved"].append("端点路径已确认，但查询参数依赖运行时拼接")
    wrappers = {item.get("wrapper") for item in frontend if item.get("wrapper")}
    if len(backend) > 1 or (frontend_symbol is None and len({item.get("function") for item in frontend}) > 1):
        contract_status = "ambiguous"
    elif dynamic:
        contract_status = "dynamic_route"
    elif wrappers:
        contract_status = "wrapper_unresolved"
        result["unresolved"].append("@inbiz/utils 请求包装器实现不在可读源码范围，最终 HTTP body 尚未静态确认")
    elif frontend and backend:
        contract_status = "matched"
    else:
        contract_status = "unresolved"
        result["unresolved"].append("前端调用者或后端 endpoint 未形成唯一闭合链")
    result.update(
        {
            "status": "ok" if frontend or backend else "unresolved" if candidate_routes else "not_found",
            "normalized_route": normalized,
            "query_status": "unresolved" if query_dynamic else "not_runtime_verified",
            "frontend_callers": frontend,
            "candidate_routes": candidate_routes,
            "backend_endpoints": backend,
            "dto_contracts": dto_contracts,
            "service_calls": service_calls,
            "service_implementations": implementations,
            "contract_status": contract_status,
        }
    )
    return bounded_result(result)


def _plain_type(value: str) -> str:
    text = value.strip().rstrip("?")
    text = re.sub(r"\[\]$", "", text)
    generic = re.match(r"(?:List|IEnumerable|ICollection|Dictionary)<\s*([^,>]+)", text)
    return generic.group(1).strip() if generic else text


def _expand_dto(name: str, contracts: list[dict[str, Any]], depth: int = 0, seen: set[str] | None = None) -> dict[str, Any] | None:
    matches = [item for item in contracts if item.get("symbol_id") == name or item.get("name") == name]
    if len(matches) != 1:
        return None
    item = matches[0]
    lookup = {str(value.get("name")) for value in contracts}
    seen = set(seen or ())
    if name in seen or depth >= 3:
        return {**item, "recursive_truncated": True}
    seen.add(name)
    properties = []
    for prop in item.get("properties", []):
        nested_name = _plain_type(str(prop.get("type", "")))
        nested = _expand_dto(nested_name, contracts, depth + 1, seen) if nested_name in lookup else None
        properties.append({**prop, **({"contract": nested} if nested else {})})
    inherited = [_expand_dto(_plain_type(base), contracts, depth + 1, seen) for base in item.get("bases", [])]
    return {**item, "properties": properties, "inherited_contracts": [value for value in inherited if value]}


def _signature_types(value: str) -> list[str]:
    aliases = {"System.String": "string", "System.Boolean": "bool", "System.Int32": "int", "System.Int64": "long", "System.Int16": "short", "System.Byte": "byte", "System.Decimal": "decimal", "System.Double": "double", "System.Single": "float", "System.Object": "object", "System.Char": "char", "System.Void": "void"}
    parts, start, depth = [], 0, 0
    for index, character in enumerate(value):
        if character in "<[":
            depth += 1
        elif character in ">]":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append(value[start:index])
            start = index + 1
    if value.strip():
        parts.append(value[start:])
    normalized = []
    for part in parts:
        part = re.sub(r"^(?:ref|out|in|params|this)\s+", "", part.strip()).split("=", 1)[0].strip()
        part = re.sub(r"\s+@?[A-Za-z_]\w*$", "", part).replace("global::", "")
        part = re.sub(r"\s+", "", part)
        part = re.sub(r"[A-Za-z_][\w.]*", lambda match: aliases.get(match.group(), match.group()), part)
        normalized.append(part)
    return normalized


def _backend_query(value: str) -> dict[str, Any]:
    frame = re.search(r"\bat\s+([^\r\n]+)", value)
    text = (frame.group(1) if frame else value.strip()).replace("global::", "").replace("::", ".")
    matched = re.match(r"(?P<identity>[A-Za-z_]\w*(?:[.+][A-Za-z_]\w*)*)\s*(?:\((?P<parameters>[^()]*)\))?", text)
    if matched is None:
        return {"type": None, "method": None, "parameters": None, "valid": False}
    identity = matched.group("identity")
    parts = identity.rsplit(".", 1)
    parameters = matched.group("parameters")
    return {"type": parts[0] if len(parts) == 2 else None, "method": parts[-1],
            "parameters": _signature_types(parameters) if parameters is not None else None, "valid": True}


def _entry_matches(symbol: dict[str, Any], query: dict[str, Any]) -> bool:
    if symbol.get("kind") != "method" or not query["valid"]:
        return False
    identity = str(symbol.get("symbol_id") or symbol.get("name", "")).split("(", 1)[0]
    owner, _, member = identity.rpartition(".")
    if member.casefold() != query["method"].casefold():
        return False
    requested_owner = query["type"]
    if requested_owner and (owner if "." in requested_owner else owner.rsplit(".", 1)[-1]).casefold() != requested_owner.casefold():
        return False
    if query["parameters"] is not None:
        if "parameters" in symbol:
            actual = _signature_types(",".join(item["type"] for item in symbol["parameters"]))
        elif "(" in str(symbol.get("symbol_id", "")):
            actual = _signature_types(symbol["symbol_id"].split("(", 1)[1].rsplit(")", 1)[0])
        else:
            return False
        return actual == query["parameters"]
    return True


@_source_layers("backend")
def trace_backend_call_chain(symbol_or_stack: str, max_depth: int = 6) -> dict[str, Any]:
    """Trace source-proven backend calls, interface implementations, and data-access operations."""
    if not isinstance(symbol_or_stack, str) or not symbol_or_stack.strip() or len(symbol_or_stack) > 20_000:
        return {"status": "error", "error": {"code": "INVALID_ARGUMENT", "message": "symbol_or_stack 无效"}, "runtime_verified": False}
    depth = max(1, min(int(max_depth), 10))
    status = ensure_source_index()
    result = _base(status, ("backend",))
    query = _backend_query(symbol_or_stack)
    symbols = load_index_file("backend/symbols.json", [])
    exact = [item for item in symbols if item.get("kind") == "method" and item.get("symbol_id") == symbol_or_stack.strip()]
    starts = exact or [item for item in symbols if _entry_matches(item, query)]
    if not starts:
        result.update({"status": "not_found", "query": query})
        result["unresolved"].append("后端符号未命中")
        return bounded_result(result)
    if len(starts) > 1:
        result.update({"status": "ambiguous", "query": query, "starts": starts, "call_tree": [], "infrastructure_calls": [],
                       "unresolved_call_count": 0, "service_bindings": [], "exception_flow": [], "cycle_truncated": False})
        result["unresolved"].append("入口符号存在歧义，请提供完整命名空间及参数签名；候选未展开")
        result["evidence"] = [_evidence("backend", "definition", item["path"], item["line"], item["name"], "candidate") for item in starts]
        return bounded_result(result)
    edges = load_index_file("graph/backend-call-edges.json", [])
    bindings = load_index_file("backend/service-bindings.json", [])
    queue = [(item.get("symbol_id", item["name"]), 0) for item in starts]
    infrastructure = []
    unresolved_calls = []
    visited: set[str] = set()
    tree: list[dict[str, Any]] = []
    while queue and len(tree) < 200:
        caller, level = queue.pop(0)
        if caller in visited:
            continue
        visited.add(caller)
        outgoing = [edge for edge in edges if edge.get("caller_id", edge.get("caller")) == caller]
        for edge in outgoing:
            if edge.get("category") == "infrastructure":
                infrastructure.append(edge)
                continue
            targets = [item for item in symbols if item.get("symbol_id") and item["symbol_id"] in edge.get("target_ids", [])]
            if not targets and not edge.get("data_access"):
                unresolved_calls.append(edge)
            tree.append({**edge, "depth": level, "targets": [item["name"] for item in targets], "ambiguous": len(targets) > 1})
            result["evidence"].append(_evidence("backend", "call", edge["path"], edge["line"], f"{caller} → {edge['callee_member']}", "structural" if len(targets) == 1 or edge.get("data_access") else "candidate"))
            if level + 1 < depth and len(targets) == 1:
                queue.append((targets[0]["symbol_id"], level + 1))
    for item in starts:
        result["evidence"].append(_evidence("backend", "definition", item["path"], item["line"], item["name"], "exact"))
    exception_flow = _exception_flow(_selected_root(status, "backend"), starts)
    result["evidence"].extend(exception_flow)
    ambiguous_edges = [item for item in tree if item["ambiguous"]]
    if ambiguous_edges:
        result["unresolved"].append("部分方法名存在多个实现，未静默选择调用目标")
    result.update({"status": "ok" if len(starts) == 1 else "ambiguous", "starts": starts, "call_tree": tree, "infrastructure_calls": infrastructure[:30], "unresolved_call_count": len(unresolved_calls), "service_bindings": [item for item in bindings if item.get("implementation_id") in {symbol.get("type_id") for symbol in starts}], "exception_flow": exception_flow, "cycle_truncated": bool(queue)})
    return bounded_result(result)


def _exception_flow(root: Path | None, starts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if root is None:
        return []
    result: list[dict[str, Any]] = []
    for item in starts[:20]:
        try:
            lexed = LexedSource((root / item["path"]).read_text(encoding="utf-8", errors="replace"), language="csharp")
            lines = lexed.code.splitlines() if not lexed.errors else []
        except OSError:
            continue
        start = max(0, int(item["line"]) - 1)
        end = min(len(lines), int(item.get("end_line") or start + 300))
        for index in range(start + 1, end):
            if index > start + 1 and re.search(r"^\s*public\s+.*\w+\s*\(", lines[index]):
                end = index
                break
        for index in range(start, end):
            stripped = lines[index].strip()
            if re.search(r"\bcatch\b", stripped):
                result.append(_evidence("backend", "exception", item["path"], index + 1, "catch", "structural"))
            if re.search(r"\bthrow(?:\s*;|\s+new\b|\s+[A-Za-z_])", stripped):
                symbol = "rethrow" if stripped == "throw;" else "throw"
                result.append(_evidence("backend", "exception", item["path"], index + 1, symbol, "structural"))
    return result[:100]


def _snapshot_usages(dataset_key: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        root = Path(load_cpm_config().snapshot_dir).resolve()
    except Exception as exc:
        return [], f"CPM 配置不可用: {str(exc)[:200]}"
    if not root.is_dir():
        return [], "CPM 快照不存在"
    needle = dataset_key.casefold()
    usages: list[dict[str, Any]] = []
    search_roots = [root / name for name in ("datasets", "pages", "public-bizflows", "menus", "navigations") if (root / name).is_dir()]
    paths: list[Path] = []
    rg = shutil.which("rg")
    if rg and search_roots:
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            found = subprocess.run(
                [rg, "--hidden", "--no-messages", "--files-with-matches", "--fixed-strings", "--ignore-case", "--null", "--glob", "*.json", "--glob", "*.md", "--", dataset_key, *(str(item) for item in search_roots)],
                capture_output=True,
                check=False,
                timeout=8,
                creationflags=flags,
            )
            if found.returncode in (0, 1):
                paths = [Path(item.decode("utf-8", errors="surrogateescape")) for item in found.stdout.split(b"\0") if item]
        except subprocess.TimeoutExpired:
            paths = []
    if not paths:
        checked = 0
        for search_root in search_roots:
            for path in search_root.rglob("*"):
                if checked >= 5000:
                    break
                checked += 1
                if path.is_file() and path.suffix.casefold() in {".json", ".md"}:
                    paths.append(path)
    for path in paths[:5000]:
        if not path.is_file() or path.is_symlink():
            continue
        try:
            if path.stat().st_size > 1_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="strict")
        except (OSError, UnicodeDecodeError):
            continue
        index = text.casefold().find(needle)
        if index < 0:
            continue
        relative = path.relative_to(root).as_posix()
        category = "dataset_definition" if relative.startswith("datasets/") and path.suffix.casefold() == ".json" else "published_form" if relative.startswith("pages/") else "published_public_action" if relative.startswith("public-bizflows/") else "workspace" if relative.startswith(("menus/", "navigations/")) else "snapshot_reference"
        usage = {
            "category": category,
            "path": relative,
            "line": text.count("\n", 0, index) + 1,
            "snippet": text[max(0, index - 80) : index + len(dataset_key) + 120].replace("\n", " ")[:240],
            "runtime_effect": category != "snapshot_reference",
        }
        if relative.startswith("pages/"):
            parts = relative.split("/")
            usage["page_snapshot"] = parts[1] if len(parts) > 1 else None
        if category == "dataset_definition":
            try:
                payload = json.loads(text)
                tables = sorted({str(field.get("tableName")) for field in ((payload.get("config") or {}).get("queryFields") or []) if isinstance(field, dict) and field.get("tableName")})
                usage["definition"] = {key: payload.get(key) for key in ("id", "code", "name", "model", "dataSourceId")}
                usage["schema_table_candidates"] = tables
            except (json.JSONDecodeError, AttributeError):
                pass
        elif path.suffix.casefold() == ".json":
            try:
                usage["references"] = _json_references(json.loads(text), dataset_key)[:20]
            except json.JSONDecodeError:
                pass
        usages.append(usage)
        if len(usages) >= 100:
            break
    return usages, None


def _json_references(value: Any, needle: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    def visit(item: Any, trail: list[str], owner: dict[str, Any] | None) -> None:
        if len(result) >= 50:
            return
        if isinstance(item, dict):
            next_owner = item
            for key, child in item.items():
                visit(child, [*trail, str(key)], next_owner)
        elif isinstance(item, list):
            for index, child in enumerate(item):
                visit(child, [*trail, str(index)], owner)
        elif needle.casefold() in str(item or "").casefold():
            context = owner or {}
            result.append(
                {
                    "json_path": ".".join(trail),
                    "control_id": context.get("controlId") or context.get("control_id") or context.get("id"),
                    "component_type": context.get("componentType") or context.get("type") or context.get("x-component"),
                    "config_role": trail[-1] if trail else None,
                }
            )

    visit(value, [], None)
    return result


def _draft_usages(dataset_key: str) -> tuple[list[dict[str, Any]], str | None]:
    try:
        repository = GxpReadonlyService().repository
        columns = repository._columns("cpm_bizflows_design")
        data_column = repository._pick(columns, "data", required=True)
        ref_column = repository._pick(columns, "ref_Id", "ref_id", required=True)
        publish_column = repository._pick(columns, "is_publish", "isPublish", required=True)
        deleted_column = repository._pick(columns, "isDeleted", "is_deleted", required=True)
        sql = (
            f"SELECT `{ref_column}` AS ref_id, `{publish_column}` AS is_publish "
            f"FROM `cpm_bizflows_design` WHERE `{deleted_column}`=0 AND `{publish_column}`=0 "
            f"AND `{data_column}` LIKE %(needle)s LIMIT 50"
        )
        with repository.database.session(timeout_ms=8000) as session:
            rows, _ = session.query(sql, {"needle": f"%{dataset_key}%"}, max_rows=50)
        return [{"category": "draft_action", "ref_id": str(row.get("ref_id", "")), "runtime_effect": False} for row in rows], None
    except Exception as exc:
        return [], f"草稿只读查询失败: {type(exc).__name__}: {str(exc)[:200]}"


def inspect_dataset_usage(dataset_key: str, include_drafts: bool = False) -> dict[str, Any]:
    """Find dataset definitions and published/draft usages without returning business rows."""
    if not isinstance(dataset_key, str) or not dataset_key.strip() or len(dataset_key) > 256:
        return {"status": "error", "error": {"code": "INVALID_ARGUMENT", "message": "dataset_key 无效"}, "runtime_verified": False}
    status = source_index_status(("frontend",))
    result = _base(status, ("frontend",))
    usages, snapshot_error = _snapshot_usages(dataset_key.strip())
    drafts: list[dict[str, Any]] = []
    draft_error = None
    if include_drafts:
        drafts, draft_error = _draft_usages(dataset_key.strip())
    for usage in usages:
        result["evidence"].append(_evidence("cpm_snapshot", "usage", usage["path"], usage.get("line", 1), dataset_key, "structural"))
    result.update({"status": "ok" if usages or drafts else "not_found", "dataset_key": dataset_key, "usages": usages, "draft_usages": drafts, "drafts_affect_runtime": False})
    for error in (snapshot_error, draft_error):
        if error:
            result["unresolved"].append(error)
    result["unresolved"].append("数据集中的表名只作为 Schema 查询锚点；跨表关系需由 declared_fk、data_verified 或 live_database 确认")
    return bounded_result(result)


def _term_evidence(root: Path | None, terms: tuple[str, ...], component_type: str, limit: int = 120) -> list[dict[str, Any]]:
    if root is None:
        return []
    evidence: list[dict[str, Any]] = []
    roots = [root / "src/core/common", root / "src/core/components"]
    for base in roots:
        if not base.is_dir():
            continue
        for directory, subdirectories, names in os.walk(base):
            subdirectories[:] = [name for name in subdirectories if name.casefold() not in EXCLUDED_PARTS]
            relative_directory = os.path.relpath(directory, root).replace(os.sep, "/")
            for name in names:
                if os.path.splitext(name)[1].casefold() not in {".ts", ".tsx"}:
                    continue
                relative_path = relative_directory + "/" + name
                relative_key = relative_path.casefold()
                if component_type.casefold() not in relative_key and not relative_key.endswith("actiondesign/element/components/datafilter.tsx"):
                    continue
                try:
                    lexed = LexedSource((Path(directory) / name).read_text(encoding="utf-8", errors="replace"))
                    generated_filter = relative_key.endswith("actiondesign/element/components/datafilter.tsx")
                    lines = (lexed.clean if generated_filter else lexed.code).splitlines() if not lexed.errors else []
                except OSError:
                    continue
                for line_number, line in enumerate(lines, 1):
                    for term in terms:
                        if term in line:
                            evidence.append(_evidence("frontend", "binding", relative_path, line_number, term, "structural"))
                            if len(evidence) >= limit:
                                return evidence
    return evidence


@_source_layers("frontend", "backend")
def trace_component_filter_contract(component_type: str) -> dict[str, Any]:
    """Trace DataFilter canvas names to component filter setters, request fields, and backend DTO fields."""
    if not isinstance(component_type, str) or not component_type.strip() or len(component_type) > 160:
        return {"status": "error", "error": {"code": "INVALID_ARGUMENT", "message": "component_type 无效"}, "runtime_verified": False}
    status = ensure_source_index()
    result = _base(status, ("frontend", "backend"))
    terms = ("dynamicWhere", "staticWhere", "setFilter", "setConditionFilter", "dynamicFilter", "conditionFilter", "filterInfo", "conditions")
    frontend_evidence = _term_evidence(_selected_root(status, "frontend"), terms, component_type)
    dto_candidates = [item for item in load_index_file("backend/dto-contracts.json", []) if item.get("name") == "DataCenterQueryDto"]
    dto = dto_candidates[0] if len(dto_candidates) == 1 else None
    dto_fields = []
    if dto:
        dto_fields = [item for item in dto.get("properties", []) if item.get("name") in {"FilterInfo", "Conditions"}]
        result["evidence"].extend(_evidence("backend", "dto", dto["path"], item["line"], f"DataCenterQueryDto.{item['name']}", "exact") for item in dto_fields)
    result["evidence"].extend(frontend_evidence)
    has_reverse = {item["symbol"] for item in frontend_evidence}
    mappings = []
    if {"dynamicWhere", "conditionFilter"}.issubset(has_reverse):
        mappings.append({"canvas_parameter": "dynamicWhere", "component_property": "conditionFilter", "meaning": "SQL 字符串", "confidence": "structural"})
    if {"staticWhere", "dynamicFilter"}.issubset(has_reverse):
        mappings.append({"canvas_parameter": "staticWhere", "component_property": "dynamicFilter", "meaning": "JSON 条件", "confidence": "structural"})
    result.update({"status": "ok" if mappings else "unresolved", "component_type": component_type, "historical_name_reversal": mappings, "dto_fields": dto_fields})
    if len(mappings) < 2:
        result["unresolved"].append("历史命名反转的设置端与消费端未全部静态命中")
    result["unresolved"].append("不同组件消费方式分别列示，不将单个组件实现推广为全局事实")
    return bounded_result(result)
