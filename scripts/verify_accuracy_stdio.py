from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def verify(root: str, mode: str) -> dict:
    fixture = Path(__file__).resolve().parents[1] / "tests/stdio_accuracy_fixture.py"
    params = StdioServerParameters(command=sys.executable, args=[str(fixture), root, mode])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == (16 if mode == "http-registry" else 35)
            schemas = {tool.name: tool.inputSchema for tool in tools.tools}
            assert "context" in schemas["diagnose_codex_input"]["properties"]
            assert "follow_calls" in schemas["inspect_control_flow"]["properties"]
            calls = [
                ("inspect_action", {"identifier": "FIXTURE1", "group": "main", "focus_fields": ["file_ver_id"], "include_generated_csharp": True}),
                ("diagnose_codex_input", {"text": "改了再看看", "context": {"anchors": [{"action_code": "FIXTURE1"}]}}),
                ("inspect_control_flow", {"identifier": "FIXTURE1", "group": "main", "follow_calls": True}),
                ("inspect_action", {"identifier": "FIXTURE1", "group": "main", "node_key": "value", "value_path": "/paramsValue/inputParams/variableValue/code"}),
            ]
            for name, arguments in calls:
                result = await session.call_tool(name, arguments)
                assert not result.isError, (name, result)
                payload = result.structuredContent or json.loads(result.content[0].text)
                if name == "diagnose_codex_input":
                    assert payload["context_anchor_reused"]
                elif name == "inspect_control_flow":
                    assert payload["call_flow"]["runtime_verified"] is False
                elif "value_path" in arguments:
                    assert payload["value_page"]["text"] == 'row["file_ver_id"]'
                else:
                    assert payload["field_match_count"] == 1
                    assert payload["generated_csharp_scope"]["status"] == "resolved_method"
            return {"registry": mode, "tools": len(tools.tools), "fixture_calls_passed": len(calls), "business_database_access": False}


async def verify_launcher(root: str) -> dict:
    params = StdioServerParameters(command=shutil.which("node") or "node", args=[str(Path(root).resolve() / "scripts/start_mcp.mjs")], cwd=str(Path(root).resolve()))
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            assert len(tools.tools) == 35
            schemas = {tool.name: tool.inputSchema for tool in tools.tools}
            assert "context" in schemas["diagnose_codex_input"]["properties"]
            assert "follow_calls" in schemas["inspect_control_flow"]["properties"]
            result = await session.call_tool("get_cpm_knowledge", {"kind": "catalog", "name": "main", "query": "全局变量", "limit": 20})
            assert not result.isError
            payload = result.structuredContent or json.loads(result.content[0].text)
            assert payload["ok"] and payload["matched_count"] > 0, payload
            return {"registry": "installed_node_launcher", "tools": len(tools.tools), "knowledge_topics": [item["name"] for item in payload["entries"]], "business_database_access": False, "refresh_requested": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--server-root", required=True)
    parser.add_argument("--launcher", action="store_true")
    args = parser.parse_args()
    results = [asyncio.run(verify(args.server_root, mode)) for mode in ("local", "http-registry")]
    if args.launcher:
        results.append(asyncio.run(verify_launcher(args.server_root)))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
