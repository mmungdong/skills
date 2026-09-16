#!/usr/bin/env python3
"""GapAnalysis JSON validation and deterministic HTML delivery."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path


ACTIONABLE = {"L-open", "L-unclosed"}
NON_ACTIONABLE = {"L-resolved", "L-uncheckable", "L-questionable"}
CAUSES = {"K1", "K2", "S1", "S2", "R", "I", "E", "O", "H"}
PLAN_TYPES = {"kb_manual", "skill_ai", "maintainer_handoff", "no_action"}
TRACE_STAGES = {"input", "profile", "routing", "assembly", "knowledge", "skill", "execution", "output"}
TRACE_STATUSES = {"passed", "failed", "unknown", "not_applicable"}
ABSOLUTE_PATH = re.compile(r"(?:^|\s)(?:/Users/|/home/|[A-Za-z]:\\\\)")
SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = SKILL_ROOT / "template" / "gap-analysis-report.html"
ECHARTS_PATH = SKILL_ROOT / "template" / "echarts.min.js"


def load_result(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("GapAnalysis 顶层必须是对象")
    return value


def _unique_index(items: list, key: str, label: str, errors: list[str]) -> dict:
    result = {}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] 必须是对象")
            continue
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label}[{index}].{key} 不得为空")
            continue
        if value in result:
            errors.append(f"{label}.{key} 重复：{value}")
            continue
        result[value] = item
    return result


def _iter_scalars(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_scalars(item)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_scalars(item)
    elif isinstance(value, str):
        yield value


def _scan_forbidden_content(result: dict) -> list[str]:
    errors = []
    for value in _iter_scalars(result):
        if ABSOLUTE_PATH.search(value):
            errors.append("报告不得包含个人绝对路径")
            break
    return errors


def _validate_summary(result: dict, gaps: list, plans: list) -> list[str]:
    summary = result.get("summary") or {}
    counts = {
        "reviewerOnly": len(gaps),
        "actionableMisses": sum(item.get("status") in ACTIONABLE for item in gaps if isinstance(item, dict)),
        "resolved": sum(item.get("status") == "L-resolved" for item in gaps if isinstance(item, dict)),
        "uncheckable": sum(item.get("status") == "L-uncheckable" for item in gaps if isinstance(item, dict)),
        "questionable": sum(item.get("status") == "L-questionable" for item in gaps if isinstance(item, dict)),
        "repairPlans": len(plans),
    }
    return [f"summary.{key} 必须可由明细重算" for key, expected in counts.items() if summary.get(key) != expected]


def validate(result: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(result, dict):
        return ["GapAnalysis 顶层必须是对象"]
    required = (
        "schemaVersion", "reportId", "project", "baselines", "summary",
        "reviewerOnlyItems", "repairPlans", "renderPolicy",
    )
    for key in required:
        if key not in result:
            errors.append(f"缺少顶层字段 {key}")

    gaps = result.get("reviewerOnlyItems") or []
    plans = result.get("repairPlans") or []
    if not isinstance(gaps, list):
        errors.append("reviewerOnlyItems 必须是数组")
        gaps = []
    if not isinstance(plans, list):
        errors.append("repairPlans 必须是数组")
        plans = []
    gap_by_id = _unique_index(gaps, "gapId", "reviewerOnlyItems", errors)
    plan_by_id = _unique_index(plans, "fixId", "repairPlans", errors)

    for gap_id, gap in gap_by_id.items():
        status = gap.get("status")
        linked = gap.get("linkedFixIds") or []
        if status in ACTIONABLE and not linked:
            errors.append(f"{gap_id}.linkedFixIds：确认漏检必须关联修复计划")
        for cause in gap.get("rootCauses") or []:
            if not isinstance(cause, dict) or cause.get("code") not in CAUSES:
                errors.append(f"{gap_id}.rootCauses 包含非法根因")
        for trace in gap.get("executionTrace") or []:
            if not isinstance(trace, dict) or trace.get("stage") not in TRACE_STAGES:
                errors.append(f"{gap_id}.executionTrace 包含非法阶段")
            elif trace.get("status") not in TRACE_STATUSES:
                errors.append(f"{gap_id}.executionTrace 包含非法状态")
        for fix_id in linked:
            if fix_id not in plan_by_id:
                errors.append(f"{gap_id}.linkedFixIds 引用未知计划 {fix_id}")
            elif gap_id not in (plan_by_id[fix_id].get("sourceGapIds") or []):
                errors.append(f"{gap_id} 与 {fix_id} 双向关系不一致")

    for fix_id, plan in plan_by_id.items():
        sources = plan.get("sourceGapIds") or []
        if not sources:
            errors.append(f"{fix_id}.sourceGapIds 不得为空")
        if plan.get("type") not in PLAN_TYPES:
            errors.append(f"{fix_id}.type 非法")
        if plan.get("type") == "kb_manual" and plan.get("executionMode") != "manual_only":
            errors.append(f"{fix_id} 知识库计划必须为 manual_only")
        for gap_id in sources:
            gap = gap_by_id.get(gap_id)
            if not gap:
                errors.append(f"{fix_id}.sourceGapIds 引用未知漏检 {gap_id}")
            elif gap.get("status") in NON_ACTIONABLE:
                errors.append(f"{fix_id} 不得包含 {gap.get('status')} 项 {gap_id}")
            elif fix_id not in (gap.get("linkedFixIds") or []):
                errors.append(f"{fix_id} 与 {gap_id} 双向关系不一致")

    errors.extend(_validate_summary(result, gaps, plans))
    errors.extend(_scan_forbidden_content(result))
    policy = result.get("renderPolicy") or {}
    if policy.get("offline") is not True or policy.get("printA4") is not True:
        errors.append("renderPolicy 必须要求离线单文件和 A4 打印")
    return errors


def _h(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def build_manual_kb_instruction(plan: dict) -> str:
    if plan.get("type") != "kb_manual" or plan.get("executionMode") != "manual_only":
        raise ValueError("仅 kb_manual/manual_only 可生成人工修复单")
    target = plan.get("target") or {}
    change = plan.get("changeSpec") or {}
    return "\n".join(
        [
            f"知识库人工修复单 {plan.get('fixId', '')}（仅人工）",
            f"对应人工独有事项：{'、'.join(plan.get('sourceGapIds') or [])}",
            f"目标文档：{target.get('kbPath', '')}",
            f"定位锚点：{target.get('anchor', '')}",
            f"当前缺口：{change.get('currentGap', '')}",
            f"修改方式：{change.get('method', '')}",
            f"建议内容结构：{'；'.join(change.get('contentOutline') or [])}",
            f"联动登记：{'；'.join(plan.get('registrations') or [])}",
            f"完成凭证：{plan.get('completionEvidence', '')}",
        ]
    )


def build_skill_prompt(result: dict, approved_fix_ids: list[str]) -> str:
    plan_by_id = {item.get("fixId"): item for item in result.get("repairPlans") or []}
    if not approved_fix_ids:
        raise ValueError("未批准任何 Skill 修复计划")
    selected = []
    for fix_id in approved_fix_ids:
        plan = plan_by_id.get(fix_id)
        if not plan:
            raise ValueError(f"未知修复计划 {fix_id}")
        if plan.get("type") != "skill_ai" or plan.get("approvalState") != "approved":
            raise ValueError(f"计划 {fix_id} 未批准或不是 Skill AI 计划")
        selected.append(plan)

    lines = [
        "我确认执行《AI—人工审核差距分析报告 {0}》中的 Skill 修复计划：{1}。".format(
            result.get("reportId", ""), "、".join(approved_fix_ids)
        ),
        "",
        "请使用 crwu-dev-audit-optimize 执行上述已批准计划。先核对报告证据、源仓当前状态和依赖；涉及知识库依赖时，只允许通过 crwu-dws 只读重新下载核验，不得对知识库执行任何写操作。",
        "",
        "执行要求：",
        "1. 仅修改以下批准计划列明的源仓 Skill 文件，不修改运行时目录，不扩大范围。",
    ]
    for number, plan in enumerate(selected, 2):
        target = plan.get("target") or {}
        change = plan.get("changeSpec") or {}
        lines.append(
            f"{number}. {plan['fixId']}（对应 {'、'.join(plan.get('sourceGapIds') or [])}）："
            f"在 {target.get('skillFile', '')} 的 {target.get('anchor', '')} 处{change.get('method', '')}；"
            f"目标内容为 {'、'.join(change.get('contentOutline') or [])}。"
        )
    next_number = len(selected) + 2
    lines.extend(
        [
            f"{next_number}. 只写 RULE/CHK 编号和库内层级路径寻址键，不复制知识库正文。",
            f"{next_number + 1}. 若最新状态冲突、目标路径变化、依赖未满足或需要修改清单外文件，立即停止并说明。",
            f"{next_number + 2}. 完成后运行各计划 validation 中的校验，并按 sourceGapIds 逐条回归原人工漏检，汇报文件级改动、测试结果和剩余风险。",
        ]
    )
    return "\n".join(lines)


def actionable_cause_counts(result: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for gap in result.get("reviewerOnlyItems") or []:
        if gap.get("status") not in ACTIONABLE:
            continue
        for cause in gap.get("rootCauses") or []:
            code = cause.get("code")
            if code:
                counts[code] = counts.get(code, 0) + 1
    return counts


def _badge(text: str) -> str:
    return f'<span class="badge">{_h(text)}</span>'


def _render_summary(result: dict) -> str:
    summary = result.get("summary") or {}
    comparison = result.get("comparison") or {}
    stats = [
        ("双方共同发现", comparison.get("overlap", 0)),
        ("AI 新增", comparison.get("aiOnly", 0)),
        ("人工独有", summary.get("reviewerOnly", 0)),
        ("确认 AI 漏检", summary.get("actionableMisses", 0)),
        ("已整改", summary.get("resolved", 0)),
        ("不可核验", summary.get("uncheckable", 0)),
        ("人工意见存疑", summary.get("questionable", 0)),
        ("修复计划", summary.get("repairPlans", 0)),
    ]
    cards = "".join(f'<div class="stat"><span>{_h(label)}</span><strong>{_h(value)}</strong></div>' for label, value in stats)
    return f'<section id="gap-summary"><h2>差距摘要</h2><div class="stats">{cards}</div></section>'


def _render_gap_rows(result: dict) -> str:
    rows = []
    plans = {item.get("fixId"): item for item in result.get("repairPlans") or []}
    for gap in result.get("reviewerOnlyItems") or []:
        causes = "、".join(item.get("code", "") for item in gap.get("rootCauses") or [])
        linked = gap.get("linkedFixIds") or []
        targets = []
        for fix_id in linked:
            target = (plans.get(fix_id) or {}).get("target") or {}
            targets.append(target.get("kbPath") or target.get("skillFile") or "")
        verification = gap.get("finalDocumentVerification") or {}
        rows.append(
            '<tr data-gap-id="{gap_id}"><td><strong>{gap_id}</strong><br>{title}</td>'
            '<td>{status}<br><span class="muted">{result}</span></td><td>{causes}</td>'
            '<td>{fixes}</td><td>{targets}</td></tr>'.format(
                gap_id=_h(gap.get("gapId")),
                title=_h(gap.get("title")),
                status=_badge(gap.get("status", "")),
                result=_h(verification.get("result", "")),
                causes=_h(causes),
                fixes=" ".join(_badge(item) for item in linked) or "—",
                targets="<br>".join(_h(item) for item in targets) or "—",
            )
        )
    return "".join(rows)


def _render_traces(result: dict) -> str:
    blocks = []
    for gap in result.get("reviewerOnlyItems") or []:
        if gap.get("status") not in ACTIONABLE:
            continue
        trace = []
        for index, item in enumerate(gap.get("executionTrace") or []):
            if index:
                trace.append('<span class="trace-line" aria-hidden="true"></span>')
            trace.append(
                '<span class="trace-step {status}" title="{evidence}">{stage} · {status}</span>'.format(
                    status=_h(item.get("status")), stage=_h(item.get("stage")), evidence=_h(item.get("evidence"))
                )
            )
        blocks.append(
            '<div data-gap-id="{gap_id}"><h3>{gap_id} · {title}</h3><div class="trace">{trace}</div></div>'.format(
                gap_id=_h(gap.get("gapId")), title=_h(gap.get("title")), trace="".join(trace) or "无执行链记录"
            )
        )
    return "".join(blocks) or '<p class="muted">没有需要归因的真实漏检。</p>'


def _render_manual_plans(result: dict) -> str:
    cards = []
    for plan in result.get("repairPlans") or []:
        if plan.get("type") != "kb_manual":
            continue
        fix_id = plan.get("fixId", "")
        instruction = build_manual_kb_instruction(plan)
        cards.append(
            '<article class="plan"><h3>{fix_id} · {title}</h3><p class="manual-only">manual_only · 仅人工修改</p>'
            '<pre id="manual-{fix_id}">{instruction}</pre><div class="copy-row">'
            '<button type="button" data-copy-target="manual-{fix_id}">复制人工修复说明</button><span class="muted copy-status"></span>'
            '</div></article>'.format(fix_id=_h(fix_id), title=_h(plan.get("title")), instruction=_h(instruction))
        )
    return "".join(cards) or '<p class="muted">本次没有知识库人工修复项。</p>'


def _render_skill_plans(result: dict) -> str:
    approved = [item.get("fixId") for item in result.get("repairPlans") or [] if item.get("type") == "skill_ai" and item.get("approvalState") == "approved"]
    cards = []
    for plan in result.get("repairPlans") or []:
        if plan.get("type") != "skill_ai":
            continue
        target = plan.get("target") or {}
        cards.append(
            '<article class="plan skill"><h3>{fix_id} · {title}</h3><dl>'
            '<dt>对应漏检</dt><dd>{gaps}</dd><dt>源仓文件</dt><dd><code>{file}</code></dd>'
            '<dt>修改方式</dt><dd>{method}</dd><dt>批准状态</dt><dd>{approval}</dd></dl></article>'.format(
                fix_id=_h(plan.get("fixId")), title=_h(plan.get("title")), gaps=_h("、".join(plan.get("sourceGapIds") or [])),
                file=_h(target.get("skillFile")), method=_h((plan.get("changeSpec") or {}).get("method")), approval=_h(plan.get("approvalState")),
            )
        )
    prompt = build_skill_prompt(result, approved) if approved else "没有已批准的 Skill 修复计划。"
    cards.append(
        '<article class="plan skill"><h3>可复制给 AI 的执行 Prompt</h3>'
        '<textarea id="skill-execution-prompt" readonly>{prompt}</textarea><div class="copy-row">'
        '<button type="button" class="primary" data-copy-target="skill-execution-prompt">复制 Skill 执行 Prompt</button>'
        '<span class="muted copy-status"></span></div></article>'.format(prompt=_h(prompt))
    )
    return "".join(cards)


def _render_validation(result: dict) -> str:
    rows = []
    for plan in result.get("repairPlans") or []:
        rows.append(
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
                _h(plan.get("fixId")), _h("、".join(plan.get("sourceGapIds") or [])),
                _h("、".join(plan.get("dependencies") or []) or "无"), _h("；".join(plan.get("validation") or [])),
            )
        )
    return "".join(rows)


def _render_sections(result: dict) -> str:
    project = result.get("project") or {}
    return "".join(
        [
            '<header><h1>AI—人工审核差距分析</h1><p class="subtitle">项目 {project} · 报告 {report}</p>'
            '<p>历史基线用于还原当时漏检原因；当前知识库仅通过 crwu-dws 只读核验缺口是否仍存在。</p></header>'.format(
                project=_h(project.get("projectId")), report=_h(result.get("reportId"))
            ),
            _render_summary(result),
            '<section id="gap-charts"><h2>差距构成与根因分布</h2><div class="charts">'
            '<div id="composition-chart" class="chart" aria-label="差距构成图"></div>'
            '<div id="cause-chart" class="chart" aria-label="根因分布图"></div></div></section>',
            '<section id="reviewer-only-table"><h2>人工独有事项逐条归因</h2><div class="table-wrap"><table>'
            '<thead><tr><th>人工独有事项</th><th>在件核验</th><th>根因</th><th>对应修复计划</th><th>修复目标</th></tr></thead>'
            f'<tbody>{_render_gap_rows(result)}</tbody></table></div></section>',
            f'<section id="execution-trace"><h2>真实漏检执行链</h2>{_render_traces(result)}</section>',
            '<section id="gap-fix-map"><h2>人工独有事项 → 根因 → 修复计划</h2>'
            '<div id="relation-chart" aria-label="漏检与修复计划关系图"></div></section>',
            f'<section id="manual-kb-plans"><h2>知识库人工修复单</h2><p class="manual-only">知识库只能由用户人工修改，AI 不得写入。</p><div class="plan-grid">{_render_manual_plans(result)}</div></section>',
            f'<section id="skill-repair-prompts"><h2>Skill 修复计划与执行 Prompt</h2><div class="plan-grid">{_render_skill_plans(result)}</div></section>',
            '<section id="validation-plan"><h2>依赖与验证</h2><div class="table-wrap"><table><thead><tr>'
            '<th>计划</th><th>对应漏检</th><th>依赖</th><th>验证</th></tr></thead>'
            f'<tbody>{_render_validation(result)}</tbody></table></div></section>',
            '<footer>由 crwu-dev-audit-optimize 差距分析模式生成 · 表格是证据主载体，图表仅用于汇总与导航</footer>',
        ]
    )


def _report_javascript() -> str:
    return r"""
(function(){
  const data = JSON.parse(document.getElementById('gap-analysis-data').textContent);
  const colors = ['#356da8','#9a5b08','#7652a8','#a92d28','#39724f','#667085'];
  const gaps = data.reviewerOnlyItems || [];
  const plans = data.repairPlans || [];
  const causeCounts = data.chartData.actionableCauseCounts;
  const composition = echarts.init(document.getElementById('composition-chart'));
  composition.setOption({animation:false,tooltip:{trigger:'axis'},grid:{left:100,right:25,top:20,bottom:30},
    xAxis:{type:'value'},yAxis:{type:'category',data:['双方共同','AI 新增','结论分歧','人工独有','确认漏检']},
    series:[{type:'bar',data:[data.comparison.overlap,data.comparison.aiOnly,data.comparison.divergent,data.summary.reviewerOnly,data.summary.actionableMisses],label:{show:true,position:'right'},itemStyle:{color:'#356da8'}}]});
  const causes = echarts.init(document.getElementById('cause-chart'));
  causes.setOption({animation:false,tooltip:{trigger:'item'},legend:{bottom:0},series:[{type:'pie',radius:['42%','68%'],data:Object.entries(causeCounts).map(([name,value],i)=>({name,value,itemStyle:{color:colors[i%colors.length]}}))}]});
  const nodes = [], links = [], seen = new Set();
  const addNode = (name, depth) => { const key=depth+':'+name; if(!seen.has(key)){seen.add(key);nodes.push({name:key,label:{formatter:name},depth});} return key; };
  gaps.filter(g=>['L-open','L-unclosed'].includes(g.status)).forEach(g=>{
    const left=addNode(g.gapId,0);
    (g.rootCauses||[]).forEach(c=>{const middle=addNode(c.code,1);links.push({source:left,target:middle,value:1});
      (g.linkedFixIds||[]).forEach(id=>{const right=addNode(id,2);if(!links.some(x=>x.source===middle&&x.target===right))links.push({source:middle,target:right,value:1});});
    });
  });
  const relation = echarts.init(document.getElementById('relation-chart'));
  relation.setOption({animation:false,tooltip:{trigger:'item'},series:[{type:'sankey',left:18,right:90,nodeWidth:15,nodeGap:13,draggable:false,data:nodes,links,lineStyle:{color:'gradient',opacity:.35}}]});
  function focusGap(gapId){document.querySelectorAll('[data-gap-id]').forEach(el=>{el.style.opacity=!gapId||el.dataset.gapId===gapId?'1':'.28';});}
  document.querySelectorAll('[data-gap-id]').forEach(el=>el.addEventListener('click',()=>focusGap(el.dataset.gapId)));
  relation.on('click',p=>{const label=(p.data&&p.data.label&&p.data.label.formatter)||'';if(/^L-/.test(label))focusGap(label);});
  document.querySelectorAll('[data-copy-target]').forEach(button=>button.addEventListener('click',async()=>{
    const target=document.getElementById(button.dataset.copyTarget);const text='value' in target?target.value:target.textContent;const status=button.parentElement.querySelector('.copy-status');
    try{await navigator.clipboard.writeText(text);status.textContent='已复制';}catch(_){if(target.select)target.select();status.textContent='请按 Ctrl/Cmd+C 复制';}
  }));
  window.addEventListener('resize',()=>{composition.resize();causes.resize();relation.resize();});
})();
"""


def render(result: dict) -> str:
    errors = validate(result)
    if errors:
        raise ValueError("GapAnalysis 校验失败：\n" + "\n".join(errors))
    rendered_result = json.loads(json.dumps(result, ensure_ascii=False))
    rendered_result["chartData"] = {"actionableCauseCounts": actionable_cause_counts(result)}
    payload = json.dumps(rendered_result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    values = {
        "{{report_title}}": _h(f"AI—人工审核差距分析 · {(result.get('project') or {}).get('projectId', '')}"),
        "{{report_content}}": _render_sections(result),
        "{{report_payload}}": payload,
        "{{echarts_bundle}}": ECHARTS_PATH.read_text(encoding="utf-8"),
        "{{report_javascript}}": _report_javascript(),
    }
    for key, value in values.items():
        template = template.replace(key, value)
    if re.search(r"\{\{[a-z_]+\}\}", template):
        raise ValueError("HTML 模板仍有未替换占位符")
    return template


def _cmd_validate(args) -> int:
    result = load_result(Path(args.input))
    errors = validate(result)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("OK")
    return 0


def _cmd_render(args) -> int:
    result = load_result(Path(args.input))
    document = render(result)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")
    print(output)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="CRWU AI—人工审核差距分析校验与单文件 HTML 渲染")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="校验 GapAnalysis JSON")
    validate_parser.add_argument("--input", required=True)
    validate_parser.set_defaults(func=_cmd_validate)
    render_parser = subparsers.add_parser("render", help="渲染自包含单文件 HTML")
    render_parser.add_argument("--input", required=True)
    render_parser.add_argument("--output", required=True)
    render_parser.set_defaults(func=_cmd_render)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
