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
    load_schema_config,
    save_schema_config,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure the local Schema snapshot and local relation decisions")
    parser.add_argument("--scope", help="Local namespace for relationship IDs")
    parser.add_argument("--snapshot-dir", type=Path)
    args = parser.parse_args()
    from dataclasses import asdict
    settings = asdict(load_schema_config())
    if args.snapshot_dir is not None:
        settings["snapshot_dir"] = str(args.snapshot_dir.expanduser().resolve())
    if args.scope is not None:
        settings["policy_scope_id"] = args.scope
    config = SchemaSnapshotConfig.from_dict(settings)
    path = save_schema_config(config)
    print(json.dumps({
        "ok": True,
        "config_path": str(path),
        "snapshot_dir": config.snapshot_dir,
        "policy_storage": "local",
        "policy_scope_id": config.policy_scope_id,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
