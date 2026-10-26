from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from contextlib import closing
from unittest.mock import patch

from gxp_core.business_graph_algorithms import components
from gxp_core.business_graph_store import BusinessGraphStore
from gxp_core.graph_budget import ACTIVE_BUDGET, GraphQueryBudgetExceeded, QueryBudget
from gxp_core.service import GxpReadonlyService
from gxp_core.canvas import CanvasInspector
from gxp_core import source_analysis
from test_accuracy_evidence import Repository, snapshot
from test_business_graph import observation
from test_conversation_accuracy import design, node


class GraphQueryWorkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.store = BusinessGraphStore(Path(temporary.name) / "graph.sqlite3", scope_id="test")

    def test_streamed_search_keeps_exact_count_order_and_uses_read_transaction(self):
        for index in range(12):
            self.store.upsert(observation(f"case-{index}"))
        statements = []
        original = self.store._connect

        def tracked(*args, **kwargs):
            connection = original(*args, **kwargs)
            connection.set_trace_callback(statements.append)
            return connection

        with patch.object(self.store, "_connect", side_effect=tracked):
            result = self.store.search(query="confirmed mapping", limit=3)
        self.assertEqual(12, result["matched_count"])
        self.assertTrue(result["matched_count_complete"])
        self.assertEqual(3, result["count"])
        self.assertTrue(result["truncated"])
        self.assertIn("BEGIN", statements)
        self.assertNotIn("BEGIN IMMEDIATE", statements)
        self.assertEqual(self.store.search(limit=50)["relations"][:3], result["relations"])

    def test_sql_work_interrupt_has_unknown_count_and_releases_connection(self):
        for index in range(20):
            self.store.upsert(observation(f"case-{index}"))
        with self.store._transaction(write=True) as connection:
            connection.execute("""WITH RECURSIVE n(value) AS (SELECT 1 UNION ALL SELECT value+1 FROM n WHERE value<200)
                INSERT INTO observations SELECT observations.id||'-copy-'||n.value,case_id,revision+n.value,
                lifecycle,level,fingerprint,body,created_at FROM observations CROSS JOIN n
                WHERE observations.id=(SELECT id FROM observations LIMIT 1)""")
        self.store.query_vm_steps = 1000
        result = self.store.search()
        self.assertEqual("GRAPH_QUERY_BUDGET_EXCEEDED", result["incomplete_reason"])
        self.assertIsNone(result["matched_count"])
        self.assertFalse(result["matched_count_complete"])
        self.assertFalse(result["query_complete"])
        self.store.query_vm_steps = 25000000
        self.assertEqual(220, self.store.search()["matched_count"])

    def test_interrupted_evidence_update_rolls_back_version_and_lifecycle(self):
        raw = observation()
        raw["evidence"][0]["dependencies"].append({"kind": "action", "key": "action", "version": "v1"})
        self.store.upsert(raw)
        with closing(sqlite3.connect(self.store.path)) as connection:
            revision = connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0]
        with patch.object(self.store, "_relation", side_effect=GraphQueryBudgetExceeded()):
            result = self.store.search(current_published_designs={"action": "v2"}, status="stale")
        self.assertEqual("incomplete", result["status"])
        with closing(sqlite3.connect(self.store.path)) as connection:
            self.assertEqual("v1", connection.execute("SELECT version FROM versions WHERE kind='action'").fetchone()[0])
            self.assertEqual("active", connection.execute("SELECT lifecycle FROM observations").fetchone()[0])
            self.assertEqual(revision, connection.execute("SELECT value FROM meta WHERE key='revision'").fetchone()[0])

    def test_expired_exact_read_and_analysis_never_claim_absence_or_isolation(self):
        self.store.upsert(observation())
        self.store.query_timeout_seconds = 0
        for operation in (lambda: self.store.search(case_key="case"), self.store.analyze):
            result = operation()
            self.assertEqual("incomplete", result["status"])
            self.assertNotIn("found", result)
            self.assertFalse(result.get("isolated"))
            self.assertFalse(result["scope_complete"])

    def test_python_graph_walk_checks_the_same_request_deadline(self):
        token = ACTIVE_BUDGET.set(QueryBudget(0, 25000000))
        try:
            with self.assertRaises(GraphQueryBudgetExceeded):
                components([{"id": "a"}], [])
        finally:
            ACTIVE_BUDGET.reset(token)

    def test_snapshot_batches_alias_support_and_boundary_reads(self):
        for index in range(20):
            raw = observation(f"case-{index}", f"A{index}", f"B{index}")
            raw["entities"][0]["boundary"] = "source"
            self.store.upsert(raw)
        statements = []
        with self.store._transaction() as connection:
            connection.set_trace_callback(statements.append)
            result = self.store._snapshot(connection, "test", "development", True)
        self.assertEqual(40, len(result["nodes"]))
        self.assertEqual(20, len(result["edges"]))
        self.assertEqual(20, sum(node["boundary"] == "source" for node in result["nodes"]))
        self.assertTrue(all(node["aliases"] == [node["label"]] for node in result["nodes"]))
        self.assertTrue(all(edge["support_count"] == 1 and "evidence_ids" not in edge for edge in result["edges"]))
        self.assertLessEqual(sum(statement.lstrip().upper().startswith(("SELECT", "WITH")) for statement in statements), 7)


class PayloadAndBackendWorkTests(unittest.TestCase):
    def test_control_flow_root_callee_and_filter_skip_generated_code(self):
        root = snapshot(design([node("call", "CallPublicAction", {"actionName": {"code": "child"}})]))
        repository = Repository(root, {"child": snapshot(design([]), "child")})
        service = object.__new__(GxpReadonlyService)
        service.repository, service.inspector = repository, CanvasInspector()
        result = service.inspect_control_flow("root", group="main", follow_calls=True)
        self.assertEqual(2, len(result["call_flow"]["designs"]))
        service.inspect_component_filters("root", "picker")
        self.assertEqual(3, len(repository.reads))
        self.assertTrue(all(options["include_csharp"] is False for _, options in repository.reads))

    def test_backend_maps_preserve_duplicate_targets_order_cycles_and_depth(self):
        symbols = [{"symbol_id": identity, "name": name, "kind": "method", "path": "S.cs", "line": index + 1}
                   for index, (identity, name) in enumerate((("App.Root.Run()", "Root.Run"), ("b", "B.first"), ("a", "A"), ("b", "B.second")))]
        def edge(caller, targets, member):
            return {"caller_id": caller, "target_ids": targets, "callee_member": member, "path": "S.cs", "line": 1}
        edges = [edge("App.Root.Run()", ["a", "b", "b"], "ambiguous"), edge("App.Root.Run()", ["a"], "single"), edge("a", ["App.Root.Run()"], "cycle")]
        files = {"backend/symbols.json": symbols, "graph/backend-call-edges.json": edges}
        with patch.object(source_analysis, "ensure_source_index", return_value={}), patch.object(source_analysis, "load_index_file", side_effect=lambda name, default: files.get(name, default)):
            result = source_analysis.trace_backend_call_chain.__wrapped__("App.Root.Run()")
            shallow = source_analysis.trace_backend_call_chain.__wrapped__("App.Root.Run()", max_depth=1)
            ambiguous = source_analysis.trace_backend_call_chain.__wrapped__("b")
        self.assertEqual(["B.first", "A", "B.second"], result["call_tree"][0]["targets"])
        self.assertTrue(result["call_tree"][0]["ambiguous"])
        self.assertEqual([0, 0, 1], [item["depth"] for item in result["call_tree"]])
        self.assertEqual(2, len(shallow["call_tree"]))
        self.assertEqual("ambiguous", ambiguous["status"])
        self.assertEqual([], ambiguous["call_tree"])


if __name__ == "__main__":
    unittest.main()
