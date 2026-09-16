#!/usr/bin/env python3
"""AuditResult 校验与 HTML 渲染的契约测试（送达规范 v1.1）。

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
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "template" / "audit-report.html"

REGION_ORDER = [
    "project-info",
    "summary",
    "actionable-issues",
    "external-data-verification",
    "review-comparison",
    "ai-scorecard",
    "manual-confirmation-items",
    "audit-basis",
    "scope-and-not-checked",
    "professional-trail",
    "file-trace",
]


def load_sample() -> dict:
    with SAMPLE_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def with_structured_review_comparison() -> dict:
    """构造新版逐条复核事实源；统计应全部能从 reviewItems 重算。"""
    result = load_sample()
    comparison = result["reviewComparison"]
    comparison["reviewFiles"] = [
        {
            "order": 1,
            "level": "一级复核",
            "displayName": "01-一级复核意见.docx",
            "version": "v1",
        },
        {
            "order": 2,
            "level": "二级复核",
            "displayName": "02-二级复核意见.docx",
            "version": "v2",
        },
    ]
    comparison["reviewItems"] = [
        {
            "itemId": "RV-001",
            "title": "报告结论与测算表不一致",
            "module": "数据勾稽",
            "reviewLevel": "一级复核",
            "matchStatus": "exact",
            "hitExplanation": {
                "reviewerScope": "specific",
                "matchedAspects": ["报告结论与测算表不一致，AI 已定位到同一处差异"],
                "unmatchedAspects": [],
                "rationale": "AI 复现了复核的同一判断。",
            },
            "linkedIssueIds": ["ISS-DC-003"],
            "reviewerEvidence": {
                "file": "01-一级复核意见.docx",
                "locator": "第1条",
                "quote": "报告结论与测算表不一致。",
            },
            "inFileResolution": "L-open",
            "inFileEvidence": {
                "file": "报告-复审版.docx",
                "locator": "第12页",
                "quote": "结论仍为1,244.00。",
            },
            "handling": "继续修改",
        },
        {
            "itemId": "RV-002",
            "title": "披露文字已补充",
            "module": "报告披露",
            "reviewLevel": "一级复核",
            "matchStatus": "miss",
            "hitExplanation": {
                "reviewerScope": "specific",
                "matchedAspects": [],
                "unmatchedAspects": ["评估范围说明的补充情况"],
                "rationale": "AI 未就该条提出任何判断。",
            },
            "linkedIssueIds": [],
            "reviewerEvidence": {
                "file": "01-一级复核意见.docx",
                "locator": "第2条",
                "quote": "补充评估范围说明。",
            },
            "inFileResolution": "L-resolved",
            "inFileEvidence": {
                "file": "报告-复审版.docx",
                "locator": "第5页",
                "quote": "已补充完整。",
            },
            "handling": "无需继续处理",
        },
        {
            "itemId": "RV-003",
            "title": "答复称已修复但仍未落实",
            "module": "市场法",
            "reviewLevel": "二级复核",
            "matchStatus": "miss",
            "hitExplanation": {
                "reviewerScope": "specific",
                "matchedAspects": [],
                "unmatchedAspects": ["时间修正依据的补充情况"],
                "rationale": "AI 未就该条提出任何判断。",
            },
            "linkedIssueIds": [],
            "reviewerEvidence": {
                "file": "02-二级复核意见.docx",
                "locator": "第1条",
                "quote": "补充时间修正依据。",
            },
            "inFileResolution": "L-unclosed",
            "inFileEvidence": {
                "file": "评估说明-复审版.docx",
                "locator": "市场法章节",
                "quote": "仍未见时间修正依据。",
            },
            "closureEvidence": {
                "file": "项目答复.docx",
                "locator": "答复1",
                "quote": "已补充。",
            },
            "handling": "优先回客户",
        },
        {
            "itemId": "RV-004",
            "title": "扫描件内容无法核验",
            "module": "市场法",
            "reviewLevel": "二级复核",
            "matchStatus": "partial",
            "hitExplanation": {
                "reviewerScope": "general",
                "matchedAspects": ["扫描件附件的核验必要性（AI 已出 ISS-MKT-007）"],
                "unmatchedAspects": ["附件逐页内容的可读性判定"],
                "rationale": "复核条目笼统，AI 覆盖了核验必要性与部分内容，未逐页核验。",
            },
            "linkedIssueIds": ["ISS-MKT-007"],
            "reviewerEvidence": {
                "file": "02-二级复核意见.docx",
                "locator": "第2条",
                "quote": "核验扫描件附件。",
            },
            "inFileResolution": "L-uncheckable",
            "handling": "补充可读文件",
        },
    ]
    comparison["metrics"] = {
        "total": 4,
        "resolved": 1,
        "uncheckable": 1,
        "evaluable": 2,
        "exactHits": 1,
        "partialHits": 0,
        "misses": 1,
        "hitRate": 50.0,
        "exactRate": 50.0,
        "partialRate": 0.0,
        "missRate": 50.0,
        "strictHitRate": 50.0,
        "coverageRate": 50.0,
    }
    return result


def module_string_constants() -> set:
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    values = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            values.add(node.value)
    if TEMPLATE_PATH.is_file():
        values.update(text_nodes(TEMPLATE_PATH.read_text(encoding="utf-8")))
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

    def test_knowledge_base_files_require_path_and_exported_at(self):
        """渲染器按 path 显示知识库文件名；误用 kbRelativePath 等别名会只显示时间。"""
        result = load_sample()
        result["auditBasis"]["knowledgeBaseFiles"] = [
            {"kbRelativePath": "06-规则库/某规则", "exportedAt": "2026-09-10T09:00:00+08:00"}
        ]
        errors = delivery.validate(result)
        self.assertTrue(any("knowledgeBaseFiles[0].path" in error for error in errors), errors)

        result = load_sample()
        result["auditBasis"]["knowledgeBaseFiles"] = [{"path": "06-规则库/某规则"}]
        errors = delivery.validate(result)
        self.assertTrue(any("knowledgeBaseFiles[0].exportedAt" in error for error in errors), errors)

        result = load_sample()
        result["auditBasis"]["knowledgeBaseFiles"] = [
            {"path": "/Users/example/kb/rule.md", "exportedAt": "2026-09-10T09:00:00+08:00"}
        ]
        errors = delivery.validate(result)
        self.assertTrue(any("knowledgeBaseFiles[0].path" in error for error in errors), errors)

        result = load_sample()
        result["auditBasis"]["knowledgeBaseFiles"] = ["06-规则库/某规则"]
        errors = delivery.validate(result)
        self.assertTrue(any("knowledgeBaseFiles[0] 必须是对象" in error for error in errors), errors)

    def test_knowledge_base_file_path_is_rendered(self):
        result = load_sample()
        document = delivery.render(result)
        self.assertIn("06-规则库/M-数据对齐-勾稽与一致性/清单-数据校对.md", document)
        self.assertNotIn('<span class="kb-path"></span>', document)

    def test_adjudication_row_keys_are_required(self):
        """裁定表按 recordId/itemRef/ruling(result) 渲染；三列齐缺会整表空白。"""
        base = load_sample()
        self.assertTrue(base["professionalTrail"]["adjudications"])

        result = load_sample()
        result["professionalTrail"]["adjudications"] = [{"applicability": "适用", "executed": True}]
        errors = delivery.validate(result)
        self.assertTrue(any("adjudications[0].recordId" in error for error in errors), errors)
        self.assertTrue(any("adjudications[0].itemRef" in error for error in errors), errors)
        self.assertTrue(any("adjudications[0] 必须给出" in error for error in errors), errors)

        result = load_sample()
        result["professionalTrail"]["adjudications"] = ["不是对象"]
        errors = delivery.validate(result)
        self.assertTrue(any("adjudications[0] 必须是对象" in error for error in errors), errors)

    def test_adjudication_row_falls_back_to_legacy_keys(self):
        result = load_sample()
        result["professionalTrail"]["adjudications"] = [
            {"chkId": "CHK-LEGACY", "checkItem": "旧键位条目", "ruling": "不符合：示例"}
        ]
        errors = delivery.validate(result)
        self.assertFalse([e for e in errors if "adjudications" in e], errors)
        document = delivery.render(result)
        self.assertIn("CHK-LEGACY", document)
        self.assertIn("旧键位条目", document)
        self.assertIn("不符合：示例", document)
        self.assertNotIn('<td></td><td></td><td></td>', document)

    def test_missing_in_file_evidence_is_not_rendered_blank(self):
        """L-uncheckable 无在件位置时应显示受控标签，不得留空白单元格（§10.3）。"""
        result = load_sample()
        item = result["reviewComparison"]["reviewerOnlyItems"][0]
        item["inFileResolution"] = "L-uncheckable"
        item.pop("inFileEvidence", None)
        errors = delivery.validate(result)
        self.assertFalse([e for e in errors if "inFileEvidence" in e], errors)
        document = delivery.render(result)
        self.assertIn(delivery.IN_FILE_ABSENT_LABEL, document)
        self.assertNotIn('<td class="value"></td>', document)


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

    def test_renderer_uses_standalone_template_with_sidebar_catalog(self):
        self.assertTrue(TEMPLATE_PATH.is_file(), "HTML 模板必须独立存放在 skill/template/")
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn("{{report_content}}", template)
        self.assertIn('class="report-catalog"', template)
        self.assertIn('aria-label="报告目录"', template)
        self.assertIn('class="report-shell"', template)
        for region in REGION_ORDER:
            self.assertIn('href="#{0}"'.format(region), template, "目录缺少区域 {0}".format(region))
            self.assertIn('href="#{0}"'.format(region), self.document, "渲染结果缺少目录项 {0}".format(region))

    def test_sidebar_is_responsive_and_hidden_for_print(self):
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        self.assertIn("position: sticky", template)
        self.assertIn("@media (max-width: 960px)", template)
        self.assertRegex(template, re.compile(r"@media print\s*\{.*?\.report-catalog\s*\{[^}]*display:\s*none", re.S))

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
            self.assertIn('severity-label">严重程度：{0}</span>'.format(label), self.document)
        for severity in delivery.SEVERITY_CLASS.values():
            self.assertIn(severity, self.document)

    def test_severity_palette_is_professional_and_not_full_card_tinted(self):
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        for color in ("#c2413b", "#b86b12", "#287596"):
            self.assertIn(color, template.lower())
        self.assertIn(".issue-card.sev-high { border-left-color: var(--high); }", template)
        self.assertNotIn("linear-gradient(90deg, var(--high-soft)", template)

    def test_professional_trail_folded_by_default(self):
        self.assertIn('<details id="professional-trail">', self.document)

    def test_scope_readability_uses_clear_icons_instead_of_booleans(self):
        start = self.document.find('id="scope-and-not-checked"')
        end = self.document.find('</section>', start)
        scope = self.document[start:end]
        self.assertIn('class="readable-status is-readable"', scope)
        self.assertIn('aria-label="可读">✅</span>', scope)
        self.assertIn('class="readable-status is-unreadable"', scope)
        self.assertIn('aria-label="不可读">❌</span>', scope)
        self.assertNotIn(">True<", scope)
        self.assertNotIn(">False<", scope)

    def test_header_leads_with_ai_audit_summary_and_compact_metrics(self):
        document = delivery.render(with_structured_review_comparison())
        expected_title = "中瑞世联AI审核报告 - PRJ-2026-0001"
        self.assertIn("<title>{0}</title>".format(expected_title), document)
        self.assertIn("<h1>{0}</h1>".format(expected_title), document)
        for label in ("AI 检出问题", "待人工确认", "未检查项", "命中率", "实际未落实"):
            self.assertIn(label, document)

    def test_issue_reasoning_is_folded_behind_explicit_control(self):
        document = delivery.render(with_structured_review_comparison())
        self.assertIn('class="issue-evidence"', document)
        self.assertIn("展开判断依据与规则", document)
        self.assertIn("问题方向：数据勾稽", document)
        first_issue = document[document.find('class="issue-card'):document.find('class="issue-card', document.find('class="issue-card') + 1)]
        self.assertLess(first_issue.find("问题描述"), first_issue.find("展开判断依据与规则"))

    def test_recommended_edits_are_folded_behind_explicit_counted_control(self):
        document = delivery.render(with_structured_review_comparison())
        self.assertIn('class="issue-edits"', document)
        self.assertIn("展开修改意见（共 1 项）", document)
        first_issue = document[document.find('class="issue-card'):document.find('class="issue-card', document.find('class="issue-card') + 1)]
        self.assertLess(first_issue.find("问题描述"), first_issue.find("展开修改意见（共 1 项）"))
        self.assertLess(first_issue.find("展开修改意见（共 1 项）"), first_issue.find("建议修改"))

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

    def test_dynamic_content_cannot_trigger_template_placeholder_replacement(self):
        result = load_sample()
        result["issues"][0]["problemDescription"] = "保留原文 {{embedded_json}} 与 {{report_content}}"
        document = delivery.render(result)
        visible_issues = re.findall(r'<span class="problem-description">(.*?)</span>', document, re.S)
        self.assertIn("保留原文 {{embedded_json}} 与 {{report_content}}", visible_issues)
        self.assertEqual(1, document.count('<main id="audit-report">'))
        self.assertEqual(1, document.count('<script id="audit-result" type="application/json">'))

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
        allowed.add("中瑞世联AI审核报告 - {0}".format(self.result["auditTask"]["projectId"]))
        allowed.update({"✅", "❌"})
        for node in text_nodes(self.document):
            if re.fullmatch(r"[0-9a-f]{64}", node):
                continue  # 渲染期计算的来源/嵌入摘要，可由输入确定性重算
            if re.fullmatch(r"[0-9]+", node):
                continue  # 渲染期按输入确定性重算的计数（如概览分区项数），非业务句子
            if any(re.fullmatch(pattern, node) for pattern in (
                r"(问题方向|严重程度|问题类型|判定)：.+",
                r"展开修改意见（共 [0-9]+ 项）",
                r"展开判断依据与规则（[0-9]+ 条规则，[0-9]+ 条材料）",
                r"展开全部审核依据（共 [0-9]+ 条规则）",
                r"展开 AI 自查错误记录（共 [0-9]+ 条）",
                r".+复核：[0-9]+ 条意见",
                r"展开.+复核意见（共 [0-9]+ 条）",
                r"：[0-9]+ 条，须优先回客户。",
                r"命中率：\([0-9]+ \+ [0-9]+\) ÷ [0-9]+ = [0-9]+(?:\.[0-9])?%；精确命中率：[0-9]+(?:\.[0-9])?%。部分命中计为命中、只是层次较低；已验证修改和无法核验项不进入分母。",
                r"命中率：\([0-9]+ \+ [0-9]+\) ÷ [0-9]+。部分命中计为命中、只是层次较低；已验证修改和无法核验项不进入分母；综合值按全部有效明细汇总，不取各维度百分比平均。",
                r"(精确命中|部分命中|未命中)：[0-9]+ / [0-9]+（[0-9]+(?:\.[0-9])?%）",
                r"展开不计入命中率分母的条目（共 [0-9]+ 条）",
                r"[0-9]+(?:\.[0-9])?%",
                r"[0-9]+ ÷ [0-9]+",
            )):
                continue  # 受控标签与输入计数/枚举的确定性组合，不创作新的业务结论
            self.assertIn(node, allowed, "渲染器生成了非标签/非数据的文本：{0}".format(node))


class ExternalDataVerificationTest(unittest.TestCase):
    """《外部数据核验》区：数据源可用性声明 + 逐项正确/不正确 + 基准日锚定。"""

    def setUp(self):
        self.result = load_sample()
        self.document = delivery.render(self.result)

    def test_region_is_rendered_in_required_position(self):
        self.assertIn('id="external-data-verification"', self.document)
        positions = [
            self.document.find('id="{0}"'.format(region)) for region in REGION_ORDER
        ]
        self.assertEqual(sorted(positions), positions, "外部数据核验区顺序必须符合 §3 交付结构")

    def test_external_data_is_named_as_ai_result_and_follows_ai_issues(self):
        document = delivery.render(with_structured_review_comparison())
        self.assertIn("AI 外部数据核验结果", document)
        self.assertLess(document.find('id="actionable-issues"'), document.find('id="external-data-verification"'))
        self.assertLess(document.find('id="external-data-verification"'), document.find('id="review-comparison"'))

    def test_unavailable_source_is_declared_in_html(self):
        result = load_sample()
        verification = result["externalDataVerification"]
        verification["sources"][0]["configured"] = False
        verification["sources"][0]["authenticated"] = False
        verification["sources"][0]["note"] = "两条取数路径都不可用；相关条目未经外部数据核验"
        verification["unavailableDeclaration"] = "本次未配置 / 未认证 同花顺 iFinD，相关条目未经外部数据核验。"
        document = delivery.render(result)
        self.assertIn(verification["unavailableDeclaration"], document)
        self.assertIn("未配置", document)
        self.assertIn("未授权", document)

    def test_each_check_shows_correct_and_incorrect_with_deviation(self):
        self.assertIn("EXTERNAL", self.document.replace("EXT-", "EXTERNAL"))  # 编号可见（示意）
        self.assertIn("符合", self.document)
        self.assertIn("不符合", self.document)
        self.assertIn("同花顺 iFinD", self.document)
        self.assertIn("2025-06-30", self.document)

    def test_overview_separates_external_data_from_issue_totals(self):
        """审核结果概览必须分列呈现：问题按模块分布 + 外部数据核验结果，不混成一句。"""
        start = self.document.find('id="summary"')
        end = self.document.find("</section>", start)
        summary = self.document[start:end]
        self.assertIn("问题按模块分布", summary)
        self.assertIn("市场法", summary, "按模块分布须使用员工可读的问题方向")
        self.assertIn("外部数据核验结果", summary, "外部数据核验须在概览中单独成块")
        self.assertIn("与哪一数据源出入较大", summary, "须给出与哪一源出入较大的分布")
        self.assertNotIn("external-data-verification", summary, "概览只做分区呈现，明细仍在专区内")

    def test_overview_counts_match_external_data_checks(self):
        checks = self.result["externalDataVerification"]["checks"]
        expected = {}
        for check in checks:
            expected[check["decision"]] = expected.get(check["decision"], 0) + 1
        start = self.document.find('id="summary"')
        end = self.document.find("</section>", start)
        summary = self.document[start:end]
        for decision, count in expected.items():
            self.assertIn(
                "<tr><td>{0}</td><td>{1}</td></tr>".format(decision, count),
                summary,
                "概览分区项数必须与核验条目重算一致：{0}={1}".format(decision, count),
            )

    def test_overview_deviation_block_labels_every_row(self):
        """「与哪一数据源出入较大」不得出现无标签的 "—" 行，且各行项数须合计等于核验项数。"""
        start = self.document.find('id="summary"')
        end = self.document.find("</section>", start)
        summary = self.document[start:end]
        block = summary[summary.find("与哪一数据源出入较大"):]
        self.assertNotIn("<tr><td>—</td>", block, "无出入/未检查必须单列，不得混进 — 行")
        counts = [int(value) for value in re.findall(r"<td>([0-9]+)</td>", block)]
        self.assertEqual(
            len(self.result["externalDataVerification"]["checks"]),
            sum(counts),
            "出入较大分块的行项数之和必须等于核验项数",
        )

    def test_unfetched_checks_are_labelled_未取数_in_detail(self):
        """逐项核验表中，判定为"未检查"的条目其"出入较大"列须显式写"未取数"，不用 — 混淆。"""
        start = self.document.find('id="external-data-verification"')
        section = self.document[start:self.document.find("</section>", start)]
        self.assertIn("<td>{0}</td>".format(delivery.EXT_DATA_NOT_FETCHED_TEXT), section)

    def test_missing_verification_renders_explicit_empty_state(self):
        result = load_sample()
        result.pop("externalDataVerification", None)
        document = delivery.render(result)
        self.assertIn('id="external-data-verification"', document)
        self.assertIn(delivery.EXT_DATA_EMPTY_TEXT, document)

    def test_required_fields_are_enforced(self):
        result = load_sample()
        verification = result["externalDataVerification"]
        verification["baseDate"] = ""
        verification["checks"][1]["decision"] = "大概符合"
        verification["checks"][0].pop("reportEvidence")
        errors = delivery.validate(result)
        joined = "\n".join(errors)
        self.assertIn("externalDataVerification.baseDate 不得为空", joined)
        self.assertIn("decision 取值非法", joined)
        self.assertIn("reportEvidence.locator", joined)

    def test_unavailable_declaration_is_required_when_source_missing(self):
        result = load_sample()
        verification = result["externalDataVerification"]
        verification["sources"][0]["configured"] = False
        verification["sources"][0]["authenticated"] = False
        verification.pop("unavailableDeclaration", None)
        errors = delivery.validate(result)
        self.assertIn("unavailableDeclaration", "\n".join(errors))

    def test_unavailable_source_cannot_be_used_as_verification_basis(self):
        result = load_sample()
        verification = result["externalDataVerification"]
        verification["sources"][0]["configured"] = False
        verification["sources"][0]["authenticated"] = False
        verification["unavailableDeclaration"] = "本次未配置 / 未认证 同花顺 iFinD，相关条目未经外部数据核验。"
        errors = delivery.validate(result)
        self.assertIn("不可用", "\n".join(errors))

    def test_source_must_be_declared(self):
        result = load_sample()
        result["externalDataVerification"]["checks"][0]["sources"][0]["source"] = "某未声明源"
        errors = delivery.validate(result)
        self.assertIn("未在 externalDataVerification.sources 中声明", "\n".join(errors))


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


class StructuredReviewComparisonTest(unittest.TestCase):
    """新版逐条复核事实源：文件顺序、分级明细与百分比必须可重算。"""

    def test_structured_sample_is_valid(self):
        self.assertEqual([], delivery.validate(with_structured_review_comparison()))

    def test_metrics_are_recomputed_from_review_items(self):
        result = with_structured_review_comparison()
        result["reviewComparison"]["metrics"]["hitRate"] = 1.0
        errors = delivery.validate(result)
        self.assertTrue(any("hitRate" in error and "重算" in error for error in errors), errors)

    def test_partial_hits_count_as_hits(self):
        """部分命中是命中（层次较低），命中率必须含 partial，不得等同于精确命中率。"""
        result = with_structured_review_comparison()
        comparison = result["reviewComparison"]
        comparison["reviewItems"][0]["matchStatus"] = "partial"
        comparison["reviewItems"][0]["hitExplanation"].update(
            {"matchedAspects": ["部分覆盖"], "unmatchedAspects": ["未覆盖部分"], "rationale": "只覆盖一部分。"})
        metrics = delivery._review_metrics(comparison["reviewItems"])
        self.assertEqual(metrics["exactHits"], 0)
        self.assertEqual(metrics["partialHits"], 1)
        self.assertEqual(metrics["hitRate"], 50.0)
        self.assertEqual(metrics["exactRate"], 0.0)
        self.assertNotEqual(metrics["hitRate"], metrics["exactRate"])

    def test_workpaper_capability_notice_is_always_rendered(self):
        """交付件必须明确说明暂不支持底稿文件审核，且底稿意见不计入 AI 命中率。"""
        document = delivery.render(with_structured_review_comparison())
        self.assertIn(delivery.CAPABILITY_WORKPAPER_NOTICE, document)
        self.assertIn("本工具当前暂不支持底稿文件审核", document)

    def test_denominator_exclusions_are_listed_with_evidence(self):
        """分母剔除清单：已修改/已落实与材料缺失项逐条给出剔除依据，使分母可审计。"""
        document = delivery.render(with_structured_review_comparison())
        self.assertIn("展开不计入命中率分母的条目（共 2 条）", document)
        self.assertIn("已修改/已落实 · 不计入分母", document)
        self.assertIn("材料缺失或不可读 · 不计入分母", document)

    def test_ai_comparison_states_both_branches_for_miss_marked_modified(self):
        """AI 未命中且复核件标注已修改时，AI 对照必须写清两种分支与分母后果。"""
        document = delivery.render(with_structured_review_comparison())
        self.assertIn("AI 未命中｜复核件标注该项「已修改」", document)
        self.assertIn("已按在件核验确认该项确已修改（复核事项在被审件中已不存在）→ 不计入命中率分母", document)
        self.assertIn("若核验发现并未修改，则须计入分母并计为 AI 漏检", document)
        # 答复称已改但未落地的未命中项同样计入分母
        self.assertIn("AI 未命中｜答复称已改但被审件未落地：计入命中率分母并计为漏检，优先回客户", document)
        # 区块图例必须说明该规则
        self.assertIn("分母判定：AI 未命中的复核意见，须先核验该事项是否已被修改", document)

    def test_ai_comparison_marks_unmodified_miss_as_counted(self):
        """AI 未命中且核验确认并未修改的，必须写明计入分母并计为漏检。"""
        result = with_structured_review_comparison()
        item = result["reviewComparison"]["reviewItems"][2]  # RV-003：miss + L-unclosed
        item["inFileResolution"] = "L-open"
        item.pop("closureEvidence", None)
        self.assertEqual([], delivery.validate(result))
        document = delivery.render(result)
        self.assertIn("AI 未命中｜已在件核验：该项并未修改 → 计入命中率分母，计为 AI 漏检", document)

    def test_miss_with_resolved_requires_in_file_proof(self):
        """AI 未命中而按 L-resolved 剔除分母时，必须给出在件原文证明已修改，否则应按 L-open 计入漏检。"""
        result = with_structured_review_comparison()
        item = result["reviewComparison"]["reviewItems"][1]  # RV-002：miss + L-resolved
        self.assertEqual("miss", item["matchStatus"])
        self.assertEqual("L-resolved", item["inFileResolution"])
        item["inFileEvidence"].pop("quote")
        errors = delivery.validate(result)
        self.assertTrue(
            any("必须给出在件原文" in e and "L-resolved" in e for e in errors), errors)

    def test_out_of_scope_items_are_registered_and_rendered(self):
        """能力边界条目：不计分但必须登记备查、可见可展开，且不得混入命中率明细。"""
        result = with_structured_review_comparison()
        comparison = result["reviewComparison"]
        comparison["outOfScopeItems"] = [{
            "itemId": "RV-900", "title": "底稿层面意见（不计分）", "module": "工作底稿与程序",
            "reviewerEvidence": {"file": "01-一级复核意见.docx", "locator": "底稿第1条", "quote": "未见底稿。"},
            "handling": "交人工底稿审核",
            "exclusionReason": "AI 当前不具备底稿审核能力，不计入命中率口径。",
        }]
        self.assertEqual([], delivery.validate(result))
        document = delivery.render(result)
        self.assertIn("展开不计入命中率的登记备查条目（共 1 条）", document)
        self.assertIn("底稿层面意见（不计分）", document)
        # 不得混入命中率明细
        comparison["outOfScopeItems"][0]["itemId"] = comparison["reviewItems"][0]["itemId"]
        self.assertTrue(any("不得混入命中率明细" in e for e in delivery.validate(result)))
        # 缺 exclusionReason 必须报错
        comparison["outOfScopeItems"][0]["itemId"] = "RV-901"
        del comparison["outOfScopeItems"][0]["exclusionReason"]
        self.assertTrue(any("exclusionReason" in e for e in delivery.validate(result)))

    def test_hit_explanation_is_required_and_consistent(self):
        result = with_structured_review_comparison()
        item = result["reviewComparison"]["reviewItems"][0]
        del item["hitExplanation"]
        self.assertTrue(any("hitExplanation" in e for e in delivery.validate(result)))
        result = with_structured_review_comparison()
        item = result["reviewComparison"]["reviewItems"][0]
        item["hitExplanation"]["unmatchedAspects"] = ["不该有"]
        self.assertTrue(any("unmatchedAspects" in e for e in delivery.validate(result)))

    def test_resolved_and_uncheckable_are_excluded_from_denominator(self):
        result = with_structured_review_comparison()
        document = delivery.render(result)
        self.assertIn("50.0%", document)
        self.assertIn("命中率：(1 + 0) ÷ 2 = 50.0%", document)
        self.assertIn("精确命中率：50.0%", document)
        self.assertIn("已验证修改", document)
        self.assertIn("无法核验", document)

    def test_review_files_are_listed_in_declared_order(self):
        document = delivery.render(with_structured_review_comparison())
        first = document.find("01-一级复核意见.docx")
        second = document.find("02-二级复核意见.docx")
        self.assertGreaterEqual(first, 0)
        self.assertGreater(second, first)

    def test_each_review_level_has_visible_summary_and_explicit_expand_control(self):
        document = delivery.render(with_structured_review_comparison())
        self.assertIn("一级复核：2 条意见", document)
        self.assertIn("二级复核：2 条意见", document)
        self.assertIn("展开一级复核意见（共 2 条）", document)
        self.assertIn("展开二级复核意见（共 2 条）", document)

    def test_unclosed_claim_is_prominent_with_both_evidence_sides(self):
        document = delivery.render(with_structured_review_comparison())
        self.assertIn("已称修复但实际未落实", document)
        self.assertIn("项目答复.docx", document)
        self.assertIn("仍未见时间修正依据", document)

    def test_objective_scorecard_shows_review_level_module_and_weighted_total(self):
        document = delivery.render(with_structured_review_comparison())
        self.assertIn("AI 审核表现评分卡", document)
        self.assertIn("按复核级次", document)
        self.assertIn("按问题模块", document)
        self.assertIn("综合命中率", document)
        self.assertIn("综合精确命中率", document)
        self.assertNotIn("综合·AI 单机", document)



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

    def test_closed_false_positive_cannot_still_be_an_active_issue(self):
        r = load_sample()
        r["selfAuditErrors"][0] = {
            "errorId": "SAE-001",
            "kind": "false_positive",
            "discoveredAt": "复审",
            "description": "复审确认该条属于误报并已撤回",
            "correction": "撤回该条",
            "status": "closed",
            "issueId": r["issues"][0]["issueId"],
        }
        self.assertTrue(any("已关闭假阳性不得仍保留在 issues" in e for e in delivery.validate(r)))

    def test_scorecard_renders_as_tables(self):
        html = delivery.render(with_structured_review_comparison())
        self.assertIn('id="ai-scorecard"', html)
        for label in ("AI 审核表现评分卡", "综合命中率", "综合精确命中率",
                      "按复核级次", "按问题模块", "展开 AI 自查错误记录"):
            self.assertIn(label, html)



if __name__ == "__main__":
    unittest.main(verbosity=2)
