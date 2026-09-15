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
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "template" / "audit-report.html"

REGION_ORDER = [
    "project-info",
    "summary",
    "actionable-issues",
    "manual-confirmation-items",
    "audit-basis",
    "external-data-verification",
    "review-comparison",
    "ai-scorecard",
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
        for node in text_nodes(self.document):
            if re.fullmatch(r"[0-9a-f]{64}", node):
                continue  # 渲染期计算的来源/嵌入摘要，可由输入确定性重算
            if re.fullmatch(r"[0-9]+", node):
                continue  # 渲染期按输入确定性重算的计数（如概览分区项数），非业务句子
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

    def test_unconfigured_source_is_declared_in_html(self):
        self.assertIn("本次未配置 / 未认证 万得，相关条目未经双源复核。", self.document)
        self.assertIn("未配置", self.document)
        self.assertIn("未授权", self.document)

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
        self.assertIn("marketApproach", summary, "按模块分布须列出问题所属模块")
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
        result["externalDataVerification"].pop("unavailableDeclaration", None)
        errors = delivery.validate(result)
        self.assertIn("unavailableDeclaration", "\n".join(errors))

    def test_unavailable_source_cannot_be_used_as_second_source(self):
        result = load_sample()
        check = result["externalDataVerification"]["checks"][0]
        check["sources"][1].pop("available", None)
        errors = delivery.validate(result)
        self.assertIn("未配置 / 未认证", "\n".join(errors))

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
