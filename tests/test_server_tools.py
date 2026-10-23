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
    LOCAL_HANDOFF_TOOLS,
    LOCAL_SETTINGS_TOOLS,
    create_mcp,
    inspect_action,
    inspect_control_flow,
    search_business_logic_graph,
    upsert_business_logic_graph,
    invalidate_business_logic_graph,
    get_business_graph,
    trace_business_data_flow,
    analyze_business_graph,
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

    def test_local_stdio_has_44_tools_and_http_factory_has_16(self) -> None:
        self.assertEqual(16, len(MCP_TOOLS))
        self.assertEqual(5, len(LOCAL_CPM_TOOLS))
        self.assertEqual(7, len(LOCAL_SCHEMA_TOOLS))
        self.assertEqual(7, len(LOCAL_SOURCE_TOOLS))
        self.assertEqual(6, len(LOCAL_GRAPH_TOOLS))
        self.assertEqual(2, len(LOCAL_HANDOFF_TOOLS))
        self.assertEqual(1, len(LOCAL_SETTINGS_TOOLS))
        self.assertEqual(44, len(create_mcp()._tool_manager._tools))
        self.assertEqual(
            16,
            len(create_mcp(include_local_cpm=False, include_local_schema=False, include_local_source=False, include_local_graph=False, include_local_handoff=False, include_local_settings=False)._tool_manager._tools),
        )

    def test_business_graph_tools_are_local_only(self) -> None:
        names = {tool.__name__ for tool in LOCAL_GRAPH_TOOLS}
        self.assertEqual(
            {"search_business_logic_graph", "upsert_business_logic_graph", "invalidate_business_logic_graph",
             "get_business_graph", "trace_business_data_flow", "analyze_business_graph"},
            names,
        )
        http_names = {tool.name for tool in asyncio.run(create_mcp(include_local_cpm=False, include_local_schema=False, include_local_source=False, include_local_graph=False, include_local_handoff=False, include_local_settings=False).list_tools())}
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
            self.assertTrue(get_business_graph(include_catalog=True)["available"])
            self.assertTrue(analyze_business_graph()["available"])
            self.assertTrue(trace_business_data_flow(start="a" * 64)["available"])
            Path(directory, "business-graph.sqlite3").write_bytes(b"broken")
            self.assertFalse(search_business_logic_graph()["available"])
            self.assertFalse(upsert_business_logic_graph(fixture)["written"])
            self.assertFalse(invalidate_business_logic_graph(saved["relation"]["relation_id"])["available"])
            self.assertFalse(get_business_graph()["available"])
            self.assertFalse(analyze_business_graph()["available"])
            self.assertFalse(trace_business_data_flow(start="a" * 64)["available"])

    def test_http_entrypoint_explicitly_excludes_graph_registration(self):
        from http_server import create_http_app
        with patch("http_server.create_mcp", wraps=create_mcp) as factory:
            create_http_app()
        self.assertIs(False, factory.call_args.kwargs["include_local_graph"])
        self.assertIs(False, factory.call_args.kwargs["include_local_handoff"])
        self.assertIs(False, factory.call_args.kwargs["include_local_settings"])
        names = {t.name for t in asyncio.run(create_mcp(**factory.call_args.kwargs).list_tools())}
        self.assertEqual({t.__name__ for t in MCP_TOOLS}, names)

    def test_settings_are_local_only_and_available_without_database_configuration(self):
        from server import database_settings
        import sys
        from types import ModuleType

        self.assertEqual({"database_settings"}, {tool.__name__ for tool in LOCAL_SETTINGS_TOOLS})
        tools = {tool.name: tool for tool in asyncio.run(create_mcp().list_tools())}
        properties = tools["database_settings"].inputSchema["properties"]
        self.assertEqual({"operation", "changes", "expected_revision"}, set(properties))
        self.assertEqual({"status", "open", "update"}, set(properties["operation"]["enum"]))
        self.assertEqual("status", properties["operation"]["default"])
        backend = ModuleType("gxp_core.connection_settings")
        with patch.object(backend, "manage_settings", create=True, return_value={"configured": False}) as manage, \
             patch.dict(sys.modules, {"gxp_core.connection_settings": backend}), \
             patch("server.service", side_effect=AssertionError("No database service required")):
            self.assertFalse(database_settings()["configured"])
            manage.assert_called_once_with("status", None, "")
            database_settings("update", {"host": "db.example.test"}, "revision")
            manage.assert_called_with("update", {"host": "db.example.test"}, "revision")
            database_settings("open")
            manage.assert_called_with("open", None, "")

    def test_handoff_tools_are_local_only_and_read_has_no_database_dependency(self):
        self.assertEqual({"export_edit_handoff", "read_edit_handoff"}, {tool.__name__ for tool in LOCAL_HANDOFF_TOOLS})
        from server import read_edit_handoff
        with patch("gxp_core.service.ReadOnlyDatabase", side_effect=AssertionError("No database required")):
            self.assertFalse(read_edit_handoff("bad/path")["available"])

    def test_handoff_schema_exposes_optional_diagnosis_and_discovery_controls(self):
        tools = {tool.name: tool for tool in asyncio.run(create_mcp().list_tools())}
        export = tools["export_edit_handoff"].inputSchema["properties"]
        self.assertEqual("edit_snapshot", export["record_kind"]["default"])
        read = tools["read_edit_handoff"].inputSchema["properties"]
        self.assertEqual("", read["environment_scope"]["default"])
        self.assertEqual("", read["cursor"]["default"])
        self.assertEqual(10, read["limit"]["default"])

    def test_handoff_public_wrappers_forward_optional_controls(self):
        from server import export_edit_handoff, read_edit_handoff
        with patch("server.service") as service:
            export_edit_handoff("code", [], {}, {}, record_kind="diagnosis_only")
            service.return_value.export_edit_handoff.assert_called_once_with("code", [], {}, {}, record_kind="diagnosis_only")
        with patch("server.GxpReadonlyService.read_edit_handoff") as read:
            read_edit_handoff(identifier="code", environment_scope="a" * 64, cursor="opaque", limit=3)
            read.assert_called_once_with("", "code", "", target_index=None, environment_scope="a" * 64, cursor="opaque", limit=3)

    def test_control_flow_defaults_match_public_contract(self) -> None:
        signature = inspect.signature(inspect_control_flow)
        self.assertEqual("auto", signature.parameters["scope"].default)
        self.assertEqual(120, signature.parameters["max_nodes"].default)
        self.assertEqual(240, signature.parameters["max_edges"].default)


if __name__ == "__main__":
    unittest.main()
