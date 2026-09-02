from __future__ import annotations

import inspect
import unittest

from server import (
    LOCAL_CPM_TOOLS,
    MCP_TOOLS,
    create_mcp,
    inspect_action,
    inspect_control_flow,
)


class ServerToolRegistrationTests(unittest.TestCase):
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

    def test_local_stdio_has_21_tools_and_http_factory_has_16(self) -> None:
        self.assertEqual(16, len(MCP_TOOLS))
        self.assertEqual(5, len(LOCAL_CPM_TOOLS))
        self.assertEqual(21, len(create_mcp()._tool_manager._tools))
        self.assertEqual(16, len(create_mcp(include_local_cpm=False)._tool_manager._tools))

    def test_control_flow_defaults_match_public_contract(self) -> None:
        signature = inspect.signature(inspect_control_flow)
        self.assertEqual("auto", signature.parameters["scope"].default)
        self.assertEqual(120, signature.parameters["max_nodes"].default)
        self.assertEqual(240, signature.parameters["max_edges"].default)


if __name__ == "__main__":
    unittest.main()
