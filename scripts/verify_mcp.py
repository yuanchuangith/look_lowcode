from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

EXPECTED_TOOL_COUNT = 35


async def check_session(session, expected_count: int) -> list[str]:
    await session.initialize()
    await session.send_ping()
    names: list[str] = []
    cursors: set[str] = set()
    page = await session.list_tools()
    while True:
        names.extend(tool.name for tool in page.tools)
        if not page.nextCursor:
            break
        if page.nextCursor in cursors:
            raise RuntimeError("MCP tools/list returned a repeated pagination cursor")
        cursors.add(page.nextCursor)
        page = await session.list_tools(cursor=page.nextCursor)
    if len(names) != expected_count or len(set(names)) != expected_count:
        raise RuntimeError(f"Expected {expected_count} unique MCP tools, got {len(names)} entries / {len(set(names))} unique")
    return names


async def verify(root: Path, timeout_seconds: float) -> list[str]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    node = shutil.which("node")
    if not node:
        raise FileNotFoundError("Node.js is not available on PATH")
    params = StdioServerParameters(
        command=node,
        args=[str(root / "scripts" / "start_mcp.mjs")],
        cwd=str(root),
        env=dict(os.environ),
    )
    failure: Exception | None = None
    names: list[str] = []
    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                try:
                    names = await asyncio.wait_for(check_session(session, EXPECTED_TOOL_COUNT), timeout=timeout_seconds)
                except Exception as exc:
                    failure = exc
    except Exception:
        if failure is None:
            raise
    if failure is not None:
        raise failure
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the actual Node MCP launcher without business tool calls")
    parser.add_argument("--server-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--timeout", type=float, default=15)
    args = parser.parse_args(argv)
    if not 0 < args.timeout < float("inf"):
        parser.error("--timeout must be a finite positive number")
    try:
        names = asyncio.run(verify(args.server_root.resolve(), args.timeout))
    except asyncio.TimeoutError:
        print(f"[ERROR] MCP protocol verification timed out after {args.timeout}s.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[ERROR] MCP protocol verification failed: {exc!r}", file=sys.stderr)
        return 1
    print(json.dumps({"tools": len(names), "initialize": True, "ping": True, "business_tool_calls": 0}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
