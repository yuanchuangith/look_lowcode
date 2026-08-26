from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "mcp"))

from gxp_core.service import GxpReadonlyService


def read_source(value: str) -> str:
    if value == "-":
        return sys.stdin.read()
    return Path(value).read_text(encoding="utf-8-sig")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Send Codex text or JSON input to the read-only GXP diagnostic core"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="UTF-8 file path, or - for plain stdin")
    source.add_argument("--json", help="UTF-8 JSON file path, or - for JSON stdin")
    parser.add_argument("--at-time", help="Optional exception time, ISO-like format")
    args = parser.parse_args()
    if args.text:
        text = read_source(args.text)
        at_time = args.at_time
    else:
        payload = json.loads(read_source(args.json))
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
            raise SystemExit("JSON input must be an object containing string field 'text'")
        text = payload["text"]
        at_time = args.at_time or payload.get("at_time")
    result = GxpReadonlyService().diagnose_codex_input(text, at_time=at_time)
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
