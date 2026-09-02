from __future__ import annotations

import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = PLUGIN_ROOT / "skills" / "gxp-lowcode-debug"


class SkillContractTests(unittest.TestCase):
    def test_dropdown_routing_and_polarity_gate_are_present(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for term in (
            "试卷下拉",
            "值被清空",
            "无可选值",
            "文件对应试卷",
            "岗位矩阵申请",
            "岗位培训申请",
            "DataFilter",
            "流程页面反查",
        ):
            self.assertIn(term, skill)
        self.assertIn("当前现象", skill)
        self.assertIn("期望规则", skill)
        self.assertIn("无匹配时行为", skill)
        self.assertIn("会话锚点", skill)
        self.assertIn("include_generated_csharp=false", skill)

    def test_component_filter_reference_is_driven_by_current_user_rule(self) -> None:
        reference = (
            SKILL_ROOT / "references" / "component-filter-audit.md"
        ).read_text(encoding="utf-8")
        self.assertIn("用户本次确认的业务不变量", reference)
        self.assertIn("不得预设字段名或字段组合", reference)
        self.assertIn("全部约束字段", reference)
        self.assertIn("全部 writers", reference)
        self.assertIn("累计小于 120 KB", reference)

    def test_default_prompt_starts_with_rule_lock_and_compact_reads(self) -> None:
        prompt = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("锁定当前现象、期望规则和无匹配行为", prompt)
        self.assertIn("紧凑只读检查", prompt)

    def test_readonly_skill_never_transitions_to_editor(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        prompt = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("只读到编辑的显式授权门禁", skill)
        self.assertIn("不得调用任何 `gxp-lowcode-editor` MCP 工具", skill)
        self.assertIn("不得加载或主动转入 `gxp-lowcode-edit`", skill)
        self.assertIn("输出修改方案不构成编辑授权", skill)
        self.assertIn("当前消息中明确调用 `$gxp-lowcode-edit`", skill)
        self.assertIn("不得调用或转入 gxp-lowcode-edit", prompt)

    def test_source_escalation_is_hit_driven_and_bounded(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        reference = (SKILL_ROOT / "references" / "source-code-evidence.md").read_text(encoding="utf-8")
        script = SKILL_ROOT / "scripts" / "search_source_evidence.py"
        for term in ("组件实现", "请求参数", "API", "Controller", "Service", "source_hints"):
            self.assertIn(term, skill)
        self.assertIn("低代码证据已足够，无需查源码", skill)
        self.assertIn(r"G:\hoyi\updateComponents\gxp2.components", reference)
        self.assertIn(r"G:\hoyi\updateWeb\gxp2.web", reference)
        self.assertIn("32 KB", reference)
        self.assertTrue(script.is_file())

    def test_cpm_snapshot_is_candidate_layer_and_knowledge_is_progressive(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        reference = (SKILL_ROOT / "references" / "cpm-snapshot-routing.md").read_text(encoding="utf-8")
        for term in ("CPM 快照", "inspect_page_snapshot", "get_cpm_knowledge", "当前发布副本"):
            self.assertIn(term, skill)
        self.assertIn("快照候选，当前发布未确认", reference)
        self.assertIn("references/components/<组件名>.md", reference)

    def test_nested_control_flow_requires_visible_structure_and_scenarios(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for term in (
            "inspect_control_flow",
            "两层及以上嵌套",
            "views.tree_text",
            "structure_status != valid",
            "结构候选/待确认",
            "不得据此判定逻辑 Bug",
            "scenario_matrix",
            "每个业务分支与空值边界",
            "三态静态实际路径",
        ):
            self.assertIn(term, skill)


if __name__ == "__main__":
    unittest.main()
