from __future__ import annotations

import unittest

from gxp_core.canvas import CanvasInspector, ControlFlowAnalyzer, condition_ast, evaluate_condition_ast


def predicate(field: str, operator: str, value: str | None = None) -> dict:
    item = {
        "target": {"paramTypes": "localVariable", "code": field, "dataType": "string"},
        "equalTo": operator,
    }
    if value is not None:
        item["value"] = {"paramTypes": "custom", "code": value, "dataType": "string"}
    return item


def block_node(key: str, element: str, depth=None, filters=None, title=None, **inputs) -> dict:
    if filters is not None:
        inputs["condition"] = {"Logic": "And", "Filters": filters}
    result = {
        "key": key,
        "title": title or key,
        "elementKey": element,
        "paramsValue": {"inputParams": inputs},
    }
    if depth is not None:
        result["depth"] = depth
    return result


def design(nodes: list[dict]) -> dict:
    return {"actionData": [{"key": "main", "title": "主流程", "data": nodes}]}


class ConditionAstTests(unittest.TestCase):
    def test_nested_and_or_ast_and_three_state_evaluation(self) -> None:
        raw = {
            "Logic": "And",
            "Filters": [
                predicate("enabled", "Equal", "true"),
                {
                    "Logic": "Or",
                    "Filters": [
                        predicate("amount", "GreaterThan", "10"),
                        predicate("name", "Equal", "'A'"),
                    ],
                },
            ],
        }
        ast = condition_ast(raw)
        self.assertEqual("AND", ast["logic"])
        self.assertEqual("OR", ast["children"][1]["logic"])
        self.assertEqual(
            "true",
            evaluate_condition_ast(ast, {"enabled": True, "amount": 11})["result"],
        )
        unknown = evaluate_condition_ast(ast, {"enabled": True})
        self.assertEqual("unknown", unknown["result"])
        self.assertIn("amount", unknown["unresolved_inputs"])


class ControlFlowPairingTests(unittest.TestCase):
    def test_if_without_else_and_if_else_pairing(self) -> None:
        nodes = [
            block_node("if-1", "IfCondition", [], [predicate("x", "NotEqualNull")]),
            block_node("body", "SetVariableValue", ["if-1"]),
            block_node("else-1", "Else", ["if-1"]),
            block_node("else-body", "ExitAction", ["else-1"]),
            block_node("end-1", "IfEnd", ["else-1"]),
            block_node("if-2", "NullCondition", [], [predicate("y", "EqualNull")]),
            block_node("end-2", "IfEnd", ["if-2"]),
        ]
        result = ControlFlowAnalyzer().analyze(design(nodes))["groups"][0]
        self.assertEqual("valid", result["structure_status"])
        self.assertEqual("if-1", result["node_control_flow"][2]["root_block"]["node_key"])
        self.assertEqual("if-1", result["node_control_flow"][2]["matched_branch"]["node_key"])
        self.assertEqual("end-1", result["node_control_flow"][0]["matched_end"]["node_key"])
        self.assertEqual(2, len(result["blocks"]))

    def test_nested_else_never_pairs_with_outer_if(self) -> None:
        nodes = [
            block_node("outer", "IfCondition", [], [predicate("outer_value", "NotEqualNull")]),
            block_node("inner", "IfCondition", ["outer"], [predicate("inner_value", "Equal", "'Y'")]),
            block_node("inner-body", "ExitAction", ["outer", "inner"]),
            block_node("inner-else", "Else", ["outer", "inner"]),
            block_node("inner-else-body", "ExitAction", ["outer", "inner-else"]),
            block_node("inner-end", "IfEnd", ["outer", "inner-else"]),
            block_node("outer-else", "Else", ["outer"]),
            block_node("outer-else-body", "ExitAction", ["outer-else"]),
            block_node("outer-end", "IfEnd", ["outer-else"]),
        ]
        result = ControlFlowAnalyzer().analyze(design(nodes))["groups"][0]
        inner_else = result["node_control_flow"][3]
        outer_else = result["node_control_flow"][6]
        self.assertEqual("valid", result["structure_status"])
        self.assertEqual("inner", inner_else["root_block"]["node_key"])
        self.assertEqual("inner", inner_else["matched_branch"]["node_key"])
        self.assertEqual("inner-end", inner_else["matched_end"]["node_key"])
        self.assertEqual("outer", outer_else["root_block"]["node_key"])
        self.assertEqual("outer", outer_else["matched_branch"]["node_key"])

    def test_else_if_chain_accepts_both_element_names(self) -> None:
        nodes = [
            block_node("if", "IfCondition", filters=[predicate("x", "Equal", "1")]),
            block_node("elseif-a", "ElseIf", filters=[predicate("x", "Equal", "2")]),
            block_node("elseif-b", "ElseIfCondition", filters=[predicate("x", "Equal", "3")]),
            block_node("else", "Else"),
            block_node("end", "IfEnd"),
        ]
        result = ControlFlowAnalyzer().analyze(design(nodes))["groups"][0]
        self.assertEqual("valid", result["structure_status"])
        self.assertEqual("elseif-a", result["node_control_flow"][2]["matched_branch"]["node_key"])
        self.assertEqual("elseif-b", result["node_control_flow"][3]["matched_branch"]["node_key"])

    def test_loop_try_and_condition_can_nest(self) -> None:
        nodes = [
            block_node("loop", "ForEachObject"),
            block_node("try", "Try"),
            block_node("if", "IfCondition", filters=[predicate("x", "Equal", "1")]),
            block_node("if-end", "IfEnd"),
            block_node("catch", "Catch"),
            block_node("finally", "Finally"),
            block_node("try-end", "EndTry"),
            block_node("loop-end", "LoopEnd"),
        ]
        result = ControlFlowAnalyzer().analyze(design(nodes))["groups"][0]
        self.assertEqual("valid", result["structure_status"])
        self.assertEqual(["loop", "try", "if"], [item["family"] for item in result["blocks"]])
        self.assertEqual("catch", result["node_control_flow"][5]["matched_branch"]["node_key"])

    def test_three_nested_same_title_nodes_pair_by_structure_and_key(self) -> None:
        nodes = [
            block_node("level-1", "IfCondition", title="相同标题"),
            block_node("level-2", "IfCondition", title="相同标题"),
            block_node("level-3", "IfCondition", title="相同标题"),
            block_node("level-3-else", "Else", title="相同标题"),
            block_node("level-3-end", "IfEnd", title="相同标题"),
            block_node("level-2-end", "IfEnd", title="相同标题"),
            block_node("level-1-end", "IfEnd", title="相同标题"),
        ]
        result = ControlFlowAnalyzer().analyze(design(nodes))["groups"][0]
        self.assertEqual("valid", result["structure_status"])
        branch = result["node_control_flow"][3]
        self.assertEqual("level-3", branch["root_block"]["node_key"])
        self.assertEqual("level-3-end", branch["matched_end"]["node_key"])
        self.assertEqual(2, branch["nesting_level"])

    def test_invalid_and_partial_structures_are_explicit(self) -> None:
        cases = [
            ([block_node("else", "Else")], "invalid", "orphan_branch"),
            ([block_node("if", "IfCondition")], "invalid", "missing_end"),
            ([block_node("try", "Try"), block_node("end", "IfEnd")], "invalid", "mismatched_end"),
            ([block_node("if", "IfCondition", ["wrong"]), block_node("end", "IfEnd", ["if"])], "invalid", "depth_drift"),
            ([block_node("a", "SetVariable"), block_node("a", "ExitAction")], "invalid", "duplicate_node_key"),
            ([block_node("custom", "PluginBlock") | {"levelMarker": True}], "partial", "unknown_plugin_block"),
        ]
        for nodes, status, warning in cases:
            with self.subTest(warning=warning):
                result = ControlFlowAnalyzer().analyze(design(nodes))["groups"][0]
                self.assertEqual(status, result["structure_status"])
                self.assertIn(warning, {item["code"] for item in result["warnings"]})
                self.assertFalse(result["node_control_flow"][0]["pairing_definitive"])

    def test_node_scope_returns_the_smallest_complete_block(self) -> None:
        nodes = [
            block_node("outer", "IfCondition"),
            block_node("inner", "IfCondition"),
            block_node("target", "ExitAction"),
            block_node("inner-end", "IfEnd"),
            block_node("outer-end", "IfEnd"),
        ]
        result = ControlFlowAnalyzer().inspect(design(nodes), node_key="target")
        canvas_keys = {
            item["node_key"] for item in result["graph"]["nodes"] if item["type"] == "canvas"
        }
        self.assertEqual({"inner", "target", "inner-end"}, canvas_keys)
        self.assertEqual(["inner"], [item["root"]["node_key"] for item in result["blocks"]])


class ControlFlowGraphAndScenarioTests(unittest.TestCase):
    def test_dependency_edges_stable_ids_mermaid_escape_and_truncation(self) -> None:
        nodes = [
            block_node(
                "read",
                "SelectData",
                modelName={"modelName": "gxp_table"},
                title='Read ["table"]',
            ),
            block_node(
                "write",
                "UpdateData",
                modelName={"modelName": "gxp_table"},
                updateParams=[{"attribute": "status", "name": {"code": "nextStatus"}}],
            ),
            block_node(
                "call",
                "CallPublicAction",
                actionName={"code": "ACTION01", "name": "下游动作"},
            ),
            block_node(
                "filter",
                "DataFilter",
                name={"value": "paper", "label": "试卷"},
            ),
            {
                **block_node("define", "SetVariable"),
                "paramsValue": {
                    "inputParams": {"variableValue": {"code": "1"}},
                    "outputParams": {"variableName": {"code": "counter"}},
                },
            },
            block_node(
                "assign",
                "SetVariableValue",
                variableName={"code": "counter"},
                attributeValue={"code": "2"},
            ),
        ]
        analyzer = ControlFlowAnalyzer()
        result = analyzer.inspect(design(nodes), group="main")
        edge_types = {edge["type"] for edge in result["graph"]["edges"]}
        self.assertTrue(
            {"reads", "writes", "maps_field", "calls", "filters", "defines", "assigns"}
            <= edge_types
        )
        first_ids = [node["id"] for node in result["graph"]["nodes"]]
        second_ids = [node["id"] for node in analyzer.inspect(design(nodes), group="main")["graph"]["nodes"]]
        self.assertEqual(first_ids, second_ids)
        self.assertNotIn('["table"]', result["views"]["control_mermaid"])
        self.assertNotIn("gxp_table", result["views"]["control_mermaid"])
        self.assertIn("gxp_table", result["views"]["dependency_mermaid"])
        truncated = analyzer.inspect(design(nodes), group="main", max_nodes=3)
        self.assertTrue(truncated["truncation"]["control_tree_omitted"])
        self.assertEqual("", truncated["views"]["tree_text"])

    def test_periodic_training_scenario_matrix(self) -> None:
        nodes = [
            block_node("outer", "IfCondition", filters=[predicate("periodic_training", "NotEqualNull")]),
            block_node(
                "inner",
                "IfCondition",
                filters=[
                    predicate("periodic_training", "Equal", "'Y'"),
                    predicate("periodic", "EqualNull"),
                ],
            ),
            block_node("missing-period", "ExitAction"),
            block_node("inner-end", "IfEnd"),
            block_node("outer-else", "Else"),
            block_node("missing-training", "ExitAction"),
            block_node("outer-end", "IfEnd"),
        ]
        scenarios = {
            "Y-with-period": {"periodic_training": "Y", "periodic": 12},
            "Y-without-period": {"periodic_training": "Y", "periodic": None},
            "N": {"periodic_training": "N"},
            "null": {"periodic_training": None},
            "unknown": {},
        }
        matrix = ControlFlowAnalyzer().inspect(
            design(nodes), group="main", scenarios=scenarios
        )["scenario_matrix"]
        by_name = {item["name"]: item for item in matrix}
        reachable = lambda name: {
            item["node_key"] for item in by_name[name]["statically_reachable_nodes"]
        }
        self.assertNotIn("missing-period", reachable("Y-with-period"))
        self.assertIn("missing-period", reachable("Y-without-period"))
        self.assertNotIn("missing-period", reachable("N"))
        self.assertIn("missing-training", reachable("null"))
        self.assertTrue(by_name["unknown"]["unresolved_inputs"])


class InspectActionCompatibilityTests(unittest.TestCase):
    def test_inspect_action_old_fields_remain_and_control_flow_is_incremental(self) -> None:
        nodes = [block_node("if", "IfCondition"), block_node("end", "IfEnd")]
        item = CanvasInspector().inspect(design(nodes), node_key="if")[0]
        for key in ("action_group", "group_key", "canvas_line", "parent_path", "facts"):
            self.assertIn(key, item)
        self.assertEqual("if_root", item["control_flow"]["role"])

    def test_compare_reports_condition_branch_pairing_and_structure_changes(self) -> None:
        published = design(
            [
                block_node("if", "IfCondition", filters=[predicate("x", "Equal", "1")]),
                block_node("body", "ExitAction"),
                block_node("end", "IfEnd"),
            ]
        )
        draft = design(
            [
                block_node("if", "IfCondition", filters=[predicate("x", "Equal", "2")]),
                block_node("body", "ExitAction"),
                block_node("else", "Else"),
                block_node("end", "IfEnd"),
            ]
        )
        semantic = CanvasInspector.compare(published, draft)["semantic"]
        self.assertEqual("valid", semantic["published_structure_status"])
        self.assertEqual("valid", semantic["draft_structure_status"])
        self.assertEqual("if", semantic["condition_changes"][0]["node_key"])
        self.assertTrue(semantic["node_branch_changes"])
        self.assertTrue(semantic["pairing_changes"])

        invalid = design([block_node("if", "IfCondition")])
        changed = CanvasInspector.compare(published, invalid)["semantic"]
        self.assertTrue(changed["structure_status_changed"])
        self.assertEqual("invalid", changed["draft_structure_status"])


if __name__ == "__main__":
    unittest.main()
