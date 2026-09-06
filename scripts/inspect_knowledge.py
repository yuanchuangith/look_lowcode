from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp"))

from gxp_core.cpm_snapshot import get_cpm_knowledge


def main() -> None:
    parser = argparse.ArgumentParser(description="Read one local knowledge topic or its catalog")
    parser.add_argument("--kind", default="catalog")
    parser.add_argument("--name", default="main")
    parser.add_argument("--query", default="")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--max-chars", type=int, default=12000)
    args = parser.parse_args()
    print(json.dumps(get_cpm_knowledge(**vars(args)), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
