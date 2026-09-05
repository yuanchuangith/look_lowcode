from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .source_scope import FRONTEND_ROOTS, BACKEND_ROOTS, FRONTEND_EXTENSIONS, BACKEND_EXTENSIONS, EXCLUDED_PARTS
from .source_budget import bounded_payload
from .source_lex import LexedSource
from .source_frontend import scan_requests, component_registrations
from .source_backend import parse_backend_file, bind_backend
from .cpm_config import _atomic_json
from .cpm_runner import _FileLock
from .source_config import (
    SOURCE_INDEX_VERSION,
    SourceRepositoryError,
    resolve_repository,
    source_index_lock_path,
    source_index_root,
)


MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_RESPONSE_BYTES = 64 * 1024


TS_SYMBOL = re.compile(r"\b(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function|class|interface|const|let|var)\s+([A-Za-z_$][\w$]*)")
TS_ROUTE = re.compile(r"/(?:api|gxp2)(?:/[A-Za-z0-9_.$?{}=&:+-]+)+", re.IGNORECASE)
TS_METHOD = re.compile(r"\brequest\.(get|post|put|patch|delete)\s*\(", re.IGNORECASE)
CS_TYPE = re.compile(r"\b(public|internal)\s+(?:(?:abstract|partial|sealed|static)\s+)*(class|interface)\s+([A-Za-z_]\w*)(?:\s*:\s*([^\{]+))?")
CS_METHOD = re.compile(
    r"\bpublic\s+(?:(?:async|static|virtual|override|partial)\s+)*(?:[A-Za-z_][\w<>,.?\[\]\s]*\s+)([A-Za-z_]\w*)\s*\((.*)"
)
CS_INTERFACE_METHOD = re.compile(r"^\s*(?:[A-Za-z_][\w<>,.?\[\]\s]*)\s+([A-Za-z_]\w*)\s*\((.*)\)\s*;")
CS_PROPERTY = re.compile(r"\bpublic\s+([A-Za-z_][\w<>,.?\[\]\s]*)\s+([A-Za-z_]\w*)\s*\{\s*get\s*;")
CS_CALL = re.compile(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\s*\(")
HTTP_ATTRIBUTE = re.compile(r"\[Http(Get|Post|Put|Patch|Delete)(?:\(\s*(?:\"([^\"]*)\")?\s*\))?\]", re.IGNORECASE)
ROUTE_ATTRIBUTE = re.compile(r"\[Route\(\s*\"([^\"]*)\"\s*\)\]", re.IGNORECASE)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_text(path: Path) -> str:
    with path.open("rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        if size > MAX_SOURCE_BYTES:
            raise ValueError("source_file_too_large")
        data = stream.read(size + 1)
    if len(data) != size:
        raise ValueError("source_changed_during_read")
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n")


def _source_files(root: Path, layer: str) -> list[Path]:
    roots = FRONTEND_ROOTS if layer == "frontend" else BACKEND_ROOTS
    extensions = FRONTEND_EXTENSIONS if layer == "frontend" else BACKEND_EXTENSIONS
    files: list[Path] = []
    for relative_root in roots:
        base = root / relative_root
        if not base.is_dir():
            continue
        for directory, subdirectories, names in os.walk(base):
            subdirectories[:] = [name for name in subdirectories if name.casefold() not in EXCLUDED_PARTS]
            files.extend(Path(directory) / name for name in names if os.path.splitext(name)[1].casefold() in extensions)
    return sorted(set(files), key=lambda item: item.as_posix().casefold())


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _frontend_component(relative: str) -> tuple[str, str] | None:
    parts = relative.split("/")
    try:
        start = parts.index("components")
    except ValueError:
        return None
    role_indexes = [index for index, part in enumerate(parts) if part in {"designer", "preview"}]
    if not role_indexes:
        return None
    role_index = role_indexes[0]
    if role_index <= start + 1:
        return None
    component = parts[role_index - 1]
    category = "/".join(parts[start + 1 : role_index - 1])
    return component, category


def _frontend_role(relative: str) -> str:
    value = f"/{relative.casefold()}"
    if "/designer/" in value:
        return "designer"
    if "/preview/web/" in value:
        return "runtime_web"
    if "/preview/wap/" in value:
        return "runtime_wap"
    name = Path(relative).name.casefold()
    if name.startswith("api.") or name.startswith("service."):
        return "api"
    if "locale" in name:
        return "locale"
    return "source"


def _scan_frontend(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    files = _source_files(root, "frontend")
    components: dict[str, dict[str, Any]] = {}
    contracts: dict[str, dict[str, Any]] = {}
    requests: list[dict[str, Any]] = []
    route_candidates: list[dict[str, Any]] = []
    symbols: list[dict[str, Any]] = []
    call_edges: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    anchor_terms = (
        "initialValues", "form.createField", "form.setValues", "dynamicFilter", "conditionFilter",
        "setFilter", "setConditionFilter", "filterInfo", "conditions", "SearchDataCenter", "QueryDataCenter", "dataSave",
    )
    for path in files:
        relative = path.relative_to(root).as_posix()
        try:
            text = _read_text(path)
        except (OSError, ValueError) as exc:
            failures.append({"path": relative, "reason": str(exc)[:120]})
            continue
        needs_lexing = any(term in text for term in ("request", "createBehavior", *anchor_terms))
        lexed = LexedSource(text if needs_lexing else "")
        component_info = _frontend_component(relative)
        parsed = scan_requests(lexed, relative) if re.search(r"\brequest\s*(?:\?\.|\.)", lexed.code) else {"requests": [], "symbols": [], "call_edges": [], "route_candidates": []}
        if lexed.errors:
            failures.append({"path": relative, "reason": "; ".join(lexed.errors[:5])})
            continue
        if component_info:
            component, category = component_info
            entry = components.setdefault(
                component.casefold(),
                {"component_type": component, "category": category, "files": [], "behavior_names": [], "selectors": []},
            )
            entry["files"].append({"path": relative, "role": _frontend_role(relative)})
            contract = contracts.setdefault(component.casefold(), {"component_type": component, "anchors": [], "routes": [], "files": []})
            contract["files"].append({"path": relative, "role": _frontend_role(relative)})
            names, selectors = component_registrations(lexed, relative) if "createBehavior" in lexed.code else ([], [])
            entry["behavior_names"].extend(names)
            entry["selectors"].extend(selectors)
            for term in anchor_terms:
                for match in re.finditer(re.escape(term), lexed.code):
                    contract["anchors"].append({"term": term, "path": relative, "line": lexed.line(match.start())})
            contract["routes"].extend(parsed["requests"])
        requests.extend(parsed["requests"])
        symbols.extend(parsed["symbols"])
        call_edges.extend(parsed["call_edges"])
        route_candidates.extend(parsed["route_candidates"])
    for collection in (components.values(), contracts.values()):
        for item in collection:
            item["files"] = sorted({(row["path"], row["role"]): row for row in item["files"]}.values(), key=lambda row: (row["role"], row["path"]))
    data = {
        "components": sorted(components.values(), key=lambda item: item["component_type"].casefold()),
        "component_contracts": sorted(contracts.values(), key=lambda item: item["component_type"].casefold()),
        "requests": requests,
        "route_candidates": route_candidates,
        "symbols": symbols,
        "call_edges": call_edges,
        "file_count": len(files),
    }
    return data, failures


def _combine_route(class_route: str, method_route: str, controller: str) -> str:
    base = (class_route or "").replace("[controller]", controller).replace("{controller}", controller)
    method = method_route or ""
    if method.startswith(("/", "~/")):
        route = method.removeprefix("~")
    else:
        route = "/".join(part.strip("/") for part in (base, method) if part.strip("/"))
    return "/" + route.strip("/")


def _parameter_types(parameters: str) -> list[str]:
    result: list[str] = []
    for part in parameters.split(","):
        clean = re.sub(r"\[[^\]]+\]", "", part).strip()
        match = re.match(r"(?:ref\s+|out\s+|in\s+)?([A-Za-z_][\w<>,.?\[\]]*)\s+[A-Za-z_]\w*", clean)
        if match:
            result.append(match.group(1))
    return result


def _scan_backend(root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    files = _source_files(root, "backend")
    parsed = []
    failures = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        try:
            data, lexed = parse_backend_file(_read_text(path), relative)
            if lexed.errors:
                failures.append({"path": relative, "reason": "; ".join(lexed.errors[:5])})
                continue
            parsed.append((data, lexed))
        except (OSError, ValueError) as exc:
            failures.append({"path": relative, "reason": str(exc)[:120]})
    return bind_backend(parsed, len(files)), failures


def _data_access_kind(line: str) -> str | None:
    lowered = line.casefold()
    if "zeroentity" in lowered or "getrepository" in lowered:
        return "zero_entity"
    if any(term in lowered for term in ("db.select", "db.queryable", ".select<")):
        return "select"
    if any(term in lowered for term in ("db.insert", ".insert<", "insertrange")):
        return "insert"
    if any(term in lowered for term in ("db.update", ".update<")):
        return "update"
    if any(term in lowered for term in ("db.delete", ".delete<")):
        return "delete"
    return None


def _brace_delta(line: str) -> int:
    code = re.sub(r'@?"(?:""|\\.|[^"\\])*"', '""', line.split("//", 1)[0])
    return code.count("{") - code.count("}")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write_layer(work: Path, layer: str, data: dict[str, Any]) -> None:
    target = work / layer
    target.mkdir(parents=True, exist_ok=True)
    if layer == "frontend":
        mapping = {
            "components.json": data["components"],
            "component-contracts.json": data["component_contracts"],
            "requests.json": data["requests"],
            "route-candidates.json": data.get("route_candidates", []),
            "symbols.json": data["symbols"],
        }
    else:
        mapping = {
            "routes.json": data["routes"],
            "symbols.json": data["symbols"],
            "dto-contracts.json": data["dto_contracts"],
            "service-bindings.json": data["service_bindings"],
        }
    for filename, value in mapping.items():
        _write_json(target / filename, value)


def _commit_index(work: Path, target: Path) -> None:
    backup = target.parent / f".{target.name}.previous"
    if backup.exists():
        shutil.rmtree(backup)
    if target.exists():
        os.replace(target, backup)
    try:
        os.replace(work, target)
    except Exception:
        if backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def source_index_status(layers: Iterable[str] = ("frontend", "backend")) -> dict[str, Any]:
    target = source_index_root()
    manifest = _read_json(target / "manifest.json", {})
    repositories: dict[str, Any] = {}
    errors: list[dict[str, Any]] = []
    for layer in layers:
        try:
            resolution = resolve_repository(layer)
            indexed = (manifest.get("repositories") or {}).get(layer) or {}
            layer_errors = [item for item in manifest.get("errors", []) if item.get("layer") == layer]
            stale = indexed.get("fingerprint") != resolution["selected"]["fingerprint"] or indexed.get("index_version") != SOURCE_INDEX_VERSION or bool(layer_errors)
            errors.extend(layer_errors)
            repositories[layer] = {**resolution, "index": indexed, "stale": stale, "parse_incomplete": bool(indexed.get("stats", {}).get("parse_failures"))}
        except SourceRepositoryError as exc:
            errors.append({"layer": layer, "code": exc.code, "message": str(exc), **exc.details})
    return {
        "status": "ok" if not errors else "partial" if repositories else "error",
        "index": {
            "version": manifest.get("version"),
            "path": str(target),
            "built_at": manifest.get("built_at"),
            "generation": manifest.get("generation"),
            "exists": bool(manifest),
        },
        "repositories": repositories,
        "errors": errors,
        "runtime_verified": False,
    }


def refresh_source_index(force: bool = False, *, layers: Iterable[str] = ("frontend", "backend")) -> dict[str, Any]:
    started = time.monotonic()
    target = source_index_root()
    target.parent.mkdir(parents=True, exist_ok=True)
    with _FileLock(source_index_lock_path(), 60):
        current_manifest = _read_json(target / "manifest.json", {})
        resolutions: dict[str, Any] = {}
        layers = tuple(layers)
        errors: list[dict[str, Any]] = [item for item in current_manifest.get("errors", []) if item.get("layer") not in layers]
        for layer in layers:
            try:
                resolutions[layer] = resolve_repository(layer)
            except SourceRepositoryError as exc:
                errors.append({"layer": layer, "code": exc.code, "message": str(exc), **exc.details})
        unchanged = current_manifest.get("version") == SOURCE_INDEX_VERSION and resolutions and all(
            ((current_manifest.get("repositories") or {}).get(layer) or {}).get("fingerprint")
            == resolution["selected"]["fingerprint"]
            and ((current_manifest.get("repositories") or {}).get(layer) or {}).get("index_version") == SOURCE_INDEX_VERSION
            for layer, resolution in resolutions.items()
        )
        if unchanged and not force and not errors:
            return {"status": "ok", "skipped": True, "reason": "fingerprint_unchanged", "manifest": current_manifest, "runtime_verified": False}
        work = Path(tempfile.mkdtemp(prefix=".source-index-refresh-", dir=target.parent))
        if target.is_dir():
            shutil.copytree(target, work, dirs_exist_ok=True)
        repository_manifest = dict(current_manifest.get("repositories") or {})
        graph_edges = {layer: _read_json(work / "graph" / f"{layer}-call-edges.json", []) for layer in ("frontend", "backend")}
        stats: dict[str, Any] = {}
        try:
            for layer, resolution in resolutions.items():
                selected = resolution["selected"]
                indexed = (current_manifest.get("repositories") or {}).get(layer) or {}
                if not force and indexed.get("fingerprint") == selected["fingerprint"] and indexed.get("index_version") == SOURCE_INDEX_VERSION and not any(item.get("layer") == layer for item in current_manifest.get("errors", [])):
                    stats[layer] = {"status": "unchanged", **((current_manifest.get("repositories") or {}).get(layer) or {}).get("stats", {})}
                    graph_edges[layer] = _read_json(work / "graph" / f"{layer}-call-edges.json", [])
                    continue
                try:
                    data, failures = (_scan_frontend(Path(selected["path"])) if layer == "frontend" else _scan_backend(Path(selected["path"])))
                    if resolve_repository(layer)["selected"]["fingerprint"] != selected["fingerprint"]:
                        raise RuntimeError("SOURCE_CHANGED_DURING_BUILD")
                    staged = work / f".build-{layer}"
                    _write_layer(staged, layer, data)
                    _commit_index(staged / layer, work / layer)
                    shutil.rmtree(staged)
                    graph_edges[layer] = data["call_edges"]
                    layer_stats = {
                        "status": "refreshed",
                        "file_count": data["file_count"],
                        "component_count": len(data.get("components", [])),
                        "route_count": len(data.get("routes", [])) + len(data.get("requests", [])),
                        "dto_count": len(data.get("dto_contracts", [])),
                        "call_edge_count": len(data["call_edges"]),
                        "parse_failures": failures[:100],
                    }
                    stats[layer] = layer_stats
                    repository_manifest[layer] = {**selected, "index_version": SOURCE_INDEX_VERSION, "stats": layer_stats, "indexed_at": _now()}
                except Exception as exc:
                    errors.append({"layer": layer, "code": "INDEX_BUILD_FAILED", "message": f"{type(exc).__name__}: {str(exc)[:300]}"})
                    stats[layer] = {"status": "stale", "preserved": (work / layer).is_dir()}
            graph = work / "graph"
            graph.mkdir(parents=True, exist_ok=True)
            for layer, edges in graph_edges.items():
                _write_json(graph / f"{layer}-call-edges.json", edges)
            _write_json(graph / "call-edges.json", [*graph_edges["frontend"], *graph_edges["backend"]])
            route_edges = _read_json(work / "frontend" / "requests.json", []) + _read_json(work / "backend" / "routes.json", [])
            _write_json(graph / "route-edges.json", route_edges)
            manifest = {
                "version": SOURCE_INDEX_VERSION,
                "generation": uuid.uuid4().hex,
                "built_at": _now(),
                "repositories": repository_manifest,
                "stats": stats,
                "errors": errors,
            }
            for layer, resolution in resolutions.items():
                if stats.get(layer, {}).get("status") == "refreshed" and resolve_repository(layer)["selected"]["fingerprint"] != resolution["selected"]["fingerprint"]:
                    raise RuntimeError("SOURCE_CHANGED_BEFORE_COMMIT")
            _write_json(work / "repositories.json", {layer: value for layer, value in resolutions.items()})
            _write_json(work / "manifest.json", manifest)
            _commit_index(work, target)
        finally:
            if work.exists():
                shutil.rmtree(work, ignore_errors=True)
    return {
        "status": "ok" if not errors else "partial",
        "skipped": False,
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "repositories": stats,
        "errors": errors,
        "index_path": str(target),
        "runtime_verified": False,
    }


_READ_VIEW: ContextVar[dict[str, Any] | None] = ContextVar("source_read_view", default=None)


@contextmanager
def source_read_view(status: dict[str, Any]):
    token = _READ_VIEW.set(status)
    try:
        yield
    finally:
        _READ_VIEW.reset(token)


def source_index_generation() -> Any:
    manifest = _read_json(source_index_root() / "manifest.json", {})
    return manifest.get("generation", manifest.get("built_at"))


def ensure_source_index(layers: Iterable[str] = ("frontend", "backend")) -> dict[str, Any]:
    active = _READ_VIEW.get()
    if active is not None:
        return active
    layers = tuple(layers)
    status = source_index_status(layers)
    repositories = status.get("repositories") or {}
    if any(layer in repositories and repositories[layer].get("stale", True) for layer in layers):
        try:
            refresh_source_index(force=False, layers=layers)
            status = source_index_status(layers)
        except (OSError, TimeoutError, ValueError, RuntimeError) as exc:
            status["errors"].append({"code": "SOURCE_REFRESH_FAILED", "message": str(exc)[:200]})
    return status


def load_index_file(relative: str, default: Any) -> Any:
    active = _READ_VIEW.get()
    if active is not None:
        layer = relative.split("/", 1)[0]
        if layer == "graph":
            layer = relative.split("/", 1)[-1].split("-", 1)[0]
        repository = (active.get("repositories") or {}).get(layer) or {}
        if repository.get("stale", True) or repository.get("parse_incomplete"):
            return default
    return _read_json(source_index_root() / relative, default)



def bounded_result(result: dict[str, Any]) -> dict[str, Any]:
    return bounded_payload(result, MAX_RESPONSE_BYTES)
