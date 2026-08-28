from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "mcp"))

from gxp_core.cpm_config import load_cpm_config
from gxp_core.cpm_runner import CpmRefreshManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely refresh the local CPM snapshot")
    parser.add_argument("--page", default=None, help="Page Route, Id, or OutId; omit for a full pull")
    parser.add_argument("--if-stale", action="store_true", help="Honor the configured TTL instead of forcing a pull")
    parser.add_argument("--json", action="store_true", help="Print the complete machine-readable report")
    args = parser.parse_args()

    config = load_cpm_config()
    report = CpmRefreshManager(config).refresh(
        force=not args.if_stale,
        page_identifier=args.page,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    elif report.get("ok") and report.get("skipped"):
        print(
            f"CPM pull skipped: snapshot is fresh "
            f"refreshed_at={report.get('refreshed_at')} cli={report.get('cli_version')}"
        )
        failures = report.get("failures") or []
        if failures:
            print(f"failures={len(failures)}")
    elif report.get("ok"):
        counts = " ".join(f"{key}={value}" for key, value in (report.get("counts") or {}).items())
        print(
            f"CPM pull completed: mode={report.get('refresh_mode')} "
            f"refreshed_at={report.get('refreshed_at')} cli={report.get('cli_version')}"
        )
        if counts:
            print(counts)
        failures = report.get("failures") or []
        if failures:
            print(f"failures={len(failures)}")
    else:
        error = report.get("error") or {}
        print(f"CPM pull failed [{error.get('code', 'UNKNOWN')}]: {error.get('message', 'unknown error')}")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
