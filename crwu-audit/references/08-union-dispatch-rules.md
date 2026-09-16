# 多轴并集分发规则

| 版本 | v1.0 | 状态 | 2026-09-09 定稿 | 维护 | 多轴候选合并、去重和执行边界唯一事实源 |
| --- | --- | --- | --- | --- | --- |

## 分发算法

先按 02–06 得到各轴全部标签，再逐项查询 07。`available` 技能加入该轴候选列表；`pending` 或未注册标签按 10 逐标签写 gap；`profile-only` 只保留画像。公共能力独立判定，且每个公共能力有各自的触发条件：**通用准则类与报告形态、对象、业务、方法、监管均无关，恒装配**；表格勾稽类按材料是否含表格触发；外部数据核验类按 `methods[]` 是否命中 `收益法`/`市场法` 触发（是否真正取数再由该能力按知识库 `M-外部数据核验` 表 A 三条自行判定）。

```text
scope_skills   = available_skills(scope_types[])
asset_skills   = available_skills(asset_types[])
business_skills = available_skills(business_types[])
method_skills  = available_skills(methods[])
overlay_skills = available_skills(overlays[])
public_skills  = [crwu-dev-audit-public-general-standards]        # 恒装配：报告披露 + 程序质控
               + [crwu-audit-datacheck] when tabular materials exist
               + [crwu-audit-external-data] when methods include 收益法 or 市场法

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

## 方法层与覆盖层的库内装配映射（2026-09-16 立规）

**背景**：方法轴技能（`crwu-audit-method-*`，7 个）与覆盖层技能（`crwu-audit-overlay-*`，4 个）在 `07-skill-registry.md` 中均为 `pending`，
不进入 `skills_to_load`。但知识库里的方法层与覆盖层**正文与清单已经存在**——
`pending` 表示**能力未落地，不表示内容可以不装**。此前这些内容既无叶子装配键、又因技能 pending 而不被装载，
导致「库里有、审核读不到」（实测：`04-监管覆盖/` 5 份规则覆盖 80.7% 的项目；`03-评估方法/` 下的收益法、资产基础法、
方法选择三个子目录，以及 `06-规则库/清单-M-收益法/`、`06-规则库/清单-M-资产基础法/` 无人装配）。

**规则**：本次 DWS 下载清单在「命中叶子装配表 ∪ 公共执行契约」之外，**再按本次 `methods[]` / `overlays[]` 的命中项追加下表目录**。
**只装命中项，不装全集**——未命中方法的层不得下载，避免把不适用规则装进本次审核。

| 轴 | canonical 标签（命中即追加） | 库内层级路径（目录项以 `/` 结尾、递归下载） |
| --- | --- | --- |
| method | `收益法` | `03-评估方法/02-收益法/`、`06-规则库/清单-M-收益法/` |
| method | `资产基础法`、`成本法` | `03-评估方法/03-资产基础法/`、`06-规则库/清单-M-资产基础法/` |
| method | 任一方法命中（选择与差异处理为跨方法事项） | `03-评估方法/04-方法选择/` |
| method | `市场法` | `06-规则库/清单-M-市场法/` |
| overlay | `国资` | `04-监管覆盖/国资/` |
| overlay | `证券` | `04-监管覆盖/证券/` |
| overlay | `司法` | `04-监管覆盖/司法/` |
| overlay | `金融/银行` | `04-监管覆盖/金融国资/` |
| overlay | `财务报告` | `04-监管覆盖/财务报告/` |

纪律：

1. **映射唯一事实源在本节**；叶子与 `SKILL.md` 只引用本节，不各自复述映射表。
2. 追加的是**知识库目录**，不是技能：不因此把 method/overlay 的 registry 状态改为 `available`，也不创建空的 pending 技能目录；
   每个 pending 标签仍按 §「pending、冲突与结果归并」逐标签写独立 `material_gaps[]`。
3. **清单外零下载**不变：映射只按 `methods[]`/`overlays[]` 的实际命中项追加，不做模糊扩展、不按对象或业务推断。
4. `03-评估方法/00-评估方法准则2019-精编/评估方法准则2019-精编条目/`、`03-评估方法/01-市场法/`、`03-评估方法/05-审核要点/`
   与 `06-规则库/清单-M-市场法/`、`清单-M-成本法/` 已由叶子装配键覆盖，本节不重复登记（去重由 `stable_unique` 与清单并集完成）。
5. 目录内含原生（非 `adoc`）节点时，取数通道由 `crwu-dws` 按 `extension` 分流（`adoc`→`doc +export`；`md`/`txt`→`drive +download`），
   本节不重复声明通道。

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
- `public_skills`：`crwu-dev-audit-public-general-standards` **恒加入**（报告披露层与程序质控层对任何对象均适用），材料含表格再追加 `crwu-audit-datacheck`。

即监管层专业能力缺失时，通用准则层与表格勾稽仍必须加载并产出结果；不得因为 `overlay` 标签 `pending` 而让 `public_skills` 空返。

### 企业价值多资产清算

画像命中 `scope=企业价值`、`asset=企业价值 + 房地产 + 机器设备 + 无形资产`、`business=司法清算与补偿`。scope 轴 `企业价值` 为 profile-only（审核内容由 asset 轴承接）；`crwu-audit-asset-enterprise-value`、`crwu-audit-asset-realestate`、`crwu-audit-asset-equipment`、`crwu-audit-asset-intangible` 与 `crwu-audit-biz-judicial-liquidation-compensation` 均 available，加载。资产标签各自保留 `materiality=key|non-key|unknown`：available 且 `key` 的技能必须加载，`unknown` 保留并人工复核，`non-key` 不得删除标签但不让其主导输出。材料含表格时再并入 `crwu-audit-datacheck`。

### 收益法 / 市场法项目的外部数据核验

画像命中 `methods=[收益法]`（或含 `市场法`）时，`public_skills` 在恒装配的 `crwu-dev-audit-public-general-standards` 之外再并入 `crwu-audit-external-data`；是否真正取数由该能力按知识库 `M-外部数据核验` 表 A 三条（业务线 × 资产线 × 方法线）自行判定，缺一即记"不在本模块范围"，不作为未检查项。该能力的唯一数据源是**同花顺 iFinD**，取数路径随宿主而异（WorkBuddy 宿主连接器 / DeepSeek Harness 的 `ifind-finance-data` 技能），**不启用万得**；两条取数路径都不可用时按库内降级口径降级，并**必须在交付 HTML《外部数据核验》区显式声明**"未配置/未认证 同花顺 iFinD，相关条目未经外部数据核验"。所有取数以 `record_context.base_date` 为锚，禁止取数时点的滚动窗口。该能力只出外部数据核验意见，不下方法适用性与参数合理性判断。
