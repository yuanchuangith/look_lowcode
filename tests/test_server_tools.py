from __future__ import annotations

import inspect
import asyncio
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from gxp_core.conversation import CONTEXT_FIELDS

from server import (
    LOCAL_CPM_TOOLS,
    LOCAL_SCHEMA_TOOLS,
    LOCAL_SOURCE_TOOLS,
    LOCAL_GRAPH_TOOLS,
    MCP_TOOLS,
    create_mcp,
    inspect_action,
    inspect_control_flow,
    search_business_logic_graph,
    upsert_business_logic_graph,
    invalidate_business_logic_graph,
)


class ServerToolRegistrationTests(unittest.TestCase):
    def test_context_schema_documents_the_fields_accepted_by_the_service(self) -> None:
        for local in (True, False):
            app = create_mcp(include_local_cpm=local, include_local_schema=local, include_local_source=local, include_local_graph=local)
            tool = next(tool for tool in asyncio.run(app.list_tools()) if tool.name == "diagnose_codex_input")
            schema = tool.inputSchema["properties"]["context"]
            context = next(item for item in schema["anyOf"] if item.get("type") == "object")
            self.assertEqual(CONTEXT_FIELDS, set(context["properties"]))
            self.assertFalse(context["additionalProperties"])
            self.assertEqual(8, context["properties"]["anchors"]["maxItems"])
            self.assertIn("conversation_context.record", tool.description)

    def test_new_readonly_tools_are_registered(self) -> None:
        names = {tool.__name__ for tool in MCP_TOOLS}
        self.assertIn("search_pages", names)
        self.assertIn("list_page_actions", names)
        self.assertIn("inspect_component_filters", names)
        self.assertIn("inspect_control_flow", names)

    def test_inspect_action_defaults_to_compact_no_csharp(self) -> None:
        signature = inspect.signature(inspect_action)
        self.assertFalse(signature.parameters["include_generated_csharp"].default)
        self.assertEqual(20, signature.parameters["max_nodes"].default)

    def test_local_stdio_has_38_tools_and_http_factory_has_16(self) -> None:
        self.assertEqual(16, len(MCP_TOOLS))
        self.assertEqual(5, len(LOCAL_CPM_TOOLS))
        self.assertEqual(7, len(LOCAL_SCHEMA_TOOLS))
        self.assertEqual(7, len(LOCAL_SOURCE_TOOLS))
        self.assertEqual(3, len(LOCAL_GRAPH_TOOLS))
        self.assertEqual(38, len(create_mcp()._tool_manager._tools))
        self.assertEqual(
            16,
            len(create_mcp(include_local_cpm=False, include_local_schema=False, include_local_source=False, include_local_graph=False)._tool_manager._tools),
        )

    def test_business_graph_tools_are_local_only(self) -> None:
        names = {tool.__name__ for tool in LOCAL_GRAPH_TOOLS}
        self.assertEqual(
            {"search_business_logic_graph", "upsert_business_logic_graph", "invalidate_business_logic_graph"},
            names,
        )
        http_names = {tool.name for tool in asyncio.run(create_mcp(include_local_cpm=False, include_local_schema=False, include_local_source=False, include_local_graph=False).list_tools())}
        self.assertTrue(names.isdisjoint(http_names))

    def test_graph_calls_never_construct_a_database(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/business_logic_graph_training.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            "os.environ", {"GXP_LOWCODE_RUNTIME_ROOT": directory}
        ), patch("gxp_core.service.ReadOnlyDatabase", side_effect=AssertionError("database must not be constructed")):
            self.assertEqual(0, search_business_logic_graph()["count"])
            saved = upsert_business_logic_graph(fixture)
            self.assertTrue(saved["available"])
            self.assertEqual(1, search_business_logic_graph(field="close_date")["count"])
            result = invalidate_business_logic_graph(saved["relation"]["relation_id"], reason="user_confirmed_incorrect")
            self.assertEqual(1, result["changed"])
            self.assertEqual(0, search_business_logic_graph()["count"])
            self.assertEqual(1, search_business_logic_graph(status="invalidated")["count"])
            Path(directory, "business-logic-graph.json").write_text("broken", encoding="utf-8")
            self.assertFalse(search_business_logic_graph()["available"])
            self.assertFalse(upsert_business_logic_graph(fixture)["written"])
            self.assertFalse(invalidate_business_logic_graph(saved["relation"]["relation_id"])["available"])

    def test_http_entrypoint_explicitly_excludes_graph_registration(self):
        from http_server import create_http_app
        with patch("http_server.create_mcp", wraps=create_mcp) as factory:
            create_http_app()
        self.assertIs(False, factory.call_args.kwargs["include_local_graph"])
        names = {t.name for t in asyncio.run(create_mcp(**factory.call_args.kwargs).list_tools())}
        self.assertEqual({t.__name__ for t in MCP_TOOLS}, names)

    def test_control_flow_defaults_match_public_contract(self) -> None:
        signature = inspect.signature(inspect_control_flow)
        self.assertEqual("auto", signature.parameters["scope"].default)
        self.assertEqual(120, signature.parameters["max_nodes"].default)
        self.assertEqual(240, signature.parameters["max_edges"].default)


if __name__ == "__main__":
    unittest.main()
