---
name: crwu-audit-biz-financing-debt
description: Use when crwu-audit has selected the canonical 融资与债务 business label for scenario-specific review.
---

# 融资与债务业务专业审核

## 调用边界

仅经 `crwu-audit` router 编排调用，禁止单独调用。本技能只审一级业务 `融资与债务` 的场景规则（评估目的、经济行为、场景对口径/材料/判断的影响），不查询报告记录、不重新获取材料、不重新下载规则正文。

共同约束见 [共同约束](../crwu-audit/references/12-leaf-common-contract.md)：轴边界、输入、一级根装配、二级选择、执行顺序、条目状态、来源优先级、证据出处与 capability gap 均按该文件执行，本文件只写本业务特有内容。

不决定对象专业事项（房地产权属、实物与经济特征、对象特有方法前提等由资产轴 Skill 处理），不替代 method/overlay/public 轴，不创建资产×业务组合 Skill。

## 输入

- 同一份 `route_profile`，且 `business_types[]` 已命中 canonical `融资与债务`；
- router 已准备并隔离的报告、评估说明、测算明细表等材料路径；
- router 已验证的本次 DWS manifest、规则快照及其文件路径。

缺少上述输入时记录 capability gap，不自行补取、猜测或沿用上一轮材料。

## 必读 references

执行前依次读取：

1. [00-applicability.md](references/00-applicability.md)：确认本业务边界、子业务识别与相邻业务消歧；
2. [01-kb-assembly.md](references/01-kb-assembly.md)：核对一级根与本次规则快照覆盖的库内层级路径；
3. [02-review-focus.md](references/02-review-focus.md)：按子业务执行必检项与历史高频复核问题。

## 执行与输出

1. 用 `00-applicability.md` 核对画像证据，识别全部 `business_subroutes[]`（含证据、`confidence`、`review_required`），不改变 router 已确定的资产标签。
2. 用本次 DWS manifest 验证 `01-kb-assembly.md` 的一级根已递归下载；缺失项按库内层级路径和原因记 gap，对应检查不引用、不编造。
3. **先执行一级共用层**（`共同审核点`，若存在且非占位），再按 `02-review-focus.md` 叠加每个命中子业务的 `01-业务通用审核要点`。
4. 必检项逐项输出 `符合/不符合/不适用/无法核验`；历史高频复核问题逐项输出 `涉及/未涉及/无法核验`；字段要求见共同约束 §7。
5. 输出业务专业 findings；每条带 `source_skills[]`（至少含 `crwu-audit-biz-financing-debt`）与本次下载证据（文件、行号、库内路径、运行时 `nodeId`、`exportedAt`）。
