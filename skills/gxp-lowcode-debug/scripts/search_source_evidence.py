from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
MCP_ROOT = PLUGIN_ROOT / "mcp"
if str(MCP_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_ROOT))

from gxp_core.source_config import SourceRepositoryError, resolve_repository


MAX_EXACT_TERMS = 8
MAX_PAIRS = 4
MAX_FILES = 20
MAX_CONTEXT_FILES = 5
MAX_RESPONSE_BYTES = 32 * 1024
MAX_TERM_LENGTH = 160
SEARCH_DEADLINE_SECONDS = 30
EXCLUDED_GLOBS = (
    "!.git/**",
    "!**/.git/**",
    "!node_modules/**",
    "!**/node_modules/**",
    "!dist/**",
    "!**/dist/**",
    "!bin/**",
    "!**/bin/**",
    "!obj/**",
    "!**/obj/**",
    "!**/.cache/**",
    "!**/cache/**",
    "!**/coverage/**",
    "!**/.next/**",
    "!**/build/**",
    "!**/out/**",
    "!**/generated/**",
)
SOURCE_GLOBS = {
    "frontend": ("*.ts", "*.tsx", "*.js", "*.jsx", "*.vue"),
    "backend": ("*.cs",),
}
SOURCE_ROOTS = {
    "frontend": ("src/core/components", "src/core/common", "src/core/entry", "src/basic"),
    "backend": ("GxP2.Web/Controllers", "GxP2.IServices", "GxP2.Services", "GxP2.Model/Dto"),
}


class SourceSearchError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _unique(values: Iterable[str], limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = " ".join(str(value or "").split()).strip()
        if not cleaned or len(cleaned) > MAX_TERM_LENGTH:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def _run(arguments: list[str], *, cwd: Path, timeout: float = SEARCH_DEADLINE_SECONDS) -> subprocess.CompletedProcess[bytes]:
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    return subprocess.run(
        arguments,
        cwd=cwd,
        capture_output=True,
        timeout=max(0.1, timeout),
        creationflags=flags,
        check=False,
    )


def _rg_base(rg: str, layer: str) -> list[str]:
    arguments = [rg, "--hidden", "--no-messages"]
    for pattern in SOURCE_GLOBS[layer]:
        arguments.extend(["--glob", pattern])
    for pattern in EXCLUDED_GLOBS:
        arguments.extend(["--glob", pattern])
    return arguments


def _search_roots(repo: Path, layer: str) -> list[str]:
    roots = [item for item in SOURCE_ROOTS[layer] if (repo / item).is_dir()]
    return roots or ["."]


def _json_events(output: bytes) -> Iterable[dict[str, Any]]:
    for raw in output.splitlines():
        if not raw.strip():
            continue
        try:
            event = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(event, dict):
            yield event


def _matching_files(rg: str, repo: Path, layer: str, term: str, timeout: float) -> list[str]:
    result = _run(
        [
            *_rg_base(rg, layer),
            "--files-with-matches",
            "--fixed-strings",
            "--ignore-case",
            "--null",
            "--",
            term,
            *_search_roots(repo, layer),
        ],
        cwd=repo,
        timeout=timeout,
    )
    if result.returncode not in (0, 1):
        stderr = result.stderr.decode("utf-8", errors="replace").strip()[:300]
        raise SourceSearchError("rg_failed", f"rg failed in {repo}: {stderr}")
    return [
        Path(raw.decode("utf-8", errors="surrogateescape")).as_posix().removeprefix("./")
        for raw in result.stdout.split(b"\0")
        if raw.strip()
    ]


def _file_context(rg: str, repo: Path, layer: str, relative_path: str, terms: list[str], lines: int, timeout: float) -> str:
    arguments = [
        *_rg_base(rg, layer),
        "--json",
        "--fixed-strings",
        "--ignore-case",
        "--max-count",
        "20",
    ]
    for term in terms:
        arguments.extend(["-e", term])
    arguments.extend(["--", relative_path])
    result = _run(arguments, cwd=repo, timeout=timeout)
    if result.returncode not in (0, 1):
        raise SourceSearchError("rg_context_failed", f"rg context read failed for {relative_path}")
    matched_lines: list[int] = []
    for event in _json_events(result.stdout):
        if event.get("type") == "match":
            line_number = (event.get("data") or {}).get("line_number")
            if isinstance(line_number, int):
                matched_lines.append(line_number)
    try:
        source_lines = (repo / relative_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    selected: set[int] = set()
    for line_number in matched_lines:
        selected.update(range(max(1, line_number - lines), min(len(source_lines), line_number + lines) + 1))
    rendered = [f"{relative_path}:{index}:{source_lines[index - 1]}" for index in sorted(selected)]
    return "\n".join(rendered)[:8192]


def _role_rank(layer: str, path: str) -> int:
    value = path.replace("\\", "/").casefold()
    if any(part in value for part in ("/docs/", "/knowledge/", "/codemaps/")):
        return 90
    if layer == "frontend":
        if "/preview/web/" in value or "/preview/wap/" in value:
            return 0
        if "/designer/" in value:
            return 1
        if value.endswith(("/api.ts", "/service.ts", "/api.tsx", "/service.tsx")):
            return 2
        if "/components/" in value:
            return 3
        return 10
    if "/controllers/" in value:
        return 0
    if "/gxp2.services/" in value or value.startswith("gxp2.services/"):
        return 1
    if "/gxp2.iservices/" in value or value.startswith("gxp2.iservices/"):
        return 2
    if "/dto/" in value:
        return 3
    return 10


def _bounded(result: dict[str, Any]) -> dict[str, Any]:
    def encoded_size() -> int:
        return len(json.dumps(result, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))

    if encoded_size() <= MAX_RESPONSE_BYTES:
        return result
    result["response_truncated"] = True
    for hit in reversed(result.get("files") or []):
        if hit.get("context"):
            hit["context"] = str(hit["context"])[:1024]
        if encoded_size() <= MAX_RESPONSE_BYTES:
            return result
    while len(result.get("files") or []) > 5 and encoded_size() > MAX_RESPONSE_BYTES:
        result["files"].pop()
    if encoded_size() > MAX_RESPONSE_BYTES:
        for hit in result.get("files") or []:
            hit.pop("context", None)
    return result


def search_source_evidence(
    *,
    layer: str,
    terms: list[str],
    pairs: list[list[str]],
    frontend_repo: Path | None = None,
    backend_repo: Path | None = None,
    context_lines: int = 3,
    rg_path: str | None = None,
) -> dict[str, Any]:
    if layer not in {"frontend", "backend", "both"}:
        raise SourceSearchError("invalid_layer", "layer must be frontend, backend, or both")
    exact_terms = _unique(terms, MAX_EXACT_TERMS)
    clean_pairs: list[list[str]] = []
    for pair in pairs[:MAX_PAIRS]:
        cleaned = _unique(pair, 2)
        if len(cleaned) == 2:
            clean_pairs.append(cleaned)
    if not exact_terms and not clean_pairs:
        raise SourceSearchError("missing_terms", "At least one --term or complete --pair is required")
    rg = rg_path or shutil.which("rg")
    if not rg:
        raise SourceSearchError("rg_unavailable", "rg is required; source scope was not expanded")

    repositories: list[tuple[str, Path, dict[str, Any]]] = []
    if layer in {"frontend", "both"}:
        try:
            resolved = resolve_repository("frontend", override=frontend_repo)
        except SourceRepositoryError as exc:
            raise SourceSearchError(exc.code.casefold(), str(exc)) from exc
        repositories.append(("frontend", Path(resolved["selected"]["path"]), resolved))
    if layer in {"backend", "both"}:
        try:
            resolved = resolve_repository("backend", override=backend_repo)
        except SourceRepositoryError as exc:
            raise SourceSearchError(exc.code.casefold(), str(exc)) from exc
        repositories.append(("backend", Path(resolved["selected"]["path"]), resolved))

    all_terms = _unique([*exact_terms, *(term for pair in clean_pairs for term in pair)], MAX_EXACT_TERMS + MAX_PAIRS * 2)
    repository_info = []
    hits: list[dict[str, Any]] = []
    deadline = time.monotonic() + SEARCH_DEADLINE_SECONDS
    truncated_reason: str | None = None
    for repo_layer, repo, resolution in repositories:
        repository_info.append({"layer": repo_layer, **resolution["selected"], "mirrors": resolution["mirrors"]})
        matched_by_path: dict[str, set[str]] = {}
        for term in all_terms:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                truncated_reason = "deadline"
                break
            try:
                paths = _matching_files(rg, repo, repo_layer, term, remaining)
            except subprocess.TimeoutExpired:
                truncated_reason = "deadline"
                break
            for path in paths:
                matched_by_path.setdefault(path, set()).add(term)
        for path, matched in matched_by_path.items():
            exact_matches = [term for term in exact_terms if term in matched]
            matched_pairs = [pair for pair in clean_pairs if all(term in matched for term in pair)]
            if not exact_matches and not matched_pairs:
                continue
            hits.append(
                {
                    "layer": repo_layer,
                    "repository": str(repo),
                    "path": path,
                    "matched_term_count": len(matched),
                    "matched_terms": [term for term in all_terms if term in matched],
                    "matched_pairs": matched_pairs,
                }
            )

    hits.sort(
        key=lambda item: (
            -item["matched_term_count"],
            _role_rank(item["layer"], item["path"]),
            -len(item["matched_pairs"]),
            item["path"].casefold(),
            item["layer"],
        )
    )
    total_file_count = len(hits)
    hits = hits[:MAX_FILES]
    for hit in hits[:MAX_CONTEXT_FILES]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            truncated_reason = "deadline"
            break
        hit["context"] = _file_context(
            rg,
            Path(hit["repository"]),
            hit["layer"],
            hit["path"],
            hit["matched_terms"],
            max(0, min(int(context_lines), 10)),
            remaining,
        )
    result = {
        "status": "ok" if hits else "no_matches",
        "scope_expanded": False,
        "repositories": repository_info,
        "search": {
            "layer": layer,
            "terms": exact_terms,
            "pairs": clean_pairs,
            "case_sensitive": False,
            "excluded_globs": list(EXCLUDED_GLOBS),
        },
        "matched_file_count": total_file_count,
        "returned_file_count": len(hits),
        "files_truncated": total_file_count > len(hits),
        "contexts_truncated": len(hits) > MAX_CONTEXT_FILES,
        "files": hits,
    }
    if truncated_reason:
        result["truncated_reason"] = truncated_reason
    if not hits:
        result["error"] = {
            "code": "no_matches",
            "message": "No source evidence matched the supplied anchors; no broader directory was searched.",
        }
    return _bounded(result)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search bounded read-only GXP source evidence with rg.")
    parser.add_argument("--layer", choices=("frontend", "backend", "both"), required=True)
    parser.add_argument("--term", action="append", default=[])
    parser.add_argument("--pair", action="append", nargs=2, metavar=("FIRST", "SECOND"), default=[])
    parser.add_argument("--frontend-repo", type=Path)
    parser.add_argument("--backend-repo", type=Path)
    parser.add_argument("--context-lines", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = search_source_evidence(
            layer=args.layer,
            terms=args.term,
            pairs=args.pair,
            frontend_repo=args.frontend_repo,
            backend_repo=args.backend_repo,
            context_lines=args.context_lines,
        )
        exit_code = 0 if result["status"] == "ok" else 1
    except (SourceSearchError, subprocess.TimeoutExpired) as exc:
        code = exc.code if isinstance(exc, SourceSearchError) else "search_timeout"
        result = {
            "status": "error",
            "scope_expanded": False,
            "error": {"code": code, "message": str(exc)[:500]},
        }
        exit_code = 2
    print(json.dumps(_bounded(result), ensure_ascii=False, separators=(",", ":")))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
