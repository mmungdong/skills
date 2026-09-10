# 知识库来源发现

## 两层事实

- 目录事实：**本次**经 `crwu-dws` 拉取的最新完整目录（`目录快照.json` / `node-index.json` / `目录树.md` 任一形态）。目录缓存只用于定位加速；用户粘贴的目录树可以用于初盘，但不证明是最新，也不证明正文内容。
- 正文事实：本次通过 `crwu-dws` 实时导出的文档。旧缓存、历史摘录和文件名不能替代正文。

`audit`、`create`、`repair`、`remap` 一律先在 `crwu-dws` 侧刷新目录再下结论（详见 [06-live-routing-reconciliation.md](06-live-routing-reconciliation.md)）。离线或刷新失败时只能用旧快照输出候选，并显式标注"目录非本次在线结果"。

目录快照不完整、存在 failures 或无法确认抓取时间时，允许输出候选，但不能据此确认删除、改名或 available 状态。

## audit 执行

将目录树或 JSON 快照保存到本次临时文件，运行：

```bash
python3 skills/crwu-audit-skill-maintainer/scripts/check_audit_skill_mappings.py \
  --repo-root <source-repo> \
  --catalog <目录树或快照文件> \
  --format json
```

需要把错误发现作为 CI 失败时追加 `--strict`；需要强制"目录必须是本次刷新"时追加 `--max-age-hours <H>`（无抓取时间 → `CATALOG_NOT_LIVE`，超期 → `CATALOG_STALE`）。检查器只读，不自动修改 source。

支持的输入口径（`--catalog` 自动识别，无需指定类型）：

| 输入 | schema | 路径来源 | 完整性 |
| --- | --- | --- | --- |
| DWS 目录快照（`目录快照.json`） | `crwu.kb-dir-snapshot.v1` | 扁平 `nodes[]`，按 `parentId` 逐级上溯重建路径 | `failures` 非空，或任一 `evidence[].hasMore=true`／`autoPageComplete=false` 即判为不完整 |
| DWS 目录索引（`node-index.json`） | `crwu.kb-node-index.v1` | `nodes{}` 字典，节点自带 `path` | 本文件无处判定，报告 `complete=null` |
| 粘贴目录树 | Markdown | `- 📁 名称/` 与 `- 📄 名称`，缩进即层级 | 无处判定 |
| 旧式快照／索引 | `crwu.kb-catalog.snapshot.v1`、`crwu.kb-dir-cache.nodeindex.v1` | 嵌套 `children`／`by_path` | 兼容保留 |

同一目录树的三种真实输入必须得到完全相同的 `catalog.paths` 与 finding 集合；出现分歧说明解析有缺陷，而不是知识库有差异。

## 一级目录识别

| 轴 | 一级根 | 新 Skill 判定 |
| --- | --- | --- |
| asset | `02-资产类型/<一级资产>/` | 一级资产未被 registry 和真实父 Skill 覆盖 |
| business | `01-业务路线/<一级业务>/` | 一级业务未被 registry 和真实父 Skill 覆盖 |

忽略 `TODO` 顶层目录。数字排序前缀只用于目录展示；比较 canonical label 时去除前缀，写映射时保留知识库中的精确路径。

## 全量下载规则

`create`、`repair` 和 `remap` 对目标一级根执行 DWS M2 目录请求：路径以 `/` 结尾，递归下载根内全部支持的正文。下载清单只包含已确认的一级根及 router 自有公共契约；不得越过根目录扩展到其他一级资产或业务。

完整下载应满足：

- 原始目录请求有成功展开记录；
- 每个支持的正文节点都有 entry，非支持类型有 skipped，失败节点有 failure；
- manifest 中 requestKind 为 `directory`；
- 导出回执含本次 localPath、sizeBytes 和 exportedAt；
- 没有清单根之外的正文 entry。

任一失败都要进入来源清单和 capability gap，不用旧正文补齐。

## 资产目录解释

一级资产 Skill 总是装配完整一级根。正式审核时：

1. 读取 `01-共性参考/` 下全部文档；对象准则、定义分类、共性审核条目和相关复核条目均进入约束或检查集合。
2. 根据评估对象、范围、资产明细和权属材料识别全部 `asset_subobjects[]`。
3. 对命中的 `02-细分对象/<对象>/` 执行其 `评估审核条目`。
4. 已下载但未命中的对象资料登记“未选用及原因”，不得强行套用。

细分对象缺少审核条目是内容缺口，不是新增 Skill 的理由。

## 业务目录解释

一级业务 Skill 总是装配完整一级根。正式审核时：

1. 识别全部 `business_subroutes[]`：以报告评估目的原文、经济行为文件、委托合同和审批材料为准。
2. 文件名和标题只能提示，不能独立确认子业务。
3. **先执行一级业务目录的共用层**：若 `01-业务路线/<一级业务>/` 下存在 `共同审核点` 文档，它与一级根一并下载，并对该一级业务的**全部**子业务生效；命中任一子业务都执行，不因命中集合变化而跳过。
4. 对每个命中子业务执行其 `01-业务通用审核要点`，并读取同目录的资产专项、方法适用索引、监管适用索引和其他关联文件。
5. 多业务全部保留；证据不足时保留合理候选并标记人工复核。

`共同审核点` 的识别与处置：

- 位置：一级业务根目录的**直接**子文档（不在某个子业务目录内）；数字排序前缀和 `.md` 后缀不影响识别，如 `01-共同审核点.md` 等价于 `共同审核点`。
- 归属：它是该一级业务的共用层，不并入任何单个子业务；不得因某次只命中一个子业务就把它记成该子业务的专属条目。
- 缺失：目录下没有该文档时**不记为缺口、不报错**——它是条件性约定，不是必备结构。
- 名称近似但不同（如 `共同审核要点`、`共性审核点`）：不得自动等同，按候选报出交人工确认；不得凭名称猜测内容归属。
- 内容无法导出、被跳过或递归下载失败：按 capability gap 记录，不静默忽略、不用旧摘录补齐。
- 内容本身不得复制进 Skill source，只在 `01-kb-assembly.md` 的 `expected_structure` 断言与 `02-review-focus.md` 的共用层关注点中回指其库内层级路径。

子业务缺少审核要点是内容缺口，不是新增 Skill 的理由。
