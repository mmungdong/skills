# 多轴并集分发规则

| 版本 | v1.0 | 状态 | 2026-09-09 定稿 | 维护 | 多轴候选合并、去重和执行边界唯一事实源 |
| --- | --- | --- | --- | --- | --- |

## 分发算法

先按 02–06 得到各轴全部标签，再逐项查询 07。`available` 技能加入该轴候选列表；`pending` 或未注册标签按 10 逐标签写 gap；`profile-only` 只保留画像。公共能力独立判定，且每个公共能力有各自的触发条件：**通用准则类与报告形态、对象、业务、方法、监管均无关，恒装配**；表格勾稽类按材料是否含表格触发。

```text
scope_skills   = available_skills(scope_types[])
asset_skills   = available_skills(asset_types[])
business_skills = available_skills(business_types[])
method_skills  = available_skills(methods[])
overlay_skills = available_skills(overlays[])
public_skills  = [crwu-audit-public-general-standards]        # 恒装配：报告披露 + 程序质控
               + [crwu-audit-datacheck] when tabular materials exist

skills_to_load = stable_unique(
  scope_skills +
  asset_skills +
  business_skills +
  method_skills +
  overlay_skills +
  public_skills
)
```

`stable_unique` 按上述轴顺序和每个分类表中的标签顺序保留第一次出现，后续同名技能只去重，不改变先后。所有轴都必须求值后才能形成 `skills_to_load`：禁止“首个命中即停止”、排他 `else-if`、用一个轴覆盖另一个轴，或因某个 pending/失败技能短路其他 available 技能。

## pending、冲突与结果归并

- 每个 pending 或未注册的 `axis+label` 单独产生一个 `material_gaps[]` 项；不得把多个缺失标签压成组合 gap。
- pending 不进入实际执行列表，但不得删除对应 route profile 标签；其他 available 技能照常加载并产出结果。
- ROUTE001 只挂起冲突涉及的业务标签及候选；ROUTE002 只挂起冲突涉及的范围/资产标签及候选。不受影响的候选继续参与稳定并集。
- ROUTE003 挂起 `record_context.base_date` 及依赖基准日的规则/结论，ROUTE004 挂起 `record_context.value_type` 及依赖价值类型的规则/结论；未确认字段不得作为事实继续使用。这两类冲突不按技能身份无差别停载，技能中不依赖冲突字段的规则仍可执行。
- 人工确认后只重算相应字段及受影响的标签候选或规则，再用所有未挂起候选形成完整 `skills_to_load` 稳定并集。
- 每条 finding 必须带 `source_skills[]`，列出实际产生或共同支持该 finding 的技能。跨技能同一事实可以合并，但合并后保留所有来源技能；不能只留最后写入者。
- 意见按报告、评估说明、测算明细表分区归并。证据相同且结论相同的 finding 去重；结论冲突时不覆盖，保留双方 `source_skills[]`、证据和冲突说明，交人工复核。

```jsonc
{
  "finding_id": "F-001",
  "section": "测算明细表",
  "finding": "租金案例调整依据不足",
  "source_skills": [
    "crwu-audit-asset-realestate",
    "crwu-audit-biz-asset-operation"
  ]
}
```

## 示例

### 房地产租赁

画像命中 `asset=房地产`、`business=资产经营`（目的原文为出租/租金，子业务为 `租赁与租金评估`）。注册表解析为 `crwu-audit-asset-realestate (available)` 与 `crwu-audit-biz-asset-operation (available)`，两者均进入 `skills_to_load`；若材料含明细表，再追加 `crwu-audit-datacheck`。不得用业务技能替代房地产对象技能，也不得为子业务另建 Skill。

### 房地产清算后拍卖处置

画像命中 `asset=房地产` 以及 `business=司法清算与补偿 + 交易与处置`（旧行为词 清算→前者，资产处置/拍卖→后者）。逐标签解析得到：

- `crwu-audit-asset-realestate`：available，继续加载；
- `crwu-audit-biz-judicial-liquidation-compensation`：available，加载，叶子内选用子业务 `破产清算与解散`；
- `crwu-audit-biz-transaction-disposal`：available，加载，叶子内选用子业务 `拍卖与处置`。

两个业务一级标签分别保留各自的 `source_skills[]`，不得因为都命中而合并成一个组合技能；子业务只在各自叶子内选用，不进入 `skills_to_load`。

### 机器设备抵押

画像命中 `asset=机器设备`、`business=融资与债务`（旧行为词 抵押质押，子业务 `抵押与担保`）。解析为 `crwu-audit-asset-equipment (available)` 与 `crwu-audit-biz-financing-debt (available)`，两者均加载。如果材料含表格，available 的 `crwu-audit-datacheck` 仍必须加载。

### 设备类报废物资残余价值评估（国资）

画像命中 `asset=废旧物资`、`business=交易与处置`、`overlay=国资`，材料含测算表。逐标签解析得到：

- `crwu-audit-asset-scrap-materials`：available，加载；
- `crwu-audit-biz-transaction-disposal`：available，加载；
- `crwu-audit-overlay-state-owned`：pending，记独立 gap；
- `public_skills`：`crwu-audit-public-general-standards` **恒加入**（报告披露层与程序质控层对任何对象均适用），材料含表格再追加 `crwu-audit-datacheck`。

即监管层专业能力缺失时，通用准则层与表格勾稽仍必须加载并产出结果；不得因为 `overlay` 标签 `pending` 而让 `public_skills` 空返。

### 企业价值多资产清算

画像命中 `scope=企业价值`、`asset=企业价值 + 房地产 + 机器设备 + 无形资产`、`business=司法清算与补偿`。scope 轴 `企业价值` 为 profile-only（审核内容由 asset 轴承接）；`crwu-audit-asset-enterprise-value`、`crwu-audit-asset-realestate`、`crwu-audit-asset-equipment`、`crwu-audit-asset-intangible` 与 `crwu-audit-biz-judicial-liquidation-compensation` 均 available，加载。资产标签各自保留 `materiality=key|non-key|unknown`：available 且 `key` 的技能必须加载，`unknown` 保留并人工复核，`non-key` 不得删除标签但不让其主导输出。材料含表格时再并入 `crwu-audit-datacheck`。
