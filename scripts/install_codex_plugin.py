from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from setup import install_runtime, runtime_root


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_NAME = "gxp-lowcode-readonly"
MARKETPLACE_NAME = "look-lowcode-local"


def _copy_entry(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns(
                ".git",
                ".venv",
                "node_modules",
                "__pycache__",
                "*.pyc",
                "tests",
                "test",
            ),
        )
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _plugin_payload(staged: Path) -> None:
    for name in (
        ".codex-plugin",
        ".mcp.json",
        "mcp",
        "skills",
        "scripts",
        "vendor",
        "requirements.txt",
        "README.md",
        "GXP低代码只读排查使用手册.md",
        "AI-SETUP.md",
    ):
        source = PLUGIN_ROOT / name
        if source.exists():
            _copy_entry(source, staged / name)
    manifest_path = staged / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("name") != PLUGIN_NAME:
        raise RuntimeError(f"Unexpected plugin name: {manifest.get('name')}")
    base_version = str(manifest.get("version") or "0.0.0").split("+", 1)[0]
    cachebuster = datetime.now(timezone.utc).strftime("local-%Y%m%d-%H%M%S")
    manifest["version"] = f"{base_version}+codex.{cachebuster}"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _replace_plugin(staged: Path, target: Path, parent: Path) -> None:
    resolved_parent = parent.resolve()
    target.resolve().relative_to(resolved_parent)
    backup = parent / f".{target.name}.previous"
    if backup.exists():
        shutil.rmtree(backup)
    if target.exists():
        os.replace(target, backup)
    try:
        os.replace(staged, target)
    except Exception:
        if backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    if backup.exists():
        shutil.rmtree(backup)


def _marketplace_document() -> dict[str, Any]:
    return {
        "name": MARKETPLACE_NAME,
        "interface": {"displayName": "Look Low-code Local"},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
                "policy": {"installation": "INSTALLED_BY_DEFAULT", "authentication": "ON_INSTALL"},
                "category": "Productivity",
            }
        ],
    }


def _ensure_marketplace(root: Path) -> bool:
    path = root / ".agents" / "plugins" / "marketplace.json"
    expected = _marketplace_document()
    if path.is_file():
        current = json.loads(path.read_text(encoding="utf-8"))
        if current != expected:
            raise RuntimeError(f"Managed marketplace has unexpected content: {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(expected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return True


def _codex_command() -> str:
    command = shutil.which("codex") or shutil.which("codex.cmd")
    if not command:
        raise RuntimeError("Codex CLI is not installed or not on PATH")
    return command


def _run_codex(args: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, shell=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError((result.stdout or result.stderr or "Codex command failed").strip())
    return result


def _marketplace_roots(codex: str) -> dict[str, Path]:
    output = _run_codex([codex, "plugin", "marketplace", "list"]).stdout
    roots: dict[str, Path] = {}
    for line in output.splitlines():
        match = re.match(r"^(\S+)\s+(.+?)\s*$", line)
        if match and match.group(1) != "MARKETPLACE":
            roots[match.group(1)] = Path(match.group(2)).expanduser().resolve()
    return roots


def install_plugin() -> dict[str, str | bool]:
    install_runtime()
    root = runtime_root() / "codex-marketplace"
    plugin_parent = root / "plugins"
    plugin_parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{PLUGIN_NAME}.install-", dir=plugin_parent))
    try:
        _plugin_payload(staged)
        target = plugin_parent / PLUGIN_NAME
        _replace_plugin(staged, target, plugin_parent)
    finally:
        if staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
    marketplace_created = _ensure_marketplace(root)
    codex = _codex_command()
    roots = _marketplace_roots(codex)
    configured = roots.get(MARKETPLACE_NAME)
    if configured is not None and configured != root.resolve():
        raise RuntimeError(f"Marketplace {MARKETPLACE_NAME} already points to {configured}")
    if configured is None:
        _run_codex([codex, "plugin", "marketplace", "add", str(root), "--json"])
    result = _run_codex([codex, "plugin", "add", f"{PLUGIN_NAME}@{MARKETPLACE_NAME}", "--json"])
    payload = {
        "ok": True,
        "plugin": PLUGIN_NAME,
        "marketplace": MARKETPLACE_NAME,
        "marketplace_root": str(root),
        "marketplace_created": marketplace_created,
        "install_result": result.stdout.strip(),
        "next": "Start a new Codex thread so the updated skill and MCP tools are loaded.",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Look as a portable local Codex plugin")
    parser.parse_args()
    install_plugin()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
