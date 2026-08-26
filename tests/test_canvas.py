from __future__ import annotations

import unittest

from gxp_core.canvas import CanvasInspector


class CanvasInspectorTests(unittest.TestCase):
    def test_reports_canvas_line_parent_neighbors_and_filters(self) -> None:
        design = {
            "actionData": [
                {
                    "key": "main",
                    "title": "主流程",
                    "data": [
                        {"key": "if1", "title": "判断", "elementKey": "IfCondition"},
                        {
                            "key": "select1",
                            "title": "查询周期培训",
                            "elementKey": "SelectData",
                            "depth": ["if1"],
                            "paramsValue": {
                                "inputParams": {
                                    "modelName": {"modelName": "gxp_tms_periodic_training"},
                                    "selectDataConfig": {
                                        "whereConditions": {
                                            "Filters": [
                                                {
                                                    "Field": "status",
                                                    "Operator": "Equal",
                                                    "ParamInput": {"code": '"default"'},
                                                }
                                            ]
                                        }
                                    },
                                }
                            },
                        },
                    ],
                }
            ]
        }
        result = CanvasInspector().inspect(design, node_key="select1")
        self.assertEqual(1, len(result))
        node = result[0]
        self.assertEqual(2, node["canvas_line"])
        self.assertEqual(1, node["internal_index"])
        self.assertEqual("if1", node["parent_path"][0]["node_key"])
        self.assertEqual(
            "gxp_tms_periodic_training", node["facts"]["model_or_table"]
        )
        self.assertEqual("status", node["facts"]["filters"][0]["field"])

    def test_focus_fields_and_generated_csharp_evidence_keep_exact_locator(self) -> None:
        design = {
            "actionData": [
                {
                    "key": "main",
                    "title": "主流程",
                    "data": [
                        {
                            "key": "add1",
                            "title": "新增周期培训",
                            "elementKey": "AddNewData",
                            "paramsValue": {
                                "inputParams": {
                                    "modelName": {"modelName": "gxp_tms_periodic_training"},
                                    "params": [
                                        {
                                            "attribute": "training_topic_id",
                                            "name": {"code": "topic.id"},
                                        }
                                    ],
                                }
                            },
                        }
                    ],
                }
            ]
        }
        nodes = CanvasInspector().inspect(design)
        fields = CanvasInspector.focus_fields(nodes, ["training_topic_id"])
        csharp = 'values.Add("training_topic_id", topic.id);'
        generated = CanvasInspector.generated_csharp_node_evidence(
            nodes, csharp, focus_fields=["training_topic_id"]
        )

        self.assertEqual("add1", fields[0]["node_key"])
        self.assertEqual(1, fields[0]["canvas_line"])
        self.assertEqual("training_topic_id", fields[0]["matches"]["field_mappings"][0]["field"])
        self.assertEqual(
            "paramsValue.inputParams.params",
            fields[0]["matches"]["field_mappings"][0]["source_path"],
        )
        self.assertEqual("add1", generated[0]["node_key"])
        self.assertFalse(generated[0]["exact_source_map"])
        self.assertEqual(["training_topic_id", 'Add("training_topic_id"'], generated[0]["search_terms"])
        self.assertIn("training_topic_id", generated[0]["matches"][0]["matched_terms"])

    def test_component_filters_collect_all_writers_conditions_and_stages(self) -> None:
        def data_filter(key, expression, depth=None):
            return {
                "key": key,
                "title": "数据过滤",
                "elementKey": "DataFilter",
                "depth": depth or [],
                "paramsValue": {
                    "inputParams": {
                        "name": {
                            "value": "testpaper_id",
                            "label": "试卷名称",
                            "componentType": "EformDynamicList",
                            "modelkey": "paper-model",
                        },
                        "whereType": "staticWhere",
                        "whereConditions": {
                            "Logic": "And",
                            "Filters": [
                                {
                                    "Field": "gxp_tms_testpaper.id",
                                    "Operator": "Any",
                                    "ParamInput": {"code": expression},
                                    "type": "varchar",
                                }
                            ],
                        },
                    }
                },
            }

        design = {
            "actionData": [
                {
                    "key": "main",
                    "title": "主动作",
                    "data": [
                        {
                            "key": "if-main",
                            "title": "IF 条件判断",
                            "elementKey": "IfCondition",
                            "paramsValue": {
                                "inputParams": {
                                    "condition": {
                                        "Filters": [
                                            {
                                                "target": {"code": "file_id"},
                                                "equalTo": "NotEqualNull",
                                            }
                                        ]
                                    }
                                }
                            },
                        },
                        data_filter("main-filter", "filePaperIds", ["if-main"]),
                        {"key": "main-next", "title": "设置值", "elementKey": "SetVariableValue"},
                    ],
                },
                {
                    "key": "defaults",
                    "title": "设置默认值",
                    "data": [data_filter("default-filter", "defaultPaperIds")],
                },
                {
                    "key": "change",
                    "title": "评估方式变更事件",
                    "data": [data_filter("change-filter", "changedPaperIds")],
                },
            ]
        }

        result = CanvasInspector().inspect_component_filters(design, "testpaper_id")

        self.assertEqual("unique", result["resolution_status"])
        self.assertEqual(3, result["writer_count"])
        self.assertEqual(
            ["initialization", "default_value", "field_change"],
            result["execution_stages"],
        )
        self.assertEqual("filePaperIds", result["writers"][0]["filter_facts"]["filters"][0]["expression"])
        self.assertEqual("file_id NotEqualNull", result["writers"][0]["parent_conditions"][0]["condition"])
        self.assertEqual("if", result["writers"][0]["parent_conditions"][0]["branch"])
        self.assertEqual("main-next", result["writers"][0]["next_node"]["node_key"])
        self.assertFalse(result["writers"][0]["may_overwrite_earlier_filter"])
        self.assertTrue(result["writers"][2]["may_overwrite_earlier_filter"])
        self.assertIn("replace an earlier filter", result["overwrite_warning"])

    def test_compare_returns_locators_for_changed_added_and_removed_nodes(self) -> None:
        published = {
            "actionData": [
                {
                    "key": "main",
                    "title": "主流程",
                    "data": [
                        {"key": "same", "title": "原节点", "elementKey": "IfCondition"},
                        {"key": "removed", "title": "删除节点", "elementKey": "ExitAction"},
                    ],
                }
            ]
        }
        draft = {
            "actionData": [
                {
                    "key": "main",
                    "title": "主流程",
                    "data": [
                        {"key": "same", "title": "已修改", "elementKey": "IfCondition"},
                        {"key": "added", "title": "新增节点", "elementKey": "SetVariable"},
                    ],
                }
            ]
        }

        result = CanvasInspector.compare(published, draft)

        self.assertFalse(result["same"])
        self.assertEqual("same", result["changed"][0]["node_key"])
        self.assertEqual(1, result["changed"][0]["published_locator"]["canvas_line"])
        self.assertEqual("IfCondition", result["changed"][0]["draft_locator"]["node_type"])
        self.assertEqual("added", result["added"][0]["node_key"])
        self.assertEqual("removed", result["removed"][0]["node_key"])


if __name__ == "__main__":
    unittest.main()
