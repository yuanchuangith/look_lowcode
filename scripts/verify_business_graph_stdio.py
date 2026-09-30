from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from setup import runtime_root


async def verify(root: Path) -> dict:
    fixtures = json.loads((Path(__file__).resolve().parents[1] / "tests/fixtures/business_graph_cases.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="gxp-graph-protocol-") as directory:
        virtualenv = runtime_root() / ".venv"
        if not virtualenv.is_dir():
            raise FileNotFoundError("Install the Look runtime before protocol verification")
        alias = Path(directory) / ".venv"
        if os.name == "nt":
            subprocess.run(["cmd", "/d", "/c", "mklink", "/J", str(alias), str(virtualenv)], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            alias.symlink_to(virtualenv, target_is_directory=True)
        environment = {**os.environ, "GXP_LOWCODE_RUNTIME_ROOT": directory,
                       "GXP_LOWCODE_CONFIG": str(Path(directory) / "missing-database-config.json")}
        params = StdioServerParameters(command=shutil.which("node") or "node",
                                       args=[str(root / "scripts/start_mcp.mjs")], cwd=str(root), env=environment)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await session.send_ping()
                tools = await session.list_tools()
                assert len(tools.tools) == 41
                calls = 0
                async def call(name, arguments):
                    nonlocal calls
                    result = await session.call_tool(name, arguments)
                    assert not result.isError, name
                    payload = result.structuredContent or json.loads(result.content[0].text)
                    assert payload["available"], (name, payload)
                    calls += 1
                    return payload
                saved = [await call("upsert_business_logic_graph", {"relation": fixture}) for fixture in fixtures]
                repeated = await call("upsert_business_logic_graph", {"relation": fixtures[0]})
                assert repeated["idempotent"] and not repeated["written"]
                graph = await call("get_business_graph", {"scope_id": "fixture", "projection": "data", "depth": 5})
                assert len(graph["nodes"]) == 4 and len(graph["edges"]) == 3
                identifiers = {node["label"]: node["id"] for node in graph["nodes"]}
                trace = await call("trace_business_data_flow", {"scope_id": "fixture", "start": identifiers["A"], "target": identifiers["D"]})
                assert len(trace["paths"][0]["edges"]) == 3 and len(trace["evidence"]) == 3
                for direction, label in (("downstream", "A"), ("upstream", "D")):
                    bounded = await call("trace_business_data_flow", {"scope_id": "fixture", "start": identifiers[label],
                                         "direction": direction, "max_depth": 3})
                    assert len(bounded["paths"]) == 1 and len(bounded["paths"][0]["edges"]) == 3
                    assert not bounded["truncated"] and bounded["frontier"] == []
                searched = await call("search_business_logic_graph", {"query": "Sanitized confirmed field mapping"})
                assert searched["count"] == 0
                analyzed = await call("analyze_business_graph", {"scope_id": "fixture", "projection": "data"})
                assert analyzed["summary"]["component_count"] == 1
                withdrawn = await call("invalidate_business_logic_graph", {"relation_id": saved[0]["relation"]["relation_id"], "reason": "user_confirmed_incorrect"})
                assert withdrawn["changed"] == 1
                broken_trace = await call("trace_business_data_flow", {"scope_id": "fixture", "start": identifiers["A"], "target": identifiers["D"]})
                assert broken_trace["paths"] == []
                legacy = json.loads((Path(__file__).resolve().parents[1] / "tests/fixtures/business_logic_graph_training.json").read_text(encoding="utf-8"))
                legacy_saved = await call("upsert_business_logic_graph", {"relation": legacy})
                legacy_search = await call("search_business_logic_graph", {"field": "close_date"})
                assert legacy_search["count"] == 1
                legacy_invalidated = await call("invalidate_business_logic_graph", {"relation_id": legacy_saved["relation"]["relation_id"], "reason": "user_confirmed_incorrect"})
                assert legacy_invalidated["changed"] == 1
                return {"tools": 41, "graph_protocol_calls": calls, "cross_case_chain": "A-B-C-D",
                        "whole_support_bundles": True, "legacy_contract": True, "depth_limit_paths": True,
                        "business_database_access": False, "temporary_cache_only": True}


def main():
    parser = argparse.ArgumentParser(description="Verify global graph MCP protocol against sanitized temporary fixtures")
    parser.add_argument("--server-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = asyncio.run(asyncio.wait_for(verify(args.server_root.resolve()), timeout=60))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
