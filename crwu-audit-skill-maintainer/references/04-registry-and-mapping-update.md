# 分类、registry 与映射更新

## 同步对象

资产能力变更至少检查：

- `crwu-audit/references/03-asset-classification.md`；
- `crwu-audit/references/07-skill-registry.md`；
- 目标 `crwu-audit-asset-*` 及三份 references；
- router、测试、`skills/README.md`、设计文档和变更记录中的引用。

业务能力变更至少检查：

- `crwu-audit/references/04-business-classification.md`；
- `crwu-audit/references/07-skill-registry.md`；
- 目标 `crwu-audit-biz-*` 及三份 references；
- router、测试、`skills/README.md`、设计文档和变更记录中的引用。

## 一级登记、二级索引

- classification 维护一级标签、别名，以及细分对象或子业务到父级的关系。
- registry 只登记一级资产和一级业务 Skill。
- 细分对象或子业务新增时，更新父 Skill 的 applicability 和 review-focus；不得新增 registry Skill 行。
- 一个一级标签在 registry 中恰好一行。多个标签共享一个 Skill 时必须有明确的同一一级目录依据，不能为了省目录合并不同一级根。

## 状态

| 状态 | 条件 |
| --- | --- |
| `available` | 真实 Skill、三份 reference、一级根、二级索引、正文核验和全部门禁完成 |
| `pending` | 一级能力已识别但材料或实现未完成；只登记，不建空 Skill |
| `profile-only` | 只保留画像，不需要执行 Skill |

缺少细分审核条目只在父 Skill 记录 gap，不因此创建空子 Skill。

## 校准表（07-kb-skill-map.md）

- **定位**：知识库 ↔ Skill 映射的**只读派生视图**，给人一眼看现状用；事实源仍是知识库最新目录 + `07-skill-registry.md` + `skills/` 真实目录。它不参与运行时路由，不替代 registry。
- **生成**：只由检查器 `--emit-map` 生成，禁止手工编辑状态列：

```bash
python3 scripts/check_audit_skill_mappings.py \
  --repo-root . --catalog <本次 crwu-dws 快照> --max-age-hours <H> \
  --emit-map <本技能目录>/references/07-kb-skill-map.md
```

- **同步时机**：`audit`/`create`/`repair`/`remap` 每个模式收尾都要刷新一次；多次校准会向「校准历史」追加行（新→旧），不覆盖旧行。
- **两区语义**：
  - 表格区（自动）：一级目录、标签、Skill、registry 状态、声明的一级根、共用层/共性参考、细分对象或子业务计数与缺项、本次问题代码。
  - 「内容级校准备注」区（**人工维护，工具不覆盖**）：写目录看不出来的内容状态——必检项是否「待补」、文档是否为空、是否 `TODO` 占位、历史问题条数与检查维度、库侧清理建议。
- **分工**：目录级事实自动化；内容级事实必须来自本次下载正文，未下载时如实写"未核"，不得留空冒充合格。

## 两阶段修改门禁

### 阶段一：只读方案

1. 保存 `git status --short`、目标文件 hash 和当前分支。
2. 运行只读 audit 检查器。
3. 刷新 DWS 目录，并对目标一级根递归下载全部正文。
4. 对照 classification、registry、Skill、references 和测试。
5. 输出逐文件方案：动作、目标、修改摘要、来源证据、依赖、风险和验证命令。

### 阶段二：确认后执行

1. 用户明确确认本次方案。
2. 重新计算目标文件 hash；任何目标变化都回到阶段一。
3. 仅修改方案列出的 source 文件，保留其他 staged、unstaged 和 untracked 内容。
4. 不写运行时目录，不提交下载正文、manifest、缓存或凭据。
5. 验证后只提交授权路径；失败时保持真实状态。

## 命名迁移

`crwu-audit-business-*` 是遗留前缀。迁移到 `crwu-audit-biz-*` 时同时检查目录名、frontmatter、registry、classification、router、测试、README、设计文档和变更记录。迁移未完成前不得把新名字标为 available，也不得同时保留两个可加载名字。
