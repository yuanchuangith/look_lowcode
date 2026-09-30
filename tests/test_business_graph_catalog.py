from __future__ import annotations

import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gxp_core.business_graph_catalog import lookup
from gxp_core.business_graph_model import normalize_v3
from gxp_core.business_graph_store import BusinessGraphStore


class BusinessGraphCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = SimpleNamespace(snapshot_dir=str(self.root), policy_scope_id="catalog-test", ttl_seconds=86400)
        self.patch = patch("gxp_core.business_graph_catalog.load_schema_config", return_value=self.config)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def call(self, node):
        result = lookup(node, "catalog-test", "development", deadline=time.monotonic() + 2)
        if "observation" in result:
            normalize_v3(result["observation"], "catalog-test")
        return result

    def test_schema_identity_exact_snapshot_without_business_rows(self):
        self.write("manifest.json", {"policy": {"scope_id": "catalog-test"}, "database": "VerifiedSchema",
                                    "completed_at": datetime.now(timezone.utc).isoformat(), "schema_fingerprint": "a" * 64})
        self.write("indexes/tables.json", [{"table_name": "Orders", "table_type": "BASE TABLE", "file": "tables/orders.json"}])
        self.write("tables/orders.json", {"columns": [{"column_name": "id"}, {"column_name": "status"}]})
        node = {"kind": "table", "key": {"datasource": "catalog-test", "schema": "VerifiedSchema", "name": "Orders"}, "label": "Orders"}
        with patch("gxp_core.service.ReadOnlyDatabase", side_effect=AssertionError("No business database")):
            result = self.call(node)
        self.assertEqual(len(result["observation"]["entities"]), 3)
        store = BusinessGraphStore(self.root / "graph.sqlite3", scope_id="catalog-test")
        store.upsert(result["observation"])
        self.assertEqual(store.get_graph()["nodes"], [])
        node["key"]["schema"] = "OtherSchema"
        self.assertEqual(self.call(node)["reason"], "identity_unresolved")

    def test_field_lookups_preserve_catalog_relations_and_version_invalidation(self):
        manifest = {"policy": {"scope_id": "catalog-test"}, "database": "VerifiedSchema",
                    "completed_at": datetime.now(timezone.utc).isoformat(), "schema_fingerprint": "a" * 64}
        self.write("manifest.json", manifest)
        self.write("indexes/tables.json", [{"table_name": "Orders", "table_type": "BASE TABLE", "file": "tables/orders.json"}])
        self.write("tables/orders.json", {"columns": [{"column_name": "id"}, {"column_name": "status"}]})
        table = {"kind": "table", "key": {"datasource": "catalog-test", "schema": "VerifiedSchema", "name": "Orders"}}
        fields = [{"kind": "field", "key": {"datasource": "catalog-test", "schema": "VerifiedSchema",
                   "owner_kind": "table", "owner": "Orders", "column": column}} for column in ("id", "status")]
        store = BusinessGraphStore(self.root / "graph.sqlite3", scope_id="catalog-test")
        store.upsert(self.call(table)["observation"])
        original = {edge["id"] for edge in store.get_graph(include_catalog=True)["edges"]}
        self.assertEqual(len(original), 2)
        for field in fields:
            with self.subTest(column=field["key"]["column"]):
                result = self.call(field)
                store.upsert(result["observation"])
                self.assertEqual({edge["id"] for edge in store.get_graph(include_catalog=True)["edges"]}, original)
                self.assertTrue(store.upsert(result["observation"])["idempotent"])
        manifest["schema_fingerprint"] = "b" * 64
        self.write("manifest.json", manifest)
        self.write("tables/orders.json", {"columns": [{"column_name": "id"}]})
        store.upsert(self.call(fields[0])["observation"])
        refreshed = store.get_graph(include_catalog=True)
        self.assertEqual(len(refreshed["edges"]), 1)
        labels = {node["id"]: node["label"] for node in refreshed["nodes"]}
        self.assertEqual(labels[refreshed["edges"][0]["target"]], "id")

    def test_report_lookups_preserve_sibling_relations(self):
        self.write("pages/example/page-meta.json", {"id": "page-1", "name": "Sanitized report"})
        self.write("pages/example/components.json", {"componentList": [{"id": "table-1", "componentType": "FormTables"},
                                                                        {"id": "table-2", "componentType": "FormTables"}]})
        store = BusinessGraphStore(self.root / "graph.sqlite3", scope_id="catalog-test")
        with patch("gxp_core.cpm_config.load_cpm_config", return_value=self.config), patch("gxp_core.cpm_runner._is_fresh", return_value=True), patch(
            "gxp_core.cpm_runner._read_status", return_value={"full": {"last_completed_at": "snapshot-1"}}):
            store.upsert(self.call({"kind": "page", "key": {"platform_id": "page-1"}})["observation"])
            original = {edge["id"] for edge in store.get_graph(include_catalog=True)["edges"]}
            self.assertEqual(len(original), 2)
            for component_id in ("table-1", "table-2"):
                with self.subTest(component_id=component_id):
                    result = self.call({"kind": "report", "key": {"page_id": "page-1", "component_id": component_id}})
                    store.upsert(result["observation"])
                    self.assertEqual({edge["id"] for edge in store.get_graph(include_catalog=True)["edges"]}, original)
                    self.assertTrue(store.upsert(result["observation"])["idempotent"])

    def test_exact_report_lookup_after_component_limit(self):
        self.write("pages/example/page-meta.json", {"id": "page-1", "name": "Sanitized report"})
        components = [{"id": f"table-{index}", "componentType": "FormTables"} for index in range(21)]
        self.write("pages/example/components.json", {"componentList": components})
        with patch("gxp_core.cpm_config.load_cpm_config", return_value=self.config), patch("gxp_core.cpm_runner._is_fresh", return_value=True), patch(
            "gxp_core.cpm_runner._read_status", return_value={"full": {"last_completed_at": "snapshot-1"}}):
            result = self.call({"kind": "report", "key": {"page_id": "page-1", "component_id": "table-20"}})
            self.assertIn("observation", result)
            self.assertEqual(len(result["observation"]["entities"]), 2)
            self.assertEqual(result["observation"]["entities"][1]["key"]["component_id"], "table-20")
            page = self.call({"kind": "page", "key": {"platform_id": "page-1"}})
            self.assertEqual(len(page["observation"]["facts"]), 20)
            missing = self.call({"kind": "report", "key": {"page_id": "page-1", "component_id": "missing"}})
            self.assertEqual(missing["reason"], "identity_unresolved")
            self.write("pages/example/components.json", {"componentList": components + [components[-1]]})
            ambiguous = self.call({"kind": "report", "key": {"page_id": "page-1", "component_id": "table-20"}})
            self.assertEqual(ambiguous["reason"], "identity_unresolved")

    def test_stale_schema_is_deferred_without_refresh(self):
        self.write("manifest.json", {"policy": {"scope_id": "catalog-test"}, "completed_at": "2000-01-01T00:00:00Z"})
        with patch("gxp_core.schema_snapshot.refresh_schema_snapshot", side_effect=AssertionError("No refresh")):
            result = self.call({"kind": "table", "key": {"datasource": "catalog-test", "schema": "VerifiedSchema", "name": "Orders"}})
        self.assertEqual(result["reason"], "catalog_missing_or_stale")

    def test_field_expansion_is_one_hop_and_fk_identity_is_not_guessed(self):
        self.write("manifest.json", {"policy": {"scope_id": "catalog-test"}, "database": "VerifiedSchema",
                                    "completed_at": datetime.now(timezone.utc).isoformat(), "schema_fingerprint": "a" * 64})
        self.write("indexes/tables.json", [{"table_name": "Orders", "table_type": "BASE TABLE", "file": "tables/orders.json"}])
        self.write("tables/orders.json", {"columns": [{"column_name": "id"}, {"column_name": "status"}],
                                        "foreign_keys": [{"columns": ["id"], "referenced_table_name": "Users", "referenced_columns": ["id"]}]})
        node = {"kind": "field", "key": {"datasource": "catalog-test", "schema": "VerifiedSchema", "owner_kind": "table", "owner": "Orders", "column": "id"}}
        result = self.call(node)
        normalized = normalize_v3(result["observation"], "catalog-test")
        self.assertEqual(len(normalized["entities"]), 2)
        self.assertEqual(len(normalized["unresolved"]), 2)
        self.assertTrue(all(item["kind"] == "contains" for item in normalized["facts"]))

    def test_cpm_real_component_list_contract(self):
        self.write("pages/example/page-meta.json", {"id": "page-1", "name": "Sanitized report"})
        self.write("pages/example/components.json", {"componentList": [{"id": "table-1", "title": "Report", "componentType": "FormTables"}]})
        with patch("gxp_core.cpm_config.load_cpm_config", return_value=self.config), patch("gxp_core.cpm_runner._is_fresh", return_value=True), patch(
            "gxp_core.cpm_runner._read_status", return_value={"full": {"last_completed_at": "snapshot-1"}}):
            result = self.call({"kind": "page", "key": {"platform_id": "page-1"}})
        self.assertEqual(result["observation"]["entities"][1]["key"], {"page_id": "page-1", "component_id": "table-1"})
        self.assertEqual(result["observation"]["facts"][0]["kind"], "contains")

    def test_source_unique_static_calls_only(self):
        self.write("backend/symbols.json", [{"symbol_id": "caller", "name": "Caller"}, {"symbol_id": "callee", "name": "Callee"}])
        self.write("backend/routes.json", [{"route": "/reports", "method": "GET", "symbol_id": "caller"}])
        self.write("graph/backend-call-edges.json", [{"caller_id": "caller", "target_ids": ["callee"], "category": "business", "confidence": "structural"},
                                                   {"caller_id": "caller", "target_ids": ["unknown", "callee"], "category": "business", "confidence": "structural"}])
        status = {"repositories": {"backend": {"stale": False, "parse_incomplete": False, "index": {"fingerprint": "source-v1"}}}, "errors": []}
        with patch("gxp_core.source_config.source_index_root", return_value=self.root), patch("gxp_core.source_index.source_index_status", return_value=status):
            result = self.call({"kind": "api", "key": {"repository": "backend", "route": "/reports", "method": "GET"}, "label": "Reports API"})
        self.assertEqual(len(result["observation"]["facts"]), 1)
        self.assertNotIn("data_binding", result["observation"]["facts"][0])
        self.assertIn("execution_condition_unresolved", result["observation"]["facts"][0]["condition"]["branch_keys"])

    def test_report_expansion_does_not_add_sibling_components(self):
        self.write("pages/example/page-meta.json", {"id": "page-1", "name": "Sanitized report"})
        self.write("pages/example/components.json", {"componentList": [{"id": "table-1", "componentType": "FormTables"},
                                                                        {"id": "table-2", "componentType": "FormTables"}]})
        with patch("gxp_core.cpm_config.load_cpm_config", return_value=self.config), patch("gxp_core.cpm_runner._is_fresh", return_value=True), patch(
            "gxp_core.cpm_runner._read_status", return_value={"full": {"last_completed_at": "snapshot-1"}}):
            result = self.call({"kind": "report", "key": {"page_id": "page-1", "component_id": "table-1"}})
        self.assertEqual(len(result["observation"]["entities"]), 2)


if __name__ == "__main__":
    unittest.main()
