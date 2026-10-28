"""Exercise diagnosis through actual MCP validation and response serialization."""
from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

from diagnostic_fixture import FixtureDatabase, STACK
from gxp_core.canvas_budget import payload_size
from gxp_core.diagnostic_cache import DIAGNOSTIC_CACHE
from gxp_core.service import GxpReadonlyService
from server import MCP_TOOLS, create_mcp


class DiagnoseMcpTests(unittest.TestCase):
    def setUp(self):
        DIAGNOSTIC_CACHE.clear()
        self.addCleanup(DIAGNOSTIC_CACHE.clear)
        self.database = FixtureDatabase()
        self.app = create_mcp()

    def call(self, name, arguments):
        with patch("server.service", side_effect=lambda: GxpReadonlyService(self.database)):
            content, result = asyncio.run(self.app.call_tool(name, arguments))
        self.assertEqual(json.loads(content[0].text), result)
        return result

    def test_dynamic_exception_continuation_is_callable_and_nested_payload_is_bounded(self):
        arguments = {"text": STACK, "context": {"goal": "review the generated exception"},
                     "max_output_bytes": 8192, "limit": 1}
        first = self.call("diagnose_codex_input", arguments)
        self.assertEqual("dynamic_exception", first["input_kind"])
        self.assertEqual("summary", first["diagnosis"]["response_detail"])
        self.assertEqual(arguments["context"], first["conversation_context"]["record"])
        next_read = first["diagnosis"]["evidence_gaps"][0]["next_read"]
        self.assertEqual("diagnose_codex_input", next_read["tool"])
        inherited = {key: arguments[key] for key in next_read["inherit_arguments"] if key in arguments}
        body_reads = self.database.body_reads
        with patch("gxp_core.diagnostics.DiagnosticEngine.trace_dynamic_exception",
                   side_effect=AssertionError("verified continuation must reuse analysis")):
            second = self.call(next_read["tool"], {**inherited, **next_read["arguments"]})
        self.assertEqual(body_reads, self.database.body_reads)
        self.assertEqual(first["diagnosis"]["snapshot_fingerprint"], second["diagnosis"]["snapshot_fingerprint"])
        for result in (first, second):
            self.assertRegex(result["trace_id"], r"^[0-9a-f]{32}$")
            # Existing budget contract excludes the MCP transport's telemetry.
            payload = {key: value for key, value in result.items()
                       if key not in {"trace_id", "timings", "total_elapsed_ms"}}
            self.assertLessEqual(payload_size(payload), 8192)

    def test_natural_language_resolution_remains_compatible_through_mcp(self):
        result = self.call("diagnose_codex_input", {"text": "ACTION01", "context": {"goal": "inspect action"}})
        self.assertEqual("natural_language", result["input_kind"])
        self.assertEqual("unique", result["action_resolution_status"])
        self.assertEqual("ACTION01", result["resolved_actions"][0]["action_code"])
        self.assertEqual({"goal": "inspect action"}, result["conversation_context"]["record"])
        self.assertNotIn("diagnosis", result)

    def test_http_factory_registers_only_the_sixteen_readonly_tools(self):
        from http_server import create_http_app

        instances = []

        def factory(*args, **kwargs):
            app = create_mcp(*args, **kwargs)
            instances.append(app)
            return app

        with patch("http_server.create_mcp", side_effect=factory):
            create_http_app()
        self.app = instances[0]
        tools = asyncio.run(self.app.list_tools())
        self.assertEqual(16, len(tools))
        self.assertEqual({tool.__name__ for tool in MCP_TOOLS}, {tool.name for tool in tools})
        result = self.call("diagnose_codex_input", {"text": STACK, "max_output_bytes": 8192, "limit": 1})
        self.assertEqual("dynamic_exception", result["input_kind"])
        self.assertTrue(result["diagnosis"]["has_more"])


if __name__ == "__main__":
    unittest.main()
