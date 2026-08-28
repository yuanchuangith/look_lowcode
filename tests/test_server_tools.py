from __future__ import annotations

import inspect
import unittest

from server import LOCAL_CPM_TOOLS, MCP_TOOLS, create_mcp, inspect_action


class ServerToolRegistrationTests(unittest.TestCase):
    def test_new_readonly_tools_are_registered(self) -> None:
        names = {tool.__name__ for tool in MCP_TOOLS}
        self.assertIn("search_pages", names)
        self.assertIn("list_page_actions", names)
        self.assertIn("inspect_component_filters", names)

    def test_inspect_action_defaults_to_compact_no_csharp(self) -> None:
        signature = inspect.signature(inspect_action)
        self.assertFalse(signature.parameters["include_generated_csharp"].default)
        self.assertEqual(20, signature.parameters["max_nodes"].default)

    def test_local_stdio_has_20_tools_and_http_factory_can_keep_original_15(self) -> None:
        self.assertEqual(15, len(MCP_TOOLS))
        self.assertEqual(5, len(LOCAL_CPM_TOOLS))
        self.assertEqual(20, len(create_mcp()._tool_manager._tools))
        self.assertEqual(15, len(create_mcp(include_local_cpm=False)._tool_manager._tools))


if __name__ == "__main__":
    unittest.main()
