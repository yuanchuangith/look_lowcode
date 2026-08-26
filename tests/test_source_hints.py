from __future__ import annotations

import json
import unittest

from gxp_core.source_hints import MAX_HINT_BYTES, build_source_hints


class SourceHintTests(unittest.TestCase):
    def test_component_identity_generates_frontend_hints_and_field_pair(self) -> None:
        filters = {
            "component": {
                "component_key": "testpaper",
                "component_type": "TestPaper",
                "model_key": "testpaper_id",
                "label": "培训试卷",
            },
            "writers": [
                {
                    "filter_facts": {
                        "filters": [
                            {"field": "document_code", "expression": "current_document"},
                            {"field": "revision_no", "expression": "current_revision"},
                        ]
                    }
                }
            ],
        }

        hints = build_source_hints(component_filters=filters)

        self.assertEqual(["frontend"], hints["candidate_layers"])
        self.assertIn("component_identity", hints["reason_codes"])
        self.assertEqual("TestPaper", hints["anchors"]["component_type"])
        self.assertIn("TestPaper", hints["exact_terms"])
        self.assertIn(["document_code", "current_document"], hints["paired_terms"])
        self.assertIn(["revision_no", "current_revision"], hints["paired_terms"])
        self.assertIn(["document_code", "revision_no"], hints["paired_terms"])
        self.assertNotIn(["current_document", "revision_no"], hints["paired_terms"])

    def test_api_service_and_real_backend_stack_generate_backend_hints(self) -> None:
        text = (
            "POST /gxp2/api/training/complete failed\n"
            "at GxP2.Services.TrainingTaskService.Complete(String id) in Service.cs:line 42"
        )

        hints = build_source_hints(text=text)

        self.assertEqual(["backend"], hints["candidate_layers"])
        self.assertIn("api_route", hints["reason_codes"])
        self.assertIn("backend_stack_frame", hints["reason_codes"])
        self.assertIn("TrainingTaskService", hints["exact_terms"])
        self.assertIn("Complete", hints["exact_terms"])

    def test_opaque_component_model_id_is_anchor_only_not_search_term(self) -> None:
        hints = build_source_hints(
            component_filters={
                "component": {
                    "component_key": "testpaper",
                    "component_type": "EformDynamicList",
                    "model_key": "f8be0e4ac19f4a26a01951901a08c4af",
                }
            }
        )

        self.assertEqual(
            "f8be0e4ac19f4a26a01951901a08c4af",
            hints["anchors"]["model_key"],
        )
        self.assertNotIn("f8be0e4ac19f4a26a01951901a08c4af", hints["exact_terms"])

    def test_frontend_and_backend_signals_generate_cross_layer_hints(self) -> None:
        hints = build_source_hints(
            component_filters={
                "component": {
                    "component_key": "testpaper",
                    "component_type": "TestPaper",
                    "model_key": "testpaper_id",
                },
                "writers": [{"api_routes": ["/api/testpaper/list"]}],
            }
        )

        self.assertEqual(["frontend", "backend"], hints["candidate_layers"])
        self.assertIn("request_contract_cross_layer", hints["reason_codes"])

    def test_action_calls_tables_and_fields_do_not_trigger_source_scan(self) -> None:
        nodes = [
            {
                "facts": {
                    "called_action": {"code": "PQDL0QlL", "id": "ref-1"},
                    "model_or_table": "gxp_tms_training_file",
                    "field_mappings": [{"field": "file_id"}],
                }
            }
        ]

        hints = build_source_hints(nodes=nodes)

        self.assertEqual([], hints["candidate_layers"])
        self.assertNotIn("PQDL0QlL", hints["exact_terms"])
        self.assertEqual("low", hints["confidence"])

    def test_generated_dynamic_class_is_not_a_source_keyword(self) -> None:
        hints = build_source_hints(
            text="at GTEoZQNMJ.GTEoZQNMJ.main(String id) in :line 213"
        )

        self.assertNotIn("GTEoZQNMJ", hints["exact_terms"])
        self.assertEqual([], hints["candidate_layers"])

    def test_hints_are_deduplicated_and_bounded(self) -> None:
        nodes = [
            {
                "facts": {
                    "component": {
                        "component_key": "component-" + str(index),
                        "component_type": "Type" + ("X" * 150) + str(index),
                        "model_key": "model_" + str(index),
                    },
                    "api_routes": [f"/api/route/{index}" for index in range(50)],
                    "service_symbols": [f"Namespace.Service{index}" for index in range(50)],
                }
            }
            for index in range(30)
        ]

        hints = build_source_hints(nodes=nodes)
        encoded = json.dumps(hints, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        self.assertLessEqual(len(hints["exact_terms"]), 8)
        self.assertLessEqual(len(hints["paired_terms"]), 4)
        self.assertLessEqual(len(encoded), MAX_HINT_BYTES)


if __name__ == "__main__":
    unittest.main()
