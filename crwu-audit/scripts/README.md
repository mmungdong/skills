# CRWU 审核意见交付工具（AuditResult 校验 + 单文件 HTML 渲染）

本目录实现《CRWU 审核意见 HTML 送达规范 v1.0》的**机器可校验 Schema**、**校验器**与**确定性 renderer**。
规范正文（唯一事实源）：本技能 `references/11-html-delivery-spec.md`。

| 文件 | 作用 | 对应规范 |
| --- | --- | --- |
| `audit_result.schema.json` | AuditResult JSON Schema（draft 2020-12）：必填、枚举、条件必填、路径安全 | §9.1–§9.3 |
| `audit_delivery.py` | 校验器 + renderer（纯标准库，无第三方依赖）；`validate` / `digest` / `render` 子命令 | §9.4、§10、§11.1、§12.2 |
| `examples/audit-result.sample.json` | 【示意】样例（数值与名称为占位，禁止当真值使用） | §9.3 |
| `test_audit_delivery.py` | 24 项契约测试（Schema 语义、门禁、证据链、统计可重算、隐私、渲染确定性、转义、打印、空态） | §13.4 |

## 用法

```bash
# 阶段一冻结指纹（写入 AuditResult.phaseControl.phase1Digest）
python3 scripts/audit_delivery.py digest <冻结快照.json>

# 交付校验（渲染前）
python3 scripts/audit_delivery.py validate scripts/examples/audit-result.sample.json

# 渲染自包含单文件 HTML（送达员工的唯一交付件；内置渲染后自检）
python3 scripts/audit_delivery.py render scripts/examples/audit-result.sample.json --out 审核意见.PRJ-2026-0001.html

# 校验渲染后状态（要求 fileTrace 摘要已回填）
python3 scripts/audit_delivery.py validate <rendered.json> --rendered

# 契约测试
python3 scripts/test_audit_delivery.py
```

退出码：`0` 通过；`1` 校验失败（错误逐条打印到 stderr，且**拒绝渲染**）。

## 编排层接入（脚本映射）

调用者唯一：`crwu-audit` 编排层（router）。叶子不得调用校验器/渲染器，也不得生成页面或定义最终字段。
规范口径见本技能 `references/11-html-delivery-spec.md` §14.1。

| 编排阶段 | 命令 | 失败处理 |
| --- | --- | --- |
| 阶段一冻结（router 步骤 11） | `digest <冻结快照.json>` → 写入 `phaseControl.phase1FrozenAt` / `phase1Digest` | 失败 → 不进阶段二，记 capability gap |
| 阶段二收口（router 步骤 14 ①） | `validate 审核意见.<项目ID>.json` | 失败 → 停止交付、逐条报错，禁止绕过或删检查 |
| 阶段二收口（router 步骤 14 ②） | `render … --out 审核意见.<项目ID>.html`（内置渲染后自检） | 失败 → 不产出 HTML，记 capability gap（只交付 JSON + 错误报告），**不得跳过校验出 HTML** |
| 交付（router 步骤 14 ③） | 交付 HTML（唯一交付件）；JSON 内部留档并已嵌入同页 | — |

`digest`、`render` 共用同一规范化序列化（排序键、UTF-8、无多余空白），故冻结指纹可复现，且可与
`fileTrace.sourceDigest` 互校；脚本仅依赖 Python 标准库。

## 校验器覆盖的强制规则（§9.4 / §11.1 / §12.2）

1. `issueId` / `ruleId` / `recordId` 等在各自作用域内唯一；
2. `decision=fail` 且 `issueType=rule_defect` 时，规则证据与材料证据**均不得为空**；
3. `authorityClass=external_formal` 必须具备名称、版本次数状态、条款与来源；版本不得写“现行/现行有效”；
4. `kbRelativePath` 必须是知识库相对路径（拒绝 `/`、盘符、`~`、`file://`）；
5. `manualConfirmationItems` 不计入不通过数量（`summary.counts` 由明细重算比对）；
6. `summary.counts`、规则 `usageCount`、`usedByIssueIds`、复核三条带与命中率分母均可由明细重算，不一致即失败；
7. 阶段二完成（`phase2CompletedAt`）时每条阶段一 issue 必须有 `reviewComparison`，复核独有项必须进 `reviewerOnlyItems`；
8. `reviewAccessedAt` 必须晚于 `phase1FrozenAt`（阶段一先冻结，阶段二才可读复核记录）；
9. 未检查项 `reasonCode` 受控枚举；`scope.notCheckedItems` 显式（无则空数组）；
10. 敏感信息扫描：绝对路径、`file://`、`nodeId`、凭据类字段名一律拒绝（§10.1 / §12.2）。

## renderer 行为（§10）

- **单一事实源**：只从 AuditResult 渲染；不接受额外业务输入，不新增/删除/合并/改写任何结论；
- **确定性**：同一输入 + 同一 renderer 版本 → 逐字节一致输出（`render` 可重复比对）；
- **自包含**：CSS 内嵌，无外链字体/样式/脚本/图片，无遥测；动态内容全部 HTML 转义；
- **九区结构**：项目信息 → 审核结果概览 → 需要处理的问题 → 需要人工确认事项 → 本次审核依据（含规则地图）
  → 人工复核对照 → 审核范围与未检查项 → 专业审核轨迹（`details` 默认折叠）→ 文件追溯信息；
- **问题卡片**：规则 → 材料 → 差异 → 结论 → 修改 固定顺序，严重程度**文字标签 + 颜色**并存；
- **A4 打印**：`@page { size: A4; margin: 16mm 15mm 18mm; }`、卡片 `break-inside: avoid`、表头跨页重复，
  黑白可读；`renderPolicy.printTrail=true` 时轨迹默认展开；
- **空态显式**：空列表输出“本次无此类事项”，不留空白标题或隐藏事实；
- **嵌入 JSON**：`<script id="audit-result" type="application/json">` 承载同源完整对象（`<` 转义为 `\u003c`），
  `fileTrace.sourceDigest` / `embeddedJsonDigest` 为 sha256 规范化摘要，可离线追溯。

## 维护规则

- 规范字段变更 → 同批更新 `audit_result.schema.json` + `audit_delivery.py` + 测试 + 规范正文 §9/§10；
  破坏性字段变更提升 `schemaVersion` 主版本，兼容新增提升次版本（§12.1）；
- renderer 任何字段映射、排序、打印或转义逻辑变化 → 记录 `fileTrace.rendererVersion`（`RENDERER_VERSION`）；
- 叶子 Skill 不得生成页面或定义最终字段（§12.2 / §13.1）；本工具只被编排层在阶段二收口调用。
