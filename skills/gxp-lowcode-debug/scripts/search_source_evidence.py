from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable


DEFAULT_FRONTEND_REPO = Path(r"G:\hoyi\updateComponents\gxp2.components")
DEFAULT_BACKEND_REPO = Path(r"G:\hoyi\updateWeb\gxp2.web")
MAX_EXACT_TERMS = 8
MAX_PAIRS = 4
MAX_FILES = 20
MAX_CONTEXT_FILES = 5
MAX_RESPONSE_BYTES = 32 * 1024
MAX_TERM_LENGTH = 160
EXCLUDED_GLOBS = (
    "!**/.git/**",
    "!**/node_modules/**",
    "!**/dist/**",
    "!**/bin/**",
    "!**/obj/**",
    "!**/.cache/**",
    "!**/cache/**",
    "!**/coverage/**",
    "!**/.next/**",
    "!**/build/**",
    "!**/out/**",
    "!**/generated/**",
)


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


def _run(arguments: list[str], *, cwd: Path, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def _repository_metadata(repo: Path) -> dict[str, Any]:
    root = _run(["git", "rev-parse", "--show-toplevel"], cwd=repo)
    if root.returncode != 0:
        raise SourceSearchError("not_git_repository", f"Source repository is not a readable Git checkout: {repo}")
    resolved_root = Path(root.stdout.strip()).resolve()
    if resolved_root != repo.resolve():
        raise SourceSearchError(
            "repository_root_mismatch",
            f"Source repository override must point to its Git root: {repo}",
        )
    commit = _run(["git", "rev-parse", "HEAD"], cwd=repo)
    branch = _run(["git", "branch", "--show-current"], cwd=repo)
    status = _run(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo)
    if any(item.returncode != 0 for item in (commit, branch, status)):
        raise SourceSearchError("git_metadata_failed", f"Cannot read source repository metadata: {repo}")
    dirty_lines = [line for line in status.stdout.splitlines() if line.strip()]
    return {
        "path": str(resolved_root),
        "branch": branch.stdout.strip() or "DETACHED",
        "commit": commit.stdout.strip(),
        "dirty_file_count": len(dirty_lines),
    }


def _rg_base(rg: str) -> list[str]:
    arguments = [rg, "--hidden", "--no-messages"]
    for pattern in EXCLUDED_GLOBS:
        arguments.extend(["--glob", pattern])
    return arguments


def _matching_files(rg: str, repo: Path, term: str) -> list[str]:
    result = _run(
        [*_rg_base(rg), "--files-with-matches", "--fixed-strings", "--ignore-case", "--null", "--", term, "."],
        cwd=repo,
    )
    if result.returncode not in (0, 1):
        raise SourceSearchError("rg_failed", f"rg failed in {repo}: {result.stderr.strip()[:300]}")
    return [
        Path(item).as_posix().removeprefix("./")
        for item in result.stdout.split("\0")
        if item.strip()
    ]


def _file_context(rg: str, repo: Path, relative_path: str, terms: list[str], lines: int) -> str:
    arguments = [
        *_rg_base(rg),
        "--line-number",
        "--with-filename",
        "--fixed-strings",
        "--ignore-case",
        "--max-count",
        "20",
        "--context",
        str(lines),
    ]
    for term in terms:
        arguments.extend(["-e", term])
    arguments.extend(["--", relative_path])
    result = _run(arguments, cwd=repo)
    if result.returncode not in (0, 1):
        raise SourceSearchError("rg_context_failed", f"rg context read failed for {relative_path}")
    return result.stdout[:8192]


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
    frontend_repo: Path = DEFAULT_FRONTEND_REPO,
    backend_repo: Path = DEFAULT_BACKEND_REPO,
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

    repositories: list[tuple[str, Path]] = []
    if layer in {"frontend", "both"}:
        repositories.append(("frontend", frontend_repo.expanduser().resolve()))
    if layer in {"backend", "both"}:
        repositories.append(("backend", backend_repo.expanduser().resolve()))
    for _, repo in repositories:
        if not repo.is_dir():
            raise SourceSearchError("repository_not_found", f"Configured source repository was not found: {repo}")

    all_terms = _unique([*exact_terms, *(term for pair in clean_pairs for term in pair)], MAX_EXACT_TERMS + MAX_PAIRS * 2)
    repository_info = []
    hits: list[dict[str, Any]] = []
    for repo_layer, repo in repositories:
        repository_info.append({"layer": repo_layer, **_repository_metadata(repo)})
        matched_by_path: dict[str, set[str]] = {}
        for term in all_terms:
            for path in _matching_files(rg, repo, term):
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

    hits.sort(key=lambda item: (-item["matched_term_count"], item["path"].casefold(), item["layer"]))
    total_file_count = len(hits)
    hits = hits[:MAX_FILES]
    for hit in hits[:MAX_CONTEXT_FILES]:
        hit["context"] = _file_context(
            rg,
            Path(hit["repository"]),
            hit["path"],
            hit["matched_terms"],
            max(0, min(int(context_lines), 10)),
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
    parser.add_argument("--frontend-repo", type=Path, default=DEFAULT_FRONTEND_REPO)
    parser.add_argument("--backend-repo", type=Path, default=DEFAULT_BACKEND_REPO)
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
