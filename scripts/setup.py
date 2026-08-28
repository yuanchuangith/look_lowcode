from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MIN_PYTHON = (3, 10)
MIN_NODE_MAJOR = 18


def runtime_root() -> Path:
    override = os.environ.get("GXP_LOWCODE_RUNTIME_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")).expanduser()
    return (base / "GxpLowcodeReadonly").resolve()


def _venv_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _command(*names: str) -> str:
    for name in names:
        value = shutil.which(name)
        if value:
            return str(Path(value).resolve())
    raise RuntimeError(f"Required command not found: {' or '.join(names)}")


def _run(args: list[str], cwd: Path | None = None) -> None:
    subprocess.run(args, cwd=cwd, shell=False, check=True)


def _assert_child(path: Path, parent: Path) -> None:
    resolved = path.resolve()
    root = parent.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"Refusing to replace path outside {root}: {resolved}") from exc


def _replace_tree(staged: Path, target: Path, parent: Path) -> None:
    _assert_child(target, parent)
    backup = parent / f".{target.name}.previous"
    _assert_child(backup, parent)
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


def _copytree(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "node_modules", ".git"),
    )


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def _node_runtime() -> tuple[str, str]:
    node = _command("node.exe", "node")
    version = subprocess.run(
        [node, "--version"], shell=False, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()
    match = re.fullmatch(r"v?(\d+)(?:\.\d+){1,2}.*", version)
    if not match or int(match.group(1)) < MIN_NODE_MAJOR:
        raise RuntimeError(f"Node.js >= {MIN_NODE_MAJOR} is required; found {version or 'unknown'}")
    return node, version


def _install_cli(root: Path, npm: str) -> tuple[Path, str]:
    package_root = PLUGIN_ROOT / "vendor" / "cpm-cli"
    package = _read_json(package_root / "package.json")
    version = str(package.get("version") or "").strip()
    if not version:
        raise RuntimeError("vendor/cpm-cli/package.json has no version")
    parent = root / "cpm-cli"
    parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{version}.install-", dir=parent))
    try:
        for name in ("dist", "skills", "assets"):
            _copytree(package_root / name, staged / name)
        for name in ("package.json", "package-lock.json", "README.md"):
            shutil.copy2(package_root / name, staged / name)
        _run([npm, "ci", "--omit=dev", "--ignore-scripts", "--no-audit", "--no-fund", "--prefix", str(staged)])
        target = parent / version
        _replace_tree(staged, target, parent)
    finally:
        if staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
    return target, version


def _install_look_runtime(root: Path, version: str) -> Path:
    parent = root / "look-runtime"
    parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix=f".{version}.install-", dir=parent))
    try:
        _copytree(PLUGIN_ROOT / "mcp", staged / "mcp")
        (staged / "scripts").mkdir()
        shutil.copy2(PLUGIN_ROOT / "scripts" / "cpm_command.py", staged / "scripts" / "cpm_command.py")
        target = parent / version
        _replace_tree(staged, target, parent)
    finally:
        if staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
    return target


def _install_global_cpm(root: Path, python: Path, look_runtime: Path) -> tuple[Path, bool]:
    command_script = look_runtime / "scripts" / "cpm_command.py"
    if os.name == "nt":
        bin_dir = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")) / "npm"
        shim = bin_dir / "cpm.cmd"
        content = f'@echo off\r\n"{python}" "{command_script}" %*\r\nexit /b %ERRORLEVEL%\r\n'
    else:
        bin_dir = Path.home() / ".local" / "bin"
        shim = bin_dir / "cpm"
        content = f"#!/bin/sh\nexec {shlex.quote(str(python))} {shlex.quote(str(command_script))} \"$@\"\n"
    bin_dir.mkdir(parents=True, exist_ok=True)
    shim.write_text(content, encoding="utf-8", newline="")
    if os.name != "nt":
        shim.chmod(0o755)
    entries = [Path(value).expanduser().resolve() for value in os.environ.get("PATH", "").split(os.pathsep) if value]
    return shim, bin_dir.resolve() in entries


def install_runtime() -> dict[str, str | bool]:
    if sys.version_info < MIN_PYTHON:
        raise RuntimeError(f"Python >= {MIN_PYTHON[0]}.{MIN_PYTHON[1]} is required")
    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    node, node_version = _node_runtime()
    npm = _command("npm.cmd", "npm")
    python = _venv_python(root)
    if not python.is_file():
        _run([sys.executable, "-m", "venv", str(root / ".venv")])
    _run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip"])
    _run([str(python), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(PLUGIN_ROOT / "requirements.txt")])
    cli_root, version = _install_cli(root, npm)
    look_runtime = _install_look_runtime(root, version)
    shim, on_path = _install_global_cpm(root, python, look_runtime)
    result: dict[str, str | bool] = {
        "runtime_root": str(root),
        "python": str(python),
        "node": node,
        "node_version": node_version,
        "cli_path": str(cli_root / "dist" / "cli.js"),
        "cli_version": version,
        "cpm_command": str(shim),
        "command_on_path": on_path,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not on_path:
        print(f"Add {shim.parent} to PATH, then reopen the terminal.")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the portable Look and CPM local runtime")
    parser.add_argument("--print-runtime-root", action="store_true")
    args = parser.parse_args()
    if args.print_runtime_root:
        print(runtime_root())
        return 0
    install_runtime()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
