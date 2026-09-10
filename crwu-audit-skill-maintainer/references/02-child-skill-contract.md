# 资产与业务 Skill 合同

## 命名和粒度

- 资产：`crwu-audit-asset-<一级资产英文标识>`。
- 业务：`crwu-audit-biz-<一级业务英文标识>`。
- 一个 Skill 恰好对应一个知识库一级目录。
- 不创建细分对象 Skill、子业务 Skill 或 `资产 × 业务` 组合 Skill。

英文标识应沿用仓库已确认名称。没有既有名称时，方案中同时给出候选名和人工确认标记；不得使用不可追溯的自动音译直接落库。

## 最小目录

```text
crwu-audit-asset-<name>/
或 crwu-audit-biz-<name>/
├── SKILL.md
└── references/
    ├── 00-applicability.md
    ├── 01-kb-assembly.md
    └── 02-review-focus.md
```

`SKILL.md` 必须声明仅经 `crwu-audit` 编排，不查询报告记录、不替代其他轴、不读取上一轮知识正文。输入为冻结的一级 route profile、隔离后的源材料和本次 DWS manifest。

**共同约束只写一份**：轴边界、输入、一级根装配、二级选择返回、执行顺序（一级共用层→命中二级条目）、必检项/历史问题状态字段、来源优先级、证据出处与 capability gap，全部落在 `crwu-audit/references/12-leaf-common-contract.md`；每个叶子 `SKILL.md` 用相对路径 `../crwu-audit/references/12-leaf-common-contract.md` 引用它，只写本轴/本标签特有内容，不复制共同规则。新建叶子时先按 `crwu-audit-biz-asset-operation` 的四个文件作为版式基线。

## 00-applicability.md

资产文件维护：

- 一级 canonical label、结构化字段和同义信号；
- 纳入、排除、冲突和人工复核条件；
- 细分对象相对目录、识别证据和父级关系。

业务文件维护：

- 一级 canonical label 和业务边界；
- 子业务相对目录、评估目的识别证据、排除和冲突；
- 多子业务同时命中的处理；
- 一级业务目录 `共同审核点`（若存在）的适用范围：对该一级业务全部子业务生效，不属于任何单个子业务。

## 01-kb-assembly.md

只登记一个一级根，不列举根内文件：

| source_key | owner_axis | canonical_label | kb_root | request_kind | recursive | required |
| --- | --- | --- | --- | --- | --- | --- |
| `<稳定键>` | `asset` 或 `business` | `<一级标签>` | `<完整一级目录路径>/` | `directory` | `true` | `true` |

二级相对路径可作为 `expected_structure` 和选择索引，但不能替代一级根。全局契约、方法正文和监管正文由 router 的其他轴装配，不复制进资产或业务根映射。

业务轴的 `expected_structure` 额外断言一级根的直接文档 `共同审核点`（若库内存在）：该文档随一级根递归下载，因此不单独登记为清单条目；断言的作用是让下载结果与维护方案可核对。资产轴对应的一级共用层是 `01-共性参考/`；业务轴没有该子目录时，`共同审核点` 就是一级业务的共用层来源。

## 02-review-focus.md

维护从本次真实来源归纳出的：

- 共性检查结构（资产轴=`01-共性参考/`；业务轴=一级根 `共同审核点`，若库内存在）；
- 二级对象或子业务选择方式；
- 必检项和历史问题状态输出；
- 资产/业务与方法、监管、数据勾稽之间的接口；
- 每项对应的 source_key、相对路径及 RULE/CHK。

执行顺序按「一级共用层 → 命中的二级条目」：业务轴先执行 `共同审核点`，再叠加命中子业务的 `01-业务通用审核要点`。共用层的关注点写在 `02-review-focus.md` 的共用段并回指其库内层级路径，不逐字复制正文。

不复制知识库正文，不把历史案例改写为无来源的强制规则。

## 二级选择返回

父 Skill 对每个命中的二级项返回：

```json
{
  "parent_label": "房地产",
  "label": "土地使用权",
  "evidence": [{"source": "评估对象原文", "location": "报告:页码或章节"}],
  "confidence": "high",
  "review_required": false,
  "selected_relative_paths": ["02-细分对象/01-土地使用权/评估审核条目"]
}
```

业务轴使用同一结构，数组名为 `business_subroutes[]`；资产轴数组名为 `asset_subobjects[]`。二级选择只记录本次执行，不回写或修改 router 已冻结的一级 route profile。
