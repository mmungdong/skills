---
name: crwu-audit-public-general-standards
description: Use when crwu-audit has selected the public 通用准则 capability for report-disclosure and procedure/quality-control review.
---

# 通用准则公共审核（报告披露 · 程序与质控）

## 调用边界

仅经 `crwu-audit` router 编排调用，禁止单独调用。本技能是 `public` 轴叶子，只审核**报告形态无关的通用准则层**：报告与披露要求、评估程序执行要求、机构质量控制要求。不查询报告记录、不准备材料、不重新下载规则，也不替代任何专业轴技能。

共同约束见 [共同约束](../crwu-audit/references/12-leaf-common-contract.md)：输入、执行顺序、条目状态、来源优先级、证据出处与 capability gap 均按该文件执行（按与本技能不冲突的部分参照适用）；本文件只写本能力特有内容。

- 对象专业事项（权属、实物与经济特征、对象特有方法前提）由 `crwu-audit-asset-*` 处理；
- 评估目的与经济行为对口径、材料、判断的影响由 `crwu-audit-biz-*` 处理；
- 方法与监管正文由 method / overlay 轴处理；表格勾稽由 `crwu-audit-datacheck` 处理；
- 本技能**不替代**上述任何一轴，也不因某专业轴 `pending` 而停止执行。对象、业务、方法、监管全部缺失时，本技能仍须独立产出通用准则层的检查结果。

本技能对**任何报告形态恒适用**，因此由 router 在公共能力求值阶段无条件并入 `public_skills[]`，不依赖材料类型条件。

## 输入

- 同一份 `route_profile`（五轴标签与证据；本技能不消费具体专业标签，只用 `report_form`、`record_context` 与材料分区）；
- router 已准备并隔离的报告、评估说明、测算明细表等材料路径；
- router 已验证的本次 DWS manifest、规则快照及其文件路径。

缺少上述输入时记录 capability gap，不自行补取、猜测或沿用上一轮材料。

## 必读 references

执行前依次读取：

1. [00-applicability.md](references/00-applicability.md)：确认本公共能力的适用、排除与边界；
2. [01-kb-assembly.md](references/01-kb-assembly.md)：核对本次规则快照覆盖的 RULE 与库内层级路径；
3. [02-review-focus.md](references/02-review-focus.md)：按报告披露层与程序质控层的关注点实施检查。

## 执行与输出

1. 用 `00-applicability.md` 界定本次适用范围；不改变 router 已确定的任何轴标签。
2. **先判规则版本**：程序准则与质控指南存在新旧两版且施行日期不同，按报告基准日／报告日所属期间选定整段引用版本，禁止新旧条款混引（判定规则见 `02-review-focus.md` §1）。版本无法确定时记录冲突并转人工判断，不任选一版。
3. 用本次 DWS manifest 验证 `01-kb-assembly.md` 所需文件；缺失项按路径和原因记录 gap，对应检查不引用、不编造。
4. 按 `02-review-focus.md` 分别审核报告、评估说明、测算明细表；报告披露层与程序质控层各自独立出条目状态，不以"未发现问题"笼统概括。
5. 索引卡类文件**不构成规则条目**，不得作为引用依据；模板参考类文件只做格式基线对照，判定以准则正文条款为准。
6. 输出通用准则层 findings；每条均带 `source_skills[]`，其中至少包含 `crwu-audit-public-general-standards`。相同事实由其他技能共同支持时保留全部来源，冲突时并列交人工复核。
7. 按本次 DWS 执行契约输出证据与修改建议；出处包含本次下载文件、实际行号、库内路径、本次运行返回的 `nodeId` 和 `exportedAt`（运行时值不写回本技能）。
