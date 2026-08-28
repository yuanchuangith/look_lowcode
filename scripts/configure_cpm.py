from __future__ import annotations

import argparse
import getpass
import json
import shutil
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "mcp"))

from gxp_core.cpm_config import CpmConfig, cpm_config_path, cpm_runtime_root, save_cpm_config, set_cpm_password
from gxp_core.cpm_runner import CpmRefreshManager


def ask(label: str, current: str = "") -> str:
    suffix = f" [{current}]" if current else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or current


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure local CPM snapshot access")
    parser.add_argument("--url", default="")
    parser.add_argument("--account", default="")
    parser.add_argument("--node-path", default="")
    parser.add_argument("--cli-path", default="")
    args = parser.parse_args()

    platform_url = args.url or ask("CPM platform URL")
    account = args.account or ask("CPM account")
    password = getpass.getpass("CPM password (hidden): ")
    snapshot = cpm_runtime_root() / "cpm-snapshot"
    package = json.loads((PLUGIN_ROOT / "vendor" / "cpm-cli" / "package.json").read_text(encoding="utf-8"))
    node_path = args.node_path or shutil.which("node") or shutil.which("node.exe") or ""
    cli_path = args.cli_path or str(cpm_runtime_root() / "cpm-cli" / str(package["version"]) / "dist" / "cli.js")
    if not node_path or not Path(node_path).is_file():
        raise RuntimeError("Node.js runtime is missing; run scripts/setup first")
    if not Path(cli_path).is_file():
        raise RuntimeError("CPM CLI runtime is missing; run scripts/setup first")
    config = CpmConfig(
        platform_url=platform_url,
        account=account,
        node_path=str(Path(node_path).resolve()),
        cli_path=str(Path(cli_path).resolve()),
        snapshot_dir=str(snapshot.resolve()),
        ttl_seconds=1800,
        timeout_seconds=300,
        concurrency=10,
    )
    save_cpm_config(config)
    set_cpm_password(account, password)
    del password
    report = CpmRefreshManager(config).refresh(force=True)
    if not report.get("ok"):
        print(json.dumps(report, ensure_ascii=False))
        return 1
    print(f"CPM configuration saved outside the plugin: {cpm_config_path()}")
    print(f"Initial full snapshot completed: {config.snapshot_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
