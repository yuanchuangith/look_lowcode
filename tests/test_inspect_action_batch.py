from __future__ import annotations

import hashlib
import json
import unittest

from gxp_core.canvas_budget import payload_size
from gxp_core.repository import DesignNotFound
from gxp_core.service import GxpReadonlyService


def _node(key, value):
    return {"key": key, "elementKey": "SetVariable", "paramsValue": value}


def _group(key, *nodes):
    return {"key": key, "title": f"title-{key}", "data": list(nodes)}


class Repository:
    def __init__(self, groups):
        self.design = {"actionData": groups}
        self.design_id = "current"
        self.load_options = []

    def resolve_action(self, identifier):
        return [{"ref_id": "ref"}] if identifier == "ACTION" else []

    def search_actions(self, identifier):
        raise AssertionError("batch reads require an exact action")

    def load_design(self, ref_id, **kwargs):
        self.load_options.append((ref_id, kwargs))
        if self.design_id is None:
            raise DesignNotFound("active copy is gone")
        return {
            "design_id": self.design_id, "version": kwargs["version"], "is_deleted": False,
            "data_sha256": hashlib.sha256(json.dumps(self.design, sort_keys=True).encode()).hexdigest(),
            "metadata": {"ref_id": ref_id, "action_code": "ACTION"}, "data_json": self.design,
        }


class InspectActionBatchTests(unittest.TestCase):
    def make_service(self, *groups):
        service = object.__new__(GxpReadonlyService)
        service.repository = Repository(groups)
        return service

    def test_batch_uses_exact_keys_preserves_order_and_loads_the_current_copy_once(self):
        service = self.make_service(
            _group("a", _node("node", {"a/b": [None], "keep": "文本"})),
            _group("b", _node("node", {"n": 3})),
        )
        result = service.inspect_action("ACTION", version="draft", targets=[
            {"group_key": "b", "node_key": "node", "value_paths": ["/paramsValue/n"]},
            {"group_key": "a", "node_key": "node", "value_paths": ["/paramsValue/a~1b/0", "/paramsValue/keep"]},
        ])
        self.assertEqual([("ref", {"version": "draft", "include_deleted": False, "include_csharp": False})],
                         service.repository.load_options)
        self.assertEqual(("draft", "current"), (result["design"]["version"], result["design"]["design_id"]))
        self.assertTrue(result["evidence_complete"])
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(["b", "a"], [item["group_key"] for item in result["targets"]])
        self.assertEqual(["3", "null", "文本"], [value["text"] for target in result["targets"] for value in target["values"]])
        self.assertEqual({"canvas_line": 1, "element_key": "SetVariable"}, result["targets"][0]["node"])

    def test_distinguishes_missing_or_ambiguous_targets_from_null_found_at_path(self):
        service = self.make_service(
            _group("a", _node("dup", {}), _node("dup", {}), _node("ok", {"null": None})),
            _group("duplicate"), _group("duplicate"),
        )
        result = service.inspect_action("ACTION", targets=[
            {"group_key": "title-a", "node_key": "ok"},
            {"group_key": "a", "node_key": "missing"},
            {"group_key": "a", "node_key": "dup"},
            {"group_key": "duplicate", "node_key": "whatever"},
            {"group_key": "a", "node_key": "ok", "value_paths": ["/paramsValue/missing", "/paramsValue/null"]},
        ])
        self.assertEqual(["group_not_found", "node_not_found", "node_ambiguous", "group_ambiguous", "found"],
                         [item["status"] for item in result["targets"]])
        self.assertEqual(["path_not_found", "complete"], [item["status"] for item in result["targets"][-1]["values"]])
        self.assertEqual("null", result["targets"][-1]["values"][1]["text"])
        self.assertTrue(result["response_complete"])
        self.assertFalse(result["evidence_complete"])

    def test_long_value_pages_independently_and_keeps_utf8_budget(self):
        text = "长文🙂" * 2400
        service = self.make_service(_group("a", _node("one", {"long": text, "short": "available"})))
        original = {"identifier": "ACTION", "targets": [{"group_key": "a", "node_key": "one",
                    "value_paths": ["/paramsValue/long", "/paramsValue/short"]}], "max_output_bytes": 8192}
        first = service.inspect_action(**original)
        self.assertLessEqual(payload_size(first), 8192)
        self.assertTrue(first["response_truncated"])
        long_value, short_value = first["targets"][0]["values"]
        self.assertEqual("available", short_value["text"])
        chunks = [long_value["text"]]
        while not long_value["complete"]:
            page = service.inspect_action(**original, design_id=first["design"]["design_id"],
                expected_data_sha256=first["design"]["data_sha256"], batch_cursor=long_value["value_cursor"])
            self.assertLessEqual(payload_size(page), 8192)
            self.assertEqual(1, len(page["targets"][0]["values"]))
            current = page["targets"][0]["values"][0]
            self.assertEqual(long_value["next_offset"], current["value_offset"])
            chunks.append(current["text"])
            long_value = current
        self.assertEqual(text, "".join(chunks))

    def test_budget_continuation_and_pin_rejects_drift_or_changed_selectors(self):
        service = self.make_service(_group("a", *[_node(f"n{index}", {"data": "界" * 1024}) for index in range(6)]))
        request = {"identifier": "ACTION", "targets": [{"group_key": "a", "node_key": f"n{index}",
                   "value_paths": ["/paramsValue/data"]} for index in range(6)], "max_output_bytes": 8192}
        result = service.inspect_action(**request)
        count = len(result["targets"])
        self.assertGreater(count, 0)
        self.assertLess(count, 6)
        self.assertLessEqual(payload_size(result), 8192)
        args = result["next_read"]["arguments"]
        next_page = service.inspect_action(**request, **args)
        self.assertEqual(count, next_page["targets"][0]["target_index"])
        with self.assertRaisesRegex(ValueError, "does not match these targets"):
            service.inspect_action(**{**request, "targets": request["targets"][::-1]}, **args)
        service.repository.design["actionData"][0]["data"][0]["paramsValue"]["data"] = "new evidence"
        changed_body = service.inspect_action(**request, **args)
        self.assertEqual("version_drift", changed_body["batch_status"])
        self.assertEqual([], changed_body["targets"])
        pinned = service.inspect_action(**request)
        service.repository.design_id = "republished"
        changed_id = service.inspect_action(**request, **pinned["next_read"]["arguments"])
        self.assertEqual("version_drift", changed_id["batch_status"])
        self.assertEqual([], changed_id["targets"])
        self.assertNotIn("design_id", service.repository.load_options[-1][1])
        service.repository.design_id = None
        deleted = service.inspect_action(**request, **args)
        self.assertEqual("version_drift", deleted["batch_status"])
        self.assertEqual([], deleted["targets"])

    def test_invalid_mixed_and_partial_pins_are_rejected_before_loading(self):
        service = self.make_service()
        targets = [{"group_key": "g", "node_key": "n"}]
        for options in ({"design_id": "id"}, {"group": "g"}, {"at_time": "past"}, {"include_generated_csharp": True}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                service.inspect_action("ACTION", targets=targets, **options)
        self.assertEqual([], service.repository.load_options)
