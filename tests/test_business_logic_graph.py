from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from gxp_core.business_logic_graph import (
    BusinessLogicGraphError,
    BusinessLogicGraphStore,
    GraphValidationError,
    validate_relation,
    MAX_RELATION_BYTES,
)
from gxp_core.relation_policy import _PolicyFileLock
from gxp_core.service import GxpReadonlyService


ROOT = Path(__file__).resolve().parent


class BusinessLogicGraphTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "business-logic-graph.json"
        self.store = BusinessLogicGraphStore(self.path)
        self.fixture = json.loads(
            (ROOT / "fixtures" / "business_logic_graph_training.json").read_text(encoding="utf-8")
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_first_upsert_is_atomic_and_idempotent(self) -> None:
        first = self.store.upsert(self.fixture)
        second = self.store.upsert(self.fixture)
        self.assertTrue(first["written"])
        self.assertTrue(second["idempotent"])
        self.assertEqual(1, len(self.store.read()["relations"]))
        self.assertTrue(self.path.is_file())
        self.assertTrue(self.path.with_name(self.path.name + ".lock").is_file())

    def test_evidence_change_supersedes_the_previous_confirmed_version(self) -> None:
        first = self.store.upsert(self.fixture)["relation"]
        changed = copy.deepcopy(self.fixture)
        changed["evidence"][2]["fingerprint"] = hashlib.sha256(b"training-schema-evidence-2").hexdigest()
        changed["evidence"][2]["summary"] = "新的只读 Schema 证据"
        result = self.store.upsert(changed)
        self.assertTrue(result["written"])
        records = self.store.read()["relations"]
        self.assertEqual(2, len(records))
        self.assertEqual("superseded", records[0]["lifecycle"])
        self.assertEqual(first["relation_id"], records[1]["relation_id"])
        self.assertEqual(2, records[1]["revision"])

    def test_unconfirmed_sensitive_and_complete_code_payloads_are_rejected(self) -> None:
        candidate = copy.deepcopy(self.fixture)
        candidate["status"] = "candidate"
        with self.assertRaises(GraphValidationError):
            validate_relation(candidate)
        secret = copy.deepcopy(self.fixture)
        secret["password"] = "should never persist"
        with self.assertRaises(GraphValidationError):
            validate_relation(secret)
        code = copy.deepcopy(self.fixture)
        code["conclusion"] = "public static void Execute() { return; }"
        with self.assertRaises(GraphValidationError):
            validate_relation(code)
        huge = copy.deepcopy(self.fixture)
        huge["evidence"][0]["summary"] = "x" * 2_000
        huge["conclusion"] = "x" * 1_001
        with self.assertRaises(GraphValidationError):
            validate_relation(huge)

    def test_mermaid_escapes_user_labels_and_search_requires_reverification(self) -> None:
        result = self.store.upsert(self.fixture)
        mermaid = result["relation"]["mermaid"]
        self.assertIn("#47;", mermaid)
        self.assertNotIn("/", mermaid)
        found = self.store.search(field="close_date")
        self.assertTrue(found["must_reverify_current_published_copy"])
        self.assertEqual(1, found["count"])

    def test_current_design_change_stales_active_relation_without_deleting_audit(self) -> None:
        relation = self.store.upsert(self.fixture)["relation"]
        found = self.store.search(
            relation_id=relation["relation_id"],
            current_published_designs={"training-ref-1": "new-published-design"},
        )
        self.assertEqual(0, found["count"])
        document = self.store.read()
        self.assertEqual("stale", document["relations"][0]["lifecycle"])
        self.assertTrue(document["audit"])

    def test_corrupt_cache_is_a_store_error_but_does_not_look_like_a_relation(self) -> None:
        self.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(BusinessLogicGraphError):
            self.store.search()

    def test_legacy_migration_imports_confirmed_only(self) -> None:
        self.path.write_text(
            json.dumps({"version": 1, "relations": [self.fixture, {**self.fixture, "status": "candidate"}]}),
            encoding="utf-8",
        )
        result = self.store.read()
        self.assertEqual(1, result["migration"]["imported"])
        self.assertEqual(1, result["migration"]["skipped"])
        self.assertEqual(1, len(result["relations"]))

    def test_legacy_script_metadata_and_summary_are_normalized(self):
        legacy_record = dict(self.fixture, schema_version=1,
                             relation_id="old-script-fingerprint", updated_at="2026-09-26T00:00:00+00:00",
                             previous_revision="2026-09-25T00:00:00+00:00",
                             reusable_when=["Same published design"], invalid_when=["Design changes"])
        legacy_record["summary"] = legacy_record.pop("conclusion")
        legacy_record.pop("relation_key")
        legacy_record.pop("business_keywords")
        original = json.dumps({"schema_version": 1, "relations": [legacy_record]}).encode()
        self.path.write_bytes(original)
        result = self.store.search()
        self.assertEqual(1, result["migration"]["imported"])
        self.assertEqual(0, result["migration"]["rejected"])
        self.assertEqual(self.fixture["conclusion"], result["relations"][0]["conclusion"])
        self.assertEqual("legacy-old-script-fingerprint", result["relations"][0]["relation_key"])
        self.assertEqual(original, self.store.legacy_path.read_bytes())
        before = self.path.read_bytes()
        self.assertEqual(result["migration"], self.store.search()["migration"])
        self.assertEqual(before, self.path.read_bytes())

    def test_real_legacy_shape_is_archived_without_inventing_evidence(self):
        original = (ROOT / "fixtures" / "business_logic_graph_legacy_training.json").read_bytes()
        self.path.write_bytes(original)
        result = self.store.search()
        self.assertTrue(result["available"])
        self.assertEqual(0, result["count"])
        self.assertEqual(1, result["migration"]["rejected"])
        self.assertTrue(result["legacy_review_required"])
        self.assertEqual(self.store.legacy_path.name, result["migration"]["legacy_archive"])
        self.assertEqual(original, self.store.legacy_path.read_bytes())
        self.store.upsert(self.fixture)
        self.assertEqual(1, self.store.search()["count"])
        self.assertEqual(original, self.store.legacy_path.read_bytes())

    def test_interrupted_migration_recovers_from_original_archive(self):
        original = json.dumps({"schema_version": 1, "relations": [self.fixture]}).encode()
        self.store.legacy_path.write_bytes(original)
        result = self.store.search()
        self.assertEqual(1, result["count"])
        self.assertEqual(original, self.store.legacy_path.read_bytes())
        self.assertTrue(self.path.is_file())

    def test_migration_never_overwrites_a_different_legacy_archive(self):
        original = json.dumps({"version": 1, "relations": [self.fixture]}).encode()
        self.path.write_bytes(original)
        self.store.legacy_path.write_bytes(b"different original archive")
        with self.assertRaisesRegex(BusinessLogicGraphError, "GRAPH_MIGRATION_ARCHIVE_CONFLICT"):
            self.store.read()
        self.assertEqual(original, self.path.read_bytes())
        self.assertEqual(b"different original archive", self.store.legacy_path.read_bytes())

    def test_archive_failure_preserves_original_and_degrades_without_leaking_errors(self):
        original = json.dumps({"version": 1, "relations": [self.fixture]}).encode()
        self.path.write_bytes(original)
        with patch("pathlib.Path.rename", side_effect=PermissionError("PRIVATE_IO_MESSAGE")):
            with patch("gxp_core.service.BusinessLogicGraphStore", return_value=self.store):
                result = GxpReadonlyService.search_business_logic_graph()
        self.assertFalse(result["available"])
        self.assertEqual("GRAPH_IO_ERROR", result["cache_error"])
        self.assertNotIn("PRIVATE_IO_MESSAGE", json.dumps(result))
        self.assertEqual(original, self.path.read_bytes())
        self.assertFalse(self.store.legacy_path.exists())

    def test_unknown_legacy_schema_version_is_not_overwritten(self):
        original = json.dumps({"schema_version": 99, "relations": [self.fixture]}).encode()
        self.path.write_bytes(original)
        with self.assertRaisesRegex(BusinessLogicGraphError, "GRAPH_UNSUPPORTED_VERSION"):
            self.store.read()
        self.assertEqual(original, self.path.read_bytes())
        self.assertFalse(self.store.legacy_path.exists())

    def test_legacy_conversion_does_not_bypass_sensitive_or_evidence_gates(self):
        records = [dict(self.fixture, schema_version=1, password="PRIVATE_FIXTURE_VALUE"),
                   dict(self.fixture, schema_version=1, evidence=[]),
                   dict(self.fixture, schema_version=99),
                   dict(self.fixture, schema_version=1, summary="Different conclusion")]
        self.path.write_text(json.dumps({"schema_version": 1, "relations": records}), encoding="utf-8")
        result = self.store.search()
        self.assertEqual(4, result["migration"]["rejected"])
        self.assertEqual(0, result["count"])
        self.assertNotIn("PRIVATE_FIXTURE_VALUE", self.path.read_text(encoding="utf-8"))

    def test_atomic_replace_failure_keeps_previous_file_and_cleans_temporary(self):
        self.store.upsert(self.fixture)
        before = self.path.read_bytes()
        changed = copy.deepcopy(self.fixture)
        changed["conclusion"] = "Updated confirmed conclusion"
        with patch("gxp_core.cpm_config.os.replace", side_effect=OSError("fixture failure")):
            with self.assertRaisesRegex(BusinessLogicGraphError, "GRAPH_IO_ERROR"):
                self.store.upsert(changed)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual([], list(self.path.parent.glob("*.tmp")))

    def test_lock_timeout_is_bounded_and_service_degrades_without_database(self):
        store = BusinessLogicGraphStore(self.path, lock_timeout_seconds=0.02)
        with _PolicyFileLock(store.lock_path):
            with self.assertRaisesRegex(BusinessLogicGraphError, "GRAPH_LOCK_TIMEOUT"):
                store.search()
            with patch("gxp_core.service.BusinessLogicGraphStore", return_value=store):
                result = GxpReadonlyService.search_business_logic_graph()
                self.assertFalse(result["available"])
                self.assertEqual("GRAPH_LOCK_TIMEOUT", result["cache_error"])
                self.assertIn("Continue", result["next_step"])

    def test_concurrent_writers_do_not_lose_records_or_duplicate_revisions(self):
        payloads = [dict(self.fixture, relation_key=f"case-{i}") for i in range(6)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(self.store.upsert, payloads + payloads))
        document = self.store.read()
        self.assertEqual(6, len(document["relations"]))
        self.assertEqual(6, len(document["audit"]))
        self.assertTrue(all(r["revision"] == 1 for r in document["relations"]))

    def test_invalidation_retains_audit_and_is_idempotent(self):
        relation = self.store.upsert(self.fixture)["relation"]
        result = self.store.invalidate(relation["relation_id"], reason="user_confirmed_incorrect")
        self.assertEqual(1, result["changed"])
        before = self.path.read_bytes()
        self.assertEqual(0, self.store.invalidate(relation["relation_id"], reason="user_confirmed_incorrect")["changed"])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(0, self.store.search()["count"])
        self.assertEqual(1, self.store.search(status="invalidated")["count"])
        self.assertEqual(["upsert", "invalidated"], [a["action"] for a in self.store.read()["audit"]])

    def test_all_filters_and_environment_isolation(self):
        self.store.upsert(self.fixture)
        self.store.upsert(dict(self.fixture, environment="production"))
        for filters in ({"query": "关闭 结束日期"}, {"action": "training.close"},
                        {"action": "training-ref-1"}, {"page": "TrainingPage"},
                        {"table": "training_task"}, {"table": "training_statistics"},
                        {"field": "close_date"}, {"status": "confirmed_data"}):
            with self.subTest(filters=filters):
                result = self.store.search(**filters)
                self.assertEqual(1, result["count"])
                self.assertEqual("development", result["relations"][0]["environment"])
        self.assertEqual(0, self.store.search(field="missing")["count"])
        self.assertEqual(1, self.store.search(environment="production")["count"])

    def test_publication_change_stales_other_conclusions_in_same_environment(self):
        self.store.upsert(self.fixture)
        self.store.upsert(dict(self.fixture, environment="production"))
        changed = copy.deepcopy(self.fixture)
        changed["relation_key"] = "other-conclusion"
        changed["published_design_id"] = "design-v2"
        changed["anchors"][0]["published_design_id"] = "design-v2"
        self.store.upsert(changed)
        self.assertEqual(1, self.store.search()["count"])
        self.assertEqual(1, self.store.search(status="stale")["count"])
        self.assertEqual(1, self.store.search(environment="production")["count"])

    def test_current_evidence_change_is_scoped_and_persistent(self):
        first = self.store.upsert(self.fixture)["relation"]
        self.store.upsert(dict(self.fixture, relation_key="another"))
        result = self.store.search(relation_id=first["relation_id"],
                                  current_evidence_fingerprints={"schema": "b" * 64})
        self.assertEqual(0, result["count"])
        self.assertEqual(1, self.store.search()["count"])
        self.assertEqual(1, self.store.search(status="stale")["count"])
        with self.assertRaises(GraphValidationError):
            self.store.search(current_evidence_fingerprints={"schema": "b" * 64})

    def test_runtime_claim_requires_runtime_and_data_evidence(self):
        claim = copy.deepcopy(self.fixture)
        claim["status"] = "runtime_verified"
        with self.assertRaisesRegex(GraphValidationError, "INSUFFICIENT_EVIDENCE"):
            self.store.upsert(claim)
        claim["evidence"].append({"id": "runtime", "type": "runtime", "fingerprint": "d" * 64,
                                  "summary": "Observed current path", "anchor_ids": ["training-close-action"]})
        self.assertTrue(self.store.upsert(claim)["written"])
        claim["status"] = "confirmed_static"
        self.assertTrue(validate_relation(claim))

    def test_incomplete_anchors_and_dangling_graph_are_rejected(self):
        for target, value in (("canvas_row", 0), ("canvas_row", True), ("ref_id", ""),
                              ("published_design_id", "wrong")):
            changed = copy.deepcopy(self.fixture)
            changed["anchors"][0][target] = value
            with self.subTest(target=target, value=value), self.assertRaises(GraphValidationError):
                self.store.upsert(changed)
        for key in ("source", "target", "evidence_ids"):
            changed = copy.deepcopy(self.fixture)
            changed["edges"][0][key] = ["missing"] if key == "evidence_ids" else "missing"
            with self.subTest(key=key), self.assertRaises(GraphValidationError):
                self.store.upsert(changed)

    def test_sensitive_nested_values_and_unknown_fields_never_reach_disk(self):
        for target in ("password", "token", "connection_string", "business_records", "paramsValue", "generated_csharp"):
            changed = copy.deepcopy(self.fixture)
            changed["nodes"][0][target] = "PRIVATE_FIXTURE_VALUE"
            with self.subTest(target=target), self.assertRaises(GraphValidationError) as raised:
                self.store.upsert(changed)
            self.assertNotIn("PRIVATE_FIXTURE_VALUE", str(raised.exception))
        for value in ("password=PRIVATE_FIXTURE_VALUE", "Bearer PRIVATE_FIXTURE_VALUE",
                      "mysql://PRIVATE_FIXTURE_VALUE", "public class Test { }",
                      '{"paramsValue": "PRIVATE_FIXTURE_VALUE"}'):
            changed = copy.deepcopy(self.fixture)
            changed["evidence"][0]["summary"] = value
            with self.subTest(value=value), self.assertRaises(GraphValidationError):
                self.store.upsert(changed)
        self.assertFalse(self.path.exists())

    def test_fingerprints_are_validated_and_generated_id_is_stable(self):
        first = validate_relation(self.fixture)
        changed = copy.deepcopy(self.fixture)
        changed["nodes"].reverse()
        changed["edges"].reverse()
        changed["evidence"].reverse()
        changed["business_keywords"].reverse()
        second = validate_relation(changed)
        self.assertEqual(first, second)
        for key in ("relation_id", "evidence_fingerprint"):
            with self.subTest(key=key), self.assertRaises(GraphValidationError):
                validate_relation(dict(self.fixture, **{key: "a" * 64}))
        changed["evidence"][0]["fingerprint"] = "not-a-sha256"
        with self.assertRaises(GraphValidationError):
            validate_relation(changed)

    def test_payload_and_store_size_limits_preserve_existing_file(self):
        self.store.upsert(self.fixture)
        before = self.path.read_bytes()
        with self.assertRaisesRegex(GraphValidationError, "PAYLOAD_TOO_LARGE"):
            self.store.upsert(dict(self.fixture, conclusion="x" * MAX_RELATION_BYTES))
        with patch("gxp_core.business_logic_graph.MAX_GRAPH_BYTES", len(before) + 10):
            with self.assertRaisesRegex(BusinessLogicGraphError, "GRAPH_TOO_LARGE"):
                self.store.upsert(dict(self.fixture, relation_key="second"))
        self.assertEqual(before, self.path.read_bytes())

    def test_mermaid_escapes_nodes_edges_and_never_uses_external_ids(self):
        changed = copy.deepcopy(self.fixture)
        label = 'A"] --> injected["<b>|#quoted'
        changed["nodes"][0]["label"] = label
        changed["edges"][0]["label"] = label
        diagram = validate_relation(changed)["mermaid"]
        self.assertNotIn(label, diagram)
        self.assertIn("#34;#93;", diagram)
        self.assertIn("#60;b#62;#124;#35;", diagram)
        self.assertEqual(1 + len(changed["nodes"]) + len(changed["edges"]), len(diagram.splitlines()))

    def test_migration_failure_preserves_legacy_and_returns_degraded_response(self):
        legacy = json.dumps({"version": 1, "records": [self.fixture]}).encode()
        self.path.write_bytes(legacy)
        with patch("gxp_core.cpm_config.os.replace", side_effect=OSError("PRIVATE_IO_MESSAGE")):
            with patch("gxp_core.service.BusinessLogicGraphStore", return_value=self.store):
                response = GxpReadonlyService.search_business_logic_graph()
                self.assertFalse(response["available"])
                self.assertNotIn("PRIVATE_IO_MESSAGE", json.dumps(response))
        self.assertEqual(legacy, self.path.read_bytes())
        self.assertEqual(1, self.store.search()["migration"]["imported"])

    def test_migration_rejects_sensitive_and_insufficient_confirmed_records(self):
        unsafe = dict(self.fixture, password="PRIVATE_FIXTURE_VALUE")
        insufficient = dict(self.fixture, evidence=[])
        self.path.write_text(json.dumps([self.fixture, self.fixture, unsafe, insufficient, {"status": "candidate"}]), encoding="utf-8")
        result = self.store.search()
        self.assertEqual({"attempted": True, "imported": 1, "skipped": 1, "rejected": 2,
                          "legacy_archive": self.store.legacy_path.name}, result["migration"])
        self.assertNotIn("PRIVATE_FIXTURE_VALUE", self.path.read_text(encoding="utf-8"))
        before = self.path.read_bytes()
        self.store.search()
        self.assertEqual(before, self.path.read_bytes())

    def test_corruption_and_unknown_versions_are_not_overwritten(self):
        for content in ('{"version": 999}', '{"version": 2, "relations": []}', '["invalid legacy"]'):
            self.path.write_text(content, encoding="utf-8")
            if content.startswith("["):
                self.assertEqual(1, self.store.search()["migration"]["skipped"])
                continue
            with self.subTest(content=content), self.assertRaises(BusinessLogicGraphError):
                self.store.upsert(self.fixture)
            self.assertEqual(content, self.path.read_text(encoding="utf-8"))

    def test_tampered_record_is_detected_on_read(self):
        self.store.upsert(self.fixture)
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        doc["relations"][0]["evidence"][0]["summary"] = "Tampered evidence"
        self.path.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaisesRegex(BusinessLogicGraphError, "GRAPH_CORRUPT"):
            self.store.search()

    def test_search_results_are_bounded_without_truncating_evidence_chains(self):
        for i in range(4):
            self.store.upsert(dict(self.fixture, relation_key=f"bounded-{i}"))
        found = self.store.search(limit=2)
        self.assertEqual(4, found["matched_count"])
        self.assertEqual(2, found["count"])
        self.assertTrue(found["truncated"])
        self.assertEqual(5, len(found["relations"][0]["nodes"]))
        with patch("gxp_core.business_logic_graph.MAX_RESPONSE_BYTES", 12000):
            found = self.store.search()
            self.assertLessEqual(len(json.dumps(found, ensure_ascii=False, indent=2).encode()), 12000)
            self.assertTrue(found["truncated"])


if __name__ == "__main__":
    unittest.main()
