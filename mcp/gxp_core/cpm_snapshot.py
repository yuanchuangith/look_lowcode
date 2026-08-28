from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from .cpm_config import CpmConfig, load_cpm_config
from .cpm_runner import CpmRefreshManager


MAX_LIMIT = 100
MAX_QUERY_CHARS = 256
MAX_SCAN_FILES = 5000
MAX_SEARCH_FILE_BYTES = 1_000_000
MAX_SEARCH_READ_CHARS = 64_000
MAX_SECTION_CHARS = 20_000
MAX_TOTAL_INSPECT_CHARS = 120_000
MAX_KNOWLEDGE_CHARS = 50_000

RESOURCE_ROOTS = {
    "pages": ("pages",),
    "menus": ("menus", "navigations"),
    "components": ("pages",),
    "models": ("models",),
    "datasets": ("datasets",),
    "dictionaries": ("dictionaries",),
    "events": ("events",),
    "workflows": ("flows",),
    "interfaces": ("interfaces",),
    "public_actions": ("public-bizflows",),
}


class SnapshotError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _bounded_limit(limit: int) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise SnapshotError("INVALID_ARGUMENT", "limit 必须是正整数")
    return min(limit, MAX_LIMIT)


def _snapshot_root(config: CpmConfig) -> Path:
    root = Path(config.snapshot_dir).resolve()
    if not root.is_dir():
        raise SnapshotError("SNAPSHOT_MISSING", "CPM 快照尚未初始化")
    manifest = root / "manifest.json"
    value = _read_json(manifest, max_bytes=2_000_000) if manifest.is_file() else None
    if not isinstance(value, dict):
        raise SnapshotError("SNAPSHOT_MALFORMED", "快照 manifest.json 缺失或无效")
    missing_indexes = [
        name
        for name in ("pages.md", "model-usage.md", "component-usage.md", "event-usage.md")
        if not (root / "indexes" / name).is_file()
    ]
    if missing_indexes:
        raise SnapshotError("SNAPSHOT_INDEX_MISSING", f"快照缺少索引: {', '.join(missing_indexes)}")
    return root


def _safe_child(root: Path, *parts: str) -> Path:
    path = root.joinpath(*parts).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise SnapshotError("PATH_TRAVERSAL", "拒绝读取快照目录以外的路径") from exc
    return path


def _read_utf8(path: Path, max_bytes: int, max_chars: int) -> tuple[str, bool]:
    try:
        if path.stat().st_size > max_bytes:
            raise SnapshotError("FILE_TOO_LARGE", f"文件超过读取上限: {path.name}")
        text = path.read_text(encoding="utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SnapshotError("NON_UTF8_FILE", f"文件不是 UTF-8: {path.name}") from exc
    except OSError as exc:
        raise SnapshotError("FILE_READ_FAILED", f"无法读取文件: {path.name}") from exc
    return text[:max_chars], len(text) > max_chars


def _read_json(path: Path, max_bytes: int = MAX_SEARCH_FILE_BYTES) -> Any:
    text, _ = _read_utf8(path, max_bytes, max_bytes)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SnapshotError("MALFORMED_JSON", f"JSON 损坏: {path.name}") from exc


def _refresh_context(manager: CpmRefreshManager, refresh: dict[str, Any] | None) -> dict[str, Any]:
    status = manager.snapshot_status()
    return {
        "source": "cpm_snapshot",
        "refreshed_at": (refresh or {}).get("refreshed_at") or status.get("refreshed_at"),
        "cli_version": (refresh or {}).get("cli_version") or status.get("cli_version"),
        "refresh_mode": (refresh or {}).get("refresh_mode"),
        "failures": list((refresh or {}).get("failures") or status.get("failures") or []),
    }


def _prepare(refresh_if_stale: bool, page_identifier: str | None = None) -> tuple[CpmConfig, CpmRefreshManager, dict[str, Any]]:
    config = load_cpm_config()
    manager = CpmRefreshManager(config)
    refresh = manager.ensure_fresh(page_identifier) if refresh_if_stale else None
    if refresh and not refresh.get("ok"):
        error = refresh.get("error") or {}
        raise SnapshotError(str(error.get("code", "REFRESH_FAILED")), str(error.get("message", "CPM 快照刷新失败")))
    return config, manager, _refresh_context(manager, refresh)


def cpm_snapshot_status() -> dict[str, Any]:
    """Return local CPM snapshot freshness, CLI version, failures, and refresh history."""
    try:
        return CpmRefreshManager().snapshot_status()
    except Exception as exc:
        return {
            "source": "cpm_snapshot",
            "configured": False,
            "refresh_mode": None,
            "refreshed_at": None,
            "cli_version": None,
            "failures": [{"type": "CONFIG_ERROR", "reason": str(exc)[:1000]}],
            "error": {"code": "CONFIG_ERROR", "message": str(exc)[:1000]},
        }


def refresh_cpm_snapshot(force: bool = False, page_identifier: str | None = None) -> dict[str, Any]:
    """Refresh only the local read-only snapshot; use one page when a safe full baseline exists."""
    try:
        if page_identifier is not None and (not isinstance(page_identifier, str) or not page_identifier.strip()):
            raise SnapshotError("INVALID_ARGUMENT", "page_identifier 不能为空")
        return CpmRefreshManager().refresh(force=bool(force), page_identifier=page_identifier)
    except SnapshotError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(SnapshotError("REFRESH_FAILED", str(exc)[:1000]))


def _iter_files(root: Path, resource_types: Iterable[str]) -> Iterable[tuple[str, Path]]:
    seen: set[Path] = set()
    yielded = 0
    for resource_type in resource_types:
        for rel_root in RESOURCE_ROOTS[resource_type]:
            base = _safe_child(root, rel_root)
            if not base.is_dir():
                continue
            for path in base.rglob("*"):
                if yielded >= MAX_SCAN_FILES:
                    return
                if not path.is_file() or path.is_symlink() or path in seen:
                    continue
                try:
                    path.resolve().relative_to(root)
                except (OSError, ValueError):
                    continue
                if resource_type == "components" and path.name not in {"components.json", "tree.md", "page-meta.json"}:
                    continue
                if resource_type == "pages" and path.name != "page-meta.json":
                    continue
                seen.add(path)
                yielded += 1
                yield resource_type, path


def search_platform_snapshot(
    query: str,
    resource_types: list[str] | None = None,
    limit: int = 20,
    refresh_if_stale: bool = True,
) -> dict[str, Any]:
    """Search bounded CPM page/menu/component/model/dataset/dictionary/event/flow/interface/action evidence."""
    try:
        if not isinstance(query, str) or not query.strip() or len(query) > MAX_QUERY_CHARS:
            raise SnapshotError("INVALID_ARGUMENT", f"query 必须为 1-{MAX_QUERY_CHARS} 个字符")
        actual_limit = _bounded_limit(limit)
        types = resource_types or list(RESOURCE_ROOTS)
        if not isinstance(types, list) or not types or any(item not in RESOURCE_ROOTS for item in types):
            raise SnapshotError("INVALID_RESOURCE_TYPE", f"resource_types 仅支持: {', '.join(RESOURCE_ROOTS)}")
        config, manager, context = _prepare(refresh_if_stale)
        root = _snapshot_root(config)
        needle = query.casefold()
        results: list[dict[str, Any]] = []
        read_failures: list[dict[str, str]] = []
        for resource_type, path in _iter_files(root, types):
            rel = path.relative_to(root).as_posix()
            haystack = rel.casefold()
            snippet = ""
            if needle not in haystack:
                try:
                    text, _ = _read_utf8(path, MAX_SEARCH_FILE_BYTES, MAX_SEARCH_READ_CHARS)
                    index = text.casefold().find(needle)
                    if index < 0:
                        continue
                    snippet = text[max(0, index - 100) : index + len(query) + 180].replace("\n", " ")
                except SnapshotError as exc:
                    read_failures.append({"type": exc.code, "reason": str(exc), "path": rel})
                    continue
            results.append({"resource_type": resource_type, "path": rel, "snippet": snippet[:300]})
            if len(results) >= actual_limit:
                break
        context["failures"].extend(read_failures[:20])
        return {**context, "ok": True, "query": query, "resource_types": types, "count": len(results), "limit": actual_limit, "results": results}
    except SnapshotError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(SnapshotError("SNAPSHOT_SEARCH_FAILED", str(exc)[:1000]))


def _page_metadata(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    pages = _safe_child(root, "pages")
    if not pages.is_dir():
        raise SnapshotError("SNAPSHOT_MALFORMED", "快照缺少 pages 目录")
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in pages.glob("*/page-meta.json"):
        if path.is_symlink() or path.parent.is_symlink():
            continue
        try:
            path.resolve().relative_to(root)
        except (OSError, ValueError):
            continue
        value = _read_json(path)
        if not isinstance(value, dict) or any(not isinstance(value.get(key), str) for key in ("route", "id", "outId", "name", "dir")):
            raise SnapshotError("SNAPSHOT_MALFORMED", f"页面元数据无效: {path.parent.name}")
        records.append((path.parent, value))
    if not records:
        raise SnapshotError("PARTIAL_BASELINE_REQUIRED", "快照缺少 page-meta.json，请先全量刷新")
    return records


def _resolve_page(root: Path, identifier: str) -> tuple[Path, dict[str, Any]]:
    records = _page_metadata(root)
    exact = [row for row in records if identifier in {row[1]["route"], row[1]["id"], row[1]["outId"], row[1]["name"], row[0].name}]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise SnapshotError("PAGE_AMBIGUOUS", "页面标识命中多个页面，请使用 Route/Id/OutId")
    folded = identifier.casefold()
    candidates = [row for row in records if folded in row[1]["route"].casefold() or folded in row[1]["name"].casefold()]
    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        raise SnapshotError("PAGE_AMBIGUOUS", "页面名称命中多个候选，请使用精确 Route/Id/OutId")
    raise SnapshotError("PAGE_NOT_FOUND", f"快照中未找到页面: {identifier}")


def inspect_page_snapshot(
    page_identifier: str,
    sections: list[str] | None = None,
    limit: int = 50,
    refresh_if_stale: bool = True,
) -> dict[str, Any]:
    """Inspect one CPM snapshot page by Route, Id, OutId, display name, or snapshot directory."""
    allowed = {"meta", "tree", "components", "bindings", "bizflows"}
    try:
        if not isinstance(page_identifier, str) or not page_identifier.strip() or len(page_identifier) > MAX_QUERY_CHARS:
            raise SnapshotError("INVALID_ARGUMENT", "page_identifier 无效")
        selected = sections or ["meta", "tree", "components", "bindings", "bizflows"]
        if not isinstance(selected, list) or not selected or any(item not in allowed for item in selected):
            raise SnapshotError("INVALID_SECTION", f"sections 仅支持: {', '.join(sorted(allowed))}")
        actual_limit = _bounded_limit(limit)
        config, manager, context = _prepare(refresh_if_stale, page_identifier)
        root = _snapshot_root(config)
        page_dir, meta = _resolve_page(root, page_identifier)
        entries: list[dict[str, Any]] = []
        budget = MAX_TOTAL_INSPECT_CHARS

        def add_file(section: str, path: Path) -> None:
            nonlocal budget
            if budget <= 0 or len(entries) >= actual_limit or not path.is_file():
                return
            text, truncated = _read_utf8(path, 2_000_000, min(MAX_SECTION_CHARS, budget))
            budget -= len(text)
            entries.append({"section": section, "path": path.relative_to(root).as_posix(), "content": text, "truncated": truncated})

        if "meta" in selected:
            entries.append({"section": "meta", "path": f"{meta['dir']}/page-meta.json", "content": meta, "truncated": False})
        if "tree" in selected:
            add_file("tree", page_dir / "tree.md")
        if "components" in selected:
            add_file("components", page_dir / "components.json")
        if "bindings" in selected:
            add_file("bindings", page_dir / "bindings.md")
        if "bizflows" in selected:
            bizflows = page_dir / "bizflows"
            if bizflows.is_dir():
                for path in sorted(bizflows.rglob("*")):
                    if path.is_file():
                        add_file("bizflows", path)
                        if len(entries) >= actual_limit or budget <= 0:
                            break
        return {**context, "ok": True, "page": meta, "sections": selected, "count": len(entries), "limit": actual_limit, "entries": entries}
    except SnapshotError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(SnapshotError("PAGE_INSPECTION_FAILED", str(exc)[:1000]))


def _knowledge_path(root: Path, kind: str, name: str) -> Path:
    skill_root = _safe_child(root, "skills", "cpm-platform")
    if kind == "skill" and name in {"main", "cpm-platform"}:
        return _safe_child(skill_root, "SKILL.md")
    if kind == "component":
        if not name or any(char in name for char in ("/", "\\")) or name in {".", ".."}:
            raise SnapshotError("KNOWLEDGE_NOT_ALLOWED", "组件名称必须是单个文件名")
        components = _safe_child(skill_root, "references", "components")
        matches = [path for path in components.glob("*.md") if path.stem.casefold() == name.casefold()]
        if len(matches) == 1:
            return _safe_child(components, matches[0].name)
        raise SnapshotError("KNOWLEDGE_NOT_FOUND", f"未找到组件知识: {name}")
    if kind == "reference":
        allowed = {"data-resources", "flows", "interfaces", "languages", "menus"}
        if name not in allowed:
            raise SnapshotError("KNOWLEDGE_NOT_ALLOWED", f"reference 仅支持: {', '.join(sorted(allowed))}")
        return _safe_child(skill_root, "references", f"{name}.md")
    if kind == "element":
        normalized = name.replace("\\", "/")
        parts = normalized.split("/")
        if len(parts) != 2 or any(part in {"", ".", ".."} for part in parts):
            raise SnapshotError("KNOWLEDGE_NOT_ALLOWED", "element 名称必须是 <分类>/<元件名>")
        return _safe_child(skill_root, "references", "elements", parts[0], f"{parts[1]}.md")
    raise SnapshotError("KNOWLEDGE_NOT_ALLOWED", "kind 仅支持 skill、component、reference、element")


def get_cpm_knowledge(kind: str, name: str, max_chars: int = 12000) -> dict[str, Any]:
    """Read one allow-listed cpm-platform skill topic from the local snapshot."""
    try:
        if not isinstance(kind, str) or not isinstance(name, str):
            raise SnapshotError("INVALID_ARGUMENT", "kind 和 name 必须是字符串")
        if not isinstance(max_chars, int) or isinstance(max_chars, bool) or max_chars < 1:
            raise SnapshotError("INVALID_ARGUMENT", "max_chars 必须是正整数")
        actual_max = min(max_chars, MAX_KNOWLEDGE_CHARS)
        config, manager, context = _prepare(False)
        root = _snapshot_root(config)
        path = _knowledge_path(root, kind, name)
        if not path.is_file():
            raise SnapshotError("KNOWLEDGE_NOT_FOUND", f"知识主题不存在: {kind}/{name}")
        content, truncated = _read_utf8(path, 2_000_000, actual_max)
        return {
            **context,
            "ok": True,
            "kind": kind,
            "name": name,
            "path": path.relative_to(root).as_posix(),
            "content": content,
            "truncated": truncated,
            "max_chars": actual_max,
        }
    except SnapshotError as exc:
        return _error_response(exc)
    except Exception as exc:
        return _error_response(SnapshotError("KNOWLEDGE_READ_FAILED", str(exc)[:1000]))


def _error_response(exc: SnapshotError) -> dict[str, Any]:
    return {
        "source": "cpm_snapshot",
        "ok": False,
        "refreshed_at": None,
        "cli_version": None,
        "refresh_mode": None,
        "failures": [{"type": exc.code, "reason": str(exc)}],
        "error": {"code": exc.code, "message": str(exc)},
    }
