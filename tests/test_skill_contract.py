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

    def test_component_filter_reference_encodes_golden_business_rule(self) -> None:
        reference = (
            SKILL_ROOT / "references" / "component-filter-audit.md"
        ).read_text(encoding="utf-8")
        self.assertIn("file_id 且 file_version", reference)
        self.assertIn("空集合，下拉不可选择", reference)
        self.assertIn("全部 writers", reference)
        self.assertIn("累计小于 120 KB", reference)

    def test_default_prompt_starts_with_rule_lock_and_compact_reads(self) -> None:
        prompt = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertIn("锁定当前现象、期望规则和无匹配行为", prompt)
        self.assertIn("紧凑只读检查", prompt)


if __name__ == "__main__":
    unittest.main()
