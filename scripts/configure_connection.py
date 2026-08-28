from __future__ import annotations

import getpass
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "mcp"))

from gxp_core.config import (
    ConfigurationError,
    DatabaseConfig,
    load_config,
    save_config,
    set_password,
)
from gxp_core.db import ReadOnlyDatabase


def ask(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def main() -> int:
    try:
        current = load_config()
    except ConfigurationError:
        current = None
    host = ask("Database host", current.host if current else "")
    port = int(ask("Database port", str(current.port) if current else "3306"))
    database = ask("Database name", current.database if current else "")
    user = ask("Database user", current.user if current else "")
    credential_target = ask(
        "Operating-system credential target",
        current.credential_target if current else "Codex.GxpLowcodeReadonly",
    )
    password = getpass.getpass("Database password (hidden): ")
    config = DatabaseConfig(
        host=host,
        port=port,
        database=database,
        user=user,
        credential_target=credential_target,
        connect_timeout_seconds=current.connect_timeout_seconds if current else 8,
        read_timeout_seconds=current.read_timeout_seconds if current else 10,
        max_execution_time_ms=current.max_execution_time_ms if current else 5000,
        pool_size=current.pool_size if current else 4,
    )
    path = save_config(config)
    set_password(config, password)
    del password
    status = ReadOnlyDatabase(config).status()
    print(f"Configuration saved outside the plugin: {path}")
    print(
        "Read-only connection succeeded; server version: "
        f"{status.get('server_version', 'unknown')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
