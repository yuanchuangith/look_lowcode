from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "gxp-lowcode-debug"
MCP_NAME = "gxp-lowcode-readonly"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.setup import _venv_python, install_runtime, runtime_root
from scripts.verify_mcp import EXPECTED_TOOL_COUNT


def ensure_link(target: Path, link_path: Path) -> None:
    target = target.resolve(strict=True)
    if not target.is_dir():
        raise NotADirectoryError(str(target))
    link_path = Path(os.path.abspath(link_path))
    link_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        link_stat = link_path.lstat()
    except FileNotFoundError:
        link_stat = None
    if link_stat is not None:
        is_symlink = stat.S_ISLNK(link_stat.st_mode)
        is_junction = getattr(link_stat, "st_reparse_tag", None) == getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)
        if not is_symlink and not is_junction:
            raise FileExistsError(f"Refusing to replace an existing file or directory: {link_path}")
        if link_path.resolve() == target:
            return
        if is_junction:
            link_path.rmdir()
        else:
            link_path.unlink()
    if os.name == "nt":
        command = (
            "$ErrorActionPreference = 'Stop'; "
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); "
            "New-Item -ItemType Junction -Path $env:LOOK_SKILL_LINK -Value $env:LOOK_SKILL_TARGET | Out-Null"
        )
        subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            env={**os.environ, "LOOK_SKILL_LINK": str(link_path), "LOOK_SKILL_TARGET": str(target)},
            check=True, capture_output=True, encoding="utf-8", errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        link_path.symlink_to(target, target_is_directory=True)


def update_gitignore() -> None:
    gitignore = REPO_ROOT / ".gitignore"
    if not gitignore.exists():
        return
    text = gitignore.read_text(encoding="utf-8")
    if ".claude/" not in text.splitlines():
        if not text.endswith("\n"):
            text += "\n"
        text += ".claude/\n"
        gitignore.write_text(text, encoding="utf-8")


def configure_mcp_json(path: Path, is_global: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    mcp_servers = data.setdefault("mcpServers", {})
    start_script = (REPO_ROOT / "scripts" / "start_mcp.mjs").as_posix() if is_global else "./scripts/start_mcp.mjs"
    cwd = REPO_ROOT.as_posix() if is_global else "."
    mcp_servers[MCP_NAME] = {
        "command": "node",
        "args": [start_script],
        "cwd": cwd,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def verify_mcp_tools(timeout_seconds: float = 15) -> bool:
    python = _venv_python(runtime_root())
    if not python.is_file():
        print(f"[ERROR] Look runtime Python is missing: {python}")
        return False
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.run(
            [str(python), str(REPO_ROOT / "scripts" / "verify_mcp.py"), "--server-root", str(REPO_ROOT), "--timeout", str(timeout_seconds)],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=timeout_seconds + 15,
            **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}),
        )
        result = json.loads(proc.stdout)
        if result.get("tools") != EXPECTED_TOOL_COUNT or result.get("initialize") is not True or result.get("ping") is not True:
            raise ValueError("Invalid MCP protocol verification result")
        print(f"[OK] MCP initialize / ping / tools/list passed: {EXPECTED_TOOL_COUNT} tools registered.")
        return True
    except subprocess.TimeoutExpired:
        print(f"[ERROR] MCP Tool verification timed out after {timeout_seconds}s.")
        return False
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] MCP verification failed: {exc.stderr or exc}")
        return False
    except Exception as exc:
        print(f"[ERROR] MCP verification failed: {exc}")
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install Look & CPM skill and MCP for Claude Code")
    parser.add_argument("--skip-runtime", action="store_true", help="Skip Python/Node runtime environment setup")
    verification = parser.add_mutually_exclusive_group()
    verification.add_argument("--verify", dest="verify", action="store_true", help="Verify MCP after installation (default)")
    verification.add_argument("--no-verify", dest="verify", action="store_false", help="Skip MCP tools verification")
    parser.set_defaults(verify=True)
    parser.add_argument("--verify-only", action="store_true", help="Only verify the current launcher; do not install or change configuration")
    parser.add_argument("--verify-timeout", type=float, default=15, help="Protocol timeout in seconds (plus bounded process cleanup)")
    args = parser.parse_args(argv)
    if not 0 < args.verify_timeout < float("inf"):
        parser.error("--verify-timeout must be a finite positive number")
    if args.verify_only:
        if not args.verify:
            parser.error("--verify-only cannot be combined with --no-verify")
        return 0 if verify_mcp_tools(args.verify_timeout) else 1

    source_skill = REPO_ROOT / "skills" / SKILL_NAME
    if not source_skill.exists():
        raise FileNotFoundError(f"Skill directory not found: {source_skill}")

    # 1. Setup local Python runtime and dependencies if needed
    if not args.skip_runtime:
        print(">>> Checking and preparing Look runtime environment...")
        install_runtime()

    # 2. Update .gitignore to hide project-level .claude from git
    update_gitignore()

    # 3. Project-level skill: <repo>/.claude/skills/gxp-lowcode-debug
    project_skill_link = REPO_ROOT / ".claude" / "skills" / SKILL_NAME
    ensure_link(source_skill, project_skill_link)
    print(f"[OK] Project-level skill configured: {project_skill_link}")

    # 4. User-level skill: ~/.claude/skills/gxp-lowcode-debug
    user_skill_link = Path.home() / ".claude" / "skills" / SKILL_NAME
    ensure_link(source_skill, user_skill_link)
    print(f"[OK] User-level skill configured: {user_skill_link}")

    # 5. Project-level MCP: <repo>/.mcp.json
    project_mcp = REPO_ROOT / ".mcp.json"
    configure_mcp_json(project_mcp, is_global=False)
    print(f"[OK] Project-level MCP configured: {project_mcp}")

    # 6. User-level MCP: ~/.claude/.mcp.json
    user_mcp = Path.home() / ".claude" / ".mcp.json"
    configure_mcp_json(user_mcp, is_global=True)
    print(f"[OK] User-level MCP configured: {user_mcp}")

    # 7. Verification
    if args.verify:
        success = verify_mcp_tools(args.verify_timeout)
        if not success:
            print("\n[WARNING] MCP tools verification did not pass. Check logs above.")
            return 1

    print("\n[SUCCESS] GXP Lowcode Skill & MCP installed cleanly for Claude!")
    print("Next step: Type '/gxp-lowcode-debug' in Claude Code to use the skill.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
