from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .cpm_config import _atomic_json, _config_root, cpm_runtime_root
from .source_scope import is_source_dependency


SOURCE_CONFIG_VERSION = 1
SOURCE_INDEX_VERSION = 3
DEFAULT_REPOSITORIES = {
    "frontend": (
        Path(r"F:\cpm\gxp2.components"),
        Path(r"G:\hoyi\updateComponents\gxp2.components"),
    ),
    "backend": (
        Path(r"F:\cpm\gxp2.web"),
        Path(r"G:\hoyi\updateWeb\gxp2.web"),
    ),
}


class SourceRepositoryError(RuntimeError):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def source_config_path() -> Path:
    override = os.environ.get("GXP_LOWCODE_SOURCE_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    return _config_root() / "GxpLowcodeReadonly" / "source-repositories.json"


def source_index_root() -> Path:
    override = os.environ.get("GXP_LOWCODE_SOURCE_INDEX")
    if override:
        return Path(override).expanduser().resolve()
    return cpm_runtime_root() / "source-index"


def source_index_lock_path() -> Path:
    return cpm_runtime_root() / "source-index.lock"


def _absolute_paths(values: Iterable[Any], name: str) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        path = Path(text).expanduser()
        if not path.is_absolute():
            raise ValueError(f"{name} 中的仓库路径必须是绝对路径")
        normalized = str(path.resolve())
        key = normalized.casefold()
        if key not in seen:
            seen.add(key)
            result.append(normalized)
    return tuple(result)


@dataclass(frozen=True)
class SourceRepositoriesConfig:
    frontend: tuple[str, ...] = ()
    backend: tuple[str, ...] = ()
    preferred_frontend: str | None = None
    preferred_backend: str | None = None
    version: int = SOURCE_CONFIG_VERSION

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "SourceRepositoriesConfig":
        unknown_secrets = {
            key for key in raw if any(word in key.casefold() for word in ("password", "token", "secret", "credential"))
        }
        if unknown_secrets:
            raise ValueError("source-repositories.json 只允许保存本地仓库路径")
        frontend = _absolute_paths(raw.get("frontend") or (), "frontend")
        backend = _absolute_paths(raw.get("backend") or (), "backend")

        def preferred(name: str) -> str | None:
            value = str(raw.get(name) or "").strip()
            if not value:
                return None
            path = Path(value).expanduser()
            if not path.is_absolute():
                raise ValueError(f"{name} 必须是绝对路径")
            return str(path.resolve())

        config = cls(
            frontend=frontend,
            backend=backend,
            preferred_frontend=preferred("preferred_frontend"),
            preferred_backend=preferred("preferred_backend"),
            version=int(raw.get("version", SOURCE_CONFIG_VERSION)),
        )
        config.validate()
        return config

    def validate(self) -> None:
        if self.version != SOURCE_CONFIG_VERSION:
            raise ValueError("source-repositories.json 版本不受支持")
        for layer in ("frontend", "backend"):
            candidates = getattr(self, layer)
            preferred = getattr(self, f"preferred_{layer}")
            if preferred and preferred.casefold() not in {item.casefold() for item in candidates}:
                raise ValueError(f"preferred_{layer} 必须同时出现在 {layer} 候选列表中")

    def candidates(self, layer: str) -> tuple[Path, ...]:
        if layer not in DEFAULT_REPOSITORIES:
            raise ValueError("layer 必须是 frontend 或 backend")
        configured = [Path(item) for item in getattr(self, layer)]
        return tuple(Path(item) for item in _absolute_paths([*configured, *DEFAULT_REPOSITORIES[layer]], layer))

    def preferred(self, layer: str) -> Path | None:
        value = getattr(self, f"preferred_{layer}")
        return Path(value) if value else None


def load_source_config() -> SourceRepositoriesConfig:
    path = source_config_path()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return SourceRepositoriesConfig()
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("source-repositories.json 不是有效 UTF-8 JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("source-repositories.json 顶层必须是对象")
    return SourceRepositoriesConfig.from_dict(raw)


def save_source_config(config: SourceRepositoriesConfig) -> Path:
    config.validate()
    path = source_config_path()
    _atomic_json(path, asdict(config))
    return path


def _git_bytes(repo: Path, *arguments: str) -> bytes:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repo,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            creationflags=flags,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        raise SourceRepositoryError("GIT_METADATA_TIMEOUT", f"读取 Git 元数据超时: {repo}") from exc
    if result.returncode != 0:
        raise SourceRepositoryError("GIT_METADATA_FAILED", f"读取 Git 元数据失败: {repo}")
    return result.stdout


def _git(repo: Path, *arguments: str) -> str:
    return _git_bytes(repo, *arguments).decode("utf-8", errors="surrogateescape").strip()


def _dirty_entries(repo: Path) -> list[dict[str, Any]]:
    records = iter(_git_bytes(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0"))
    result = []
    for record in records:
        if not record:
            continue
        state = record[:2].decode("ascii")
        entry = {"status": state, "path": os.fsdecode(record[3:])}
        if "R" in state or "C" in state:
            entry["original_path"] = os.fsdecode(next(records, b""))
        result.append(entry)
    return result


def repository_metadata(repo: Path, *, layer: str | None = None) -> dict[str, Any]:
    requested = repo.expanduser().resolve()
    if not requested.is_dir():
        raise SourceRepositoryError("REPOSITORY_NOT_FOUND", f"源码仓库目录不存在: {requested}")
    identity = _git(requested, "rev-parse", "--show-toplevel", "HEAD", "--abbrev-ref", "HEAD").splitlines()
    if len(identity) != 3:
        raise SourceRepositoryError("GIT_METADATA_FAILED", "Git identity response was incomplete")
    root = Path(identity[0]).resolve()
    if os.path.normcase(str(root)) != os.path.normcase(str(requested)):
        raise SourceRepositoryError("REPOSITORY_ROOT_MISMATCH", f"源码路径必须直接指向 Git 根目录: {requested}")
    commit = identity[1]
    branch = identity[2] if identity[2] != "HEAD" else "DETACHED"
    dirty_files = _dirty_entries(root)
    try:
        remote = _git(root, "remote", "get-url", "origin")
    except SourceRepositoryError:
        remote = f"local:{root.name.casefold()}"
    remote_fingerprint = hashlib.sha256(remote.casefold().encode("utf-8", errors="surrogatepass")).hexdigest()
    relevant_dirty: list[dict[str, Any]] = []
    for entry in dirty_files:
        relevant = any(is_source_dependency(entry[name], layer) for name in ("path", "original_path") if name in entry)
        entry["index_relevant"] = relevant
        if not relevant:
            continue
        path = root / entry["path"]
        try:
            digest = hashlib.sha256()
            if path.is_symlink():
                digest.update(os.fsencode(os.readlink(path)))
            else:
                with path.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
            relevant_dirty.append({**entry, "content_hash": digest.hexdigest()})
        except FileNotFoundError:
            relevant_dirty.append({**entry, "missing": True})
        except OSError as exc:
            raise SourceRepositoryError("DIRTY_FILE_UNREADABLE", f"读取修改文件失败: {entry['path']}") from exc
    fingerprint_payload = {
        "version": SOURCE_INDEX_VERSION,
        "layer": layer,
        "root": str(root),
        "commit": commit,
        "dirty": relevant_dirty,
    }
    fingerprint = hashlib.sha256(
        json.dumps(fingerprint_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    dirty_by_path = {entry["path"]: entry for entry in relevant_dirty}
    return {
        "path": str(root),
        "branch": branch,
        "commit": commit,
        "remote_fingerprint": remote_fingerprint,
        "dirty_file_count": len(dirty_files),
        "dirty_files": [dirty_by_path.get(entry["path"], entry) for entry in dirty_files],
        "source_dirty_files": relevant_dirty,
        "source_dirty_file_count": len(relevant_dirty),
        "fingerprint_scope": layer or "repository",
        "fingerprint": fingerprint,
    }


def resolve_repository(
    layer: str,
    *,
    config: SourceRepositoriesConfig | None = None,
    override: Path | str | None = None,
) -> dict[str, Any]:
    if layer not in DEFAULT_REPOSITORIES:
        raise ValueError("layer 必须是 frontend 或 backend")
    config = config or load_source_config()
    candidates = (Path(override).expanduser().resolve(),) if override else config.candidates(layer)
    checked: list[dict[str, Any]] = []
    valid: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            metadata = repository_metadata(candidate, layer=layer)
            item = {"status": "valid", **metadata}
            valid.append(item)
        except SourceRepositoryError as exc:
            item = {"path": str(candidate), "status": "invalid", "error": {"code": exc.code, "message": str(exc)}}
        checked.append(item)
    if not valid:
        raise SourceRepositoryError(
            "REPOSITORY_NOT_FOUND",
            f"未找到可用的 {layer} 源码仓库",
            details={"layer": layer, "checked": checked},
        )
    preferred = Path(override).resolve() if override else config.preferred(layer)
    preferred_key = os.path.normcase(str(preferred.resolve())) if preferred else None
    distinct_commits = {item["commit"] for item in valid}
    distinct_remotes = {item["remote_fingerprint"] for item in valid}
    dirty_states = {json.dumps(item["source_dirty_files"], ensure_ascii=False, sort_keys=True) for item in valid}
    if (len(distinct_commits) > 1 or len(distinct_remotes) > 1 or len(dirty_states) > 1) and not preferred_key:
        raise SourceRepositoryError(
            "REPOSITORY_AMBIGUOUS",
            f"{layer} 存在来源或 commit 不一致的多个源码副本，请配置 preferred_{layer}",
            details={"layer": layer, "checked": checked, "candidates": valid},
        )
    selected = next(
        (item for item in valid if preferred_key and os.path.normcase(item["path"]) == preferred_key),
        valid[0],
    )
    if preferred_key and os.path.normcase(selected["path"]) != preferred_key:
        raise SourceRepositoryError(
            "PREFERRED_REPOSITORY_INVALID",
            f"preferred_{layer} 当前不可用",
            details={"layer": layer, "checked": checked},
        )
    mirrors = [item for item in valid if item["path"] != selected["path"]]
    return {
        "layer": layer,
        "selected": selected,
        "mirrors": mirrors,
        "checked": checked,
        "alternates_present": bool(mirrors),
        "commits_differ": len(distinct_commits) > 1,
        "remotes_differ": len(distinct_remotes) > 1,
    }


def resolve_repositories() -> dict[str, Any]:
    result: dict[str, Any] = {"status": "ok", "repositories": {}, "errors": []}
    for layer in ("frontend", "backend"):
        try:
            result["repositories"][layer] = resolve_repository(layer)
        except SourceRepositoryError as exc:
            result["status"] = "partial" if result["repositories"] else "error"
            result["errors"].append({"layer": layer, "code": exc.code, "message": str(exc), **exc.details})
    return result
