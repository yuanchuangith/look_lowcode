from __future__ import annotations

import copy
import json
import sqlite3
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from gxp_core.business_graph_model import entity, normalize_v3
from gxp_core.business_graph_store import BusinessGraphStore
from gxp_core.business_logic_graph import BusinessLogicGraphError, GraphValidationError, _encoded


def observation(case="case", source="A", target="B", version="v1", kind="flows_to"):
    def field(name):
        return {"id": name, "kind": "field", "label": name,
                "key": {"datasource": "test", "schema": "main", "owner_kind": "table", "owner": "Orders", "column": name}}
    return {"format_version": 3, "scope_id": "test", "environment": "development", "case_key": case,
            "conclusion": "Sanitized confirmed mapping", "status": "confirmed_static",
            "entities": [field(source), field(target)],
            "facts": [{"id": "flow", "source": source, "target": target, "kind": kind, "label": "field copy",
                       "granularity": "field_level", "mapping": {"kind": "copy", "fingerprint": "c" * 64},
                       "evidence_ids": ["code", "schema"]}],
            "evidence": [{"id": "code", "type": "source_static", "fingerprint": "a" * 64,
                          "summary": "Static source mapping", "dependencies": [{"kind": "source", "key": "mapping-" + case, "version": version}],
                          "anchors": [{"repository": "backend", "file": "Mapping.cs", "symbol": "Map", "line": 12}]},
                         {"id": "schema", "type": "schema", "fingerprint": "b" * 64, "summary": "Verified schema identity",
                          "dependencies": [{"kind": "schema", "key": "test-schema", "version": "schema-v1"}]}]}


class BusinessGraphTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = BusinessGraphStore(self.root / "business-graph.sqlite3", scope_id="test")

    def ids(self, raw):
        return [entity(item, "test", "development")["id"] for item in raw["entities"]]

    def test_cross_case_chain_and_idempotency(self):
        first = observation("one", "A", "B")
        result = self.store.upsert(first)
        self.assertTrue(result["written"])
        self.assertTrue(self.store.upsert(first)["idempotent"])
        self.store.upsert(observation("two", "B", "C"))
        last = observation("three", "C", "D")
        self.store.upsert(last)
        graph = self.store.get_graph(depth=5, projection="data")
        self.assertEqual(len(graph["nodes"]), 4)
        self.assertEqual(len(graph["edges"]), 3)
        trace = self.store.trace(start=self.ids(first)[0], target=self.ids(last)[1])
        self.assertEqual(len(trace["paths"][0]["edges"]), 3)
        self.assertEqual(trace["paths"][0]["granularity"], "field_level")
        self.assertTrue(all(bundle["evidence"][0].get("anchors") or bundle["evidence"][1].get("anchors") for bundle in trace["evidence"]))

    def test_terminal_paths_at_depth_limit_in_both_directions(self):
        increments = [observation(f"hop-{index}", f"N{index}", f"N{index + 1}") for index in range(8)]
        for raw in increments:
            self.store.upsert(raw)
        for depth in (1, 8):
            for direction in ("downstream", "upstream"):
                with self.subTest(depth=depth, direction=direction):
                    start = self.ids(increments[8 - depth])[0] if direction == "downstream" else self.ids(increments[depth - 1])[1]
                    result = self.store.trace(start=start, direction=direction, max_depth=depth)
                    self.assertEqual(len(result["paths"]), 1)
                    self.assertEqual(len(result["paths"][0]["edges"]), depth)
                    self.assertFalse(result["truncated"])
                    self.assertEqual(result["frontier"], [])
        for direction, start in (("downstream", self.ids(increments[0])[0]),
                                 ("upstream", self.ids(increments[-1])[1])):
            with self.subTest(direction=direction, unfinished=True):
                result = self.store.trace(start=start, direction=direction, max_depth=7)
                self.assertEqual(result["paths"], [])
                self.assertTrue(result["truncated"])
                self.assertEqual(len(result["frontier"]), 1)

    def test_independent_supports_and_version_dependencies(self):
        first, second = observation("one"), observation("two")
        result = self.store.upsert(first)
        self.store.upsert(second)
        self.assertEqual(self.store.get_graph()["edges"][0]["support_count"], 2)
        self.store.invalidate(result["relation"]["relation_id"], reason="user_confirmed_incorrect")
        self.assertEqual(self.store.get_graph()["edges"][0]["support_count"], 1)
        changed = observation("version-check", "X", "Y")
        changed["evidence"][0]["dependencies"] = [{"kind": "source", "key": "mapping-two", "version": "v2"}]
        self.store.upsert(changed)
        self.assertEqual(len(self.store.get_graph()["edges"]), 1)
        with closing(sqlite3.connect(self.store.path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM supports WHERE lifecycle='stale'").fetchone()[0], 1)

    def test_dependency_set_invalidates_only_affected_fact(self):
        raw = observation()
        extra = copy.deepcopy(raw["facts"][0])
        extra.update(id="other", kind="associated_with", evidence_ids=["schema", "other-code"])
        raw["facts"].append(extra)
        proof = copy.deepcopy(raw["evidence"][0])
        proof.update(id="other-code", dependencies=[{"kind": "source", "key": "unrelated", "version": "v1"}])
        raw["evidence"].append(proof)
        self.store.upsert(raw)
        change = observation("new", "X", "Y", "v2")
        change["evidence"][0]["dependencies"][0]["key"] = "mapping-case"
        self.store.upsert(change)
        self.assertEqual({edge["kind"] for edge in self.store.get_graph()["edges"]}, {"associated_with", "flows_to"})

    def test_identity_namespace_aliases_and_boundaries(self):
        raw = observation()
        first = self.ids(raw)[0]
        renamed = copy.deepcopy(raw)
        renamed["case_key"] = "rename"
        renamed["entities"][0].update(label="Renamed", boundary="source")
        self.store.upsert(raw)
        self.store.upsert(renamed)
        self.store.upsert(observation("later"))
        graph = self.store.get_graph(query="Renamed")
        self.assertIn(first, {node["id"] for node in graph["nodes"]})
        self.assertEqual(next(node for node in graph["nodes"] if node["id"] == first)["boundary"], "source")
        for path, value in (("owner", "Other"), ("datasource", "other")):
            changed = copy.deepcopy(raw["entities"][0])
            changed["key"][path] = value
            self.assertNotEqual(entity(changed, "test", "development")["id"], first)
        self.assertNotEqual(entity(raw["entities"][0], "test", "production")["id"], first)
        broken = copy.deepcopy(raw)
        del broken["entities"][0]["key"]["owner"]
        self.assertEqual(self.store.upsert(broken)["delta"]["pending_review"], 2)
        self.assertTrue(self.store.analyze()["pending_review"])

    def test_catalog_structural_edges_are_not_lineage(self):
        raw = observation(kind="contains")
        raw["facts"][0]["granularity"] = "dataset_level"
        raw["evidence"] = [{"id": "catalog", "type": "schema_catalog", "fingerprint": "d" * 64,
                            "summary": "Existing directory", "dependencies": [{"kind": "catalog", "key": "schema", "version": "v1"}]}]
        raw["facts"][0]["evidence_ids"] = ["catalog"]
        self.store.upsert(raw)
        self.assertEqual(self.store.get_graph()["nodes"], [])
        self.assertTrue(all(node["catalog"] for node in self.store.get_graph(include_catalog=True)["nodes"]))
        self.assertEqual(self.store.get_graph(include_catalog=True, projection="data")["edges"], [])

    def test_cycles_islands_boundaries_and_bridge(self):
        self.store.upsert(observation("forward"))
        self.store.upsert(observation("feedback", "B", "A"))
        lone = observation("lone", "L", "M")
        lone["entities"] = lone["entities"][:1]
        lone["entities"][0]["boundary"] = "independent"
        lone["facts"] = []
        self.store.upsert(lone)
        analyzed = self.store.analyze(projection="data")
        self.assertEqual(analyzed["summary"]["component_count"], 2)
        self.assertEqual(analyzed["summary"]["cycle_count"], 1)
        self.assertEqual(analyzed["gaps"][0]["reason"], "business_independent")
        self.assertIn("flowchart", analyzed["condensation"]["mermaid"])
        self.store.upsert(observation("bridge", "B", "L"))
        self.assertEqual(self.store.analyze()["summary"]["component_count"], 1)

    def test_calls_require_binding_for_data_projection(self):
        raw = observation(kind="calls")
        raw["entities"] = [{"id": name, "kind": "service", "label": name,
                            "key": {"repository": "backend", "symbol": name}} for name in ("A", "B")]
        raw["facts"][0]["granularity"] = "dataset_level"
        self.store.upsert(raw)
        self.assertFalse(self.store.get_graph(projection="data")["edges"])
        raw["case_key"] = "binding"
        raw["facts"][0].update(data_binding=True, mapping={"kind": "binding", "fingerprint": "f" * 64})
        self.store.upsert(raw)
        self.assertEqual(len(self.store.get_graph(projection="data")["edges"]), 1)

    def test_field_granularity_and_sensitive_gate(self):
        raw = observation()
        raw["entities"][1] = {"id": "B", "kind": "view", "label": "Summary", "key": {"datasource": "test", "schema": "main", "name": "Summary"}}
        with self.assertRaises(GraphValidationError):
            self.store.upsert(raw)
        for text in ("password=secret", "Bearer abcdefghijklmnop", "SELECT * FROM Orders"):
            raw = observation()
            raw["conclusion"] = text
            with self.assertRaises(GraphValidationError):
                self.store.upsert(raw)
        raw = observation()
        raw["business_rows"] = [{"value": "unsafe"}]
        with self.assertRaises(GraphValidationError):
            self.store.upsert(raw)

    def test_concurrent_transactions_and_lock_timeout(self):
        with ThreadPoolExecutor(max_workers=4) as workers:
            results = list(workers.map(lambda index: self.store.upsert(observation(str(index))), range(8)))
        self.assertEqual(len(results), 8)
        self.assertEqual(self.store.get_graph()["edges"][0]["support_count"], 8)
        with closing(sqlite3.connect(self.store.path)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            locked = BusinessGraphStore(self.store.path, scope_id="test", lock_timeout_seconds=0.02)
            with self.assertRaisesRegex(BusinessLogicGraphError, "GRAPH_LOCK_TIMEOUT"):
                locked.upsert(observation("locked"))

    def test_corrupt_database_and_legacy_import_idempotency(self):
        legacy = json.loads((Path(__file__).parent / "fixtures/business_logic_graph_training.json").read_text(encoding="utf-8"))
        legacy_file = self.root / "business-logic-graph.json"
        legacy_file.write_text(json.dumps({"version": 2, "schema_version": 1, "relations": [legacy]}), encoding="utf-8")
        original = legacy_file.read_bytes()
        result = self.store.search()
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["migration"]["imported"], 1)
        self.assertEqual(legacy_file.read_bytes(), original)
        self.assertEqual(BusinessGraphStore(self.store.path, scope_id="test").search()["migration"], result["migration"])
        with closing(sqlite3.connect(self.store.path)) as connection:
            self.assertGreater(connection.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 0)
        broken = self.root / "broken.sqlite3"
        broken.write_bytes(b"not sqlite")
        with self.assertRaises(BusinessLogicGraphError):
            BusinessGraphStore(broken, scope_id="test").get_graph()

    def test_catalog_budget_shared_and_timeout(self):
        raw = observation()
        self.store.upsert(raw)
        def missing(*args, **kwargs):
            return {"reason": "catalog_missing_or_stale"}
        with patch("gxp_core.business_graph_catalog.lookup", side_effect=missing) as lookup:
            self.store.get_graph(request_id="request-one")
            self.store.analyze(request_id="request-one")
            self.assertEqual(lookup.call_count, 2)
        started = time.monotonic()
        def slow(*args, **kwargs):
            time.sleep(0.15)
            return {}
        self.assertEqual(self.store._bounded_lookup(slow, {}, "test", "development", 0.02)["reason"], "catalog_budget_exhausted")
        self.assertLess(time.monotonic() - started, 0.1)

    def test_truncation_does_not_report_fake_islands(self):
        self.store.upsert(observation())
        with patch.object(self.store, "_snapshot", wraps=self.store._snapshot) as snapshot:
            original = snapshot._mock_wraps
            snapshot.side_effect = lambda *args: {**original(*args), "complete": False}
            result = self.store.analyze()
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["isolated"], [])
        self.assertLessEqual(len(_encoded(result)), 256 * 1024)

    def test_parallel_branches_and_conversions_remain_distinct(self):
        for index, branch in enumerate(("if-main", "else-main")):
            raw = observation(str(index))
            raw["facts"][0]["condition"] = {"branch_keys": [branch]}
            self.store.upsert(raw)
        changed = observation("derived")
        changed["facts"][0].update(kind="transforms", mapping={"kind": "derive", "fingerprint": "f" * 64})
        self.store.upsert(changed)
        self.assertEqual(len(self.store.get_graph()["edges"]), 3)

    def test_typed_api_route_templates_are_safe_identities(self):
        raw = {"id": "api", "kind": "api", "label": "Orders API",
               "key": {"repository": "backend", "method": "get", "route": "api/orders/{id:int}"}}
        normalized = entity(raw, "test", "development")
        self.assertEqual(normalized["key"]["route"], "/api/orders/{id:int}")
        self.assertEqual(normalized["key"]["method"], "GET")
        raw["key"]["route"] = "/api/orders?password=secret"
        with self.assertRaises(GraphValidationError):
            entity(raw, "test", "development")

    def test_business_keyword_resolves_entities_through_cases(self):
        raw = observation()
        raw["conclusion"] = "Confirmed cancellation flow in the training domain"
        self.store.upsert(raw)
        graph = self.store.get_graph(query="training cancellation")
        self.assertEqual(len(graph["edges"]), 1)
        self.assertTrue(graph["query_complete"])

    def test_reordered_increment_and_duplicate_facts_are_canonical(self):
        raw = observation()
        self.store.upsert(raw)
        raw["entities"].reverse()
        raw["evidence"].reverse()
        self.assertTrue(self.store.upsert(raw)["idempotent"])
        raw["facts"].append({**raw["facts"][0], "id": "duplicate"})
        self.assertTrue(self.store.upsert(raw)["idempotent"])

    def test_revoked_boundary_cannot_hide_a_missing_producer(self):
        self.store.upsert(observation())
        explicit = observation("boundary")
        explicit["entities"][0]["boundary"] = "source"
        saved = self.store.upsert(explicit)
        self.store.upsert(observation("later"))
        self.store.invalidate(saved["relation"]["relation_id"], reason="user_confirmed_incorrect")
        graph = self.store.get_graph()
        self.assertEqual(next(node for node in graph["nodes"] if node["id"] == self.ids(explicit)[0])["boundary"], "unknown")

    def test_all_action_dependencies_are_checked(self):
        raw = observation(kind="calls")
        raw["entities"] = [{"id": "A", "kind": "action", "label": "Caller", "key": {"ref_id": "caller"}},
                           {"id": "B", "kind": "action", "label": "Callee", "key": {"ref_id": "callee"}}]
        raw["facts"][0]["granularity"] = "dataset_level"
        dependencies = [{"kind": "action", "key": name, "version": "published-v1"} for name in ("caller", "callee")]
        raw["evidence"] = [{"id": "code", "type": "published_design", "fingerprint": "a" * 64,
                            "summary": "Current published identities", "dependencies": dependencies},
                           {"id": "schema", "type": "control_flow", "fingerprint": "b" * 64,
                            "summary": "Confirmed control blocks", "dependencies": dependencies}]
        self.store.upsert(raw)
        self.store.upsert(observation("unrelated", "X", "Y"))
        self.store.search(current_published_designs={"callee": "published-v2"})
        self.assertEqual(len(self.store.get_graph()["edges"]), 1)
        self.assertEqual(self.store.get_graph()["edges"][0]["kind"], "flows_to")

    def test_effective_metadata_never_uses_withdrawn_support(self):
        self.store.upsert(observation("field-proof"))
        newer = observation("dataset-proof")
        newer["facts"][0].update(granularity="dataset_level", label="Withdrawn coarse description")
        saved = self.store.upsert(newer)
        self.store.invalidate(saved["relation"]["relation_id"], reason="user_confirmed_incorrect")
        edge = self.store.get_graph()["edges"][0]
        self.assertEqual(edge["granularity"], "field_level")
        self.assertEqual(edge["label"], "field copy")

    def test_large_support_bundles_are_never_cut_in_half(self):
        raw = observation("large")
        for index in range(70):
            proof = {"id": "proof-" + str(index), "type": "source_static", "fingerprint": "d" * 64,
                     "summary": "Safe structural summary " * 38,
                     "dependencies": [{"kind": "source", "key": "source-large", "version": "v1"}]}
            raw["evidence"].append(proof)
            raw["facts"][0]["evidence_ids"].append(proof["id"])
        for index in range(3):
            raw["case_key"] = "large-" + str(index)
            self.store.upsert(raw)
        result = self.store.get_graph()
        self.assertEqual(len(result["edges"]), 1)
        self.assertEqual(result["edges"][0]["support_count"], 3)
        self.assertFalse(result["edges"][0]["evidence_page_complete"])
        self.assertTrue(all(len(bundle["evidence"]) == 72 for bundle in result["evidence"]))
        self.assertLessEqual(len(_encoded(result)), 256 * 1024)

    def test_bad_catalog_proof_is_deferred_not_fatal(self):
        self.store.upsert(observation())
        with patch("gxp_core.business_graph_catalog.lookup", return_value={"observation": {}, "source": "existing", "version": "v1"}):
            result = self.store.get_graph(request_id="bad-catalog")
        self.assertEqual(len(result["edges"]), 1)
        self.assertTrue(all(item["reason"] == "catalog_evidence_incomplete" for item in result["expansion"]["deferred"]))

    def test_dense_increment_stores_evidence_once_and_bounds_write_response(self):
        raw = observation()
        raw["evidence"][0]["summary"] = "Safe mapping evidence " * 40
        raw["evidence"][1]["summary"] = "Safe schema evidence " * 40
        base = raw["facts"][0]
        raw["facts"] = [{**base, "id": "branch-" + str(index), "condition": {"branch_keys": ["branch-" + str(index)]}}
                        for index in range(180)]
        saved = self.store.upsert(raw)
        self.assertLessEqual(len(_encoded(saved)), 256 * 1024)
        self.assertTrue(all("evidence_ids" in fact and "evidence" not in fact for fact in normalize_v3(raw, "test")["facts"]))
        with closing(sqlite3.connect(self.store.path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM evidence").fetchone()[0], 2)

    def test_parallel_edge_budget_can_continue_with_cursor(self):
        raw = observation()
        for index in range(70):
            proof = {"id": "proof-" + str(index), "type": "source_static", "fingerprint": "d" * 64,
                     "summary": "Safe structural summary " * 38,
                     "dependencies": [{"kind": "source", "key": "source-large", "version": "v1"}]}
            raw["evidence"].append(proof)
            raw["facts"][0]["evidence_ids"].append(proof["id"])
        second = copy.deepcopy(raw["facts"][0])
        second.update(id="parallel", condition={"branch_keys": ["else"]})
        raw["facts"].append(second)
        self.store.upsert(raw)
        first = self.store.get_graph()
        self.assertEqual(len(first["edges"]), 1)
        self.assertTrue(first["next_edge_cursor"])
        later = self.store.get_graph(edge_cursor=first["next_edge_cursor"])
        self.assertEqual(len(later["edges"]), 1)
        self.assertNotEqual(first["edges"][0]["id"], later["edges"][0]["id"])
        self.assertTrue(all(len(bundle["evidence"]) == 72 for page in (first, later) for bundle in page["evidence"]))

    def test_budget_never_resets_between_graph_tools(self):
        self.store.upsert(observation())
        self.store.upsert(observation("next", "C", "D"))
        with patch("gxp_core.business_graph_catalog.lookup", return_value={"reason": "catalog_missing_or_stale"}) as lookup:
            first = self.store.get_graph(request_id="shared")
            second = self.store.analyze(request_id="shared")
            self.assertEqual(first["expansion"]["total_attempts"], 3)
            self.assertEqual(second["expansion"]["attempted"], 0)
            self.assertEqual(lookup.call_count, 3)

    def test_malformed_import_record_cannot_leave_partial_transaction(self):
        raw = json.loads((Path(__file__).parent / "fixtures/business_logic_graph_training.json").read_text(encoding="utf-8"))
        malformed = {**raw, "lifecycle": ["invalid"]}
        self.store.legacy_path.write_text(json.dumps({"version": 2, "relations": [{"status": []}, malformed, raw]}), encoding="utf-8")
        result = self.store.search()
        self.assertEqual(result["migration"]["imported"], 1)
        self.assertEqual(result["migration"]["rejected"], 1)
        self.assertEqual(result["migration"]["skipped"], 1)
        with closing(sqlite3.connect(self.store.path)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
