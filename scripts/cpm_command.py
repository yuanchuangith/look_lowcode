from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT / "mcp"))

from gxp_core.cpm_config import load_cpm_config
from gxp_core.cpm_runner import CpmRefreshManager


def print_pull(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False))
        return
    if not report.get("ok"):
        error = report.get("error") or {}
        print(f"CPM pull failed [{error.get('code', 'UNKNOWN')}]: {error.get('message', 'unknown error')}")
        return
    if report.get("skipped"):
        print(
            f"CPM pull skipped: snapshot is fresh "
            f"refreshed_at={report.get('refreshed_at')} cli={report.get('cli_version')}"
        )
    else:
        print(
            f"CPM pull completed: mode={report.get('refresh_mode')} "
            f"refreshed_at={report.get('refreshed_at')} cli={report.get('cli_version')}"
        )
        counts = report.get("counts") or {}
        if counts:
            print(" ".join(f"{key}={value}" for key, value in counts.items()))
    failures = report.get("failures") or []
    if failures:
        print(f"failures={len(failures)}")


def print_status(status: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(status, ensure_ascii=False))
        return
    print(
        f"CPM snapshot: exists={status.get('snapshot_exists')} stale={status.get('stale')} "
        f"ttl={status.get('ttl_seconds')}s cli={status.get('cli_version')}"
    )
    print(f"refreshed_at={status.get('refreshed_at')} path={status.get('snapshot_dir')}")
    failures = status.get("failures") or []
    if failures:
        print(f"failures={len(failures)}")


def print_whoami(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, ensure_ascii=False))
        return
    if report.get("token_valid"):
        print("CPM token valid (online check passed).")
        if report.get("message"):
            print(report["message"])
        return
    error = report.get("error") or {}
    print(f"CPM token invalid [{error.get('code', 'UNKNOWN')}]: {error.get('message', 'unknown error')}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cpm", description="Look-managed local CPM snapshot command")
    parser.add_argument("--version", action="version", version="cpm 0.3.1")
    commands = parser.add_subparsers(dest="command")

    pull = commands.add_parser("pull", help="Safely refresh the local snapshot")
    pull.add_argument("--page", "-p", default=None, help="Page Route, Id, or OutId; omit for full pull")
    pull.add_argument("--if-stale", action="store_true", help="Honor the 30-minute TTL")
    pull.add_argument("--json", action="store_true", help="Print the complete JSON report")

    status = commands.add_parser("status", help="Show snapshot freshness and configuration status")
    status.add_argument("--json", action="store_true", help="Print the complete JSON status")
    whoami = commands.add_parser("whoami", help="Validate the cached platform token online")
    whoami.add_argument("--json", action="store_true", help="Print the complete JSON result")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return 0
    config = load_cpm_config()
    manager = CpmRefreshManager(config)
    if args.command == "status":
        print_status(manager.snapshot_status(), args.json)
        return 0
    if args.command == "whoami":
        report = manager.validate_token()
        print_whoami(report, args.json)
        return 0 if report.get("ok") else 1
    report = manager.refresh(force=not args.if_stale, page_identifier=args.page)
    print_pull(report, args.json)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
