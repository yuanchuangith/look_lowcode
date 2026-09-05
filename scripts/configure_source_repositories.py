from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MCP_DIR = ROOT / "mcp"
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from gxp_core.source_config import SourceRepositoriesConfig, save_source_config


def _paths(values: list[Path]) -> tuple[str, ...]:
    return tuple(str(item.expanduser().resolve()) for item in values)


def main() -> int:
    parser = argparse.ArgumentParser(description="Configure bounded local GXP frontend/backend source repositories")
    parser.add_argument("--frontend", type=Path, action="append", default=[])
    parser.add_argument("--backend", type=Path, action="append", default=[])
    parser.add_argument("--preferred-frontend", type=Path)
    parser.add_argument("--preferred-backend", type=Path)
    args = parser.parse_args()
    frontend = _paths(args.frontend)
    backend = _paths(args.backend)
    config = SourceRepositoriesConfig(
        frontend=frontend,
        backend=backend,
        preferred_frontend=str(args.preferred_frontend.expanduser().resolve()) if args.preferred_frontend else None,
        preferred_backend=str(args.preferred_backend.expanduser().resolve()) if args.preferred_backend else None,
    )
    path = save_source_config(config)
    print(
        json.dumps(
            {
                "ok": True,
                "config_path": str(path),
                "frontend": list(config.frontend),
                "backend": list(config.backend),
                "preferred_frontend": config.preferred_frontend,
                "preferred_backend": config.preferred_backend,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
