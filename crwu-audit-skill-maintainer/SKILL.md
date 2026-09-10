---
name: crwu-audit-skill-maintainer
description: Use when auditing/inventorying, creating, repairing, or remapping crwu-audit asset and biz skills after a DingTalk wiki directory changes or capability gaps are reported.
---

# crwu-audit Skill 维护器

## 职责

维护 `crwu-audit` 的一级资产 Skill、一级业务 Skill、分类、registry，以及一份**知识库 ↔ Skill 映射校准表**。它不执行评估报告审核、不修改钉钉知识库、不替代 `crwu-dws`，也不创建资产与业务组合 Skill。

资产 Skill 使用 `crwu-audit-asset-*`，业务 Skill 使用 `crwu-audit-biz-*`（`crwu-audit-business-*` 为待迁移遗留前缀）。Skill 只对应一级目录；细分对象和子业务由父 Skill 在目录包内选择，**不各建 Skill、不占 registry 行**。

**词表口径**：`business_types[]` 只取 `01-业务路线/` 下的一级业务标签；历史行为词（租赁、清算、破产、拍卖、抵押质押、减值测试、计税、追溯评估、复核…）降级为**命中信号**，不是标签、不占 registry 行。新增一级能力时同步 `04-business-classification.md`／`03-asset-classification.md` 与 `07-skill-registry.md` 两处。

一级业务目录下若存在 `共同审核点` 文档，必须与一级根一并拉取、并作为该业务 Skill 的共用审核层参考：它在目录包内先于子业务条目执行，适用于该一级业务的全部子业务，不因命中哪几个子业务而改变。文档不存在时不视为缺口，也不得凭经验或旧摘录补造其内容。

**叶子共同约束**：公共规则只写一份 —— `crwu-audit/references/12-leaf-common-contract.md`（轴边界、输入、一级根装配、二级选择返回、执行顺序、条目状态字段、来源优先级、证据出处、capability gap）。新建或修复叶子按它执行，叶子只写本轴/本标签特有内容并引用它，**不得复述共同规则**；版式基线取任一 `crwu-audit-biz-*` 的四件套（`SKILL.md` + `00-applicability.md` + `01-kb-assembly.md` + `02-review-focus.md`）。

## 模式

| 用户意图 | 模式 | 是否修改 source |
| --- | --- | --- |
| 检查当前 skill 体系与最新知识库是否一致（路由、注册、是否存在、是否需创建） | `audit` | 否（只同步校准表） |
| 新增一级资产或一级业务能力 | `create` | 确认后 |
| 修正名称、结构、边界或登记 | `repair` | 确认后 |
| 知识库路径调整后重建映射 | `remap` | 确认后 |

`audit` 是只读模式的规范名（设计 §7.4）；早期草稿曾用 `inventory`，仅作同义旧称，不得再用作新入口。

先读 [00-responsibility-and-modes.md](references/00-responsibility-and-modes.md)。随后按任务读取：

- 目录发现或目录树盘点：[01-kb-source-discovery.md](references/01-kb-source-discovery.md)
- 拉最新目录并与 router/registry/真实 Skill 对比：[06-live-routing-reconciliation.md](references/06-live-routing-reconciliation.md)
- 创建或修正子 Skill：[02-child-skill-contract.md](references/02-child-skill-contract.md)
- 处理准则、必检项和历史问题：[03-review-item-execution-contract.md](references/03-review-item-execution-contract.md)
- 修改分类、registry 或映射：[04-registry-and-mapping-update.md](references/04-registry-and-mapping-update.md)
- 校验与交付：[05-validation-and-delivery.md](references/05-validation-and-delivery.md)
- **映射校准表（每次校准后重写，含人工备注与历史）**：[07-kb-skill-map.md](references/07-kb-skill-map.md)

## 执行

1. 确认 source repo、模式、目标范围和本次知识库身份。
2. **先经 `crwu-dws` 拉最新知识库目录**（只读），记录 `fetchedAt`/`complete`/`failures`；缓存只用于定位，不得当成最新。离线或刷新失败时只能用旧快照输出候选，并显式标注"非本次在线结果"。
3. `audit` 用最新目录运行只读检查器，按 [06-live-routing-reconciliation.md](references/06-live-routing-reconciliation.md) 逐项对比四层：路由机制、路由参考是否注册、Skill 是否存在、是否需要创建。
4. `create`、`repair`、`remap` 在同一份最新目录基础上，递归下载目标一级目录内全部可读正文到本次临时区；业务轴额外确认 `共同审核点` 是否随根下载到位。下载正文后核对**内容级状态**：必检项是否「待补」、文档是否为空、是否 `TODO` 占位、结构是否与 `expected_structure` 断言一致。
5. 形成逐文件《Skill 维护方案》；列出新增、修改、移动、删除、映射变化、依据和验证命令。
6. 用户未确认时停止在方案阶段。确认后重新核对 git 基线与目标文件 hash，只修改已批准的 source 文件。
7. 执行验证并报告真实结果；失败项保持 pending 或 capability gap。
8. **同步校准表（每个模式收尾必做，`audit` 也做）**：带 `--emit-map` 运行检查器刷新 [07-kb-skill-map.md](references/07-kb-skill-map.md)，并在其「内容级校准备注」区补写本次正文核对结论与缺口清单。

## 硬门禁

- 不把知识库名称、个人绝对路径、nodeId 常量、下载正文或凭据写入 Skill source。
- **一级根逐字使用知识库中的精确路径**（含 `01-` 等数字排序前缀）：带前缀与省略前缀是两条不同路径（例：`02-资产类型/01-房地产/` ← 库内真名）；不得按显示名简写，也不得按另一个库的目录名推断。反例见下条。
- 不用目录名相似度确认映射；路径来自最新完整目录，内容关系来自本次下载正文。
- 不用缓存命中、历史摘录或他人粘贴的目录冒充"已核实最新"；`audit` 结论必须能追溯到本次 `crwu-dws` 抓取时间。
- 不把细分对象、子业务或知识库结构缺口列进"需创建 Skill"；它们只进父级二级索引或 gap。
- 不为土地使用权等细分对象或租赁与租金评估等子业务另建 Skill。
- 不把一级业务目录的 `共同审核点` 当成某个子业务的专属条目；它是该一级业务的共用层，命中任一子业务都执行。
- **必检项为「待补」、文档为空或为 `TODO` 占位时，登记知识库内容缺口并声明覆盖不完整，绝不据标题、经验或历史问题补造要求。**
- 新建或修复叶子不得复述 `12-leaf-common-contract.md` 的共同规则，只引用它。
- 校准表只由检查器 `--emit-map` 生成；与实际不一致时重新校准，不手改状态列。
- **本文档里的路径只写库内真名**；需要举反例时不要写成反引号寻址键（检查器会把反引号内容当寻址键校验）。
- 不直接写、复制、链接或删除任何运行时 Skill 目录。
- 不覆盖工作区无关改动；目标文件在确认后变化时重新分析。
