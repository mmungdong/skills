#!/usr/bin/env python3
"""AuditResult 校验与 HTML 渲染的契约测试（送达规范 v1.0）。

运行：在技能目录内 `python3 scripts/test_audit_delivery.py`
本测试**自洽**：只依赖本技能 `scripts/` 内的脚本、schema 与样例，可随技能一起安装。
"""

from __future__ import annotations

import ast
import contextlib
import copy
import html
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit_delivery as delivery  # noqa: E402

MODULE_PATH = Path(__file__).resolve().parent / "audit_delivery.py"
SAMPLE_PATH = Path(__file__).resolve().parent / "examples" / "audit-result.sample.json"

REGION_ORDER = [
    "project-info",
    "summary",
    "actionable-issues",
    "manual-confirmation-items",
    "audit-basis",
    "review-comparison",
    "scope-and-not-checked",
    "professional-trail",
    "file-trace",
]


def load_sample() -> dict:
    with SAMPLE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def module_string_constants() -> set:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    values = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.add(node.value)
    return values


def strip_css_and_scripts(document: str) -> str:
    document = re.sub(r"<style>.*?</style>", " ", document, flags=re.S)
    document = re.sub(r"<script.*?</script>", " ", document, flags=re.S)
    return document


def text_nodes(document: str):
    body = strip_css_and_scripts(document)
    for raw in re.findall(r">([^<>]+)<", body):
        value = html.unescape(raw).strip()
        if value:
            yield value


class AuditResultValidationTest(unittest.TestCase):
    def test_sample_passes(self):
        self.assertEqual([], delivery.validate(load_sample()))

    def test_missing_material_evidence_is_rejected(self):
        result = load_sample()
        result["issues"][0]["materialEvidence"] = []
        errors = delivery.validate(result)
        self.assertTrue(any("materialEvidence 至少一条" in error for error in errors), errors)

    def test_rule_defect_fail_requires_rule_evidence(self):
        result = load_sample()
        result["issues"][0]["ruleEvidence"] = []
        result["auditBasis"]["rules"][0]["usedByIssueIds"] = []
        result["auditBasis"]["rules"][0]["usageCount"] = 0
        errors = delivery.validate(result)
        self.assertTrue(any("必须同时具备规则证据与材料证据" in error for error in errors), errors)

    def test_counts_must_be_recomputable(self):
        result = load_sample()
        result["summary"]["counts"]["fail"] = 0
        errors = delivery.validate(result)
        self.assertTrue(any("summary.counts.fail" in error for error in errors), errors)

    def test_phase_order_is_enforced(self):
        result = load_sample()
        result["phaseControl"]["reviewAccessedAt"] = "2026-09-09T09:00:00+08:00"
        errors = delivery.validate(result)
        self.assertTrue(any("reviewAccessedAt 必须晚于 phase1FrozenAt" in error for error in errors), errors)

    def test_phase2_requires_review_comparison_per_issue(self):
        result = load_sample()
        result["issues"][0]["reviewComparison"] = {"status": "not_performed"}
        errors = delivery.validate(result)
        self.assertTrue(any("必须具有 reviewComparison" in error for error in errors), errors)

    def test_external_formal_must_not_claim_current_version(self):
        result = load_sample()
        rule = result["auditBasis"]["rules"][0]
        rule["version"] = "现行"
        errors = delivery.validate(result)
        self.assertTrue(any("不得宣称" in error for error in errors), errors)

    def test_usage_count_and_used_by_are_recomputed(self):
        result = load_sample()
        result["auditBasis"]["rules"][0]["usageCount"] = 7
        errors = delivery.validate(result)
        self.assertTrue(any("usageCount 必须可由明细重算" in error for error in errors), errors)

    def test_review_bands_must_match_details(self):
        result = load_sample()
        result["reviewComparison"]["bands"]["overlap"] = 0
        errors = delivery.validate(result)
        self.assertTrue(any("bands.overlap" in error for error in errors), errors)

    def test_kb_relative_path_must_be_relative(self):
        result = load_sample()
        result["auditBasis"]["rules"][0]["kbRelativePath"] = "/Users/example/kb/rule.md"
        errors = delivery.validate(result)
        self.assertTrue(any("kbRelativePath" in error or "绝对路径" in error for error in errors), errors)

    def test_absolute_path_and_node_id_are_forbidden(self):
        result = load_sample()
        result["issues"][0]["problemDescription"] = "见 /Users/example/报告.docx"
        errors = delivery.validate(result)
        self.assertTrue(any("绝对路径" in error for error in errors), errors)

        result = load_sample()
        result["auditTask"]["profile"]["routeProfile"] = {"nodeId": "abc123"}
        errors = delivery.validate(result)
        self.assertTrue(any("nodeId" in error for error in errors), errors)

    def test_not_checked_reason_code_enum(self):
        result = load_sample()
        result["scope"]["notCheckedItems"][0]["reasonCode"] = "whatever"
        errors = delivery.validate(result)
        self.assertTrue(any("reasonCode 取值非法" in error for error in errors), errors)


class AuditResultRenderTest(unittest.TestCase):
    def setUp(self):
        self.result = load_sample()
        self.document = delivery.render(self.result)

    def test_sections_in_required_order(self):
        positions = []
        for region in REGION_ORDER:
            index = self.document.find('id="{0}"'.format(region))
            self.assertNotEqual(-1, index, "缺少区域 {0}".format(region))
            positions.append(index)
        self.assertEqual(sorted(positions), positions, "区域顺序必须符合 §3 交付结构")

    def test_self_contained_and_offline_safe(self):
        for token in ("http://", "https://", "<link", "script src", "@import"):
            self.assertNotIn(token, self.document)
        self.assertIn("<style>", self.document)
        self.assertIn('type="application/json"', self.document)

    def test_a4_print_and_black_white_readability(self):
        self.assertIn("@page { size: A4", self.document)
        self.assertIn("break-inside: avoid", self.document)
        self.assertIn("thead { display: table-header-group; }", self.document)
        for issue in self.result["issues"]:
            label = delivery.SEVERITY_LABEL[issue["severity"]]
            self.assertIn('<span class="severity-label">{0}</span>'.format(label), self.document)
        for severity in delivery.SEVERITY_CLASS.values():
            self.assertIn(severity, self.document)

    def test_professional_trail_folded_by_default(self):
        self.assertIn('<details id="professional-trail">', self.document)

    def test_embedded_json_matches_digests(self):
        match = re.search(
            r'<script id="audit-result" type="application/json">(.*?)</script>', self.document, re.S
        )
        self.assertIsNotNone(match)
        embedded = json.loads(match.group(1).replace("<\\/", "</"))
        file_trace = embedded["fileTrace"]
        self.assertEqual(delivery.RENDERER_VERSION, file_trace["rendererVersion"])
        without_digests = copy.deepcopy(embedded)
        without_digests["fileTrace"]["sourceDigest"] = ""
        without_digests["fileTrace"]["embeddedJsonDigest"] = ""
        self.assertEqual(delivery.sha256_hex(delivery.canonical_json(without_digests)), file_trace["sourceDigest"])
        with_source = copy.deepcopy(embedded)
        with_source["fileTrace"]["embeddedJsonDigest"] = ""
        self.assertEqual(delivery.sha256_hex(delivery.canonical_json(with_source)), file_trace["embeddedJsonDigest"])
        self.assertEqual([], delivery.validate(embedded, rendered=True, expect_renderer=True))

    def test_render_is_deterministic(self):
        self.assertEqual(self.document, delivery.render(load_sample()))

    def test_dynamic_content_is_escaped(self):
        result = load_sample()
        payload = "<script>alert(1)</script>"
        result["issues"][0]["problemDescription"] = payload
        document = delivery.render(result)
        self.assertNotIn(payload, document)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", document)
        # 嵌入 JSON 必须安全转义 <，全文只能有本页面自己的一个结束标签
        self.assertEqual(1, document.count("</script>"))
        self.assertIn("\\u003cscript>alert(1)", document)

    def test_empty_lists_show_explicit_message(self):
        result = load_sample()
        result["manualConfirmationItems"] = []
        result["summary"]["counts"]["pendingConfirmation"] = 0
        result["reviewComparison"]["status"] = "not_performed"
        result["reviewComparison"]["bands"] = {"overlap": 0, "aiOnly": 0, "divergent": 0, "reviewerOnly": 0}
        result["reviewComparison"]["reviewerOnlyItems"] = []
        for issue in result["issues"]:
            issue["reviewComparison"] = {"status": "not_performed"}
        result["scope"]["notCheckedItems"] = []
        result["summary"]["counts"]["notChecked"] = 0
        result["professionalTrail"]["adjudications"] = []
        result["professionalTrail"]["checkRecords"] = []
        self.assertEqual([], delivery.validate(result))
        document = delivery.render(result)
        self.assertIn(delivery.EMPTY_TEXT, document)
        self.assertIn("需要人工确认事项", document)
        self.assertIn("未检查项", document)

    def test_renderer_does_not_author_business_text(self):
        """文本节点只能来自受控标签常量或输入数据，不得拼接出新句子（§12.2 / §10.3）。"""
        allowed = set(module_string_constants())
        for scalar in delivery.iter_all_scalars(self.result):
            allowed.add(scalar)

        def collect(value):
            if isinstance(value, dict):
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                allowed.add("、".join(str(item) for item in value))
                for item in value:
                    collect(item)

        collect(self.result)
        for node in text_nodes(self.document):
            if re.fullmatch(r"[0-9a-f]{64}", node):
                continue  # 渲染期计算的来源/嵌入摘要，可由输入确定性重算
            self.assertIn(node, allowed, "渲染器生成了非标签/非数据的文本：{0}".format(node))


class AuditDeliveryCliTest(unittest.TestCase):
    """编排层调用的三个子命令：validate / digest / render。"""

    def test_digest_matches_canonical_sha256(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = delivery.main(["digest", str(SAMPLE_PATH)])
        self.assertEqual(0, code)
        expected = delivery.sha256_hex(delivery.canonical_json(load_sample()))
        self.assertEqual(expected, buffer.getvalue().strip())

    def test_validate_cli_exit_codes(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, delivery.main(["validate", str(SAMPLE_PATH)]))
        broken = load_sample()
        broken["issues"][0]["materialEvidence"] = []
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(1, delivery.main(["validate", str(path)]))

    def test_render_cli_refuses_invalid_input(self):
        broken = load_sample()
        broken["summary"]["counts"]["fail"] = 99
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "broken.json"
            out = Path(tmp) / "out.html"
            path.write_text(json.dumps(broken, ensure_ascii=False), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(1, delivery.main(["render", str(path), "--out", str(out)]))
            self.assertFalse(out.exists(), "校验失败时不得产出 HTML")


class ReviewerOnlyInFileResolutionTest(unittest.TestCase):
    """复核独有项在件核验三态（L-resolved/open/unclosed/uncheckable）的校验契约。

    以样例为基底，只改 phaseControl.reviewComparison，隔离断言目标字段，
    不触发与三态无关的其他校验。
    """

    def _reviewer_item(self, **over):
        item = {
            "itemId": "R-1",
            "title": "人工复核独有项",
            "reviewerEvidence": {"file": "复核意见.pdf", "locator": "P3", "quote": "……"},
            "inFileResolution": "L-open",
            "inFileEvidence": {"file": "定稿.docx", "locator": "P12"},
            "handling": "进入隔离补审",
        }
        item.update(over)
        return item

    def _result(self, reviewer_item):
        result = load_sample()
        result["reviewComparison"] = {
            "status": "not_performed",
            "bands": {"overlap": 0, "aiOnly": 0, "divergent": 0, "reviewerOnly": 1},
            "reviewerOnlyItems": [reviewer_item],
            "metrics": {"denominator": "人工复核共 5 项"},
        }
        return result

    def _errors(self, item):
        return delivery.validate(self._result(item))

    def test_missing_inFileResolution_is_rejected(self):
        it = self._reviewer_item(); del it["inFileResolution"]
        self.assertTrue(any("inFileResolution" in e for e in self._errors(it)))

    def test_invalid_resolution_value_is_rejected(self):
        self.assertTrue(any("inFileResolution" in e for e in self._errors(self._reviewer_item(inFileResolution="L-foo"))))

    def test_L_open_requires_inFileEvidence(self):
        it = self._reviewer_item(); del it["inFileEvidence"]
        self.assertTrue(any("inFileEvidence.file" in e for e in self._errors(it)))

    def test_L_unclosed_requires_closureEvidence(self):
        it = self._reviewer_item(inFileResolution="L-unclosed")
        self.assertTrue(any("closureEvidence" in e for e in self._errors(it)))

    def test_L_uncheckable_allows_missing_inFileEvidence(self):
        it = self._reviewer_item(inFileResolution="L-uncheckable"); del it["inFileEvidence"]
        self.assertFalse(any("inFileEvidence" in e for e in self._errors(it)), self._errors(it))

    def test_dual_denominator_is_accepted(self):
        it = self._reviewer_item()
        r = self._result(it)
        r["reviewComparison"]["metrics"] = {
            "denominator": "含 L-resolved：5 项", "aiHitRate": "60%",
            "denominatorExclResolved": "仅 L-open：2 项", "aiHitRateExclResolved": "50%",
        }
        self.assertFalse(any("denominator" in e for e in delivery.validate(r)), delivery.validate(r))



class AiScorecardTest(unittest.TestCase):
    """AI 审核评分卡（自评六维 + 复审校正 + 审核错误项）的校验契约。"""

    def _result(self, **over):
        r = load_sample()
        if "level" in over:
            r["aiScorecard"]["level"] = over["level"]
        return r

    def _dim(self, r, key):
        return next(d for d in r["aiScorecard"]["dimensions"] if d["key"] == key)

    def test_sample_scorecard_is_valid(self):
        self.assertEqual([], delivery.validate(load_sample()))

    def test_missing_dimension_is_rejected(self):
        r = load_sample()
        r["aiScorecard"]["dimensions"] = [d for d in r["aiScorecard"]["dimensions"]
                                          if d["key"] != "judgment_quality"]
        self.assertTrue(any("恰好覆盖六维" in e for e in delivery.validate(r)))

    def test_score_out_of_range_or_step_is_rejected(self):
        for bad in (10.5, -0.5, 6.3):
            r = load_sample()
            self._dim(r, "self_correction")["score"] = bad
            self.assertTrue(any("0–10 且 0.5 的整数倍" in e for e in delivery.validate(r)), bad)

    def test_empty_basis_is_rejected(self):
        r = load_sample()
        self._dim(r, "coverage_completeness")["basis"] = " "
        self.assertTrue(any("basis 不得为空" in e for e in delivery.validate(r)))

    def test_ai_only_must_be_recomputable(self):
        r = load_sample()
        r["aiScorecard"]["composites"]["aiOnly"] = 9.5
        self.assertTrue(any("aiOnly 必须可由六维均值" in e for e in delivery.validate(r)))

    def test_correction_from_must_equal_first_score(self):
        r = load_sample()
        r["aiScorecard"]["corrections"][0]["from"] = 5.0
        self.assertTrue(any("只增不覆盖" in e for e in delivery.validate(r)))

    def test_correction_requires_reason(self):
        r = load_sample()
        r["aiScorecard"]["corrections"][0]["reason"] = ""
        self.assertTrue(any("校正必须给理由" in e for e in delivery.validate(r)))

    def test_first_review_with_corrections_is_rejected(self):
        r = self._result(level="初审")
        r["aiScorecard"]["corrections"] = []
        r["aiScorecard"]["composites"].pop("withHumanLoop", None)
        self.assertEqual([], delivery.validate(r))
        r["aiScorecard"]["corrections"] = [{"key": "self_correction", "from": 7.0, "to": 7.5, "reason": "x"}]
        self.assertTrue(any("初审不得事后校正" in e for e in delivery.validate(r)))

    def test_second_review_requires_recomputable_with_human_loop(self):
        r = load_sample()
        r["aiScorecard"]["composites"]["withHumanLoop"] = 9.0
        self.assertTrue(any("withHumanLoop 必须可由复审校正后" in e for e in delivery.validate(r)))

    def test_invalid_error_kind_and_duplicate_id_are_rejected(self):
        r = load_sample()
        r["selfAuditErrors"][0]["kind"] = "typo"
        r["selfAuditErrors"][1]["errorId"] = r["selfAuditErrors"][0]["errorId"]
        errors = delivery.validate(r)
        self.assertTrue(any("kind 取值非法" in e for e in errors))
        self.assertTrue(any("errorId 重复" in e for e in errors))

    def test_scorecard_renders_as_tables(self):
        html = delivery.render(load_sample())
        self.assertIn('id="ai-scorecard"', html)
        for label in ("本次 AI 审核六维评分卡", "初审分", "复审校正", "最终分",
                      "综合·AI 单机", "综合·含人机复核闭环", "AI 审核错误项"):
            self.assertIn(label, html)



if __name__ == "__main__":
    unittest.main(verbosity=2)
