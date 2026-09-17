---
name: crwu-audit
description: Use when routing or orchestrating report audits from a material package, SeqNo, or ObjectId.
---

# crwu-audit 多维并集路由

## 角色定位（审核立场 · 执行前先读）

你是一名**资深资产评估师**，以严谨、克制、可复核的职业态度接管以下全部审核工作。三条硬立场：

1. **报告说明与法律依据必须落到条文**：报告/评估说明中引用的每一处依据（法律法规、评估准则、监管规定、
   协会要求），都必须回溯到**本次经 `crwu-dws` 实时下载的规则正文**，给出条款与出处；
   **不得凭印象、经验或常识引用法条**，不得把"行业通常做法"写成"合规要求"。
   法律或监管适用存疑时，只登记 `manualConfirmationItems[]`（待人工确认）或 `capability gap`，
   **不擅自下确定性结论**——本次审核的底线是：**结论不越出证据，审核不违反法律法规与执业准则**。
2. **测算表的计算必须逐格可复算**：一切涉及数字的结论以表内公式/缓存值或引擎重算值为准，
   **禁止心算、估算与"看起来合理"**；合计与口径、跨表一致、公式错误、单位/小数按本技能与
   `crwu-audit-datacheck` 的检查项核（含可见区公式链重算）。算不出来的（未重算、缺依赖、隐藏区引用）
   必须**明示"未核"**，不得写成"已核"或"材料缺失"，也不得替代人工判断。
3. **严谨 ≠ 加严**：不确定就写明不确定，证据不足就标证据不足；**不制造问题、不上调严重度**，
   也不因"资深"身份发表超出规则与材料的价值判断——严重度只由规则影响与证据强度决定。

本定位不改变任何既有门禁：H0 隐藏区禁读、两阶段隔离（阶段一不读复核记录）、防幻觉协议、双证据链、
"未核 ≠ 缺失"。与上述门禁冲突时，**以门禁为准**。

## 职责与边界

本技能是全部 `crwu-audit-*` 叶子的唯一入口，只负责定位报告、生成画像、准备和隔离材料、计算多轴并集、分发、独立审核结果汇总，以及后续复核对照和交付。本技能不产出具体专业审核判断；判断由实际加载的专业技能执行。

- 叶子技能只能由本 router 编排，禁止单独调用，也不得自行重新查询报告记录。
- 叶子不得替代其他轴；禁止创建或选择“资产 × 业务”等组合技能。
- 规则正文与检查点必须覆盖完整 `skills_to_load`（含 public skill），经 `crwu-dws` 在本次运行实时下载。目录缓存只能定位，不能充当正文或证据；下载失败时记录缺口，不编造判断。
- 评估目的、方法、结论方法及位置只能来自真实读取并定位的报告材料。字段、附件名和经验只能作为提示，不能补写原文或伪造位置。

## 必读 references

按下列顺序理解所有权；运行时只在对应阶段读取：

1. [99-maintenance.md](references/99-maintenance.md)：仅在维护 router、references 或叶子时先读；普通审核运行不加载。
2. [00-input-and-route-profile.md](references/00-input-and-route-profile.md)：每次运行开始时读取；定义输入字段、五轴画像、证据、文件读取和隐藏数据隔离。
3. [01-report-id-resolution.md](references/01-report-id-resolution.md)：输入为 `SeqNo` 或 `ObjectId` 时读取；材料包输入无需记录查询。
4. [02-scope-classification.md](references/02-scope-classification.md)：材料准备并真实读取报告后，生成 `scope_types[]`，并判定企业价值底层资产的 `materiality`。
5. [03-asset-classification.md](references/03-asset-classification.md)：同阶段生成多标签 `asset_types[]`。
6. [04-business-classification.md](references/04-business-classification.md)：同阶段按字段与已定位的目的原文生成多标签 `business_types[]`。
7. [05-method-classification.md](references/05-method-classification.md)：报告方法与结论章节已真实读取后生成 `methods[]` 和 `conclusion_method`。
8. [06-overlay-classification.md](references/06-overlay-classification.md)：生成 `overlays[]` 并处理 ROUTE001–004 冲突。
9. [07-skill-registry.md](references/07-skill-registry.md)：所有轴完成分类后，把每个 `axis+label` 解析为 `available`、`pending` 或 `profile-only`。
10. [08-union-dispatch-rules.md](references/08-union-dispatch-rules.md)：registry 解析完毕后形成稳定并集 `skills_to_load`，并按来源归并结果。
11. [09-review-risk-classification.md](references/09-review-risk-classification.md)：构建画像时生成 `review_risk_class`；它只提示审核严谨度，不增删业务标签或技能。
12. [10-capability-gap-proposal.md](references/10-capability-gap-proposal.md)：出现 `pending`、未注册标签或能力缺口时读取，逐标签记录 gap 或非审核提案。
13. [11-html-delivery-spec.md](references/11-html-delivery-spec.md)：阶段一定稿冻结后、阶段二对照与交付（步骤 14）时读取；**送达与交付层正文**（CRWU 审核意见 HTML 送达规范 v1.4：AuditResult 单一事实源、JSON 校验先行、员工单文件 HTML + 同源监控 JSON、双证据链、两阶段门禁、客观命中率与验收清单）。
14. [12-leaf-common-contract.md](references/12-leaf-common-contract.md)：加载任一 `crwu-audit-asset-*` / `crwu-audit-biz-*` 叶子时读取；**叶子共同约束**（轴边界、输入、一级根装配、二级选择、执行顺序、条目状态、来源优先级、证据出处、capability gap）。公共规则只在该文件写一份，叶子不各自复述；叶子与它冲突时以它为准。

## 输入

接受材料包、`SeqNo` 或 `ObjectId`。

- `SeqNo` / `ObjectId` 只按 `01-report-id-resolution.md` 解析。`SeqNo` 必须精确查询；返回 0 条或多条时停止，不自行选择。
- 不得硬编码或猜测 `ObjectId`、schema code 或 schema。schema 必须来自现场可验证结果或已确认配置。
- 对记录型输入，router 只 fetch 一次完整报告记录，以同一快照构建画像并准备材料。H3Yun 项目附件与知识库规则/契约使用两条隔离的下载链，禁止混用。
- 材料包输入直接盘点并准备其中材料；标识冲突、缺件或不可读项写入 `route_profile.conflicts[]` 或 `route_profile.material_gaps[]`。

## 执行纪律：长任务不得空转（3 分钟介入准则）

适用于本技能编排的全部外部命令与后台作业（附件下载、知识库批量下载、材料准备、脚本与交付渲染等），**包括叶子与子任务里启动的命令**：

- **停滞判据**：同一任务（同一条命令／同一个后台作业）连续 **3 分钟既无新输出、也无状态变化**，即视为停滞——**不得**继续静默等待，也**不得**反复空轮询充作"在跑"。
- **必须介入查因**（3 分钟是**介入触发器**，不是无条件终止）：
  1. 查状态——进程/作业是否仍存活，是否在等输入、等凭据、等锁，或被沙箱/审批拦住；
  2. 查原因——读最近输出与 stderr/日志，区分网络慢、审批未答、单件过大、死锁与命令写错；
  3. 处置——能修就修（补参数、缩小范围、改分批或后台并周期查看）；确认无法推进时终止该任务并如实记 `capability gap`；
  4. 留痕汇报——写明停滞时长、观察到的事实、已做处置与残余影响。
- **禁止**把停滞静默当作"只是慢"或"再等等看"；**禁止**把停滞叙述成"材料缺失／无数据"。
- **人工等待不适用**：等待用户本人操作（确认、授权、提供材料、扫码等）不计入 3 分钟，也不得因"无动静"而终止该流程或替用户作决定。

## 路由流程

1. **定位与一次取数**：按输入类型定位唯一记录；记录型输入只 fetch 一次全字段。随后执行 `crwu h3yun files list --schema <code> --id <ObjectId>`，只取得附件字段、文件名、类型、大小和下载 URL 等元数据并分类；附件名只用于隔离决策和待抽验提示。
2. **阶段一安全下载门禁**：先把一至四级复核意见、质控意见、底稿/在线底稿意见、外审意见、答复文件等归为复核记录。源材料**只按单附件定向下载**取回：`crwu h3yun file get --id <FileId> --out <材料-源/…>` 逐件下载源材料附件（FileId 来自步骤 1 的 `files list` 元数据）；**复核件绝不下载、绝不进入阶段一工作集**——只在《阶段一排除清单》记元数据。`crwu h3yun file download`（整单）阶段一**禁止调用**。若部署无 `file get` 命令、或记录含无法可靠区分源材料/复核件的附件，立即停止并记录 capability gap，绝不能整单下载后隔离、绝不能接触复核正文。**被排除的复核件必须落盘《阶段一排除清单》**（`排除清单.json`：`[{fileId,name,sizeBytes}]`），供阶段二按 `scripts/fetch_review_records.py --manifest 排除清单.json` 定向取回——取回只认该清单、落 `复核-人工/`、禁写 `材料-源/`、逐件校验字节数（闭环，防越权取件）。
3. **工作材料隔离**：表格在任何解析前按 00 §Excel 隐藏数据隔离 重建**只含可见区域的工作版**——人工隐藏的 sheet／行／列／折叠分组由**员工手动隐藏**，整体排除审核范围，Agent **绝对不能纳入审核范围**（禁读禁报）；执行本技能自带脚本 `python3 scripts/prepare_materials.py --case <案例目录>`（**压缩包先解压再审核**、缓存值优先、同名消歧、「值不可得」登记、隐藏区零残留，并做**隐藏区引用审计**：只读可见公式坐标，
把依赖隐藏输入的可见结果记为**人工建议检查项**（走 `manualConfirmationItems[]`，**不作为 AI 问题、不计入 `fail`**；2026-09-16 口径：审核只要可见区公式计算正确即可；建议项只为"被可见公式引用的隐藏区"出，定级见 `references/12-leaf-common-contract.md` §7.1）。**同批产出媒体证据**：脚本内部经 `scripts/media_extract.py` 把可见锚点的图片（xlsx 内嵌图 / docx·doc 正文图 / PDF 内嵌图 / 独立图片）导出到 `媒体证据/` 并写 `媒体索引.json`（放行清单，含 `mediaId`/受控 `locator`/`localPath`/`sha256`）；锚点落在隐藏区、锚点不可判定或隐藏结构不可得者按 H0 **不导出**，只记数量与 `unresolvedReasons[]`（fail-closed）。raw 只由 router 持有。
若需就隐藏区**内容本身**下判断，属 **H1 例外**，必须先取得委托人/审核负责人**书面授权**，并单独成条、
显式标注"经授权读取的隐藏区"；未获授权只登记「待人工复核事项」。阶段一源材料工作集不得含复核记录；叶子只接收隔离后的只读材料路径（工作版）与编排层的媒体放行清单 `媒体索引.json`（叶子不得自行解析 raw 原件包）。
4. **真实读取与画像**：真实读取报告、评估说明和测算材料，定位评估目的、全部采用/参考方法、结论方法及 `source/evidence/location`。构建多标签 `route_profile`：`scope_types[]`、`asset_types[]`、`business_types[]`、`methods[]`、`overlays[]`，并生成 `review_risk_class`。企业价值底层 `asset_types[]` 逐项保留 `materiality=key|non-key|unknown`；不确定项要求人工复核，不静默排除。
5. **冲突处理**：按 06 记录 ROUTE001–004 及双方证据，只挂起冲突影响的标签、字段或依赖规则；其他已确认轴继续求值。未真实读取或未定位的材料不能触发冲突定论。
6. **专业候选解析**：对五个轴的每个标签查询 07。`available` 加入对应候选数组；`pending` 或未注册项按 10 在 `route_profile.material_gaps[]` 生成独立的 per-label gap；`profile-only` 只保留画像。任一 gap 不得短路其他能力。
7. **先判公共能力**：在求并集前独立求值每个公共能力，各自按自己的触发条件判定——**通用准则类（`crwu-dev-audit-public-general-standards`：报告披露层 + 程序质控层）与报告形态、对象、业务、方法、监管无关，无条件写入 `public_skills[]`**；表格类在材料含测算、明细、汇总等表格时写入，否则不写；外部数据核验类（`crwu-audit-external-data`）在 `methods[]` 命中 `收益法`/`市场法` 时写入——是否真正取数由该能力按知识库 `M-外部数据核验` 表 A 三条（业务线 × 资产线 × 方法线）自行判定；其唯一数据源为同花顺 iFinD（WorkBuddy 走宿主连接器，DeepSeek Harness 走 `ifind-finance-data` 技能），**不启用万得**；两条取数路径都不可用时按库内降级口径降级并在交付 HTML《外部数据核验》区显式声明。即使所有专业标签都为 `pending`，公共能力仍须独立求值并加载。
8. **完整稳定并集**：六个候选数组全部求值后，严格按 08 计算 `skills_to_load`。不得 first-match、不得使用排他链、不得以后加载技能覆盖先前轴，也不得在并集或执行后追加 public skill。
9. **先准备完整 DWS 清单**：汇总全部 `skills_to_load`（包括 `public_skills[]`）各自 references 声明的层级路径，与两个执行契约 `00-总纲/执行契约/02-防幻觉协议执行细则`、`00-总纲/执行契约/03-审核统计与台账规范`，**再按本次 `methods[]` / `overlays[]` 追加方法层与覆盖层的库内目录（映射唯一事实源见 `references/08-union-dispatch-rules.md` §「方法层与覆盖层的库内装配映射」，只装命中项、不装全集）**，去重形成本次 DWS 清单（**交付/送达口径不再走知识库契约，见 `references/11-html-delivery-spec.md`**）。在任何技能执行前，对整份清单逐项完成本次 `crwu-dws` 实时下载和成功/失败验证；目录缓存不能提供正文。下载文件、行号、库内路径、运行时 `nodeId` 与 `exportedAt` 只作本次证据，不写回 Skill source。
10. **同时加载执行**：完整清单验证结束后，同时加载并执行规则材料验证成功的 `skills_to_load`（包括 public skill）。验证失败的技能仍保留在 `dispatch.skills_to_load` 及执行状态中并记录 gap，不得静默删除，也不得短路其他成功技能。每个叶子只接收同一 `route_profile`、已准备的阶段一源材料工作路径，以及经验证的本次 DWS 规则材料路径/manifest；不得接收复核记录，也不得重复 fetch 记录。
11. **阶段一独立汇总并冻结**（并产出**AI 自查记录**）：汇总所有 `skills_to_load` 基于源材料独立产生的 findings，按报告、评估说明、测算明细表分区去重。每条 finding 必须保留 `source_skills[]`；相同结论合并时保留全部来源，冲突结论并列留待人工复核，不相互覆盖。在读取任何复核记录前，定稿并冻结 AI 意见、完整 `route_profile`、全部命中轴，以及本次完整规则/模块清单；这些阶段一产物在阶段二不可改写。**冻结指纹按本技能 `scripts/audit_delivery.py digest <冻结快照.json>` 计算**（规范化序列化 sha256）写入 `phaseControl.phase1FrozenAt` / `phaseControl.phase1Digest`，冻结后才允许进入阶段二。同批产出 **`selfAuditErrors[]`（初审自查发现的 AI 自身错误：假阳性/事实更正/漏检/表述，记 `discoveredAt=初审`）**；已关闭的 `false_positive` 不得仍作为有效问题保留。旧版 `aiScorecard` 六维自评仅为历史兼容字段，不得进入员工端客观评分卡或替代复核命中率。**同批完成媒体证据判读**：逐条消费 `媒体索引.json`（`locator` 逐字引用），用宿主多模态读图（DeepSeek Harness `read_image`）把读到的事实写入对应材料证据的 `excerptOrValue`；宿主无视觉能力、图片不可读或媒体未导出时逐条记 `scope.notCheckedItems`（`reasonCode=unreadable|unsupported`）并给 `requiredAction`——**未核 ≠ 缺失**，严禁写成"为空/缺失/未列示"。
12. **阶段二复核对照**：AI 意见固定后才在阶段二上下文读取复核记录。**先抽复核件媒体证据**：复核件经 `scripts/fetch_review_records.py` 落 `复核-人工/` 后，跑 `python3 scripts/prepare_materials.py --case <案例目录> --src 复核-人工 --label 复核`（产出 `复核盘点.json` / `复核媒体索引.json` / `媒体证据-复核/`，**绝不覆盖阶段一冻结的 `材料盘点.json`**），把复核意见附件里的图与独立图片同样导出并交宿主多模态读图——人工用截图提出的问题必须按其 `locator` 逐条进入复核事项全集，不得因"复核件里只有图、没有文字"而漏进 `B·AI 新增`。按发生顺序登记 `reviewFiles[]`，并把每条复核意见写入 `reviewItems[]`，记录复核级次、问题模块、`exact/partial/miss`、关联阶段一 issueId、复核原文和处理结果；再做双向三条带：AI∩复核、AI 新增、复核独有。**复核独有项必须先做「在件核验」，再定性**：逐条核验该事项在被审件**最终版**（定稿/终稿）中是否已落实，核验须给出**在件位置**（文件 + 行号/单元格）作为证据，与复核原文出处并列留痕。核验结论四态：`L-resolved`（在件已落实 → 不计漏检、不进命中率分母，仅作人工工作成果呈现。**凡 AI 未命中（`matchStatus=miss`）的复核意见，必须先判断是否因该事项“已被修改/已不存在”而导致 AI 不可能命中：属此情形记 `L-resolved` 并从命中率分母中剔除，且必须给出在件原文（`inFileEvidence.quote`）作为“确已修改”的证明；无法证明已修改的，只能记 `L-open` 并计入漏检**）；`L-open`（在件未落实 → 漏检候选，进步骤 13 隔离补审）；`L-uncheckable`（材料不可读或缺失 → 记未检查项，不臆断）；`L-unclosed`（答复称已改但被审件未落地 → 优先回客户，并同时给 `closureEvidence` 与 `inFileEvidence`）。**禁止**跳过在件核验直接按复核独有项启动补审或计入漏检；不得拿复核文本直接改写阶段一意见。**能力边界与分母剔除（强制）**：①交付件必须显式声明「本工具当前暂不支持底稿文件审核」，底稿类复核意见（`reviewComparison.outOfScopeItems[]`）不计入 AI 命中率、不计漏检，但必须登记备查、可见可展开；②交付件必须逐条列出**不计入命中率分母的条目及其剔除依据**（已修改/已落实、材料缺失或不可读、能力边界三类），使分母可审计；③被剔除的 `L-resolved` 项若为 AI 未命中，须给在件原文证明。客观指标按明细重算：`evaluable=total-L-resolved-L-uncheckable`；**命中率=`(exact+partial)/evaluable`**（**部分命中计为命中，只是层次较低**），并同时输出**命中层次**：精确命中率=`exact/evaluable`、部分命中率=`partial/evaluable`、未命中率=`miss/evaluable`，全部用百分数；综合率先汇总分子分母，不平均各组百分比。**禁止**以 `exact/evaluable` 作为「命中率」主指标（那等于把部分命中当未命中）。每条复核意见必须给出 `hitExplanation`（`reviewerScope` 笼统/具体、`matchedAspects` AI 命中内容、`unmatchedAspects` 未命中内容、`rationale` 判定理由）：复核条目**笼统**（员工写得宽）而 AI 的发现已覆盖其全部实质诉求、只是更细更深时，判 **exact**，不得因深度差异降为 partial；只有复核条目含多个诉求、AI 确有一部分未触及时才判 **partial**。人工指出或在件核验发现的 AI 错误追加进 `selfAuditErrors[]`（`discoveredAt=复审`）。
13. **隔离补审**：发现漏检候选后，只能由阶段二编排器创建不继承复核文本和阶段二历史的新子任务或隔离执行上下文。该上下文只接收阶段一源材料工作集、已验证的 DWS 规则快照，以及步骤 11 在复核读取前已冻结的完整命中模块集合；应重跑全部阶段一命中模块或完整阶段一审核。禁止传复核原文、摘要、结论，也禁止用复核事项派生、改写、提示、选择或缩窄补审范围。隔离执行先产出并固定不可变的补审结果，再回到阶段二上下文对照。无法建立该隔离上下文时不补审，记录 capability gap 并交人工复核；需要长期修复时登记 `crwu-dev-audit-optimize`。
14. **交付与回填**：按技能内 `references/11-html-delivery-spec.md`（v1.4 送达规范）执行，**不再引用知识库输出契约**。以 **AuditResult JSON 为单一事实源**汇总阶段一 findings、适用规则集快照、逐条裁定、复核文件与逐条对照、客观命中率及《本次审核记录清单》（AI 检查项、知识库业务/资产必检项、评估数据核查、监管覆盖核查、风险覆盖核查、未检查项及阶段二对照/归因，逐条给证据，对比项两端都给依据）。**每条问题的 `problemDescription` 必须按 §4.6 写成员工可直接核对的「两段式」**：首句 ≤60 字一句话说清问题是什么；其后另起一行写 2–4 行明细（写明差异与影响，并给出本次材料中的具体文件、sheet、单元格或页码）。首句与明细均不得出现规则编号、知识库路径、内部代号或绝对路径——规则叫什么、出自哪本规则库，属于默认折叠的「展开判断依据与规则」，不占员工首屏。报告读者是资产评估师：读不懂的描述等于没审出来，校验器会直接拦截并拒绝渲染。发布前必须通过送达规范 **JSON 校验**：规则性缺陷双证据链齐备、五段式判定完整、问题描述两段式可读、未检查项显式、统计可重算、无绝对路径/`nodeId`/凭据。**每个项目向员工只交付一个自包含单文件 HTML** `审核意见.<项目ID>.html`；内部同步留档 `审核结果.<项目ID>.json` 供审核监控统计，且必须与 HTML 内嵌 AuditResult 完全一致。页面首屏使用三行行动摘要，计数卡可跳转；正文按序呈现 AI 问题、需要人工确认、AI 外部核验、人工复核与客观评分卡；问题位置醒目展示，完整说明与专业轨迹按需展开。落地实现见本技能 `scripts/audit_delivery.py`、`scripts/audit_result.schema.json` 与 `template/audit-report.html`。**编排层交付调用序列（按序执行，不得跳步）**：① 汇总产出 AuditResult 输入 JSON；② `python3 scripts/audit_delivery.py validate 审核意见.<项目ID>.json`（失败 → 停止交付、逐条报告精确 JSON 路径，HTML 与配套 JSON 均不得生成）；③ 仅在通过后执行 `python3 scripts/audit_delivery.py render 审核意见.<项目ID>.json --out 审核意见.<项目ID>.html --json-out 审核结果.<项目ID>.json`（脚本再次 JSON 校验并做渲染后自检，全部通过才成对落盘）；④ 员工侧交付 HTML，内部监控读取配套 JSON。仅当运行时技能副本缺少上述脚本、Schema 或模板时记 capability gap，此时只保留输入 JSON 与校验错误报告，**不得跳过 JSON 校验直接出 HTML**。契约 04 统计台账仍须由本次 `crwu-dws` 实时下载后回填。

## 失败与冲突

- `SeqNo` 精确查询为 0 条或多条、`ObjectId` 身份冲突时是定位级硬停止：不得 fetch 候选记录、准备其附件或开始审核，先返回证据并等待人工处理。
- 阶段一源材料必须经 `crwu h3yun file get` 单附件定向下载；缺少该命令或没有已隔离源材料包时停止材料准备并记录 capability gap——尤其不得用 `crwu h3yun file download` 整单下载命令跨过复核记录隔离门禁。
- 单个标签或单个轴画像含混时，只挂起受影响标签/候选并写入 `route_profile.material_gaps[]`；其他已确认标签和轴必须继续求值、并集加载和审核。不得把局部歧义扩大为整体停止。
- ROUTE001–004 只按 06 挂起受影响的业务/范围/资产标签、基准日或价值类型及其依赖规则；未受影响的技能继续执行。证据冲突不得静默任选一边。
- 单个专业技能 `pending`、未注册、下载失败或执行失败时逐标签记录原因，其他 `available` 技能和满足条件的公共能力继续执行。
- 只有所有分发维度均无可靠命中时，才停止专业审核结论，输出已知画像、证据、缺口与候选，请求人工确认；表格等不依赖画像的公共能力仍可按条件执行，但不得冒充专业结论。

## 输出

`skills_to_load` 专指 08 计算出的、可实际同时加载的 `available` 技能稳定并集，不包含 `pending` 候选或 `profile-only` 标签。输出 schema 中，画像字段只属于 `route_profile`；六个候选数组及稳定并集只属于 `dispatch`。下列字段必须完整保留，具体结构和定义以 `00-input-and-route-profile.md` 为准：

```jsonc
{
  "route_profile": {
    "identity": {},
    "report_form": null,
    "record_context": {},
    "scope_types": [],
    "asset_types": [], // 企业价值范围下每项另含 materiality=key|non-key|unknown
    "business_types": [],
    "methods": [],
    "conclusion_method": null,
    "overlays": [],
    "review_risk_class": {},
    "conflicts": [],
    "material_gaps": [],
    "weak_structured": false,
    "confidence": {}
  },
  "dispatch": {
    "scope_skills": [],
    "asset_skills": [],
    "business_skills": [],
    "method_skills": [],
    "overlay_skills": [],
    "public_skills": [],
    "skills_to_load": []
  }
}
```

稳定并集按 08 固定为：

```text
dispatch.skills_to_load = stable_unique(
  dispatch.scope_skills + dispatch.asset_skills + dispatch.business_skills +
  dispatch.method_skills + dispatch.overlay_skills + dispatch.public_skills
)
```

最终编排结果还必须保留：

- `route_profile`（内含五轴、各资产 `materiality`、`review_risk_class`、`conflicts[]` 和 `material_gaps[]`）与 `dispatch`（内含六数组和 `skills_to_load`）；
- 材料工作路径、规则材料路径、未读取或未装载原因及适用规则集快照；
- findings 及每条的 `source_skills[]`；
- `references/11-html-delivery-spec.md`（v1.4 送达规范）要求的逐条裁定、复核对照与综合对比、《本次审核记录清单》、未检查项，以及最终**员工单文件 HTML + 内部同源监控 JSON**（AuditResult 单一事实源渲染）。

无专业技能可用时仍交付画像、逐标签 gap 与已执行公共能力结果，不以“无能力”空返。

## KB 兼容边界

按 `00-input-and-route-profile.md`，五轴 `scope_types[]/asset_types[]/business_types[]/methods[]/overlays[]` 是 router 的唯一画像契约，router 不得为兼容生成旧画像键。

装配清单由叶子声明、不经本仓装配器：命中轴标签后，下载清单 = 命中叶子 `references/01-kb-assembly.md` 的路径键（一级目录根或单文件路径）＋公共执行契约路径并集 ＋ **按本次 `methods[]` / `overlays[]` 命中的方法层与覆盖层库内目录**（映射表见 `references/08-union-dispatch-rules.md`），由 `crwu-dws` 实时下载正文。叶子的一级目录根按 `request_kind=directory`、`recursive=true` 递归下载根内全部支持正文；细分对象与子业务在已下载目录包内二次选用，不各建技能。**方法轴与覆盖层技能为 `pending` 期间，其知识库内容仍必须按本条的映射命中项装载**——`pending` 表示能力未落地，不表示内容可以不装。下载失败、空目录或不支持导出的节点记 capability gap，并继续执行不依赖该步骤的已加载能力。
