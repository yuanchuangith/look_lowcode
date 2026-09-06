from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "mcp"))

from gxp_core.service import GxpReadonlyService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only GXP action inspector")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--action-code")
    source.add_argument("--ref-id")
    parser.add_argument("--version", choices=("published", "draft"), default="published")
    parser.add_argument("--compare-versions", action="store_true")
    parser.add_argument("--group")
    parser.add_argument("--terms", default="")
    parser.add_argument("--focus-fields", default="")
    parser.add_argument("--node-key")
    parser.add_argument("--start", type=int)
    parser.add_argument("--end", type=int)
    parser.add_argument("--show-params", action="store_true")
    parser.add_argument("--precise-locator", action="store_true")
    parser.add_argument("--show-csharp", action="store_true")
    parser.add_argument("--csharp-line", type=int)
    parser.add_argument("--csharp-context", type=int, default=3)
    parser.add_argument(
        "--include-generated-csharp",
        action="store_true",
        help="Opt in to generated C# term-match candidates",
    )
    parser.add_argument(
        "--no-generated-csharp",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--max-nodes", type=int, default=20)
    parser.add_argument("--max-output-bytes", type=int, default=32768)
    parser.add_argument("--design-id")
    parser.add_argument("--at-time")
    parser.add_argument("--value-path")
    parser.add_argument("--value-offset", type=int, default=0)
    parser.add_argument("--value-limit", type=int, default=2048)
    parser.add_argument("--control-flow", action="store_true")
    parser.add_argument("--follow-calls", action="store_true")
    parser.add_argument("--max-call-depth", type=int, default=2)
    parser.add_argument("--max-actions", type=int, default=8)
    parser.add_argument("--max-edges", type=int, default=240)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    identifier = args.action_code or args.ref_id
    service = GxpReadonlyService()
    if args.control_flow or args.follow_calls:
        result = service.inspect_control_flow(identifier, version=args.version, group=args.group, node_key=args.node_key, start=args.start, end=args.end, design_id=args.design_id, at_time=args.at_time, follow_calls=args.follow_calls, max_call_depth=args.max_call_depth, max_actions=args.max_actions, max_nodes=args.max_nodes, max_edges=args.max_edges, max_output_bytes=args.max_output_bytes)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    result = service.inspect_action(
        identifier,
        version=args.version,
        group=args.group,
        terms=[item.strip() for item in args.terms.split(",") if item.strip()],
        focus_fields=[
            item.strip() for item in args.focus_fields.split(",") if item.strip()
        ],
        node_key=args.node_key,
        start=args.start,
        end=args.end,
        include_params=args.show_params,
        csharp_line=args.csharp_line if args.show_csharp or args.csharp_line else None,
        csharp_context=args.csharp_context,
        include_generated_csharp=(
            (args.include_generated_csharp or args.show_csharp)
            and not args.no_generated_csharp
        ),
        max_nodes=args.max_nodes,
        max_output_bytes=args.max_output_bytes,
        design_id=args.design_id,
        at_time=args.at_time,
        value_path=args.value_path,
        value_offset=args.value_offset,
        value_limit=args.value_limit,
    )
    if args.compare_versions:
        result["published_vs_draft"] = service.compare_designs(
            str(result["action"].get("ref_id") or identifier)
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
