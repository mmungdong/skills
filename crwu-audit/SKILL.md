---
name: crwu-audit
description: Use when routing or orchestrating report audits from a material package, SeqNo, or ObjectId.
---

# crwu-audit 多维并集路由

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
13. [11-html-delivery-spec.md](references/11-html-delivery-spec.md)：阶段一定稿冻结后、阶段二对照与交付（步骤 14）时读取；**送达与交付层正文**（CRWU 审核意见 HTML 送达规范 v1.0：AuditResult 单一事实源、单文件 HTML 交付、双证据链、两阶段门禁、验收清单）。
14. [12-leaf-common-contract.md](references/12-leaf-common-contract.md)：加载任一 `crwu-audit-asset-*` / `crwu-audit-biz-*` 叶子时读取；**叶子共同约束**（轴边界、输入、一级根装配、二级选择、执行顺序、条目状态、来源优先级、证据出处、capability gap）。公共规则只在该文件写一份，叶子不各自复述；叶子与它冲突时以它为准。

## 输入

接受材料包、`SeqNo` 或 `ObjectId`。

- `SeqNo` / `ObjectId` 只按 `01-report-id-resolution.md` 解析。`SeqNo` 必须精确查询；返回 0 条或多条时停止，不自行选择。
- 不得硬编码或猜测 `ObjectId`、schema code 或 schema。schema 必须来自现场可验证结果或已确认配置。
- 对记录型输入，router 只 fetch 一次完整报告记录，以同一快照构建画像并准备材料。H3Yun 项目附件与知识库规则/契约使用两条隔离的下载链，禁止混用。
- 材料包输入直接盘点并准备其中材料；标识冲突、缺件或不可读项写入 `route_profile.conflicts[]` 或 `route_profile.material_gaps[]`。

## 路由流程

1. **定位与一次取数**：按输入类型定位唯一记录；记录型输入只 fetch 一次全字段。随后执行 `crwu h3yun files list --schema <code> --id <ObjectId>`，只取得附件字段、文件名、类型、大小和下载 URL 等元数据并分类；附件名只用于隔离决策和待抽验提示。
2. **阶段一安全下载门禁**：先把一至四级复核意见、质控意见、底稿/在线底稿意见、外审意见、答复文件等归为复核记录。只有部署环境提供经验证的单附件/allowlist 下载能力，或用户已经提供确认隔离的源材料包，才继续准备报告、评估说明和测算材料。当前 `crwu h3yun file download --schema <code> --id <ObjectId> --out <dir>` 会下载整条记录的全部附件，阶段一禁止调用；如果只有该命令且记录含复核附件，立即停止并记录 capability gap，绝不能先整单下载再隔离或让模型接触复核正文。**被排除的复核件必须落盘《阶段一排除清单》**（`排除清单.json`：`[{fileId,name,sizeBytes}]`），供阶段二按 `scripts/fetch_review_records.py --manifest 排除清单.json` 定向取回——取回只认该清单、落 `复核-人工/`、禁写 `材料-源/`、逐件校验字节数（闭环，防越权取件）。
3. **工作材料隔离**：表格在任何解析前按 00 §Excel 隐藏数据隔离 重建**只含可见区域的工作版**——人工隐藏的 sheet／行／列／折叠分组由**员工手动隐藏**，整体排除审核范围，Agent **绝对不能纳入审核范围**（禁读禁报）；执行本技能自带脚本 `python3 scripts/prepare_materials.py --case <案例目录>`（**压缩包先解压再审核**、缓存值优先、同名消歧、「值不可得」登记、隐藏区零残留，并做**隐藏区引用审计**：只读可见公式坐标，
把依赖隐藏输入的可见结果标为「计算链不可复核」——属 H0 范围的可见区缺陷，必须出）。raw 只由 router 持有。
若需就隐藏区**内容本身**下判断，属 **H1 例外**，必须先取得委托人/审核负责人**书面授权**，并单独成条、
显式标注"经授权读取的隐藏区"；未获授权只登记「待人工复核事项」。阶段一源材料工作集不得含复核记录；叶子只接收隔离后的只读材料路径。
4. **真实读取与画像**：真实读取报告、评估说明和测算材料，定位评估目的、全部采用/参考方法、结论方法及 `source/evidence/location`。构建多标签 `route_profile`：`scope_types[]`、`asset_types[]`、`business_types[]`、`methods[]`、`overlays[]`，并生成 `review_risk_class`。企业价值底层 `asset_types[]` 逐项保留 `materiality=key|non-key|unknown`；不确定项要求人工复核，不静默排除。
5. **冲突处理**：按 06 记录 ROUTE001–004 及双方证据，只挂起冲突影响的标签、字段或依赖规则；其他已确认轴继续求值。未真实读取或未定位的材料不能触发冲突定论。
6. **专业候选解析**：对五个轴的每个标签查询 07。`available` 加入对应候选数组；`pending` 或未注册项按 10 在 `route_profile.material_gaps[]` 生成独立的 per-label gap；`profile-only` 只保留画像。任一 gap 不得短路其他能力。
7. **先判公共能力**：在求并集前独立求值每个公共能力，各自按自己的触发条件判定——**通用准则类（`crwu-audit-public-general-standards`：报告披露层 + 程序质控层）与报告形态、对象、业务、方法、监管无关，无条件写入 `public_skills[]`**；表格类在材料含测算、明细、汇总等表格时写入，否则不写。即使所有专业标签都为 `pending`，公共能力仍须独立求值并加载。
8. **完整稳定并集**：六个候选数组全部求值后，严格按 08 计算 `skills_to_load`。不得 first-match、不得使用排他链、不得以后加载技能覆盖先前轴，也不得在并集或执行后追加 public skill。
9. **先准备完整 DWS 清单**：汇总全部 `skills_to_load`（包括 `public_skills[]`）各自 references 声明的层级路径，与两个执行契约 `00-总纲/执行契约/02-防幻觉协议执行细则`、`00-总纲/执行契约/03-审核统计与台账规范`，去重形成本次 DWS 清单（**交付/送达口径不再走知识库契约，见 `references/11-html-delivery-spec.md`**）。在任何技能执行前，对整份清单逐项完成本次 `crwu-dws` 实时下载和成功/失败验证；目录缓存不能提供正文。下载文件、行号、库内路径、运行时 `nodeId` 与 `exportedAt` 只作本次证据，不写回 Skill source。
10. **同时加载执行**：完整清单验证结束后，同时加载并执行规则材料验证成功的 `skills_to_load`（包括 public skill）。验证失败的技能仍保留在 `dispatch.skills_to_load` 及执行状态中并记录 gap，不得静默删除，也不得短路其他成功技能。每个叶子只接收同一 `route_profile`、已准备的阶段一源材料工作路径，以及经验证的本次 DWS 规则材料路径/manifest；不得接收复核记录，也不得重复 fetch 记录。
11. **阶段一独立汇总并冻结**（并产出**初审自评**）：汇总所有 `skills_to_load` 基于源材料独立产生的 findings，按报告、评估说明、测算明细表分区去重。每条 finding 必须保留 `source_skills[]`；相同结论合并时保留全部来源，冲突结论并列留待人工复核，不相互覆盖。在读取任何复核记录前，定稿并冻结 AI 意见、完整 `route_profile`、全部命中轴，以及本次完整规则/模块清单；这些阶段一产物在阶段二不可改写。**冻结指纹按本技能 `scripts/audit_delivery.py digest <冻结快照.json>` 计算**（规范化序列化 sha256）写入 `phaseControl.phase1FrozenAt` / `phaseControl.phase1Digest`，冻结后才允许进入阶段二。同批产出 **`aiScorecard`（`level=初审`：六维自评 0–10、0.5 步长、每维必给打分依据；`composites.aiOnly`＝六维均值按 0.5 取整；初审不得填 corrections/withHumanLoop）**与 **`selfAuditErrors[]`（初审自查发现的 AI 自身错误：假阳性/事实更正/漏检/表述，记 `discoveredAt=初审`）**——用于量化 AI 审核与人工复核的差距（见 references/11 §6.3）。
12. **阶段二复核对照**：AI 意见固定后才在阶段二上下文读取复核记录。逐条标记 A（复核已提出，给出处）、B（AI 新增）、C（材料缺失或不可读而未对照）；再做双向三条带：AI∩复核、AI 新增、复核独有。**复核独有项必须先做「在件核验」，再定性**：逐条核验该事项在被审件**最终版**（定稿/终稿）中是否已落实，核验须给出**在件位置**（文件 + 行号/单元格）作为证据，与复核原文出处并列留痕。核验结论三态：`L-resolved`（在件已落实 → 不计漏检、不进命中率分母，仅作人工工作成果呈现）；`L-open`（在件未落实 → 漏检候选，进步骤 13 隔离补审）；`L-uncheckable`（材料不可读或缺失 → 记未检查项，不臆断）。复核记录若附**答复文本**（仅阶段二读取），须同步做**闭环核验**：核验“答复称已改”是否在被审件真正落地；未落地者单列 `L-unclosed`（已答复未落实），优先回客户。**禁止**跳过在件核验直接按复核独有项启动补审或计入漏检；不得拿复核文本直接改写阶段一意见。本步同批产出**复审自评**：`aiScorecard.level=复审`，`dimensions` 仍保存初审分，仅通过 `corrections[]{key,from,to,reason}` 做**补充与校正**（`from` 必须等于初审分，只增不覆盖），`composites.withHumanLoop`＝校正后六维均值按 0.5 取整；并把人工指出或在件核验发现的 AI 错误追加进 `selfAuditErrors[]`（`discoveredAt=复审`）。
13. **隔离补审**：发现漏检候选后，只能由阶段二编排器创建不继承复核文本和阶段二历史的新子任务或隔离执行上下文。该上下文只接收阶段一源材料工作集、已验证的 DWS 规则快照，以及步骤 11 在复核读取前已冻结的完整命中模块集合；应重跑全部阶段一命中模块或完整阶段一审核。禁止传复核原文、摘要、结论，也禁止用复核事项派生、改写、提示、选择或缩窄补审范围。隔离执行先产出并固定不可变的补审结果，再回到阶段二上下文对照。无法建立该隔离上下文时不补审，记录 capability gap 并交人工复核；需要长期修复时登记 `crwu-audit-optimize`。
14. **交付与回填**：按技能内 `references/11-html-delivery-spec.md`（v1.0 送达规范）执行，**不再引用知识库输出契约**。以 **AuditResult JSON 为单一事实源**汇总阶段一 findings、适用规则集快照、逐条裁定、复核对照与综合对比、《本次审核记录清单》（AI 检查项、知识库业务/资产必检项、评估数据核查、监管覆盖核查、风险覆盖核查、未检查项及阶段二对照/归因，逐条给证据，对比项两端都给依据）。发布前必须通过送达规范校验：规则性缺陷双证据链齐备、五段式判定完整、未检查项显式、统计可重算、无绝对路径/`nodeId`/凭据。**每个项目只交付一个自包含单文件 HTML** `审核意见.<项目ID>.html`（由 AuditResult 确定性渲染，可离线打开、A4 可打印、含默认折叠的专业审核轨迹；renderer 只呈现不改写，JSON 可嵌入同页但不作为独立交付件）。落地实现见本技能 `scripts/audit_delivery.py`（`validate` 校验 + `digest` 冻结指纹 + `render` 渲染）与 `scripts/audit_result.schema.json`（随技能安装）。**编排层交付调用序列（按序执行，不得跳步）**：① 汇总产出 AuditResult 写入 `审核意见.<项目ID>.json`；② `python3 scripts/audit_delivery.py validate 审核意见.<项目ID>.json`（在技能目录内执行）（失败 → 停止交付、逐条报错，禁止人工绕过或删检查）；③ `python3 scripts/audit_delivery.py render 审核意见.<项目ID>.json --out 审核意见.<项目ID>.html`（脚本内置渲染后自检，失败即报错且不产出 HTML）；④ 交付 HTML 为唯一交付件、JSON 作内部留档（已嵌入同页）。交付脚本随本技能安装（技能内 `scripts/`：`audit_delivery.py` + `audit_result.schema.json` + `examples/`）；仅当运行时技能副本缺该目录时记 capability gap，此时只交付 JSON 与校验错误报告，**不得跳过校验直接出 HTML**。契约 04 统计台账仍须由本次 `crwu-dws` 实时下载后回填。

## 失败与冲突

- `SeqNo` 精确查询为 0 条或多条、`ObjectId` 身份冲突时是定位级硬停止：不得 fetch 候选记录、准备其附件或开始审核，先返回证据并等待人工处理。
- 阶段一缺少经验证的单附件/allowlist 下载能力且没有已隔离源材料包时停止材料准备并记录 capability gap；尤其不得用全附件下载命令跨过复核记录隔离门禁。
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
- `references/11-html-delivery-spec.md`（v1.0 送达规范）要求的逐条裁定、复核对照与综合对比、《本次审核记录清单》、未检查项，以及最终**单文件 HTML 交付物**（AuditResult 单一事实源渲染）。

无专业技能可用时仍交付画像、逐标签 gap 与已执行公共能力结果，不以“无能力”空返。

## KB 兼容边界

按 `00-input-and-route-profile.md`，五轴 `scope_types[]/asset_types[]/business_types[]/methods[]/overlays[]` 是 router 的唯一画像契约，router 不得为兼容生成旧画像键。

装配清单由叶子声明、不经本仓装配器：命中轴标签后，下载清单 = 命中叶子 `references/01-kb-assembly.md` 的路径键（一级目录根或单文件路径）＋公共执行契约路径并集，由 `crwu-dws` 实时下载正文。叶子的一级目录根按 `request_kind=directory`、`recursive=true` 递归下载根内全部支持正文；细分对象与子业务在已下载目录包内二次选用，不各建技能。下载失败、空目录或不支持导出的节点记 capability gap，并继续执行不依赖该步骤的已加载能力。
