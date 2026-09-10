# 验证与交付

## 检查器

```bash
python3 skills/crwu-audit-skill-maintainer/scripts/check_audit_skill_mappings.py \
  --repo-root <source-repo> \
  --catalog <目录树、snapshot 或 node-index> \
  --format text
```

输出 schema 为 `crwu.audit-skill-maintainer.report.v1`。主要 finding：

| 类型 | 级别 | 处理 |
| --- | --- | --- |
| `ROUTER_FILE_MISSING` | error | 总路由 `crwu-audit/SKILL.md` 不存在 |
| `ROUTER_REFERENCE_MISSING` | error | router 依赖的路由 reference 缺失（00/02–08/10/99） |
| `ROUTER_REFERENCE_UNRESOLVED` | error | router 命名的 `NN-*.md` 在 `crwu-audit/references/` 下不存在 |
| `ROUTER_AXIS_UNDISPATCHED` | error | 知识库有该轴一级目录，但并集规则从不加载对应输入（`asset_skills`/`business_skills`） |
| `ROUTER_SKILL_REFERENCE_UNRESOLVED` | error | router 或并集规则命名的具体技能既非真实目录、也非 registry 行 |
| `REGISTRY_FILE_MISSING` | error | registry 缺失；先恢复 registry 再做其他判断 |
| `FIRST_LEVEL_SKILL_MISSING` | error | 建议创建或登记父级 Skill |
| `FIRST_LEVEL_SKILL_PENDING` | warning | 一级能力已登记但未落地；只登记 gap，不建空目录 |
| `LEGACY_BUSINESS_PREFIX` | error | 制定 `crwu-audit-biz-*` 迁移方案 |
| `AXIS_PREFIX_MISMATCH` | error | 轴与 Skill 前缀不符；改名或改登记，不得两者都留 |
| `AVAILABLE_SKILL_DIRECTORY_MISSING` | error | `available` 声明的真实目录不存在；修复或降级状态（含 public 轴行） |
| `SKILL_NAME_MISMATCH` | error | 目录名、frontmatter 与 registry 名称不一致（含 public 轴行） |
| `SKILL_REFERENCE_MISSING` | error | available Skill 缺少规定 reference；**public 轴**只要求声明一份 KB 装配表（`01-kb-assembly.md` 或横切能力沿用的 `00-KB装配表.md`），不套用资产/业务叶子的三件套命名 |
| `REGISTRY_LABEL_DUPLICATE` | error | 一级标签登记多行；合并为恰好一行 |
| `REGISTRY_LABEL_NOT_IN_CATALOG` | warning | `available` 标签在最新目录中无对应一级目录（改名或失效） |
| `CLASSIFICATION_LABEL_MISSING` | warning | 一级标签未写入对应 classification |
| `ORPHAN_SKILL` | warning | source 中存在未登记资产/业务 Skill |
| `LEGACY_COMBINED_SKILL` | error | 既非已登记轴 Skill、也非 router/维护/横切能力的遗留组合 Skill（如 `crwu-audit-realestate-rent`）；登记或迁移到 `crwu-audit-asset-*`／`crwu-audit-biz-*` |
| `ASSEMBLY_FILE_MAPPING` | error | 仍逐文件登记；改为一句话递归一级根 |
| `ASSEMBLY_FIRST_LEVEL_ROOT_MISSING` | error | available Skill 缺少精确一级根或 `directory`/`recursive` 契约 |
| `MAPPING_ROOT_NOT_IN_CATALOG` | error | 声明的一级根在最新目录中已不存在 |
| `AXIS_ROOT_MISMATCH` | error | 资产 Skill 登记业务根（或反向），跨轴越界 |
| `ASSET_COMMON_REFERENCE_MISSING` | error | 知识库内容缺口，不创建子 Skill |
| `ASSET_SUBOBJECT_REVIEW_MISSING` | warning | 细分对象内容缺口，不创建子 Skill |
| `BUSINESS_SUBROUTE_REVIEW_MISSING` | warning | 子业务内容缺口，不创建子 Skill |
| `KB_PATH_KEY_NOT_IN_CATALOG` | error | 技能里写的库内路径键在最新目录中不存在（跨库/改名/编号漂移） |
| `KB_PATH_KEY_HAS_EXPORT_SUFFIX` | error | 路径键带了 `.md` 导出后缀（或把文件当目录写）；`.md` 只是导出后的本地文件名，不是库内节点名 |
| `KB_PATH_KEY_FOLDER_NEEDS_SLASH` | error | 路径键指向目录却没以 `/` 结尾（会被当成单文件项而记 failure） |
| `BUSINESS_COMMON_REVIEW_NOT_REFERENCED` | warning | 一级业务目录存在 `共同审核点`，但该业务 Skill 未下载/未回指它；仅在该文档确实存在时触发，文档不存在不报 |
| `CATALOG_NOT_LIVE` | error | 使用 `--max-age-hours` 时，快照无可解析抓取时间（无法证明是最新） |
| `CATALOG_STALE` | error | 使用 `--max-age-hours` 时，快照抓取时间超过时限 |

判定边界：

- 每一条资产/业务 registry 行都会被独立校验，即使其 label 不在本次目录快照内；否则目录改名会掩盖 registry 漂移。
- **公共轴（`public`）行另行校验**：与报告形态无关的公共能力不在 `02-资产类型/` / `01-业务路线/` 一级根模型内，其装配键位于 `06-规则库/` 下且可以多于一个，因此**不适用** `ASSEMBLY_FIRST_LEVEL_ROOT_MISSING`、`ASSEMBLY_FILE_MAPPING`、`AXIS_ROOT_MISMATCH`、`AXIS_PREFIX_MISMATCH` 与 `MAPPING_ROOT_NOT_IN_CATALOG`。适用于它们的是一级目录根之外的完整性检查：目录存在、frontmatter 名一致、声明了一份 KB 装配表；其库内路径键由 `inspect_path_keys` 统一校验（该函数遍历全部 `crwu-audit*` 目录，公共轴天然在内）。
- `MAPPING_ROOT_NOT_IN_CATALOG`、`AXIS_ROOT_MISMATCH` 和 `REGISTRY_LABEL_NOT_IN_CATALOG` 只在该轴的容器目录（`02-资产类型/`、`01-业务路线/`）已被本次目录捕获时才判定；只抓了一个轴的局部快照不会被误读为另一轴已被删除。
- `REGISTRY_LABEL_NOT_IN_CATALOG` 只针对 `available` 行；`pending` 行的目录缺失属于正常中间态。
- 重复 registry 行只按一条主张校验，避免同一问题重复计数。

路径键检查范围：`skills/crwu-audit*` 全部 `.md` 的**反引号内容**（技能约定寻址键写在反引号里）；只判断**本次目录已捕获的顶层容器**下的键——局部快照不会被误读为"另一轴全失效"。含 `…`／`*`／`<>`／`某`／`待建`／`不存在`／`省略` 的写法视为示例，不检查。

默认发现错误仍退出 0，方便盘点交付；CI 使用 `--strict`，存在 error finding 时退出 1。解析失败或输入不支持退出 2。

## 新 Skill 验证

```bash
python3 tools/kb/test_audit_skill_maintainer.py
python3 <skill-creator>/scripts/quick_validate.py skills/crwu-audit-skill-maintainer
python3 tools/kb/test_audit_multiaxis_router.py
python3 tools/kb/test_dws_source_contract.py
python3 tools/kb/kb_tool.py validate --skill-root skills
git diff --check
```

读取完整输出并逐项记录 exit code。迁移中的既有失败与本次回归分开报告；不得删除测试、扩大范围或修改无关文件来制造全绿。

## 目录树盘点交付

报告按以下顺序输出：

1. **结论分级**：已核实最新（本次在线且 complete=true、failures 为空）／候选·待核验（非本次在线、complete=false 或 failures 非空）／无法判定（刷新失败且无可用快照）；
2. 输入类型、抓取时间、complete 状态和一级目录数量；
3. 路由机制结论（入口与路由 reference 齐全、知识库出现的轴都已分发）；
4. 当前完整且映射正确的 Skill；
5. 建议新增的一级资产、一级业务 Skill（并说明细分对象、子业务、结构缺口**不**进入该清单）；
6. 需要修复、改名或重映射的 Skill；
7. 细分对象和子业务的内容缺口，以及一级业务目录 `共同审核点` 的有无与是否已回指；
8. 只凭目录无法确认、必须下载正文的项目；
9. 下一步逐文件方案及是否需要用户确认；
10. 校准表路径与本次刷新结果（表格区自动同步；内容级备注写明"已核"或"未核"）。

每个建议包含 axis、一级 label、建议 Skill 名、一级 kb_root、现状证据和动作。细分对象、子业务只能出现在父级索引或内容缺口中，不能进入“新增 Skill”列表。

## 完成判据

- 检查器对 Markdown、`node-index.json` 和 `目录快照.json` 三种真实输入的路径结论完全一致；
- `catalog.complete=false` 时只输出候选与待核验项，不得据此确认删除、改名或 `available`；
- 一级根与 registry 一一对应；
- available Skill 真实存在且 references 完整；
- 资产共性参考、细分审核条目、业务审核要点已覆盖或明确记 gap；
- 一级业务目录存在 `共同审核点` 时，该文档已随一级根下载并在 `02-review-focus.md` 回指；不存在时如实记录"未发现"，不记缺口；
- `07-kb-skill-map.md` 已用本次快照刷新，校准历史追加了一行，内容级备注与本次正文核对结论一致；
- 库内路径键检查为 0 未命中（含公共轴 `00-总纲`/`03`/`04`/`06` 的键）；有未命中时先修键再谈内容；
- Skill source 不含知识库名称、个人绝对路径、nodeId 值、下载正文或凭据；
- 所有验证结果真实报告，提交范围不包含用户的无关改动。
