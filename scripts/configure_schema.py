from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = ROOT / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from gxp_core.schema_config import (
    SchemaSnapshotConfig,
    default_schema_snapshot_dir,
    save_schema_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure the local Schema snapshot and remote relation policy")
    parser.add_argument("--policy-url", required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--snapshot-dir", type=Path, default=default_schema_snapshot_dir())
    args = parser.parse_args()
    config = SchemaSnapshotConfig(
        snapshot_dir=str(args.snapshot_dir.expanduser().resolve()),
        policy_url=args.policy_url,
        policy_scope_id=args.scope,
    )
    path = save_schema_config(config)
    print(json.dumps({
        "ok": True,
        "config_path": str(path),
        "snapshot_dir": config.snapshot_dir,
        "policy_url": config.policy_url,
        "policy_scope_id": config.policy_scope_id,
        "authentication": "disabled",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
