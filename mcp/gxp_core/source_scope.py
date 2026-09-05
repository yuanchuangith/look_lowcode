from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath


FRONTEND_EXTENSIONS = {".ts", ".tsx", ".js", ".jsx", ".vue"}
BACKEND_EXTENSIONS = {".cs"}
EXCLUDED_PARTS = {".git", ".vs", ".dist", "node_modules", "dist", "bin", "obj", "build", "out", "generated", "coverage", "wwwroot", "dbinit"}
FRONTEND_ROOTS = ("src/core/components", "src/core/common", "src/core/entry", "src/basic")
BACKEND_ROOTS = ("GxP2.Web/Controllers", "GxP2.IServices", "GxP2.Services", "GxP2.Model/Dto")
CONFIG_PATTERNS = {
    "frontend": ("package.json", "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock", "tsconfig*.json", "jsconfig*.json", "*.config.js", "*.config.ts", "*.config.mjs", "*.config.cjs", ".env", ".env.*", ".babelrc*", ".npmrc"),
    "backend": ("*.csproj", "*.sln", "*.slnx", "*.props", "*.targets", "global.json", "nuget.config", "packages.lock.json", "appsettings*.json"),
}


def is_source_dependency(relative: str, layer: str | None) -> bool:
    if layer is None:
        return True
    path = PurePosixPath(relative.replace("\\", "/").casefold())
    if any(part in EXCLUDED_PARTS for part in path.parts[:-1]):
        return False
    if path.name in {".gitignore", ".gitattributes"} or any(fnmatch.fnmatchcase(path.name, pattern) for pattern in CONFIG_PATTERNS[layer]):
        return True
    roots, extensions = (FRONTEND_ROOTS, FRONTEND_EXTENSIONS) if layer == "frontend" else (BACKEND_ROOTS, BACKEND_EXTENSIONS)
    return path.suffix in extensions and any(path.as_posix().startswith(root.casefold() + "/") for root in roots)
