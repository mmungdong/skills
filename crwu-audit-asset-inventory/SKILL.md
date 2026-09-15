---
name: crwu-audit-asset-inventory
description: Use when crwu-audit has selected the canonical 存货 asset label for professional asset-object review.
---

# 存货资产专业审核

## 调用边界

仅经 `crwu-audit` router 编排调用，禁止单独调用。本技能只审核 canonical `存货` 对象的资产专业事项，不查询报告记录、不准备材料、不重新下载规则，也不替代其他轴技能。

共同约束见 [共同约束](../crwu-audit/references/12-leaf-common-contract.md)：轴边界、输入、一级根装配、二级选择、执行顺序、条目状态、来源优先级、证据出处与 capability gap 均按该文件执行，本文件只写本对象特有内容。

不得决定租赁、清算、资产处置、拍卖、抵押质押、财务报告等业务标签或业务判断；这些事项由 router 同时加载的 business skills 处理。材料含测算、明细或汇总表时，表格勾稽由 router 并入 public skill 执行，本技能只提供本对象侧的界面与一致性检查。

## 输入

- 同一份 `route_profile`，且 `asset_types[]` 已命中 canonical `存货`；
- router 已准备并隔离的报告、评估说明、测算明细表等材料路径；
- router 已验证的本次 DWS manifest、规则快照及其文件路径。

缺少上述输入时记录 capability gap，不自行补取、猜测或沿用上一轮材料。

## 必读 references

执行前依次读取：

1. [00-applicability.md](references/00-applicability.md)：确认对象适用、排除和多资产边界；
2. [01-kb-assembly.md](references/01-kb-assembly.md)：核对本次规则快照覆盖的库内层级路径；
3. [02-review-focus.md](references/02-review-focus.md)：按本对象专业关注点实施检查。

## 执行与输出

1. 用 `00-applicability.md` 核对画像证据，不改变 router 已确定的业务标签。
2. 用本次 DWS manifest 验证 `01-kb-assembly.md` 所需文件；缺失项按路径和原因记录 gap，对应检查不引用、不编造。
3. 按 `02-review-focus.md` 分别审核报告、评估说明、测算明细表，只使用本次规则快照与已准备材料。
4. 输出对象专业 findings；每条均带 `source_skills[]`，其中至少包含 `crwu-audit-asset-inventory`。相同事实由其他技能共同支持时保留全部来源，冲突时并列交人工复核。
5. 按本次 DWS 执行契约输出证据与修改建议；出处满足 R6，包含本次下载文件、实际行号、库内路径、运行时 `nodeId` 和 `exportedAt`。
