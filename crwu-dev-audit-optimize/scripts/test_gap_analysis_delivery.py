#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import gap_analysis_delivery as delivery

SAMPLE = SCRIPT_DIR / "examples" / "gap-analysis.sample.json"
TEMPLATE = SCRIPT_DIR.parent / "template" / "gap-analysis-report.html"


def load_sample() -> dict:
    return json.loads(SAMPLE.read_text(encoding="utf-8"))


class GapAnalysisValidationTest(unittest.TestCase):
    def test_sample_passes(self):
        self.assertEqual([], delivery.validate(load_sample()))

    def test_every_actionable_gap_has_a_fix(self):
        result = load_sample()
        result["reviewerOnlyItems"][0]["linkedFixIds"] = []
        errors = delivery.validate(result)
        self.assertTrue(any("linkedFixIds" in item for item in errors), errors)

    def test_every_fix_points_back_to_a_gap(self):
        result = load_sample()
        result["repairPlans"][0]["sourceGapIds"] = []
        errors = delivery.validate(result)
        self.assertTrue(any("sourceGapIds" in item for item in errors), errors)

    def test_non_actionable_gap_cannot_enter_repair_plan(self):
        result = load_sample()
        result["repairPlans"][0]["sourceGapIds"].append("L-03")
        errors = delivery.validate(result)
        self.assertTrue(any("L-resolved" in item for item in errors), errors)

    def test_kb_plan_is_manual_only(self):
        result = load_sample()
        kb = next(item for item in result["repairPlans"] if item["type"] == "kb_manual")
        kb["executionMode"] = "ai"
        errors = delivery.validate(result)
        self.assertTrue(any("manual_only" in item for item in errors), errors)

    def test_duplicate_gap_id_is_rejected(self):
        result = load_sample()
        result["reviewerOnlyItems"].append(copy.deepcopy(result["reviewerOnlyItems"][0]))
        result["summary"]["reviewerOnly"] += 1
        result["summary"]["actionableMisses"] += 1
        errors = delivery.validate(result)
        self.assertTrue(any("重复" in item for item in errors), errors)

    def test_absolute_paths_are_rejected(self):
        result = load_sample()
        result["project"]["auditResult"] = "/Users/example/审核意见.json"
        errors = delivery.validate(result)
        self.assertTrue(any("绝对路径" in item for item in errors), errors)


class GapAnalysisRenderTest(unittest.TestCase):
    def setUp(self):
        self.result = load_sample()

    def test_is_single_file_and_offline(self):
        document = delivery.render(self.result)
        for token in ("<link", "script src", "@import"):
            self.assertNotIn(token, document)
        self.assertIn("echarts.init", document)

    def test_required_sections_exist(self):
        document = delivery.render(self.result)
        for region in (
            "gap-summary",
            "gap-charts",
            "reviewer-only-table",
            "execution-trace",
            "gap-fix-map",
            "manual-kb-plans",
            "skill-repair-prompts",
            "validation-plan",
        ):
            self.assertIn(f'id="{region}"', document)

    def test_a4_and_table_print_contract(self):
        document = delivery.render(self.result)
        self.assertIn("@page { size: A4", document)
        self.assertIn("thead { display: table-header-group; }", document)
        self.assertIn("break-inside: avoid", document)

    def test_embedded_payload_is_parseable(self):
        document = delivery.render(self.result)
        match = re.search(
            r'<script id="gap-analysis-data" type="application/json">(.*?)</script>',
            document,
            re.S,
        )
        self.assertIsNotNone(match)
        self.assertEqual(self.result["reportId"], json.loads(match.group(1))["reportId"])

    def test_manual_and_skill_outputs_are_separated(self):
        kb = next(item for item in self.result["repairPlans"] if item["type"] == "kb_manual")
        manual = delivery.build_manual_kb_instruction(kb)
        prompt = delivery.build_skill_prompt(self.result, ["FIX-SKILL-01"])
        self.assertIn("FIX-KB-01", manual)
        self.assertIn("仅人工", manual)
        self.assertIn("FIX-SKILL-01", prompt)
        self.assertIn("crwu-dws 只读", prompt)
        self.assertIn("不得对知识库执行任何写操作", prompt)
        self.assertNotIn("修改知识库", prompt)

    def test_unapproved_skill_plan_is_rejected(self):
        self.result["repairPlans"][1]["approvalState"] = "pending"
        with self.assertRaisesRegex(ValueError, "未批准"):
            delivery.build_skill_prompt(self.result, ["FIX-SKILL-01"])

    def test_root_cause_chart_excludes_non_actionable_items(self):
        self.assertEqual({"K2": 1, "S2": 1}, delivery.actionable_cause_counts(self.result))

    def test_documented_cli_flags_validate_and_render(self):
        self.assertEqual(0, delivery.main(["validate", "--input", str(SAMPLE)]))
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report.html"
            self.assertEqual(
                0,
                delivery.main(
                    ["render", "--input", str(SAMPLE), "--output", str(output)]
                ),
            )
            self.assertIn("AI—人工审核差距分析", output.read_text(encoding="utf-8"))


class SkillIntegrationTest(unittest.TestCase):
    def test_skill_routes_gap_analysis_mode(self):
        skill = (SCRIPT_DIR.parent / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("AI—人工差距分析模式", skill)
        self.assertIn("references/03-AI人工差距分析流程.md", skill)

    def test_skill_keeps_knowledge_base_manual_only(self):
        files = [
            SCRIPT_DIR.parent / "SKILL.md",
            SCRIPT_DIR.parent / "references" / "03-AI人工差距分析流程.md",
        ]
        text = "\n".join(path.read_text(encoding="utf-8") for path in files if path.is_file())
        self.assertIn("manual_only", text)
        self.assertIn("禁止修改知识库", text)

    def test_gap_reference_defines_bidirectional_traceability(self):
        reference = SCRIPT_DIR.parent / "references" / "03-AI人工差距分析流程.md"
        text = reference.read_text(encoding="utf-8")
        self.assertIn("sourceGapIds", text)
        self.assertIn("linkedFixIds", text)
        self.assertIn("L-open", text)
        self.assertIn("L-resolved", text)


if __name__ == "__main__":
    unittest.main()
