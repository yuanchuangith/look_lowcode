from __future__ import annotations

import copy
import hashlib
import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gxp_core.canvas import CanvasInspector
from gxp_core.handoff_store import (
    HandoffError, HandoffStore, canonical_sha256, compare_targets,
    environment_scope, snapshot_targets, validate_change_spec,
)
from gxp_core.service import GxpReadonlyService
from gxp_core.telemetry import traced_tool


def design(value="old", parent="parent", *, design_id="draft", version="draft"):
    data = {"actionData": [{"key": "main", "data": [
        {"key": "parent", "elementKey": "IfCondition", "paramsValue": {"inputParams": {"condition": "true"}}},
        {"key": "node", "title": "Target", "elementKey": "SetVariableValue", "depth": [parent], "paramsValue": {"inputParams": {"value": {"code": value}}}},
    ]}]}
    raw = json.dumps(data, ensure_ascii=False)
    return {"design_id": design_id, "version": version, "is_deleted": False, "data": raw, "data_json": data,
            "data_sha256": hashlib.sha256(raw.encode()).hexdigest(), "csharp_code": "do not export generated source"}


TARGETS = [{"group_key": "main", "node_key": "node"}]
SPEC = {"user_request": "Fix target and preserve old eval expression", "summary": "Update target value", "changes": [{"group_key": "main", "node_key": "node", "description": "Replace value", "parameter_path": "/inputParams/value", "before": {"code": "old"}, "after": {"code": "new"}}], "preserve": ["eval(requestResult.Data)"], "scenarios": [{"name": "empty", "expected": "Skip"}]}


def diagnosed_spec():
    spec = copy.deepcopy(SPEC)
    confirmed = {
        "issue_id": "wrong-value", "status": "confirmed", "symptom": "Target receives the old value",
        "expected": "Target receives the new value", "root_cause": "The target expression still contains old",
        "solution": "Replace the target value and preserve the surrounding condition",
        "evidence": [{"source": "inspect_action", "finding": "Target expression contains old", "group_key": "main", "node_key": "node", "design_id": "published"}],
        "verification": "static_confirmed",
    }
    candidate = copy.deepcopy(confirmed)
    candidate.update(issue_id="runtime-behavior", status="candidate", root_cause="Runtime effect still needs verification", verification="pending")
    candidate["evidence"] = [{"source": "inspect_control_flow", "finding": "The target is guarded by the existing condition"}]
    spec["diagnosis"] = {
        "issues": [confirmed, candidate], "excluded": ["The selected node identity is unambiguous"],
        "unresolved": ["Run the expected scenario after publication"],
    }
    return spec


def evidence_only_spec(*, include_changes=False):
    spec = diagnosed_spec()
    spec["summary"] = "Preserve observed target behavior for later analysis"
    for issue in spec["diagnosis"]["issues"]:
        for key in ("expected", "root_cause", "solution"):
            issue.pop(key)
    if include_changes:
        spec["changes"] = []
    else:
        spec.pop("changes")
    return spec


def make_record():
    draft = design()
    targets = snapshot_targets(draft["data_json"], TARGETS)
    return {"environment_scope": environment_scope({"host": "localhost", "port": 3306, "database": "test"}),
            "action": {"ref_id": "ref", "action_code": "code", "action_name": "Title", "action_type": "form", "page_id": "page"},
            "draft": {"design_id": "draft", "data_sha256": draft["data_sha256"]},
            "diagnosis_source": {"version": "draft", "design_id": "draft", "data_sha256": draft["data_sha256"]},
            "targets": targets, "diagnosis_targets": copy.deepcopy(targets), "source_target_differences": [], "change_spec": copy.deepcopy(SPEC)}


class HandoffStoreTests(unittest.TestCase):
    def test_cross_package_protocol_is_byte_identical(self):
        readonly = Path(__file__).resolve().parents[1] / "mcp/gxp_core/handoff_store.py"
        editor = readonly.parents[3] / "write/mcp/gxp_editor/handoff_store.py"
        if editor.exists():
            self.assertEqual(readonly.read_bytes(), editor.read_bytes())

    def test_atomic_round_trip_and_explicit_candidate_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            store = HandoffStore(Path(directory))
            first = store.write(make_record())
            second = store.write(make_record())
            self.assertNotEqual(first["handoff_id"], second["handoff_id"])
            self.assertEqual(SPEC, store.read(**first["handoff_ref"])["change_spec"])
            self.assertEqual(2, len(store.list("code")))
            self.assertFalse(list(Path(directory).glob("*.tmp")))
            with self.assertRaises(HandoffError):
                store.read(first["handoff_id"], "0" * 64)

    def test_legacy_record_without_diagnosis_or_changes_remains_readable(self):
        record = make_record()
        record["change_spec"] = {"user_request": "Original request", "summary": "Legacy proposal"}
        with tempfile.TemporaryDirectory() as directory:
            store = HandoffStore(Path(directory))
            saved = store.write(record)
            restored = store.read(**saved["handoff_ref"])
        self.assertEqual(1, restored["schema_version"])
        self.assertEqual(record["change_spec"], restored["change_spec"])

    def test_diagnosis_requires_evidence_fields_valid_enums_and_precise_evidence(self):
        mutations = []
        for field in ("issue_id", "status", "symptom", "evidence", "verification"):
            mutations.append(("missing-" + field, lambda spec, field=field: spec["diagnosis"]["issues"][0].pop(field)))
        for field in ("expected", "root_cause", "solution"):
            mutations.append(("empty-" + field, lambda spec, field=field: spec["diagnosis"]["issues"][0].update({field: " "})))
            mutations.append(("invalid-" + field, lambda spec, field=field: spec["diagnosis"]["issues"][0].update({field: None})))
        mutations.extend([
            ("status", lambda spec: spec["diagnosis"]["issues"][0].update(status="verified")),
            ("verification", lambda spec: spec["diagnosis"]["issues"][0].update(verification="checksum_verified")),
            ("empty-evidence", lambda spec: spec["diagnosis"]["issues"][0].update(evidence=[])),
            ("missing-source", lambda spec: spec["diagnosis"]["issues"][0]["evidence"][0].pop("source")),
            ("missing-finding", lambda spec: spec["diagnosis"]["issues"][0]["evidence"][0].pop("finding")),
            ("unpaired-group", lambda spec: spec["diagnosis"]["issues"][0]["evidence"][0].pop("node_key")),
            ("unpaired-node", lambda spec: spec["diagnosis"]["issues"][0]["evidence"][0].pop("group_key")),
            ("empty-design", lambda spec: spec["diagnosis"]["issues"][0]["evidence"][0].update(design_id="")),
            ("unknown-field", lambda spec: spec["diagnosis"].update(unknown="unsupported")),
            ("unknown-issue-field", lambda spec: spec["diagnosis"]["issues"][0].update(unknown="unsupported")),
            ("empty-excluded", lambda spec: spec["diagnosis"].update(excluded=[""])),
            ("invalid-unresolved", lambda spec: spec["diagnosis"].update(unresolved=[{}])),
        ])
        for name, mutate in mutations:
            with self.subTest(name=name):
                spec = diagnosed_spec()
                mutate(spec)
                with self.assertRaises(HandoffError) as exc:
                    validate_change_spec(spec)
                self.assertEqual("HANDOFF_CHANGE_SPEC", exc.exception.code)

    def test_diagnosis_limits_private_data_and_supplied_changes(self):
        for name, mutate, code in [
            ("no-issues", lambda spec: spec["diagnosis"].update(issues=[]), "HANDOFF_CHANGE_SPEC"),
            ("too-many-issues", lambda spec: spec["diagnosis"].update(issues=[spec["diagnosis"]["issues"][0]] * 21), "HANDOFF_CHANGE_SPEC"),
            ("too-many-evidence", lambda spec: spec["diagnosis"]["issues"][0].update(evidence=[{"source": "tool", "finding": "observed"}] * 21), "HANDOFF_CHANGE_SPEC"),
            ("too-many-excluded", lambda spec: spec["diagnosis"].update(excluded=["excluded"] * 51), "HANDOFF_CHANGE_SPEC"),
            ("too-many-unresolved", lambda spec: spec["diagnosis"].update(unresolved=["pending"] * 51), "HANDOFF_CHANGE_SPEC"),
            ("long-id", lambda spec: spec["diagnosis"]["issues"][0].update(issue_id="x" * 201), "HANDOFF_LIMIT"),
            ("long-text", lambda spec: spec["diagnosis"]["issues"][0].update(symptom="中" * 1366), "HANDOFF_LIMIT"),
            ("private", lambda spec: spec["diagnosis"]["issues"][0]["evidence"][0].update(password="secret"), "HANDOFF_PRIVATE_DATA"),
            ("missing-group", lambda spec: spec["changes"][0].pop("group_key"), "HANDOFF_CHANGE_SPEC"),
            ("missing-node", lambda spec: spec["changes"][0].pop("node_key"), "HANDOFF_CHANGE_SPEC"),
            ("empty-description", lambda spec: spec["changes"][0].update(description=" "), "HANDOFF_CHANGE_SPEC"),
        ]:
            with self.subTest(name=name):
                spec = diagnosed_spec()
                mutate(spec)
                with self.assertRaises(HandoffError) as exc:
                    validate_change_spec(spec)
                self.assertEqual(code, exc.exception.code)
        spec = diagnosed_spec()
        spec["changes"] = [{"group_key": "main", "node_key": "node", "description": "Insert a node after this target"}]
        spec["diagnosis"]["issues"][0]["verification"] = "runtime_verified"
        self.assertEqual(spec, validate_change_spec(spec))

    def test_evidence_only_diagnosis_round_trip_without_required_solution_or_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            store = HandoffStore(Path(directory))
            for include_changes in (False, True):
                with self.subTest(include_changes=include_changes):
                    record = make_record()
                    record["change_spec"] = evidence_only_spec(include_changes=include_changes)
                    saved = store.write(record)
                    restored = store.read(**saved["handoff_ref"])
                    self.assertEqual(record["change_spec"], restored["change_spec"])

    def test_optional_diagnosis_text_still_has_a_four_kib_limit(self):
        for field in ("expected", "root_cause", "solution"):
            with self.subTest(field=field):
                spec = evidence_only_spec()
                spec["diagnosis"]["issues"][0][field] = "x" * 4097
                with self.assertRaises(HandoffError) as exc:
                    validate_change_spec(spec)
                self.assertEqual("HANDOFF_LIMIT", exc.exception.code)

    def test_environment_destination_excludes_account_and_secret(self):
        first = {"host": " LOCALHOST ", "port": "3306", "database": "test", "user": "one", "password": "first"}
        second = {**first, "host": "localhost", "port": 3306, "user": "two", "password": "second"}
        self.assertEqual(environment_scope(first), environment_scope(second))
        self.assertNotEqual(environment_scope(first), environment_scope({**second, "database": "other"}))

    def test_paths_nonfinite_private_and_oversize_records_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = HandoffStore(Path(directory))
            for identifier in ("../bad", "C:/secret.json", "A" * 32, "0" * 31):
                with self.assertRaises(HandoffError):
                    store.read(identifier)
            for value in (math.nan, math.inf):
                with self.assertRaises(HandoffError):
                    canonical_sha256({"value": value})
            record = make_record()
            record["change_spec"]["changes"][0]["after"] = {"password": "secret"}
            with self.assertRaises(HandoffError):
                store.write(record)
            record = make_record()
            record["change_spec"]["user_request"] = "x" * 9000
            with self.assertRaises(HandoffError):
                store.write(record)

    def test_corrupt_checksum_version_and_snapshot_are_explicit_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            store = HandoffStore(Path(directory))
            saved = store.write(make_record())
            path = Path(directory, saved["handoff_id"] + ".json")
            envelope = json.loads(path.read_text(encoding="utf-8"))
            for mutate in (lambda record: record.update(schema_version=2), lambda record: record["targets"][0].update(paramsValue={"changed": True})):
                changed = copy.deepcopy(envelope)
                mutate(changed["record"])
                path.write_text(json.dumps(changed), encoding="utf-8")
                with self.assertRaises(HandoffError):
                    store.read(saved["handoff_id"])
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(HandoffError) as exc:
                store.read(saved["handoff_id"])
            self.assertEqual("HANDOFF_FORMAT", exc.exception.code)

    def test_parent_parameters_structure_and_neighbors_are_guards(self):
        original = design()["data_json"]
        changed = copy.deepcopy(original)
        changed["actionData"][0]["data"][0]["paramsValue"] = {"inputParams": {"condition": "false"}}
        differences = compare_targets(snapshot_targets(original, TARGETS), snapshot_targets(changed, TARGETS))
        self.assertIn("parent_path", differences[0]["changed_fields"])
        changed["actionData"][0]["data"].insert(1, {"key": "inserted", "elementKey": "Return", "paramsValue": {}})
        differences = compare_targets(snapshot_targets(original, TARGETS), snapshot_targets(changed, TARGETS))
        self.assertIn("previous_node", differences[0]["changed_fields"])
        self.assertIn("control_flow", differences[0]["changed_fields"])

    def test_flat_if_conditions_and_group_io_are_context_guards(self):
        original = design()["data_json"]
        original["actionData"][0]["data"][1]["depth"] = []
        original["actionData"][0]["data"].append({"key": "end", "elementKey": "IfEnd", "paramsValue": {}})
        before = snapshot_targets(original, TARGETS)
        changed = copy.deepcopy(original)
        changed["actionData"][0]["data"][0]["paramsValue"] = {"inputParams": {"condition": "false"}}
        after = snapshot_targets(changed, TARGETS)
        self.assertEqual(before[0]["paramsValue"], after[0]["paramsValue"])
        self.assertEqual([], before[0]["parent_path"])
        self.assertEqual(before[0]["control_flow"]["group_structure_sha256"], after[0]["control_flow"]["group_structure_sha256"])
        self.assertIn("control_flow", compare_targets(before, after)[0]["changed_fields"])
        changed = copy.deepcopy(original)
        changed["actionData"][0]["inputParams"] = [{"name": "argument", "type": "string"}]
        self.assertIn("control_flow", compare_targets(before, snapshot_targets(changed, TARGETS))[0]["changed_fields"])


class EditHandoffServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict("os.environ", {"LOCALAPPDATA": self.directory.name})
        self.environment.start()
        self.draft, self.published = design(), design(design_id="published", version="published")
        owner = self
        class Repository:
            calls = []
            def resolve_action(self, identifier):
                return [{"ref_id": "ref", "action_code": "code", "action_name": "Title", "action_type": "form", "page_id": "page"}] if identifier in {"ref", "code"} else []
            def load_design(self, ref_id, *, version, include_deleted):
                self.calls.append((version, include_deleted))
                return copy.deepcopy(owner.draft if version == "draft" else owner.published)
        self.service = object.__new__(GxpReadonlyService)
        self.service.repository = Repository()
        self.service.database = SimpleNamespace(config=SimpleNamespace(host="localhost", port=3306, database="test"))
        self.service.inspector = CanvasInspector()

    def tearDown(self):
        self.environment.stop()
        self.directory.cleanup()

    def export(self, source=None):
        return self.service.export_edit_handoff("code", TARGETS, SPEC, source or {"version": "published", "design_id": "published", "data_sha256": self.published["data_sha256"]})

    def test_export_current_draft_once_and_preserve_source_differences(self):
        self.published = design("published-value", design_id="published", version="published")
        result = self.export()
        self.assertTrue(result["available"])
        self.assertFalse(result["authorization_granted"])
        self.assertEqual(1, self.service.repository.calls.count(("draft", False)))
        self.assertIn("paramsValue", result["source_target_differences"][0]["changed_fields"])
        record = HandoffStore().read(**result["handoff_ref"])
        self.assertEqual("old", record["targets"][0]["paramsValue"]["inputParams"]["value"]["code"])
        self.assertNotIn("do not export generated source", json.dumps(record))

    def test_export_and_read_preserve_complete_diagnosis_without_promoting_findings(self):
        spec = diagnosed_spec()
        exported = self.service.export_edit_handoff("code", TARGETS, spec, {
            "version": "published", "design_id": "published", "data_sha256": self.published["data_sha256"],
        })
        self.assertTrue(exported["available"])
        restored = GxpReadonlyService.read_edit_handoff(**exported["handoff_ref"])
        self.assertTrue(restored["response_complete"])
        self.assertEqual(spec, restored["record"]["change_spec"])
        issues = restored["record"]["change_spec"]["diagnosis"]["issues"]
        self.assertEqual(["confirmed", "candidate"], [issue["status"] for issue in issues])
        self.assertEqual(["static_confirmed", "pending"], [issue["verification"] for issue in issues])
        self.assertFalse(restored["authorization_granted"])

    def test_export_and_read_evidence_only_diagnosis_with_no_or_empty_changes(self):
        for include_changes in (False, True):
            with self.subTest(include_changes=include_changes):
                spec = evidence_only_spec(include_changes=include_changes)
                exported = self.service.export_edit_handoff("code", TARGETS, spec, {
                    "version": "published", "design_id": "published", "data_sha256": self.published["data_sha256"],
                })
                self.assertTrue(exported["available"])
                restored = GxpReadonlyService.read_edit_handoff(**exported["handoff_ref"])
                self.assertTrue(restored["response_complete"])
                self.assertEqual(spec, restored["record"]["change_spec"])
                self.assertFalse(restored["authorization_granted"])

    def test_diagnosis_only_published_evidence_needs_no_draft_or_nodes(self):
        source = {"version": "published", "design_id": "published", "data_sha256": self.published["data_sha256"]}
        repository_load = self.service.repository.load_design
        def published_only(ref_id, *, version, include_deleted):
            self.assertEqual("published", version)
            return repository_load(ref_id, version=version, include_deleted=include_deleted)
        with patch.object(self.service.repository, "load_design", side_effect=published_only):
            exported = self.service.export_edit_handoff("code", [], evidence_only_spec(), source, record_kind="diagnosis_only")
        self.assertTrue(exported["available"], exported)
        record = HandoffStore().read(**exported["handoff_ref"])
        self.assertEqual("diagnosis_only", record["record_kind"])
        self.assertIsNone(record["draft"])
        self.assertEqual([], record["targets"])
        self.assertEqual([], record["diagnosis_targets"])
        self.assertEqual([], record["source_target_differences"])
        self.assertEqual(evidence_only_spec(), record["change_spec"])
        read = GxpReadonlyService.read_edit_handoff(**exported["handoff_ref"])
        self.assertTrue(read["response_complete"])
        self.assertFalse(read["authorization_granted"])
        bad_target = GxpReadonlyService.read_edit_handoff(**exported["handoff_ref"], target_index=0)
        self.assertEqual("HANDOFF_TARGETS", bad_target["error_code"])

    def test_diagnosis_only_rechecks_current_diagnosed_copy(self):
        source = {"version": "published", "design_id": "historical", "data_sha256": self.published["data_sha256"]}
        result = self.service.export_edit_handoff("code", [], evidence_only_spec(), source, record_kind="diagnosis_only")
        self.assertEqual("HANDOFF_STALE_DIAGNOSIS", result["error_code"])
        self.assertNotIn("draft_observed", result)
        self.assertEqual([("published", False)], self.service.repository.calls)
        self.assertFalse(list(HandoffStore().root.glob("*.json")))

    def test_diagnosis_only_refuses_snapshot_targets_changes_or_missing_findings(self):
        source = {"version": "published", "design_id": "published", "data_sha256": self.published["data_sha256"]}
        for targets, spec, kind in [
            (TARGETS, evidence_only_spec(), "diagnosis_only"),
            ([], diagnosed_spec(), "diagnosis_only"),
            ([], {"user_request": "Keep evidence", "summary": "No findings"}, "diagnosis_only"),
            ([], evidence_only_spec(), "unknown"),
            ([], evidence_only_spec(), "edit_snapshot"),
        ]:
            with self.subTest(kind=kind, targets=targets, spec=spec):
                result = self.service.export_edit_handoff("code", targets, spec, source, record_kind=kind)
                self.assertFalse(result["available"], result)
        self.assertFalse(list(HandoffStore().root.glob("*.json")))

    def test_default_snapshot_contains_semantic_fingerprint_and_keeps_source_strict(self):
        exported = self.export()
        self.assertTrue(exported["available"], exported)
        record = HandoffStore().read(**exported["handoff_ref"])
        self.assertEqual("edit_snapshot", record["record_kind"])
        self.assertEqual(canonical_sha256(self.draft["data_json"]), record["draft"]["semantic_sha256"])
        self.assertEqual({"version", "design_id", "data_sha256"}, set(record["diagnosis_source"]))

    def test_cross_dialogue_read_is_database_free_and_requires_explicit_scope(self):
        first, second = self.export(), self.export()
        with patch("gxp_core.service.ReadOnlyDatabase", side_effect=AssertionError("No DB")):
            listed = GxpReadonlyService.read_edit_handoff(identifier="code")
            self.assertEqual(2, listed["count"])
            self.assertTrue(listed["selection_required"])
            result = GxpReadonlyService.read_edit_handoff(**first["handoff_ref"])
        self.assertTrue(result["requires_current_scope_confirmation"])
        self.assertNotIn("session_id", result)

    def test_published_condition_change_is_not_hidden_by_flat_node_depth(self):
        self.draft["data_json"]["actionData"][0]["data"][1]["depth"] = []
        self.draft["data"] = json.dumps(self.draft["data_json"])
        self.published = copy.deepcopy(self.draft)
        self.published.update(design_id="published", version="published")
        self.published["data_json"]["actionData"][0]["data"][0]["paramsValue"] = {"inputParams": {"condition": "different"}}
        self.published["data"] = json.dumps(self.published["data_json"])
        self.published["data_sha256"] = hashlib.sha256(self.published["data"].encode()).hexdigest()
        result = self.export()
        self.assertTrue(result["available"])
        self.assertIn("control_flow", result["source_target_differences"][0]["changed_fields"])

    def test_stale_historical_deleted_source_does_not_export(self):
        source = {"version": "published", "design_id": "historical", "data_sha256": self.published["data_sha256"]}
        result = self.export(source)
        self.assertEqual("HANDOFF_STALE_DIAGNOSIS", result["error_code"])
        self.assertFalse(list(HandoffStore().root.glob("*.json")))
        self.published["is_deleted"] = True
        self.assertEqual("HANDOFF_DESIGN", self.export()["error_code"])

    def test_missing_target_bad_request_and_corrupt_record_have_fallback(self):
        result = self.service.export_edit_handoff("code", [{"group_key": "main", "node_key": "missing"}], SPEC, {})
        self.assertFalse(result["available"])
        result = GxpReadonlyService.read_edit_handoff("/path/forbidden")
        self.assertEqual("HANDOFF_ID", result["error_code"])
        self.assertIn("inspect_action", result["next_step"])

    def test_large_parameters_continue_without_silent_truncation(self):
        self.draft = design("x" * 50000)
        self.published = copy.deepcopy(self.draft)
        self.published.update(design_id="published", version="published")
        exported = self.export()
        self.assertTrue(exported["available"])
        read = GxpReadonlyService.read_edit_handoff(**exported["handoff_ref"])
        self.assertFalse(read["response_complete"])
        self.assertEqual(1, len(read["next_read"]))
        record = HandoffStore().read(**exported["handoff_ref"])
        self.assertEqual(50000, len(record["targets"][0]["paramsValue"]["inputParams"]["value"]["code"]))

    def test_success_and_failure_keep_timings_outside_record(self):
        measured = traced_tool(self.export)
        success = measured()
        self.assertTrue(success["trace_id"])
        self.assertIn("draft.read", [item["stage"] for item in success["timings"]])
        record = HandoffStore().read(**success["handoff_ref"])
        self.assertNotIn("timings", record)
        failed = measured({"version": "published", "design_id": "old", "data_sha256": "0" * 64})
        self.assertFalse(failed["available"])
        self.assertIn("handoff.diagnosis_read", [item["stage"] for item in failed["timings"]])

    def test_large_candidate_list_pages_without_truncating_records(self):
        record = make_record()
        record["change_spec"]["summary"] = "x" * 2000
        store = HandoffStore()
        references = [store.write(record)["handoff_ref"] for _ in range(35)]
        result = GxpReadonlyService.read_edit_handoff(identifier="code", limit=50)
        seen = []
        while True:
            self.assertTrue(result["available"], result)
            self.assertLess(len(json.dumps(result).encode()), 64 * 1024)
            seen.extend(item["handoff_id"] for item in result["candidates"])
            if not result["has_more"]:
                break
            self.assertEqual("read_edit_handoff", result["next_read"]["tool"])
            result = GxpReadonlyService.read_edit_handoff(**result["next_read"]["arguments"])
        self.assertEqual(35, len(set(seen)))
        self.assertEqual(35, len(store.list("code")))
        self.assertTrue(GxpReadonlyService.read_edit_handoff(**references[0])["available"])

    def test_environment_filter_survives_continuation_and_exact_read(self):
        store = HandoffStore()
        record = make_record()
        desired_scope = record["environment_scope"]
        wanted = [store.write(record)["handoff_ref"] for _ in range(3)]
        record["environment_scope"] = "f" * 64
        wrong = store.write(record)["handoff_ref"]
        result = GxpReadonlyService.read_edit_handoff(identifier="code", environment_scope=desired_scope, limit=1)
        seen = []
        while True:
            self.assertTrue(result["available"], result)
            for candidate in result["candidates"]:
                self.assertEqual(desired_scope, candidate["environment_scope"])
                seen.append(candidate["handoff_id"])
            if not result["has_more"]:
                break
            arguments = result["next_read"]["arguments"]
            self.assertEqual(desired_scope, arguments["environment_scope"])
            self.assertEqual(1, arguments["limit"])
            result = GxpReadonlyService.read_edit_handoff(**arguments)
        self.assertEqual({item["handoff_id"] for item in wanted}, set(seen))
        mismatch = GxpReadonlyService.read_edit_handoff(**wrong, environment_scope=desired_scope)
        self.assertEqual("HANDOFF_ENVIRONMENT", mismatch["error_code"])
        invalid_cursor = GxpReadonlyService.read_edit_handoff(**wanted[0], cursor="cursor")
        self.assertEqual("HANDOFF_ID", invalid_cursor["error_code"])

    def test_large_fallback_metadata_never_bypasses_response_budget(self):
        record = make_record()
        record["action"]["action_name"] = "x" * 50000
        record["change_spec"]["preserve"] = ["y" * 18000]
        reference = HandoffStore().write(record)["handoff_ref"]
        result = GxpReadonlyService.read_edit_handoff(**reference)
        self.assertTrue(result["available"], result)
        self.assertFalse(result["response_complete"])
        self.assertTrue(result["summary"]["summary_truncated"])
        self.assertEqual(["targets", "diagnosis_targets"], result["omitted"])
        self.assertLess(len(json.dumps(result).encode()), 64 * 1024)
        self.assertEqual(50000, len(HandoffStore().read(**reference)["action"]["action_name"]))


if __name__ == "__main__":
    unittest.main()
