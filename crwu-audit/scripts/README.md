# CRWU 审核意见交付工具（AuditResult 校验 + 单文件 HTML 渲染）

本目录实现《CRWU 审核意见 HTML 送达规范 v1.6》的**机器可校验 Schema**、**校验器**与**确定性 renderer**。
规范正文（唯一事实源）：本技能 `references/11-html-delivery-spec.md`。

| 文件 | 作用 | 对应规范 |
| --- | --- | --- |
| `audit_result.schema.json` | AuditResult JSON Schema（draft 2020-12）：必填、枚举、条件必填、路径安全 | §9.1–§9.3 |
| `audit_delivery.py` | 校验器 + renderer（纯标准库，无第三方依赖）；`validate` / `digest` / `render` 子命令 | §9.4、§10、§11.1、§12.2 |
| `upload_audit_result.py` | 最终态 AuditResult 钉钉回传：固定组织/空间/结果目录，按审核年月归档并写后验证 | `references/13-dingtalk-result-publish.md` |
| `template/audit-report.html`（从技能根目录定位） | 独立 HTML/CSS 模板：左侧目录、响应式正文、折叠轨迹与 A4 打印 | §10、附录 B |
| `examples/audit-result.sample.json` | 【示意】样例（数值与名称为占位，禁止当真值使用） | §9.3 |
| `test_audit_delivery.py` | 契约测试（Schema 语义、门禁、证据链、统计可重算、隐私、模板、目录、渲染确定性、转义、打印、空态） | §13.4 |
| `test_upload_audit_result.py` | 钉钉回传契约测试（组织门禁、年月目录、时间戳命名、重名保护、最终态门禁） | `references/13-dingtalk-result-publish.md` |

## 用法

```bash
# 阶段一冻结指纹（写入 AuditResult.phaseControl.phase1Digest）
python3 scripts/audit_delivery.py digest <冻结快照.json>

# 交付校验（渲染前）
python3 scripts/audit_delivery.py validate scripts/examples/audit-result.sample.json

# JSON 校验通过后，再成对输出 HTML 与监控留档 JSON（两者数据完全一致）
python3 scripts/audit_delivery.py render scripts/examples/audit-result.sample.json \
  --out 审核意见.PRJ-2026-0001.html \
  --json-out 审核结果.PRJ-2026-0001.json

# 校验渲染后状态（要求 fileTrace 摘要已回填）
python3 scripts/audit_delivery.py validate <rendered.json> --rendered

# 最终态监控 JSON 回传钉钉（只允许自动创建 YYYY/MM）
python3 scripts/upload_audit_result.py 审核结果.PRJ-2026-0001.json

# 契约测试
python3 scripts/test_audit_delivery.py
python3 scripts/test_upload_audit_result.py
```

退出码：`0` 通过；`1` 校验失败（错误逐条打印到 stderr，且**拒绝渲染**）。`render` 严格先做 JSON 校验；
任一输入错误都会返回精确 JSON 路径，并且 HTML、配套 JSON 均不落盘。校验通过后才在内存中渲染、自检，最后成对写出。
配套 JSON 是最终渲染态 AuditResult，必须与 HTML 内嵌 `#audit-result` 解析出的对象完全一致，供后续审核监控与统计使用。

## 材料准备与媒体证据通道（阶段一 / 阶段二复核件）

| 文件 | 作用 | 对应口径 |
| --- | --- | --- |
| `prepare_materials.py` | 材料盘点 + 隐藏区隔离（工作版重建）+ 归档解压 + **媒体证据导出与放行清单** | `references/00-input-and-route-profile.md` §Excel 隐藏数据隔离 |
| `media_extract.py` | 媒体抽取库：xlsx 绘图锚点 / docx·doc 正文图（段落序）/ PDF 内嵌图 / 独立图片；H0 与 fail-closed | 同上 §非单元格证据 |
| `test_prepare_materials.py`、`test_media_extract.py` | 上述两脚本的契约测试 | — |

```bash
# 阶段一：盘点 + 工作版 + 媒体证据（产出 材料盘点.json / 媒体索引.json / 提取/ / 工作版/ / 媒体证据/）
python3 scripts/prepare_materials.py --case <案例目录>

# 阶段二：复核件（复核意见附件里的图同样要抽取；产物名加后缀，绝不覆盖阶段一冻结产物）
python3 scripts/prepare_materials.py --case <案例目录> --src 复核-人工 --label 复核

# 契约测试
python3 scripts/test_prepare_materials.py
python3 scripts/test_media_extract.py
```

- `媒体索引.json` 是**媒体放行清单**：逐条含 `mediaId`、`kind`、受控 `locator`、`localPath`（案例内相对路径）、
  `sha256`、`evidenceChannel=host-vision`。叶子只按该清单消费（经宿主多模态读图），**不得自行解析 raw 原件包**。
- **H0**：锚点落在隐藏 sheet / 隐藏行 / 隐藏列的媒体**不导出、不定位**，只记 `hiddenSkippedCount`；
  锚点不可判定或隐藏结构不可得时 fail-closed 不导出，并记 `unresolvedReasons[]` —— **未核 ≠ 缺失**。
- 可选依赖：`openpyxl`（xlsx）、`pypdf`（PDF 内嵌图）。缺 `pypdf` 时 PDF 媒体本次未核，脚本会在盘点与
  标准输出显式汇报，**不得**当作"材料缺失"。

## 编排层接入（脚本映射）

调用者唯一：`crwu-audit` 编排层（router）。叶子不得调用校验器/渲染器，也不得生成页面或定义最终字段。
规范口径见本技能 `references/11-html-delivery-spec.md` §14.1。

| 编排阶段 | 命令 | 失败处理 |
| --- | --- | --- |
| 阶段一冻结（router 步骤 11） | `digest <冻结快照.json>` → 写入 `phaseControl.phase1FrozenAt` / `phase1Digest` | 失败 → 不进阶段二，记 capability gap |
| 阶段二收口（router 步骤 14 ①） | `validate 审核意见.<项目ID>.json` | 失败 → 停止交付、逐条报错，禁止绕过或删检查 |
| 阶段二收口（router 步骤 14 ②） | `render … --out 审核意见.<项目ID>.html --json-out 审核结果.<项目ID>.json`（内置 JSON 校验与渲染后自检） | 失败 → HTML 与配套 JSON 均不产出，记 capability gap，**不得跳过 JSON 校验出 HTML** |
| 交付（router 步骤 14 ③） | 员工侧交付 HTML；内部监控读取配套 JSON，且该 JSON 与 HTML 内嵌对象逐字段一致 | — |
| 钉钉回传（router 步骤 15） | `python3 scripts/upload_audit_result.py 审核结果.<项目ID>.json` | 失败 → 保留本地交付件并报告真实原因；不得换组织、猜目录或覆盖同名文件 |

`digest`、`render` 共用同一规范化序列化（排序键、UTF-8、无多余空白），故冻结指纹可复现，且可与
`fileTrace.sourceDigest` 互校；脚本仅依赖 Python 标准库。

### JSON 与员工页面映射

- 首屏「AI 检出问题 / 待人工确认 / 未检查项」分别来自 `summary.counts.issuesTotal`、
  `summary.counts.pendingConfirmation`、`summary.counts.notChecked`；计数还会根据明细重算，不一致即拒绝交付。
- 三行「优先处理 / 继续核对 / 人工确认」只摘取 `issues[]` 的严重度与标题、
  `manualConfirmationItems[]` 的标题，不生成新审核事实；完整 `summary.narrative` 默认折叠保留。
- 问题位置只来自 `issues[].locationSummary` 与 `issues[].materialEvidence[]` 的文件名、定位，
  不拿修改建议冒充问题位置。
- 三张计数卡分别跳转到问题项、人工确认和 `scope.notCheckedItems[]` 对应区块；
  「需要人工确认事项」紧跟「AI 检出的问题项」，方便连续处理。
- AI 问题、人工确认、复核意见和未检查项均显示区内连续序号；稳定业务 ID 仍从 JSON 原样保留。
- `L-unclosed` 完全由 `reviewItems[].inFileResolution` 驱动：首屏结论给出直达告警，《人工复核对照》标题下前置总数，各级摘要与具体条目同步显示异常标签。
- 外部数据核验先读取 `externalDataVerification.applicability`：`not_applicable` 显示“不适用”、原因和知识库依据，且不显示数据源告警；只有 `required` 才展示来源可用性与逐项核验结果。

这些展示均由最终配套 JSON 确定性派生；renderer 不新增业务字段，`schemaVersion` 为 `1.2.0`。

## 校验器覆盖的强制规则（§9.4 / §11.1 / §12.2）

1. `issueId` / `ruleId` / `recordId` 等在各自作用域内唯一；
2. `decision=fail` 且 `issueType=rule_defect` 时，规则证据与材料证据**均不得为空**；
3. `authorityClass=external_formal` 必须具备名称、版本次数状态、条款与来源；版本不得写“现行/现行有效”；
4. `kbRelativePath` 必须是知识库相对路径（拒绝 `/`、盘符、`~`、`file://`）；
5. `manualConfirmationItems` 不计入不通过数量（`summary.counts` 由明细重算比对）；
6. `summary.counts`、规则 `usageCount`、`usedByIssueIds`、复核三条带及 `reviewItems` 客观命中率均可由明细重算，不一致即失败；
7. 阶段二完成（`phase2CompletedAt`）时每条阶段一 issue 必须有 `reviewComparison`，复核独有项必须进 `reviewerOnlyItems`；
8. `reviewAccessedAt` 必须晚于 `phase1FrozenAt`（阶段一先冻结，阶段二才可读复核记录）；
9. 未检查项 `reasonCode` 受控枚举；`scope.notCheckedItems` 显式（无则空数组）；
10. 敏感信息扫描：绝对路径、`file://`、`nodeId`、凭据类字段名一律拒绝（§10.1 / §12.2）。
11. 已关闭的 `false_positive` 不得继续以有效问题项保留在 `issues`；`L-unclosed` 必须同时给出答复与在件核验证据。
12. **问题描述写法（§4.6）**：`problemDescription` 必须是「首句 + 明细」两段式——首句 ≤60 字、以句读收尾、一句话说清问题是什么；
    明细 2–4 行、每行 ≤80 字、全字段 ≤420 字，每行以句读或可核对落点（文件名/sheet/单元格/页码）收尾；
    首句与明细不得含规则编号（`RULE-`/`CHK-`/`kb_id`）、知识库相对路径或 `issueId` 形态的内部代号；明细须给出本次材料的可核对落点。
    首句另不得含公式串（`=SUM(...)`）、区域坐标（`AD6:AD10`）、`文件!表` 定位串或案例目录内相对路径（`工作版/…`、`提取/…`）——
    这类坐标移到明细行。不合格即校验失败、拒绝渲染，堵住“员工读不懂的长描述”。
13. `externalDataVerification.applicability` 必填；`not_applicable` 时来源、检查项必须为空且禁止不可用声明，只有 `required` 才允许记录数据源不可用与未检查。

## renderer 行为（§10）

- **单一事实源**：只从 AuditResult 渲染；不接受额外业务输入，不新增/删除/合并/改写任何结论；
- **确定性**：同一输入 + 同一 renderer 版本 → 逐字节一致输出（`render` 可重复比对）；
- **自包含**：CSS 内嵌，无外链字体/样式/脚本/图片，无遥测；动态内容全部 HTML 转义；
- **独立模板**：页面结构和 CSS 只维护在 `template/audit-report.html`；桌面端左侧目录可直达全部区域，窄屏转为顶部目录，打印时隐藏；
- **完整结构**：中瑞世联AI审核报告 - [报告流水号ID] → AI 检出的问题项 → 需要人工确认事项 → AI 外部数据核验结果 → 人工复核对照 → AI 审核表现评分卡
  → 本次审核依据 → 审核范围与未检查项 → 专业审核轨迹（默认折叠）→ 文件追溯信息；
- **问题卡片**：位置和问题直接可读；**问题描述按 §4.6 分行呈现——首句为加粗单行结论，明细逐行列点**，不拼成一整段；阶段二已执行时单列 AI 独立检出总数及高/中/低分布，`category=B` 卡片在标题区显示“AI 独立发现”；修改意见收进“展开修改意见（共 N 项）”，规则、材料、差异与结论收进另一带计数的明确展开控件；打印时两类折叠内容完整展开，严重程度**文字标签 + 颜色**并存；
- **复核对照**：按文件声明顺序列出复核层级，逐级显示已验证修改、精确/部分/未命中及命中率；`L-unclosed` 在首屏、复核区标题下、复核级次与条目四处联动提示，并高亮呈现答复与实际未落实证据；
- **客观评分卡**：命中率=`(exact+partial)/evaluable`（**部分命中计为命中，只是层次较低**），精确/部分/未命中作为命中层次单列；`L-resolved` 与 `L-uncheckable` 不进分母，综合率按明细加权重算；
- **A4 打印**：`@page { size: A4; margin: 16mm 15mm 18mm; }`、卡片 `break-inside: avoid`、表头跨页重复，
  黑白可读；`renderPolicy.printTrail=true` 时轨迹默认展开；
- **空态显式**：空列表输出“本次无此类事项”，不留空白标题或隐藏事实；
- **嵌入 JSON**：`<script id="audit-result" type="application/json">` 承载同源完整对象（`<` 转义为 `\u003c`），
  `fileTrace.sourceDigest` / `embeddedJsonDigest` 为 sha256 规范化摘要，可离线追溯。

## 维护规则

- 规范字段变更 → 同批更新 `audit_result.schema.json` + `audit_delivery.py` + 测试 + 规范正文 §9/§10；
  破坏性字段变更提升 `schemaVersion` 主版本，兼容新增提升次版本（§12.1）；
- renderer 任何字段映射、排序、打印或转义逻辑变化 → 记录 `fileTrace.rendererVersion`（`RENDERER_VERSION`）；
- 收紧既有字段的**写法约束**（如 §4.6 问题描述两段式）→ 同批更新规范正文、本 README 的强制规则清单、样例 JSON 与测试；
  此类约束会让旧 JSON 校验不通过，属于交付口径变更，但不新增/删除字段，故 `schemaVersion` 次版本不变（§12.1）；
- 叶子 Skill 不得生成页面或定义最终字段（§12.2 / §13.1）；本工具只被编排层在阶段二收口调用。
