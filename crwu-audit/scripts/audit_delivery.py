#!/usr/bin/env python3
"""CRWU 审核意见交付工具：AuditResult 校验 + 单文件 HTML 渲染。

实现《CRWU 审核意见 HTML 送达规范 v1.0》
（正文：本技能 references/11-html-delivery-spec.md）：

- AuditResult JSON 是唯一事实源；HTML 仅如实呈现，不新增/删除/合并/改写任何结论；
- 校验覆盖 §9.4 关键校验规则 + §11.1 门禁 + §12.2 维护红线（敏感信息扫描）；
- 渲染输出自包含单文件 HTML（内嵌 CSS、无外链资源、A4 可打印、专业审核轨迹默认折叠）。

用法：
    python3 scripts/audit_delivery.py validate <audit-result.json> [--rendered]
    python3 scripts/audit_delivery.py render   <audit-result.json> --out <opinion.html>
退出码：0 成功；1 校验失败（错误打印到 stderr）。
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path

RENDERER_VERSION = "renderer/1.0.0"
SCHEMA_VERSION_PREFIX = "1."

SEVERITY_LABEL = {"high": "高", "medium": "中", "low": "低"}
SEVERITY_CLASS = {"high": "sev-high", "medium": "sev-medium", "low": "sev-low"}
ISSUE_TYPE_LABEL = {
    "rule_defect": "规则性缺陷",
    "reasonableness_doubt": "合理性存疑",
    "unsupported_pending": "无依据待判",
}
DECISION_LABEL = {"fail": "不符合", "pending_confirmation": "需人工确认", "pass": "符合"}
OVERALL_LABEL = {"fail": "存在需要处理的问题", "pending_confirmation": "有待人工确认事项", "pass": "本次未发现需要处理的问题"}
AUTHORITY_LABEL = {
    "external_formal": "外部正式依据",
    "internal_auxiliary": "内部辅助规则",
    "experience_reference": "历史风险经验",
}
SOURCE_TYPE_LABEL = {
    "law": "法律法规",
    "valuation_standard": "资产评估准则",
    "valuation_method_rule": "评估方法规则",
    "regulatory": "监管规则",
    "association": "行业协会要求",
    "internal_audit": "内部审核规则",
    "crwu_kb": "CRWU 知识库规则",
    "risk_case": "历史风险案例",
}
FLOW_LABEL = {"pending_response": "待答复", "answered": "已答复", "reviewed": "已复核"}
REVIEW_CATEGORY_LABEL = {
    "A": "AI 与人工复核均发现",
    "B": "仅 AI 发现",
    "C": "AI 与复核均涉及但结论或范围不同",
}
REVIEWER_ONLY_LABEL = "仅人工复核发现"
REASON_LABEL = {
    "missing_material": "缺材料",
    "unreadable": "不可读",
    "unsupported": "能力不支持",
    "out_of_scope": "超出本次范围",
    "not_applicable": "不适用",
}
RESULT_LABEL = {"pass": "符合", "difference": "差异", "not_applicable": "不适用", "not_checked": "未检查"}
CONFIDENCE_LABEL = {"high": "高", "medium": "中", "low": "低"}
REVIEW_STATUS_LABEL = {"not_performed": "未执行", "performed": "已执行"}

EMPTY_TEXT = "本次无此类事项"

HEX64 = re.compile(r"^[0-9a-f]{64}$")
ABSOLUTE_PATH_PATTERNS = [
    (re.compile(r"(?:^|[^A-Za-z0-9])/(?:Users|home|var|tmp|private|Volumes|opt)/"), "绝对路径"),
    (re.compile(r"\b[A-Za-z]:[\\/]"), "Windows 绝对路径"),
    (re.compile(r"file://"), "file:// 地址"),
]
FORBIDDEN_KEY_PATTERN = re.compile(r"(?i)(token|api[_-]?key|cookie|password|passwd|secret|connection[_-]?string|nodeId)")

REQUIRED_TOP_LEVEL = [
    "schemaVersion",
    "auditTask",
    "phaseControl",
    "summary",
    "issues",
    "manualConfirmationItems",
    "auditBasis",
    "reviewComparison",
    "scope",
    "professionalTrail",
    "fileTrace",
    "renderPolicy",
]

ISSUE_REQUIRED = [
    "issueId",
    "title",
    "module",
    "locationSummary",
    "severity",
    "issueType",
    "decision",
    "problemDescription",
    "handlingRequirement",
    "ruleEvidence",
    "materialEvidence",
    "gapAnalysis",
    "recommendedEdits",
    "flowStatus",
    "confidence",
    "reviewComparison",
]

RULE_REQUIRED = [
    "ruleId",
    "authorityClass",
    "sourceType",
    "title",
    "version",
    "clause",
    "quote",
    "kbRelativePath",
    "exportedAt",
    "usageCount",
    "purposes",
    "usedByIssueIds",
]

MATERIAL_EVIDENCE_REQUIRED = ["fileId", "displayName", "locator", "excerptOrValue", "evidenceRole"]
NOT_CHECKED_REQUIRED = ["itemId", "item", "reasonCode", "reason", "impact", "requiredAction", "relatedFiles"]
MANUAL_ITEM_REQUIRED = [
    "itemId",
    "title",
    "locationSummary",
    "observation",
    "questionToConfirm",
    "evidence",
    "suggestedAction",
]
CHECK_RECORD_REQUIRED = [
    "recordId",
    "domain",
    "checkItem",
    "targets",
    "evidence",
    "result",
    "linkedIssueIds",
    "performedAt",
    "executor",
]
REVIEWER_ONLY_REQUIRED = ["itemId", "title", "reviewerEvidence", "handling", "inFileResolution"]
# ---- AI 审核评分卡（自评；量化工种差距。维度与算法为技能内受控取值，知识库暂无对应词表） ----
SCORECARD_DIMENSIONS = [
    ("first_delivery_correctness", "首轮交付正确性"),
    ("self_correction", "自我纠错与定位"),
    ("incremental_value", "增量发现价值"),
    ("coverage_completeness", "覆盖完整性"),
    ("process_discipline", "过程纪律与可追溯"),
    ("judgment_quality", "本轮判断质量"),
]
SCORECARD_DIMENSION_KEYS = [key for key, _label in SCORECARD_DIMENSIONS]
SCORECARD_LEVELS = ("初审", "复审", "终审")
SCORECARD_ERROR_KINDS = {"false_positive", "correction", "omission", "wording"}
SCORECARD_ERROR_KIND_LABEL = {
    "false_positive": "假阳性（原判不成立）",
    "correction": "事实更正（结论成立但表述有误）",
    "omission": "漏检（人工复核已提出而 AI 未命中）",
    "wording": "表述修正",
}


def _round_half_up(value: float) -> float:
    """按 0.5 取整（四舍五入，非银行家舍入）。"""
    import math
    return math.floor(value * 2 + 0.5) / 2.0


def _mean_score(dimensions: list) -> float:
    scores = [float(d.get("score")) for d in dimensions]
    return _round_half_up(sum(scores) / len(scores))
IN_FILE_RESOLUTION_VALUES = {"L-resolved", "L-open", "L-unclosed", "L-uncheckable"}
IN_FILE_RESOLUTION_LABEL = {
    "L-resolved": "复核已提出 · 被审件已落实",
    "L-open": "复核已提出 · 被审件未落实",
    "L-unclosed": "复核答复称已改 · 被审件未落地",
    "L-uncheckable": "材料缺失或不可读 · 未能核验",
}


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def canonical_json(value) -> str:
    """确定性序列化：字段排序、UTF-8、无多余空白（摘要与嵌入均基于它）。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_result(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("AuditResult 顶层必须是 JSON 对象")
    return data


def iter_all_scalars(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            for scalar in iter_all_scalars(item):
                yield scalar
    elif isinstance(value, list):
        for item in value:
            for scalar in iter_all_scalars(item):
                yield scalar
    elif value is None:
        return
    else:
        yield value if isinstance(value, str) else str(value)


def iter_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            for nested in iter_keys(item):
                yield nested
    elif isinstance(value, list):
        for item in value:
            for nested in iter_keys(item):
                yield nested


def scan_sensitive(result: dict):
    """§10.1 / §12.2：绝对路径、file://、nodeId、凭据类字段一律不得进入交付物。"""
    errors = []
    for key in iter_keys(result):
        match = FORBIDDEN_KEY_PATTERN.search(key)
        if match:
            errors.append("禁止字段名 {0}（交付物不得含 nodeId 或任何凭据类字段）".format(key))
    for text in iter_all_scalars(result):
        for pattern, label in ABSOLUTE_PATH_PATTERNS:
            if pattern.search(text):
                errors.append("禁止出现{0}：{1}".format(label, text[:80]))
    return errors


# --------------------------------------------------------------------------- #
# 校验（§9.4 / §11.1）
# --------------------------------------------------------------------------- #
def _is_nonempty_str(value) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _check_relative_path(value: str) -> bool:
    if not _is_nonempty_str(value):
        return False
    if value.startswith("/") or value.startswith("~") or value.startswith("file://"):
        return False
    if re.match(r"^[A-Za-z]:", value):
        return False
    return True


def _parse_time(value: str):
    try:
        return __import__("datetime").datetime.fromisoformat(value)
    except ValueError:
        return None


def validate(result: dict, rendered: bool = False, expect_renderer: bool = False):
    errors = []
    for key in REQUIRED_TOP_LEVEL:
        if key not in result:
            errors.append("缺少顶层字段 {0}".format(key))
    if errors:
        return errors

    schema_version = result.get("schemaVersion")
    if not _is_nonempty_str(schema_version) or not str(schema_version).startswith(SCHEMA_VERSION_PREFIX):
        errors.append("schemaVersion 必须是 {0}x 版本".format(SCHEMA_VERSION_PREFIX))

    # auditTask
    audit_task = result.get("auditTask") or {}
    for field in ("projectId", "reportVersion", "auditTime", "engineVersion"):
        if not _is_nonempty_str(audit_task.get(field)):
            errors.append("auditTask.{0} 不得为空".format(field))

    # phaseControl（§11 两阶段门禁）
    phase = result.get("phaseControl") or {}
    frozen_at = phase.get("phase1FrozenAt")
    digest = phase.get("phase1Digest")
    accessed_at = phase.get("reviewAccessedAt")
    phase2_at = phase.get("phase2CompletedAt")
    if not _is_nonempty_str(frozen_at):
        errors.append("phaseControl.phase1FrozenAt 不得为空")
    if not _is_nonempty_str(digest) or not HEX64.match(str(digest)):
        errors.append("phaseControl.phase1Digest 必须是 sha256 十六进制摘要")
    if _is_nonempty_str(accessed_at):
        if not _is_nonempty_str(frozen_at):
            errors.append("存在 reviewAccessedAt 时必须先记录 phase1FrozenAt")
        else:
            frozen_dt, accessed_dt = _parse_time(str(frozen_at)), _parse_time(str(accessed_at))
            if frozen_dt is None or accessed_dt is None:
                errors.append("phaseControl 时间必须为 ISO-8601 字符串")
            elif accessed_dt <= frozen_dt:
                errors.append("reviewAccessedAt 必须晚于 phase1FrozenAt（阶段一必须先冻结）")
    if _is_nonempty_str(phase2_at):
        if not _is_nonempty_str(accessed_at):
            errors.append("phase2CompletedAt 非空时必须记录 reviewAccessedAt")
        else:
            accessed_dt, phase2_dt = _parse_time(str(accessed_at)), _parse_time(str(phase2_at))
            if accessed_dt and phase2_dt and phase2_dt < accessed_dt:
                errors.append("phase2CompletedAt 不得早于 reviewAccessedAt")

    # issues
    issues = result.get("issues")
    if not isinstance(issues, list):
        errors.append("issues 必须是数组")
        issues = []
    seen_issue_ids = set()
    rules_used_by_issues = {}
    review_categories = {"A": 0, "B": 0, "C": 0}
    severity_counts = {"high": 0, "medium": 0, "low": 0}
    fail_count = 0

    for index, issue in enumerate(issues):
        where = "issues[{0}]".format(index)
        if not isinstance(issue, dict):
            errors.append("{0} 必须是对象".format(where))
            continue
        for field in ISSUE_REQUIRED:
            if field not in issue:
                errors.append("{0} 缺少字段 {1}".format(where, field))
        issue_id = issue.get("issueId")
        if not _is_nonempty_str(issue_id):
            errors.append("{0}.issueId 不得为空".format(where))
        elif issue_id in seen_issue_ids:
            errors.append("issueId 重复：{0}".format(issue_id))
        else:
            seen_issue_ids.add(issue_id)
            where = "{0}({1})".format(where, issue_id)
        for field, label in (("severity", "severity"), ("issueType", "issueType"), ("decision", "decision")):
            value = issue.get(field)
            table = {"severity": SEVERITY_LABEL, "issueType": ISSUE_TYPE_LABEL, "decision": DECISION_LABEL}[field]
            if value not in table:
                errors.append("{0}.{1} 取值非法：{2}".format(where, label, value))
        for field in ("title", "problemDescription", "handlingRequirement", "locationSummary", "module"):
            if not _is_nonempty_str(issue.get(field)):
                errors.append("{0}.{1} 不得为空".format(where, field))

        severity = issue.get("severity")
        if severity in severity_counts and issue.get("decision") == "fail":
            severity_counts[severity] += 1
        if issue.get("decision") == "fail":
            fail_count += 1

        rule_evidence = issue.get("ruleEvidence")
        material_evidence = issue.get("materialEvidence")
        if not isinstance(rule_evidence, list):
            errors.append("{0}.ruleEvidence 必须是数组".format(where))
            rule_evidence = []
        if not isinstance(material_evidence, list):
            errors.append("{0}.materialEvidence 必须是数组".format(where))
            material_evidence = []
        if not material_evidence:
            errors.append("{0}.materialEvidence 至少一条（材料证据缺失不得形成结论）".format(where))
        if issue.get("decision") == "fail" and issue.get("issueType") == "rule_defect" and not rule_evidence:
            errors.append("{0} 规则性缺陷不通过必须同时具备规则证据与材料证据".format(where))
        for position, evidence in enumerate(material_evidence):
            if not isinstance(evidence, dict):
                errors.append("{0}.materialEvidence[{1}] 必须是对象".format(where, position))
                continue
            for field in MATERIAL_EVIDENCE_REQUIRED:
                if not _is_nonempty_str(evidence.get(field)) and field != "evidenceRole":
                    errors.append("{0}.materialEvidence[{1}].{2} 不得为空".format(where, position, field))
            if not _is_nonempty_str(evidence.get("evidenceRole")):
                errors.append("{0}.materialEvidence[{1}].evidenceRole 不得为空".format(where, position))
        for position, evidence in enumerate(rule_evidence):
            if not isinstance(evidence, dict):
                errors.append("{0}.ruleEvidence[{1}] 必须是对象".format(where, position))
                continue
            rule_id = evidence.get("ruleId")
            if not _is_nonempty_str(rule_id):
                errors.append("{0}.ruleEvidence[{1}].ruleId 不得为空".format(where, position))
            else:
                rules_used_by_issues.setdefault(str(rule_id), set()).add(str(issue_id))
            if not _is_nonempty_str(evidence.get("quote")):
                errors.append("{0}.ruleEvidence[{1}].quote 不得为空（须为本次真实读取原文）".format(where, position))

        gap = issue.get("gapAnalysis") or {}
        if not isinstance(gap, dict):
            errors.append("{0}.gapAnalysis 必须是对象".format(where))
        else:
            for field in ("ruleRequirement", "observedCondition", "difference", "finalJudgment"):
                if not _is_nonempty_str(gap.get(field)):
                    errors.append("{0}.gapAnalysis.{1} 不得为空".format(where, field))

        edits = issue.get("recommendedEdits")
        if not isinstance(edits, list) or not edits:
            errors.append("{0}.recommendedEdits 至少一条".format(where))
        else:
            for position, edit in enumerate(edits):
                if not isinstance(edit, dict):
                    errors.append("{0}.recommendedEdits[{1}] 必须是对象".format(where, position))
                    continue
                for field in ("fileId", "displayName", "locator", "action"):
                    if not _is_nonempty_str(edit.get(field)):
                        errors.append("{0}.recommendedEdits[{1}].{2} 不得为空".format(where, position, field))

        if issue.get("flowStatus") not in FLOW_LABEL:
            errors.append("{0}.flowStatus 取值非法：{1}".format(where, issue.get("flowStatus")))
        confidence = issue.get("confidence") or {}
        if not isinstance(confidence, dict) or confidence.get("level") not in CONFIDENCE_LABEL:
            errors.append("{0}.confidence.level 取值非法".format(where))
        elif not _is_nonempty_str(confidence.get("reason")):
            errors.append("{0}.confidence.reason 不得为空".format(where))

        comparison = issue.get("reviewComparison") or {}
        if not isinstance(comparison, dict) or comparison.get("status") not in REVIEW_STATUS_LABEL:
            errors.append("{0}.reviewComparison.status 取值非法".format(where))
        elif comparison.get("status") == "performed":
            category = comparison.get("category")
            if category not in review_categories:
                errors.append("{0}.reviewComparison.category 必须是 A/B/C".format(where))
            else:
                review_categories[category] += 1

    # manualConfirmationItems
    manual_items = result.get("manualConfirmationItems")
    if not isinstance(manual_items, list):
        errors.append("manualConfirmationItems 必须是数组")
        manual_items = []
    manual_ids = set()
    for index, item in enumerate(manual_items):
        where = "manualConfirmationItems[{0}]".format(index)
        if not isinstance(item, dict):
            errors.append("{0} 必须是对象".format(where))
            continue
        for field in MANUAL_ITEM_REQUIRED:
            if field not in item:
                errors.append("{0} 缺少字段 {1}".format(where, field))
        item_id = item.get("itemId")
        if not _is_nonempty_str(item_id):
            errors.append("{0}.itemId 不得为空".format(where))
        elif item_id in manual_ids:
            errors.append("manualConfirmationItems.itemId 重复：{0}".format(item_id))
        else:
            manual_ids.add(item_id)
        for field in ("title", "locationSummary", "observation", "questionToConfirm", "suggestedAction"):
            if not _is_nonempty_str(item.get(field)):
                errors.append("{0}.{1} 不得为空".format(where, field))
        if not isinstance(item.get("evidence"), list) or not item.get("evidence"):
            errors.append("{0}.evidence 至少一条".format(where))

    # auditBasis
    audit_basis = result.get("auditBasis") or {}
    rules = audit_basis.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("auditBasis.rules 至少一条（只列本次实际使用规则）")
        rules = []
    seen_rule_ids = set()
    for index, rule in enumerate(rules):
        where = "auditBasis.rules[{0}]".format(index)
        if not isinstance(rule, dict):
            errors.append("{0} 必须是对象".format(where))
            continue
        for field in RULE_REQUIRED:
            if field not in rule:
                errors.append("{0} 缺少字段 {1}".format(where, field))
        rule_id = rule.get("ruleId")
        if not _is_nonempty_str(rule_id):
            errors.append("{0}.ruleId 不得为空".format(where))
        elif rule_id in seen_rule_ids:
            errors.append("ruleId 重复：{0}".format(rule_id))
        else:
            seen_rule_ids.add(rule_id)
            where = "{0}({1})".format(where, rule_id)
        authority = rule.get("authorityClass")
        if authority not in AUTHORITY_LABEL:
            errors.append("{0}.authorityClass 取值非法：{1}".format(where, authority))
        if rule.get("sourceType") not in SOURCE_TYPE_LABEL:
            errors.append("{0}.sourceType 取值非法：{1}".format(where, rule.get("sourceType")))
        if authority == "external_formal":
            for field in ("title", "version", "clause", "quote"):
                if not _is_nonempty_str(rule.get(field)):
                    errors.append("{0} 外部正式依据必须给出 {1}".format(where, field))
            if str(rule.get("version")).strip() in {"现行", "现行有效", "有效"}:
                errors.append("{0}.version 不得宣称“现行”（须写本次实际读取版本）".format(where))
        if not _check_relative_path(str(rule.get("kbRelativePath"))):
            errors.append("{0}.kbRelativePath 必须是知识库相对路径".format(where))
        if not _is_nonempty_str(rule.get("exportedAt")):
            errors.append("{0}.exportedAt 不得为空".format(where))
        if not isinstance(rule.get("purposes"), list) or not rule.get("purposes"):
            errors.append("{0}.purposes 至少一项".format(where))
        expected_users = rules_used_by_issues.get(str(rule_id), set())
        declared_users = set(map(str, rule.get("usedByIssueIds") or []))
        if declared_users != expected_users:
            errors.append(
                "{0}.usedByIssueIds 与明细不一致（应为 {1}）".format(where, sorted(expected_users) or "空")
            )
        expected_usage = len(expected_users)
        if rule.get("usageCount") != expected_usage:
            errors.append(
                "{0}.usageCount 必须可由明细重算（应为 {1}）".format(where, expected_usage)
            )

    # reviewComparison（§6）
    comparison = result.get("reviewComparison") or {}
    status = comparison.get("status")
    if status not in REVIEW_STATUS_LABEL:
        errors.append("reviewComparison.status 取值非法：{0}".format(status))
    reviewer_only = comparison.get("reviewerOnlyItems")
    if not isinstance(reviewer_only, list):
        errors.append("reviewComparison.reviewerOnlyItems 必须是数组")
        reviewer_only = []
    reviewer_ids = set()
    for index, item in enumerate(reviewer_only):
        where = "reviewComparison.reviewerOnlyItems[{0}]".format(index)
        if not isinstance(item, dict):
            errors.append("{0} 必须是对象".format(where))
            continue
        for field in REVIEWER_ONLY_REQUIRED:
            if field not in item:
                errors.append("{0} 缺少字段 {1}".format(where, field))
        item_id = item.get("itemId")
        if not _is_nonempty_str(item_id):
            errors.append("{0}.itemId 不得为空".format(where))
        elif item_id in reviewer_ids:
            errors.append("reviewerOnlyItems.itemId 重复：{0}".format(item_id))
        else:
            reviewer_ids.add(item_id)
        evidence = item.get("reviewerEvidence") or {}
        if not isinstance(evidence, dict):
            errors.append("{0}.reviewerEvidence 必须是对象".format(where))
        else:
            for field in ("file", "locator", "quote"):
                if not _is_nonempty_str(evidence.get(field)):
                    errors.append("{0}.reviewerEvidence.{1} 不得为空".format(where, field))
        if not _is_nonempty_str(item.get("handling")):
            errors.append("{0}.handling 不得为空".format(where))
        resolution = item.get("inFileResolution")
        if resolution not in IN_FILE_RESOLUTION_VALUES:
            errors.append("{0}.inFileResolution 必须为 L-resolved/L-open/L-unclosed/L-uncheckable".format(where))
        else:
            if resolution in ("L-resolved", "L-open", "L-unclosed"):
                in_file = item.get("inFileEvidence") or {}
                for field in ("file", "locator"):
                    if not _is_nonempty_str(in_file.get(field)):
                        errors.append("{0}.inFileResolution={1} 必须给出 inFileEvidence.{2}（被审件在件位置）".format(where, resolution, field))
            if resolution == "L-unclosed":
                closure = item.get("closureEvidence") or {}
                if not (_is_nonempty_str(closure.get("file")) and _is_nonempty_str(closure.get("locator"))):
                    errors.append("{0}.inFileResolution=L-unclosed 必须给出 closureEvidence（答复出处）".format(where))
    hidden_access = comparison.get("hiddenRegionAccess")
    if hidden_access is not None:
        if not isinstance(hidden_access, list):
            errors.append("reviewComparison.hiddenRegionAccess 必须是数组")
        else:
            for idx, entry in enumerate(hidden_access):
                where = "reviewComparison.hiddenRegionAccess[{0}]".format(idx)
                if not isinstance(entry, dict):
                    errors.append("{0} 必须是对象".format(where))
                    continue
                for field in ("authorizedBy", "authorizedAt", "authorization", "scope"):
                    if not _is_nonempty_str(entry.get(field)):
                        errors.append("{0}.{1} 不得为空".format(where, field))

    if status == "performed":
        expected_bands = {
            "overlap": review_categories["A"],
            "aiOnly": review_categories["B"],
            "divergent": review_categories["C"],
            "reviewerOnly": len(reviewer_only),
        }
        bands = comparison.get("bands")
        if not isinstance(bands, dict):
            errors.append("reviewComparison.bands 必须是对象（阶段二已完成）")
        else:
            for band, expected in expected_bands.items():
                if bands.get(band) != expected:
                    errors.append(
                        "reviewComparison.bands.{0} 必须可由明细重算（应为 {1}）".format(band, expected)
                    )
        metrics = comparison.get("metrics") or {}
        if not isinstance(metrics, dict) or not _is_nonempty_str(metrics.get("denominator")):
            errors.append("reviewComparison.metrics.denominator 不得为空（命中率必须给出分母口径）")
        for index, issue in enumerate(issues):
            if isinstance(issue, dict):
                item = issue.get("reviewComparison") or {}
                if item.get("status") != "performed":
                    errors.append(
                        "阶段二已完成，issues[{0}] 必须具有 reviewComparison（不得标未执行）".format(index)
                    )
    elif status == "not_performed":
        if reviewer_only:
            errors.append("reviewComparison.status=not_performed 时不得填写复核独有项")
        for index, issue in enumerate(issues):
            if isinstance(issue, dict):
                item = issue.get("reviewComparison") or {}
                if item.get("status") == "performed":
                    errors.append(
                        "reviewComparison.status=not_performed 时 issues[{0}] 不得标为已执行".format(index)
                    )

    # scope（§7）
    scope = result.get("scope") or {}
    if not isinstance(scope.get("inputs"), list) or not scope.get("inputs"):
        errors.append("scope.inputs 至少一项")
    if not isinstance(scope.get("checkDomains"), list) or not scope.get("checkDomains"):
        errors.append("scope.checkDomains 至少一项")
    not_checked = scope.get("notCheckedItems")
    if not isinstance(not_checked, list):
        errors.append("scope.notCheckedItems 必须是数组（无则空数组）")
        not_checked = []
    not_checked_ids = set()
    for index, item in enumerate(not_checked):
        where = "scope.notCheckedItems[{0}]".format(index)
        if not isinstance(item, dict):
            errors.append("{0} 必须是对象".format(where))
            continue
        for field in NOT_CHECKED_REQUIRED:
            if field not in item:
                errors.append("{0} 缺少字段 {1}".format(where, field))
        item_id = item.get("itemId")
        if not _is_nonempty_str(item_id):
            errors.append("{0}.itemId 不得为空".format(where))
        elif item_id in not_checked_ids:
            errors.append("notCheckedItems.itemId 重复：{0}".format(item_id))
        else:
            not_checked_ids.add(item_id)
        if item.get("reasonCode") not in REASON_LABEL:
            errors.append("{0}.reasonCode 取值非法：{1}".format(where, item.get("reasonCode")))
        for field in ("item", "reason", "impact", "requiredAction"):
            if not _is_nonempty_str(item.get(field)):
                errors.append("{0}.{1} 不得为空".format(where, field))
        if not isinstance(item.get("relatedFiles"), list):
            errors.append("{0}.relatedFiles 必须是数组".format(where))

    # professionalTrail（§8）
    trail = result.get("professionalTrail") or {}
    if not isinstance(trail.get("applicableRuleSnapshot"), dict):
        errors.append("professionalTrail.applicableRuleSnapshot 必须是对象")
    for field in ("adjudications", "checkRecords"):
        if not isinstance(trail.get(field), list):
            errors.append("professionalTrail.{0} 必须是数组".format(field))
    if not isinstance(trail.get("comprehensiveComparison"), dict):
        errors.append("professionalTrail.comprehensiveComparison 必须是对象")
    check_record_ids = set()
    for index, record in enumerate(trail.get("checkRecords") or []):
        where = "professionalTrail.checkRecords[{0}]".format(index)
        if not isinstance(record, dict):
            errors.append("{0} 必须是对象".format(where))
            continue
        for field in CHECK_RECORD_REQUIRED:
            if field not in record:
                errors.append("{0} 缺少字段 {1}".format(where, field))
        record_id = record.get("recordId")
        if not _is_nonempty_str(record_id):
            errors.append("{0}.recordId 不得为空".format(where))
        elif record_id in check_record_ids:
            errors.append("checkRecords.recordId 重复：{0}".format(record_id))
        else:
            check_record_ids.add(record_id)
        if record.get("result") not in RESULT_LABEL:
            errors.append("{0}.result 取值非法：{1}".format(where, record.get("result")))
        for field in ("checkItem", "performedAt", "executor"):
            if not _is_nonempty_str(record.get(field)):
                errors.append("{0}.{1} 不得为空".format(where, field))
        if not isinstance(record.get("evidence"), list) or not record.get("evidence"):
            errors.append("{0}.evidence 至少一条（每条“检查过”必须有真实文件证据）".format(where))
        for field in ("targets", "linkedIssueIds"):
            if not isinstance(record.get(field), list):
                errors.append("{0}.{1} 必须是数组".format(where, field))

    # summary（§9.4 可重算）
    summary = result.get("summary") or {}
    if summary.get("overallDecision") not in OVERALL_LABEL:
        errors.append("summary.overallDecision 取值非法：{0}".format(summary.get("overallDecision")))
    expected_counts = {
        "issuesTotal": len(issues),
        "fail": fail_count,
        "high": severity_counts["high"],
        "medium": severity_counts["medium"],
        "low": severity_counts["low"],
        "pendingConfirmation": len(manual_items),
        "notChecked": len(not_checked),
    }
    counts = summary.get("counts")
    if not isinstance(counts, dict):
        errors.append("summary.counts 必须是对象且可由明细重算")
    else:
        for key, expected in expected_counts.items():
            if counts.get(key) != expected:
                errors.append("summary.counts.{0} 必须可由明细重算（应为 {1}）".format(key, expected))
    if fail_count and summary.get("overallDecision") == "pass":
        errors.append("存在不通过问题，summary.overallDecision 不得为 pass")
    if not fail_count and summary.get("overallDecision") == "fail":
        errors.append("不存在不通过问题，summary.overallDecision 不得为 fail")
    if not _is_nonempty_str(summary.get("narrative")):
        errors.append("summary.narrative 不得为空")

    # fileTrace（§10 / §12）
    file_trace = result.get("fileTrace") or {}
    if not _is_nonempty_str(file_trace.get("generatedAt")):
        errors.append("fileTrace.generatedAt 不得为空")
    renderer_version = file_trace.get("rendererVersion")
    if not _is_nonempty_str(renderer_version):
        errors.append("fileTrace.rendererVersion 不得为空")
    for field in ("sourceDigest", "embeddedJsonDigest"):
        value = file_trace.get(field)
        if rendered:
            if not _is_nonempty_str(value) or not HEX64.match(str(value)):
                errors.append("fileTrace.{0} 必须是渲染后的 sha256 摘要".format(field))
        elif _is_nonempty_str(value) and not HEX64.match(str(value)):
            errors.append("fileTrace.{0} 如果不是空值必须是 sha256 摘要".format(field))
    if expect_renderer and renderer_version != RENDERER_VERSION:
        errors.append("fileTrace.rendererVersion 与当前 renderer 不一致：{0}".format(renderer_version))

    # renderPolicy
    policy = result.get("renderPolicy") or {}
    if not isinstance(policy, dict):
        errors.append("renderPolicy 必须是对象")
    elif not isinstance(policy.get("printTrail"), bool):
        errors.append("renderPolicy.printTrail 必须是布尔值")

    # 敏感信息（§10.1 / §12.2）
    errors.extend(scan_sensitive(result))

    # ---- AI 审核评分卡（自评）+ 审核错误项 ----
    scorecard = result.get("aiScorecard")
    if not isinstance(scorecard, dict):
        errors.append("aiScorecard 必须是对象")
        scorecard = {}
    level = scorecard.get("level")
    if level not in SCORECARD_LEVELS:
        errors.append("aiScorecard.level 必须为 初审/复审/终审（与台账 review_level 一致）")
    dimensions = scorecard.get("dimensions")
    if not isinstance(dimensions, list):
        errors.append("aiScorecard.dimensions 必须是数组")
        dimensions = []
    seen_keys = []
    for idx, dim in enumerate(dimensions):
        where = "aiScorecard.dimensions[{0}]".format(idx)
        if not isinstance(dim, dict):
            errors.append("{0} 必须是对象".format(where))
            continue
        key = dim.get("key")
        if key not in SCORECARD_DIMENSION_KEYS:
            errors.append("{0}.key 取值非法：{1}".format(where, key))
        else:
            seen_keys.append(key)
        score = dim.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            errors.append("{0}.score 必须是数值".format(where))
        elif not (0 <= float(score) <= 10) or abs(float(score) * 2 - round(float(score) * 2)) > 1e-9:
            errors.append("{0}.score 必须为 0–10 且 0.5 的整数倍".format(where))
        if dim.get("max") != 10:
            errors.append("{0}.max 必须为 10".format(where))
        if not _is_nonempty_str(dim.get("basis")):
            errors.append("{0}.basis 不得为空（禁止无依据给分）".format(where))
    if sorted(seen_keys) != sorted(SCORECARD_DIMENSION_KEYS):
        errors.append("aiScorecard.dimensions 必须恰好覆盖六维：{0}".format(SCORECARD_DIMENSION_KEYS))

    composites = scorecard.get("composites")
    if not isinstance(composites, dict):
        errors.append("aiScorecard.composites 必须是对象")
        composites = {}
    corrections = scorecard.get("corrections") or []
    if not isinstance(corrections, list):
        errors.append("aiScorecard.corrections 必须是数组")
        corrections = []
    by_key = {d.get("key"): d.get("score") for d in dimensions if isinstance(d, dict)}

    if dimensions:
        expected_ai_only = _mean_score(dimensions)
        if composites.get("aiOnly") != expected_ai_only:
            errors.append("aiScorecard.composites.aiOnly 必须可由六维均值按 0.5 取整复算（应为 {0}）".format(expected_ai_only))

    def _final_score(key):
        score = by_key.get(key)
        for cor in corrections:
            if isinstance(cor, dict) and cor.get("key") == key:
                score = cor.get("to")
        return score

    for idx, cor in enumerate(corrections):
        where = "aiScorecard.corrections[{0}]".format(idx)
        if not isinstance(cor, dict):
            errors.append("{0} 必须是对象".format(where))
            continue
        key = cor.get("key")
        if key not in SCORECARD_DIMENSION_KEYS:
            errors.append("{0}.key 取值非法：{1}".format(where, key))
            continue
        if cor.get("from") != by_key.get(key):
            errors.append("{0}.from 必须等于初审该维分数（只增不覆盖：不得改写初审分）".format(where))
        if not _is_nonempty_str(cor.get("reason")):
            errors.append("{0}.reason 不得为空（校正必须给理由）".format(where))

    expected_loop = _round_half_up(
        sum(float(_final_score(k)) for k in SCORECARD_DIMENSION_KEYS) / len(SCORECARD_DIMENSION_KEYS)
    ) if dimensions else None
    if level == "初审":
        if corrections:
            errors.append("aiScorecard.corrections 仅在复审/终审填写（初审不得事后校正）")
        if composites.get("withHumanLoop") is not None:
            errors.append("aiScorecard.composites.withHumanLoop 仅在复审/终审填写")
    elif level in ("复审", "终审"):
        if composites.get("withHumanLoop") != expected_loop:
            errors.append("aiScorecard.composites.withHumanLoop 必须可由复审校正后六维均值按 0.5 取整复算（应为 {0}）".format(expected_loop))

    self_errors = result.get("selfAuditErrors")
    if not isinstance(self_errors, list):
        errors.append("selfAuditErrors 必须是数组")
        self_errors = []
    error_ids = set()
    for idx, item in enumerate(self_errors):
        where = "selfAuditErrors[{0}]".format(idx)
        if not isinstance(item, dict):
            errors.append("{0} 必须是对象".format(where))
            continue
        for field in ("errorId", "kind", "discoveredAt", "description"):
            if field not in item:
                errors.append("{0} 缺少字段 {1}".format(where, field))
        error_id = item.get("errorId")
        if _is_nonempty_str(error_id):
            if error_id in error_ids:
                errors.append("selfAuditErrors.errorId 重复：{0}".format(error_id))
            error_ids.add(error_id)
        if item.get("kind") not in SCORECARD_ERROR_KINDS:
            errors.append("{0}.kind 取值非法：{1}".format(where, item.get("kind")))
        if item.get("discoveredAt") not in SCORECARD_LEVELS:
            errors.append("{0}.discoveredAt 必须为 初审/复审/终审".format(where))
        if not _is_nonempty_str(item.get("description")):
            errors.append("{0}.description 不得为空".format(where))
        if item.get("status") is not None and item.get("status") not in ("open", "closed"):
            errors.append("{0}.status 取值非法：{1}".format(where, item.get("status")))

    return errors


# --------------------------------------------------------------------------- #
# 渲染（§10）
# --------------------------------------------------------------------------- #
def _text(value) -> str:
    if isinstance(value, (dict, list)):
        value = canonical_json(value)
    return html.escape("" if value is None else str(value), quote=True)


def _dt(value: str) -> str:
    parsed = _parse_time(str(value))
    return parsed.isoformat() if parsed else str(value)


def _span(cls: str, value) -> str:
    return '<span class="{0}">{1}</span>'.format(cls, _text(value))


def _rows(pairs) -> str:
    return "".join(
        "<tr><th scope=\"row\">{0}</th><td>{1}</td></tr>".format(_text(label), _text(value))
        for label, value in pairs
    )


def _list_block(items, formatter, empty_text=EMPTY_TEXT) -> str:
    if not items:
        return '<p class="empty">{0}</p>'.format(_text(empty_text))
    return "<ul>" + "".join("<li>{0}</li>".format(formatter(item)) for item in items) + "</ul>"


def _rule_map(rules) -> str:
    grouped = {}
    for rule in rules:
        authority = rule.get("authorityClass")
        source = rule.get("sourceType")
        grouped.setdefault(authority, {}).setdefault(source, []).append(rule)
    parts = ['<nav aria-label="审核规则地图" class="rule-map">']
    for authority in sorted(grouped):
        parts.append("<section><h4>{0}</h4>".format(_text(AUTHORITY_LABEL.get(authority, authority))))
        for source in sorted(grouped[authority]):
            parts.append("<p class=\"source\">{0}</p>".format(_text(SOURCE_TYPE_LABEL.get(source, source))))
            parts.append("<ul>")
            for rule in sorted(grouped[authority][source], key=lambda item: str(item.get("ruleId"))):
                parts.append(
                    "<li>{0}{1}</li>".format(
                        _span("rule-id", rule.get("ruleId")),
                        _span("rule-title", rule.get("title")),
                    )
                )
            parts.append("</ul>")
        parts.append("</section>")
    parts.append("</nav>")
    return "".join(parts)


def _issue_card(issue) -> str:
    cards = ['<article class="issue-card {0}">'.format(SEVERITY_CLASS.get(issue.get("severity"), ""))]
    cards.append('<header class="issue-head">')
    cards.append("<h3>{0}</h3>".format(_span("issue-title", issue.get("title"))))
    cards.append(
        '<p class="issue-meta">{0}{1}{2}{3}{4}</p>'.format(
            _span("issue-id", issue.get("issueId")),
            _span("severity-label", SEVERITY_LABEL.get(issue.get("severity"), issue.get("severity"))),
            _span("type-label", ISSUE_TYPE_LABEL.get(issue.get("issueType"), issue.get("issueType"))),
            _span("decision-label", DECISION_LABEL.get(issue.get("decision"), issue.get("decision"))),
            _span("location", issue.get("locationSummary")),
        )
    )
    cards.append("</header>")
    cards.append(
        '<p class="problem">{0}{1}</p>'.format(
            _span("problem-label", "问题描述"), _span("problem-description", issue.get("problemDescription"))
        )
    )

    cards.append('<section class="stage stage-rule"><h4>{0}</h4>'.format(_text("规则")))
    cards.append(_list_block(issue.get("ruleEvidence"), _rule_evidence_item) if issue.get("ruleEvidence") else _list_block([], None))
    cards.append("</section>")

    cards.append('<section class="stage stage-material"><h4>{0}</h4>'.format(_text("材料")))
    cards.append(_list_block(issue.get("materialEvidence"), _material_evidence_item) if issue.get("materialEvidence") else _list_block([], None))
    cards.append("</section>")

    gap = issue.get("gapAnalysis") or {}
    cards.append(
        '<section class="stage stage-diff"><h4>{0}</h4><table class="kv">{1}</table></section>'.format(
            _text("差异"),
            _rows(
                [
                    ("规则要求", gap.get("ruleRequirement")),
                    ("材料现状", gap.get("observedCondition")),
                    ("差异", gap.get("difference")),
                    ("判断", gap.get("finalJudgment")),
                ]
            ),
        )
    )

    confidence = issue.get("confidence") or {}
    cards.append(
        '<section class="stage stage-conclusion"><h4>{0}</h4><table class="kv">{1}</table></section>'.format(
            _text("结论"),
            _rows(
                [
                    ("处理要求", issue.get("handlingRequirement")),
                    ("流转状态", FLOW_LABEL.get(issue.get("flowStatus"), issue.get("flowStatus"))),
                    ("置信度", CONFIDENCE_LABEL.get(confidence.get("level"), confidence.get("level"))),
                    ("置信度理由", confidence.get("reason")),
                ]
            ),
        )
    )

    cards.append('<section class="stage stage-edit"><h4>{0}</h4>'.format(_text("修改")))
    cards.append(_list_block(issue.get("recommendedEdits"), _edit_item) if issue.get("recommendedEdits") else _list_block([], None))
    cards.append("</section>")

    comparison = issue.get("reviewComparison") or {}
    if comparison.get("status") == "performed":
        cards.append(
            '<details class="issue-compare"><summary>{0}</summary><table class="kv">{1}</table></details>'.format(
                _text("人工复核对照"),
                _rows([("对照分类", REVIEW_CATEGORY_LABEL.get(comparison.get("category"), comparison.get("category")))]),
            )
        )
    else:
        cards.append(
            '<p class="compare-status">{0}{1}</p>'.format(
                _span("compare-label", "人工复核对照"), _span("compare-value", REVIEW_STATUS_LABEL["not_performed"])
            )
        )
    cards.append("</article>")
    return "".join(cards)


def _rule_evidence_item(evidence) -> str:
    return (
        '<span class="rule-id">{0}</span>'
        '<span class="authority">{1}</span>'
        '<span class="clause">{2}</span>'
        '<span class="quote">{3}</span>'
        '<span class="kb-path">{4}</span>'
        '<span class="exported-at">{5}</span>'
    ).format(
        _text(evidence.get("ruleId")),
        _text(AUTHORITY_LABEL.get(evidence.get("authorityClass"), evidence.get("authorityClass"))),
        _text(evidence.get("clause")),
        _text(evidence.get("quote")),
        _text(evidence.get("kbRelativePath")),
        _text(evidence.get("exportedAt")),
    )


def _material_evidence_item(evidence) -> str:
    return (
        '<span class="file">{0}</span>'
        '<span class="section">{1}</span>'
        '<span class="locator">{2}</span>'
        '<span class="excerpt">{3}</span>'
        '<span class="role">{4}</span>'
    ).format(
        _text(evidence.get("displayName")),
        _text(evidence.get("section")),
        _text(evidence.get("locator")),
        _text(evidence.get("excerptOrValue")),
        _text(evidence.get("evidenceRole")),
    )


def _edit_item(edit) -> str:
    return (
        '<span class="file">{0}</span><span class="locator">{1}</span><span class="action">{2}</span>'
    ).format(_text(edit.get("displayName")), _text(edit.get("locator")), _text(edit.get("action")))


def _manual_item(item) -> str:
    return (
        "<h4>{0}</h4><table class=\"kv\">{1}</table>"
    ).format(
        _text(item.get("title")),
        _rows(
            [
                ("编号", item.get("itemId")),
                ("位置", item.get("locationSummary")),
                ("客观发现", item.get("observation")),
                ("需确认问题", item.get("questionToConfirm")),
                ("建议动作", item.get("suggestedAction")),
            ]
        ),
    )



SCORECARD_DIMENSION_LABEL = dict(SCORECARD_DIMENSIONS)
SCORECARD_COMPOSITE_LABEL = {"aiOnly": "综合·AI 单机", "withHumanLoop": "综合·含人机复核闭环"}
SCORECARD_LABEL = "本次 AI 审核六维评分卡"
SCORECARD_LEVEL_LABEL = "审核级次"
SCORECARD_CORRECTION_LABEL = "复审校正（只增不覆盖）"
SELF_ERROR_LABEL = "AI 审核错误项"
SCORECARD_COL_DIMENSION = "维度"
SCORECARD_COL_FIRST = "初审分"
SCORECARD_COL_CORRECTION = "复审校正"
SCORECARD_COL_FINAL = "最终分"
SCORECARD_COL_BASIS = "打分依据"
SCORECARD_COL_REASON = "校正理由"
SCORECARD_COL_ERROR_ID = "编号"
SCORECARD_COL_ERROR_KIND = "错误类型"
SCORECARD_COL_ERROR_AT = "发现级次"
SCORECARD_COL_ERROR_DESC = "说明"
SCORECARD_COL_ERROR_FIX = "处置"


def _scorecard_section(scorecard, self_errors) -> str:
    """AI 审核评分卡（表格呈现）：六维分数 + 复审校正 + 综合分 + 审核错误项。"""
    corrections = {c.get("key"): c for c in (scorecard.get("corrections") or []) if isinstance(c, dict)}
    rows = []
    for dim in scorecard.get("dimensions") or []:
        key = dim.get("key")
        cor = corrections.get(key)
        rows.append(
            "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td></tr>".format(
                _text(dim.get("label")),
                _text(dim.get("score")),
                _text(cor.get("to")) if cor else _text(EMPTY_TEXT),
                _text(cor.get("to") if cor else dim.get("score")),
                _text(dim.get("basis")),
            )
        )
    composites = scorecard.get("composites") or {}
    comp_rows = []
    for field in ("aiOnly", "withHumanLoop"):
        if field == "withHumanLoop" and composites.get(field) is None:
            continue
        comp_rows.append(
            "<tr><th scope=\"row\">{0}</th><td>{1}</td></tr>".format(
                _text(SCORECARD_COMPOSITE_LABEL[field]), _text(composites.get(field))
            )
        )
    cor_rows = []
    for cor in scorecard.get("corrections") or []:
        cor_rows.append(
            "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td></tr>".format(
                _text(SCORECARD_DIMENSION_LABEL.get(cor.get("key"), cor.get("key"))),
                _text(cor.get("from")), _text(cor.get("to")), _text(cor.get("reason")),
            )
        )
    err_rows = []
    for item in self_errors or []:
        err_rows.append(
            "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td></tr>".format(
                _text(item.get("errorId")),
                _text(SCORECARD_ERROR_KIND_LABEL.get(item.get("kind"), item.get("kind"))),
                _text(item.get("discoveredAt")),
                _text(item.get("description")),
                _text(item.get("correction")),
            )
        )
    parts = ["<section id=\"ai-scorecard\">", "<h3>{0}</h3>".format(_text(SCORECARD_LABEL))]
    parts.append("<table class=\"kv\"><tr><th scope=\"row\">{0}</th><td>{1}</td></tr></table>".format(
        _text(SCORECARD_LEVEL_LABEL), _text(scorecard.get("level"))))
    parts.append("<table><thead><tr><th>{0}</th><th>{1}</th><th>{2}</th><th>{3}</th><th>{4}</th></tr></thead><tbody>".format(
        _text(SCORECARD_COL_DIMENSION), _text(SCORECARD_COL_FIRST), _text(SCORECARD_COL_CORRECTION),
        _text(SCORECARD_COL_FINAL), _text(SCORECARD_COL_BASIS)))
    parts.extend(rows)
    parts.append("</tbody></table>")
    if comp_rows:
        parts.append("<table class=\"kv\">{0}</table>".format("".join(comp_rows)))
    if cor_rows:
        parts.append("<h4>{0}</h4>".format(_text(SCORECARD_CORRECTION_LABEL)))
        parts.append("<table><thead><tr><th>{0}</th><th>{1}</th><th>{2}</th><th>{3}</th></tr></thead><tbody>".format(
            _text(SCORECARD_COL_DIMENSION), _text(SCORECARD_COL_FIRST), _text(SCORECARD_COL_FINAL),
            _text(SCORECARD_COL_REASON)))
        parts.extend(cor_rows)
        parts.append("</tbody></table>")
    parts.append("<h4>{0}</h4>".format(_text(SELF_ERROR_LABEL)))
    if err_rows:
        parts.append("<table><thead><tr><th>{0}</th><th>{1}</th><th>{2}</th><th>{3}</th><th>{4}</th></tr></thead><tbody>".format(
            _text(SCORECARD_COL_ERROR_ID), _text(SCORECARD_COL_ERROR_KIND),
            _text(SCORECARD_COL_ERROR_AT), _text(SCORECARD_COL_ERROR_DESC),
            _text(SCORECARD_COL_ERROR_FIX)))
        parts.extend(err_rows)
        parts.append("</tbody></table>")
    else:
        parts.append("<p class=\"empty\">{0}</p>".format(_text(EMPTY_TEXT)))
    parts.append("</section>")
    return "".join(parts)


def _reviewer_only_item(item) -> str:
    evidence = item.get("reviewerEvidence") or {}
    in_file = item.get("inFileEvidence") or {}
    closure = item.get("closureEvidence") or {}
    resolution = item.get("inFileResolution")
    rows = [
        ("编号", item.get("itemId")),
        ("复核文件", evidence.get("file")),
        ("定位", evidence.get("locator")),
        ("原文摘录", evidence.get("quote")),
        ("在件核验", IN_FILE_RESOLUTION_LABEL.get(resolution, resolution)),
        ("被审件文件", in_file.get("file", "")),
        ("被审件定位", in_file.get("locator", "")),
        ("处理", item.get("handling")),
    ]
    if resolution == "L-unclosed":
        rows.insert(6, ("答复文件", closure.get("file", "")))
        rows.insert(7, ("答复定位", closure.get("locator", "")))
    return (
        "<h4>{0}</h4><table class=\"kv\">{1}</table>"
    ).format(_text(item.get("title")), _rows(rows))


def _not_checked_item(item) -> str:
    return (
        "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td><td>{5}</td></tr>"
    ).format(
        _text(item.get("itemId")),
        _text(item.get("item")),
        _text(REASON_LABEL.get(item.get("reasonCode"), item.get("reasonCode"))),
        _text(item.get("reason")),
        _text(item.get("impact")),
        _text(item.get("requiredAction")),
    )


def _check_record_row(record) -> str:
    return "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td></tr>".format(
        _text(record.get("recordId")),
        _text(record.get("checkItem")),
        _text(RESULT_LABEL.get(record.get("result"), record.get("result"))),
        _text(record.get("executor")),
    )


def _adjudication_row(record) -> str:
    return "<tr><td>{0}</td><td>{1}</td><td>{2}</td></tr>".format(
        _text(record.get("recordId")),
        _text(record.get("itemRef") or record.get("item")),
        _text(RESULT_LABEL.get(record.get("result"), record.get("result"))),
    )


STYLE = """
:root { --line:#c9ced6; --muted:#5b6472; --high:#b3261e; --medium:#a15c00; --low:#6b6b00; }
* { box-sizing: border-box; }
body { margin:0; padding:0; color:#1b1f24; background:#fff;
  font-family: "PingFang SC","Microsoft YaHei","Noto Sans CJK SC",-apple-system,"Segoe UI",sans-serif; line-height:1.55; }
main { max-width: 980px; margin: 0 auto; padding: 24px 20px 48px; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 18px; margin: 28px 0 10px; padding-bottom:6px; border-bottom:2px solid var(--line); }
h3 { font-size: 16px; margin: 0 0 6px; }
h4 { font-size: 13px; margin: 10px 0 6px; color: var(--muted); }
section { margin-bottom: 14px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid var(--line); padding: 6px 8px; text-align: left; vertical-align: top; font-size: 13px; }
thead th { background:#f4f6f8; }
table.kv th { width: 96px; background:#f7f8fa; }
ul { margin: 6px 0; padding-left: 18px; }
li { margin: 4px 0; break-inside: avoid; }
.issue-card { border:1px solid var(--line); border-left-width:5px; border-radius:4px; padding:12px 14px; margin:14px 0; break-inside: avoid; }
.issue-card.sev-high { border-left-color: var(--high); }
.issue-card.sev-medium { border-left-color: var(--medium); }
.issue-card.sev-low { border-left-color: var(--low); }
.issue-meta span, .stage li span { margin-right:10px; }
.issue-meta .severity-label { font-weight:700; border:1px solid var(--line); border-radius:3px; padding:0 6px; }
.sev-high .severity-label { color: var(--high); border-color: var(--high); }
.sev-medium .severity-label { color: var(--medium); border-color: var(--medium); }
.sev-low .severity-label { color: var(--low); border-color: var(--low); }
.issue-id, .rule-id, .file, .locator, .kb-path, .exported-at, .role { color: var(--muted); }
.quote, .excerpt { font-style: italic; }
.problem-label { font-weight:600; margin-right:6px; }
.empty { color: var(--muted); margin:6px 0; }
.rule-map h4 { margin-top:14px; }
.banner { background:#fbf3f2; border:1px solid var(--high); border-radius:4px; padding:8px 10px; font-size:13px; }
details { border:1px dashed var(--line); border-radius:4px; padding:8px 10px; margin:10px 0; }
summary { cursor: pointer; font-weight:600; }
.footer-meta { color: var(--muted); font-size:12px; }
.badge { display:inline-block; border:1px solid var(--line); border-radius:3px; padding:0 6px; margin-right:6px; font-size:12px; }
@media print {
  @page { size: A4; margin: 16mm 15mm 18mm; }
  main { max-width: none; padding: 0; }
  details { border:none; padding:0; }
  details > summary { display:none; }
  details:not([open]) > *:not(summary) { display: block; }
  .issue-card { break-inside: avoid; }
  thead { display: table-header-group; }
  a[href]:after { content: ""; }
}
"""


def render(result: dict, print_trail: bool = None) -> str:
    """确定性渲染：文本节点只来自受控标签或输入数据，不生成新的业务句子。"""
    rendered_result = json.loads(json.dumps(result, ensure_ascii=False))
    file_trace = rendered_result.setdefault("fileTrace", {})

    # sourceDigest：渲染输入的规范化摘要（摘要字段自身清零）
    file_trace["sourceDigest"] = ""
    file_trace["embeddedJsonDigest"] = ""
    source_digest = sha256_hex(canonical_json(rendered_result))
    file_trace["sourceDigest"] = source_digest
    file_trace["rendererVersion"] = RENDERER_VERSION

    embedded_digest = sha256_hex(canonical_json(rendered_result))
    file_trace["embeddedJsonDigest"] = embedded_digest

    payload = canonical_json(rendered_result).replace("<", "\\u003c")
    audit_task = rendered_result.get("auditTask") or {}
    summary = rendered_result.get("summary") or {}
    counts = summary.get("counts") or {}
    issues = rendered_result.get("issues") or []
    manual_items = rendered_result.get("manualConfirmationItems") or []
    audit_basis = rendered_result.get("auditBasis") or {}
    rules = audit_basis.get("rules") or []
    comparison = rendered_result.get("reviewComparison") or {}
    scope = rendered_result.get("scope") or {}
    trail = rendered_result.get("professionalTrail") or {}
    policy = rendered_result.get("renderPolicy") or {}
    if print_trail is None:
        print_trail = bool(policy.get("printTrail"))

    sorted_issues = sorted(
        issues,
        key=lambda item: (
            {"high": 0, "medium": 1, "low": 2}.get(item.get("severity"), 3),
            str(item.get("module")),
            str(item.get("issueId")),
        ),
    )

    parts = []
    parts.append("<!doctype html>")
    parts.append('<html lang="zh-CN">')
    parts.append("<head>")
    parts.append('<meta charset="utf-8">')
    parts.append('<meta name="viewport" content="width=device-width,initial-scale=1">')
    parts.append("<title>{0}</title>".format(_text("审核意见")))
    parts.append("<style>{0}</style>".format(STYLE))
    parts.append("</head>")
    parts.append("<body>")
    parts.append('<main id="audit-report">')

    # 01 项目信息
    parts.append('<header id="project-info">')
    parts.append("<h1>{0}</h1>".format(_text("审核意见")))
    parts.append(
        '<p class="badge">{0}</p>'.format(
            _span(
                "phase-note",
                "阶段一独立审核已完成并冻结；阶段二复核对照不改变阶段一结论"
                if comparison.get("status") == "performed"
                else "阶段一独立审核已完成并冻结；本次未执行阶段二复核对照",
            )
        )
    )
    parts.append(
        '<table class="kv">{0}</table>'.format(
            _rows(
                [
                    ("项目编号", audit_task.get("projectId")),
                    ("报告版本", audit_task.get("reportVersion")),
                    ("审核时间", _dt(audit_task.get("auditTime", ""))),
                    ("对象类型", ((audit_task.get("profile") or {}).get("objectType"))),
                    ("评估方法", "、".join((audit_task.get("profile") or {}).get("methods") or [])),
                    ("场景", ((audit_task.get("profile") or {}).get("scenario"))),
                    ("环节", ((audit_task.get("profile") or {}).get("stage"))),
                    ("引擎版本", audit_task.get("engineVersion")),
                ]
            )
        )
    )
    parts.append("</header>")

    # 02 审核结果概览
    parts.append('<section id="summary">')
    parts.append("<h2>{0}</h2>".format(_text("审核结果概览")))
    parts.append('<p class="banner">{0}</p>'.format(_text(OVERALL_LABEL.get(summary.get("overallDecision"), summary.get("overallDecision")))))
    parts.append('<p>{0}</p>'.format(_span("narrative", summary.get("narrative"))))
    parts.append(
        '<table class="kv">{0}</table>'.format(
            _rows(
                [
                    ("问题总数", counts.get("issuesTotal")),
                    ("高", counts.get("high")),
                    ("中", counts.get("medium")),
                    ("低", counts.get("low")),
                    ("不通过", counts.get("fail")),
                    ("待人工确认", counts.get("pendingConfirmation")),
                    ("未检查项", counts.get("notChecked")),
                ]
            )
        )
    )
    parts.append("</section>")

    # 03 需要处理的问题
    parts.append('<section id="actionable-issues">')
    parts.append("<h2>{0}</h2>".format(_text("需要处理的问题")))
    if sorted_issues:
        for issue in sorted_issues:
            parts.append(_issue_card(issue))
    else:
        parts.append('<p class="empty">{0}</p>'.format(_text(EMPTY_TEXT)))
    parts.append("</section>")

    # 04 需要人工确认事项
    parts.append('<section id="manual-confirmation-items">')
    parts.append("<h2>{0}</h2>".format(_text("需要人工确认事项")))
    parts.append(_list_block(manual_items, _manual_item, empty_text=EMPTY_TEXT))
    parts.append("</section>")

    # 05 本次审核依据
    parts.append('<section id="audit-basis">')
    parts.append("<h2>{0}</h2>".format(_text("本次审核依据")))
    parts.append(_rule_map(rules))
    parts.append('<table><thead><tr><th>{0}</th><th>{1}</th><th>{2}</th><th>{3}</th><th>{4}</th><th>{5}</th><th>{6}</th></tr></thead><tbody>'.format(
        _text("规则编号"), _text("权威层级"), _text("来源分类"), _text("名称"), _text("版本"), _text("条款"), _text("引用次数")))
    for rule in sorted(rules, key=lambda item: str(item.get("ruleId"))):
        parts.append(
            "<tr><td>{0}</td><td>{1}</td><td>{2}</td><td>{3}</td><td>{4}</td><td>{5}</td><td>{6}</td></tr>".format(
                _text(rule.get("ruleId")),
                _text(AUTHORITY_LABEL.get(rule.get("authorityClass"), rule.get("authorityClass"))),
                _text(SOURCE_TYPE_LABEL.get(rule.get("sourceType"), rule.get("sourceType"))),
                _text(rule.get("title")),
                _text(rule.get("version")),
                _text(rule.get("clause")),
                _text(rule.get("usageCount")),
            )
        )
    parts.append("</tbody></table>")
    kb_files = audit_basis.get("knowledgeBaseFiles") or []
    if kb_files:
        parts.append("<h4>{0}</h4>".format(_text("本次知识库文件")))
        parts.append(
            "<ul>"
            + "".join(
                "<li>{0}{1}</li>".format(_span("kb-path", item.get("path")), _span("exported-at", item.get("exportedAt")))
                for item in kb_files
            )
            + "</ul>"
        )
    parts.append("</section>")

    # 06 人工复核对照
    parts.append('<section id="review-comparison">')
    parts.append("<h2>{0}</h2>".format(_text("人工复核对照")))
    parts.append(
        '<table class="kv">{0}</table>'.format(
            _rows(
                [
                    ("状态", REVIEW_STATUS_LABEL.get(comparison.get("status"), comparison.get("status"))),
                    ("AI 与人工复核均发现", (comparison.get("bands") or {}).get("overlap")),
                    ("仅 AI 发现", (comparison.get("bands") or {}).get("aiOnly")),
                    ("结论或范围不同", (comparison.get("bands") or {}).get("divergent")),
                    ("仅人工复核发现", (comparison.get("bands") or {}).get("reviewerOnly")),
                    ("命中率", (comparison.get("metrics") or {}).get("aiHitRate")),
                    ("分母口径", (comparison.get("metrics") or {}).get("denominator")),
                    ("命中率（仅未落实）", (comparison.get("metrics") or {}).get("aiHitRateExclResolved")),
                    ("分母口径（仅未落实）", (comparison.get("metrics") or {}).get("denominatorExclResolved")),
                ]
            )
        )
    )
    reviewer_items = comparison.get("reviewerOnlyItems") or []
    if comparison.get("status") == "performed":
        parts.append("<h4>{0}</h4>".format(_text(REVIEWER_ONLY_LABEL)))
        parts.append(_list_block(reviewer_items, _reviewer_only_item, empty_text=EMPTY_TEXT))
    else:
        parts.append('<p class="empty">{0}</p>'.format(_text(EMPTY_TEXT)))
    parts.append("</section>")

    # 06.5 AI 审核评分卡（自评；初审自评 → 复审补充与校正）
    parts.append(_scorecard_section(result.get("aiScorecard") or {}, result.get("selfAuditErrors") or []))

    # 07 审核范围与未检查项
    parts.append('<section id="scope-and-not-checked">')
    parts.append("<h2>{0}</h2>".format(_text("审核范围与未检查项")))
    parts.append(
        '<table><thead><tr><th>{0}</th><th>{1}</th><th>{2}</th></tr></thead><tbody>'.format(
            _text("文件"), _text("版本"), _text("可读")
        )
    )
    for item in scope.get("inputs") or []:
        parts.append(
            "<tr><td>{0}</td><td>{1}</td><td>{2}</td></tr>".format(
                _text(item.get("displayName")), _text(item.get("version")), _text(item.get("readable"))
            )
        )
    parts.append("</tbody></table>")
    parts.append("<h4>{0}</h4>".format(_text("检查域")))
    parts.append("<ul>" + "".join("<li>{0}</li>".format(_text(domain)) for domain in (scope.get("checkDomains") or [])) + "</ul>")
    parts.append("<h4>{0}</h4>".format(_text("未检查项")))
    not_checked = scope.get("notCheckedItems") or []
    if not_checked:
        parts.append(
            '<table><thead><tr><th>{0}</th><th>{1}</th><th>{2}</th><th>{3}</th><th>{4}</th><th>{5}</th></tr></thead><tbody>'.format(
                _text("编号"), _text("未检查项"), _text("原因码"), _text("原因"), _text("影响"), _text("需要的动作")
            )
        )
        for item in not_checked:
            parts.append(_not_checked_item(item))
        parts.append("</tbody></table>")
    else:
        parts.append('<p class="empty">{0}</p>'.format(_text(EMPTY_TEXT)))
    limitations = scope.get("limitations") or []
    if limitations:
        parts.append("<h4>{0}</h4>".format(_text("能力边界")))
        parts.append("<ul>" + "".join("<li>{0}</li>".format(_text(item)) for item in limitations) + "</ul>")
    parts.append("</section>")

    # 08 专业审核轨迹（默认折叠）
    parts.append('<details id="professional-trail"{0}>'.format(" open" if print_trail else ""))
    parts.append("<summary>{0}</summary>".format(_text("专业审核轨迹")))
    parts.append('<section id="rule-snapshot"><h4>{0}</h4><table class="kv">{1}</table></section>'.format(
        _text("适用规则集快照"),
        _rows([(key, value) for key, value in sorted((trail.get("applicableRuleSnapshot") or {}).items())]),
    ))
    parts.append('<section id="adjudications"><h4>{0}</h4>'.format(_text("逐条裁定表")))
    adjudications = trail.get("adjudications") or []
    if adjudications:
        parts.append('<table><thead><tr><th>{0}</th><th>{1}</th><th>{2}</th></tr></thead><tbody>'.format(
            _text("编号"), _text("条目"), _text("裁定")))
        for record in adjudications:
            parts.append(_adjudication_row(record))
        parts.append("</tbody></table>")
    else:
        parts.append('<p class="empty">{0}</p>'.format(_text(EMPTY_TEXT)))
    parts.append("</section>")
    parts.append('<section id="check-records"><h4>{0}</h4>'.format(_text("审核记录清单")))
    check_records = trail.get("checkRecords") or []
    if check_records:
        parts.append('<table><thead><tr><th>{0}</th><th>{1}</th><th>{2}</th><th>{3}</th></tr></thead><tbody>'.format(
            _text("记录编号"), _text("检查项"), _text("结论"), _text("执行模块")))
        for record in check_records:
            parts.append(_check_record_row(record))
        parts.append("</tbody></table>")
    else:
        parts.append('<p class="empty">{0}</p>'.format(_text(EMPTY_TEXT)))
    parts.append("</section>")
    parts.append('<section id="comprehensive-comparison"><h4>{0}</h4><table class="kv">{1}</table></section>'.format(
        _text("复核综合对比"),
        _rows([(key, value) for key, value in sorted((trail.get("comprehensiveComparison") or {}).items())]),
    ))
    parts.append("</details>")

    # 09 文件追溯信息
    file_trace = rendered_result.get("fileTrace") or {}
    parts.append('<footer id="file-trace">')
    parts.append("<h2>{0}</h2>".format(_text("文件追溯信息")))
    parts.append(
        '<table class="kv">{0}</table>'.format(
            _rows(
                [
                    ("生成时间", file_trace.get("generatedAt")),
                    ("渲染器版本", file_trace.get("rendererVersion")),
                    ("数据摘要", file_trace.get("sourceDigest")),
                    ("嵌入 JSON 摘要", file_trace.get("embeddedJsonDigest")),
                ]
            )
        )
    )
    parts.append('<p class="footer-meta">{0}</p>'.format(_text("AI 辅助审核结果，供人工三级复核与员工答复流转；合理性质疑与无依据待判事项须人工确认后方可作为结论依据。")))
    parts.append("</footer>")

    parts.append("</main>")
    parts.append('<script id="audit-result" type="application/json">{0}</script>'.format(payload))
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts) + "\n"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _cmd_validate(args) -> int:
    result = load_result(Path(args.path))
    errors = validate(result, rendered=args.rendered, expect_renderer=args.rendered)
    if errors:
        for error in errors:
            print("ERROR: {0}".format(error), file=sys.stderr)
        print("校验失败：{0} 项".format(len(errors)), file=sys.stderr)
        return 1
    print("校验通过：{0}".format(args.path))
    return 0


def _cmd_digest(args) -> int:
    """阶段一冻结指纹：对冻结快照做规范化序列化后取 sha256（写入 phaseControl.phase1Digest）。"""
    result = load_result(Path(args.path))
    print(sha256_hex(canonical_json(result)))
    return 0


def _cmd_render(args) -> int:
    path = Path(args.path)
    result = load_result(path)
    errors = validate(result, rendered=False)
    if errors:
        for error in errors:
            print("ERROR: {0}".format(error), file=sys.stderr)
        print("校验失败，拒绝渲染：{0} 项".format(len(errors)), file=sys.stderr)
        return 1
    document = render(result)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(document, encoding="utf-8")
    rendered = json.loads(re.search(r'<script id="audit-result" type="application/json">(.*?)</script>', document, re.S).group(1))
    post_errors = validate(rendered, rendered=True, expect_renderer=True)
    if post_errors:
        for error in post_errors:
            print("ERROR: {0}".format(error), file=sys.stderr)
        print("渲染后自检失败：{0} 项".format(len(post_errors)), file=sys.stderr)
        return 1
    print("已渲染：{0}".format(out_path))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="CRWU AuditResult 校验与单文件 HTML 渲染（送达规范 v1.0）")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="校验 AuditResult JSON")
    validate_parser.add_argument("path", help="AuditResult JSON 路径")
    validate_parser.add_argument("--rendered", action="store_true", help="按渲染后状态校验（要求摘要已回填）")
    validate_parser.set_defaults(func=_cmd_validate)

    digest_parser = subparsers.add_parser("digest", help="计算阶段一冻结指纹（规范化 JSON 的 sha256）")
    digest_parser.add_argument("path", help="冻结快照 JSON 路径")
    digest_parser.set_defaults(func=_cmd_digest)

    render_parser = subparsers.add_parser("render", help="渲染自包含单文件 HTML")
    render_parser.add_argument("path", help="AuditResult JSON 路径")
    render_parser.add_argument("--out", required=True, help="输出 HTML 路径")
    render_parser.set_defaults(func=_cmd_render)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
