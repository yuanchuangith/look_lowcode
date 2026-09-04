from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = ROOT / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from gxp_core.relation_policy import RelationPolicyStore


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the opaque relation-policy JSON file")
    parser.add_argument("--file", type=Path, help="Override the policy JSON path")
    commands = parser.add_subparsers(dest="command", required=True)

    create_scope = commands.add_parser("create-scope")
    create_scope.add_argument("scope_id")

    args = parser.parse_args()
    store = RelationPolicyStore(args.file) if args.file else RelationPolicyStore()
    result = store.create_scope(args.scope_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
