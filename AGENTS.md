# Repository bootstrap

- When the user asks to install, bootstrap, update, or migrate this Look plugin on a computer, read `AI-SETUP.md` completely and run the repository's `scripts/install_codex_plugin.py` with the available Python 3 command.
- The installer is the authority for Windows, macOS, and Linux. Do not recreate marketplace files or copy plugin folders by hand.
- Installing the plugin does not authorize guessing or exposing credentials. Configure CPM or the database only when the user requests it, use hidden input, and store secrets only in the operating-system credential store.
- After installation, verify `codex plugin list`, `cpm --version`, and `cpm status`. Use `cpm whoami` only when an online token check is requested or useful.
- Tell the user to start a new Codex thread after a plugin install or update so the new skill and MCP tools are loaded.
