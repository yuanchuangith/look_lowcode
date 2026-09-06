# Repository bootstrap

- When the user asks to install, bootstrap, update, or migrate this Look plugin / skill on a computer, read `AI-SETUP.md` completely:
  - For **Codex**: run `scripts/install_codex_plugin.py` with the available Python 3 command. After installation, verify `codex plugin list`, `cpm --version`, and `cpm status`. Tell the user to start a new Codex thread so the new skill and MCP tools are loaded.
  - For **Claude Code**: run `scripts/install_claude.py` with the available Python 3 command. It automatically links the skill to `.claude/skills/` and `~/.claude/skills/`, configures `.mcp.json`, and verifies the 35 MCP tools. Tell the user `/gxp-lowcode-debug` is ready.
- The installer is the authority for Windows, macOS, and Linux. Do not recreate marketplace files or copy plugin folders by hand.
- Installing the plugin does not authorize guessing or exposing credentials. Configure CPM or the database only when the user requests it, use hidden input, and store secrets only in the operating-system credential store.

