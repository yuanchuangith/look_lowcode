from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "gxp-lowcode-debug"
MCP_NAME = "gxp-lowcode-readonly"


def ensure_link(target: Path, link_path: Path) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    target_str = str(target.resolve())
    link_str = os.path.abspath(str(link_path))
    if os.name == "nt":
        subprocess.run(f'cmd /c rmdir "{link_str}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(f'cmd /c mklink /J "{link_str}" "{target_str}"', shell=True, check=True)
    else:
        if link_path.is_symlink() or link_path.is_file():
            link_path.unlink()
        elif link_path.is_dir():
            import shutil
            shutil.rmtree(link_path)
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


def main() -> int:
    source_skill = REPO_ROOT / "skills" / SKILL_NAME
    if not source_skill.exists():
        raise FileNotFoundError(f"Skill directory not found: {source_skill}")

    # 1. Update .gitignore to hide project-level .claude from git
    update_gitignore()

    # 2. Project-level skill: <repo>/.claude/skills/gxp-lowcode-debug
    project_skill_link = REPO_ROOT / ".claude" / "skills" / SKILL_NAME
    ensure_link(source_skill, project_skill_link)
    print(f"[OK] Project-level skill configured: {project_skill_link}")

    # 3. User-level skill: ~/.claude/skills/gxp-lowcode-debug
    user_skill_link = Path.home() / ".claude" / "skills" / SKILL_NAME
    ensure_link(source_skill, user_skill_link)
    print(f"[OK] User-level skill configured: {user_skill_link}")

    # 4. Project-level MCP: <repo>/.mcp.json
    project_mcp = REPO_ROOT / ".mcp.json"
    configure_mcp_json(project_mcp, is_global=False)
    print(f"[OK] Project-level MCP configured: {project_mcp}")

    # 5. User-level MCP: ~/.claude/.mcp.json
    user_mcp = Path.home() / ".claude" / ".mcp.json"
    configure_mcp_json(user_mcp, is_global=True)
    print(f"[OK] User-level MCP configured: {user_mcp}")

    print("\n[SUCCESS] GXP Lowcode Skill & MCP reinstalled cleanly for Claude!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
