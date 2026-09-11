# 实时路由一致性核对

## 为什么单独一层

`audit` 原本只能证明"某份目录快照与当前登记一致"，不能证明"这份快照还是最新的"。钉钉侧一旦改名、新增或删除一级目录，基于旧快照的结论就会把"已失效"读成"正常"，把"该新建"读成"已覆盖"。

因此本层强制：**先用 `crwu-dws` 拉取最新知识库目录，再与当前 skill 体系逐项对比**，结论必须能追溯到本次抓取时间。

## 步骤一：拉最新目录（经 `crwu-dws`）

- 只读：走 `crwu-dws` 的 M1 目录查询，或 M3 刷新路径；对钉钉零写（`crwu-dws/SKILL.md` §2 白名单）。
- 缓存只用于定位加速：缓存身份（`.cache-meta.space` 的 name+workspaceId）与本次目标库不一致时，先清理缓存、再在线重下目录结构（`crwu-dws` §5.0）；**不得把旧缓存当作"最新"**。
- 记录四项：`fetchedAt`（抓取时间）、`complete`、`failures`、一级目录清单。
- 把本次结果落成本次临时快照（`目录快照.json` / `node-index.json` / `目录树.md` 任一形态），供检查器读取。
- 同一知识库的三种形态必须给出**完全相同的路径集合**；出现分歧说明解析有问题，不是知识库有差异。
- 在线刷新失败 → 不进入"已核实最新"结论；只能用旧快照输出**候选**，并显式标注"目录非本次在线结果"。

## 步骤二：与当前 skill 体系逐项对比

| 对比方 | 位置 | 角色 |
| --- | --- | --- |
| 知识库 | 本次最新目录 | **唯一路径事实** |
| 路由机制 | `crwu-audit/SKILL.md` + `references/08-union-dispatch-rules.md` | 分发与并集规则 |
| 路由参考 | `references/02`~`06` classification + `references/07-skill-registry.md` | 标签与登记 |
| 真实 Skill | skills 根下的 `crwu-audit*` 技能目录及其 references | 实现事实 |
| 分类表 | `03-asset-classification.md` / `04-business-classification.md` | 一级标签与二级识别规则 |

## 步骤三：四类检查

### 1 路由机制是否完好

- router 入口 `<skills 根>/crwu-audit/SKILL.md` 存在（否则 `ROUTER_FILE_MISSING`）。
- router 依赖的路由 reference 齐全：`00-input-and-route-profile.md`、`02`~`06` classification、`07-skill-registry.md`、`08-union-dispatch-rules.md`、`10-capability-gap-proposal.md`、`99-maintenance.md`（缺失 → `ROUTER_REFERENCE_MISSING`）。
- router 命名的 `NN-*.md` 必须真实存在于 `crwu-audit/references/`；叶子自有 reference 名（`00-applicability.md`/`01-kb-assembly.md`/`02-review-focus.md`）不计（未解析 → `ROUTER_REFERENCE_UNRESOLVED`）。
- 知识库里出现的轴，并集规则必须真的会加载它：资产 → `asset_skills`，业务 → `business_skills`（缺 → `ROUTER_AXIS_UNDISPATCHED`）。

### 2 路由参考是否注册

- 每个知识库一级目录 → registry **恰好一行**：0 行 = 未登记（`FIRST_LEVEL_SKILL_MISSING`）；多于 1 行 = 重复（`REGISTRY_LABEL_DUPLICATE`）。
- registry 的 label 必须与知识库一级目录同名（比较时去掉数字排序前缀，写映射时保留完整路径）。
- 该 label 必须出现在对应 classification（缺 → `CLASSIFICATION_LABEL_MISSING`）。
- `available` 行必须在真实目录、references、一级根契约上全部成立。
- registry 声称 `available`、而知识库已无该一级目录 → `REGISTRY_LABEL_NOT_IN_CATALOG`（改名/迁走）。

### 3 Skill 是否存在

- `available` → 目录存在（否则 `AVAILABLE_SKILL_DIRECTORY_MISSING`）+ 三份规定 reference（否则 `SKILL_REFERENCE_MISSING`）+ 名称一致（否则 `SKILL_NAME_MISMATCH`）。
- 一级根契约：声明的一级根必须精确存在（否则 `ASSEMBLY_FIRST_LEVEL_ROOT_MISSING`）、必须属于本轴（否则 `AXIS_ROOT_MISMATCH`）、必须仍在最新目录中（否则 `MAPPING_ROOT_NOT_IN_CATALOG`）。
- router 与并集规则里出现的**具体技能名**，必须能解析到真实目录或 registry 行（否则 `ROUTER_SKILL_REFERENCE_UNRESOLVED`）。通配写法（`crwu-audit-asset-*`）与占位写法（`crwu-audit-<axis>-<label>`）不算具体名字。
- 遗留组合技能与遗留前缀 → `LEGACY_COMBINED_SKILL` / `LEGACY_BUSINESS_PREFIX`，属迁移项，不属"当前可用能力"。

### 4 是否需要创建

- 知识库一级目录没有 registry 行 → **创建候选**（一级资产/业务 Skill），并给出建议名与一级根。
- 细分对象（如土地使用权）与子业务（如租赁与租金评估）→ **不建 Skill**；进入父级 Skill 的二级索引或内容 gap，绝不能出现在"需创建"清单里。
- 知识库结构缺口（资产缺 `01-共性参考`、细分对象缺 `评估审核条目`、子业务缺 `01-业务通用审核要点`、业务一级根缺 `共同审核点`）→ 记内容 gap，不新建 Skill。
- `pending` → 只在 registry 记录，不创建空 Skill 目录。

## 结论分级（必须标注）

| 结论 | 成立条件 |
| --- | --- |
| 已核实最新 | 本次在线抓取成功且 `complete=true`、`failures` 为空 |
| 候选 / 待核验 | 快照非本次在线结果、`complete=false` 或 `failures` 非空 |
| 无法判定 | 在线刷新失败且无可用快照 |

## 与各模式的关系

- `audit`：本层就是主流程——先拉最新，再对比，最后按上表标注结论级别。
- `create` / `remap`：本层是前置，必须刷新后才形成方案。
- `repair`：改名、结构或边界修复前必须刷新，否则会按过期目录"修"出新漂移。
- 任何模式都不得只凭旧缓存、历史摘录或他人粘贴的目录下"是否需要创建"的最终结论。

## 命令

```bash
python3 scripts/check_audit_skill_mappings.py \
  --repo-root <source-repo> \
  --catalog <本次 crwu-dws 刷新落地的快照> \
  --max-age-hours 1 \
  --format text
```

`--max-age-hours` 让"必须是最新"可执行：快照没有可解析抓取时间 → `CATALOG_NOT_LIVE`；超过时限 → `CATALOG_STALE`。离线盘点时可省略该参数，但结论必须降级为"候选/待核验"。

## 输出要求

1. 抓取时间、`complete`、`failures` 与一级目录数量；
2. 路由机制结论（入口/参考齐全、轴已分发）；
3. 注册一致性（未登记、重复、label 不符）；
4. 技能存在性（目录、references、一级根）；
5. 需创建清单，以及**明确不需要创建**的项（细分对象、子业务、结构缺口）；
6. 结论分级与下一步逐文件方案。

## 红线

- 不得用"缓存命中"冒充"已核实最新"。
- 不得仅凭快照的"缺席"删除或改名 Skill；删除必须基于最新完整目录并取得用户确认。
- 不得把细分对象、子业务或知识库结构缺口列进"需创建 Skill"。
- 不得因在线刷新失败就把旧结论标为最新。
