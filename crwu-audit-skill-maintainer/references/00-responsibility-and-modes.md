# 职责、模式与输入

## 唯一职责

本 Skill 管理 `crwu-audit` 资产轴和业务轴 Skill 的生命周期：盘点、创建、修复、重映射和一致性验证。正式审核由 `crwu-audit` 编排，知识库访问由 `crwu-dws` 执行，反馈根因诊断由 `crwu-audit-optimize` 负责。

## 模式判定

### audit

用户提供目录树、DWS snapshot 或 node-index，要求查看缺失、错误或需要新增的能力时使用。该模式永远只读，可以立即执行，不需要修改确认。`audit` 是设计 §7.4 的规范模式名；早期草稿的 `inventory` 只是同义旧称。

输出至少分为：

1. 一级资产 Skill 缺口；
2. 一级业务 Skill 缺口；
3. 已有 Skill 的名称、结构或一级根映射问题；
4. 细分对象和子业务的审核文件缺口；
5. classification、registry 和真实目录不一致；
6. 无需处理项与待正文核验项。

### create

知识库出现一个尚无父级能力覆盖的一级资产或一级业务目录时使用。只有一级目录可以触发新 Skill 候选；目录中的细分对象和子业务只能扩展父 Skill。

### repair

Skill 已存在，但目录名、frontmatter、references、适用边界、二级选择规则、classification 或 registry 不一致时使用。

### remap

知识库一级根改名、移动、失效，或旧装配仍逐文件列举时使用。目标结果是一个一级目录根映射，不是重新挑选文件清单。

## 输入合同

| 字段 | 要求 |
| --- | --- |
| `mode` | `audit/create/repair/remap`；可由用户意图确定 |
| `repo_root` | source repo；默认当前仓库，但必须验证存在 `skills/crwu-audit/` |
| `catalog` | 粘贴目录树、DWS snapshot 或 node-index；create/remap 还需在线刷新 |
| `axis` | 创建或定向修复时为 `asset` 或 `business` |
| `canonical_label` | 一级资产或一级业务标签；不得传细分对象冒充一级标签 |
| `target_skill` | 修复目标；缺省时从 registry 和一级根映射推导 |

如果用户只给目录树，先完成结构盘点。正文未下载前，将“内容是否足以支撑审核”和“文件是否应归入该 Skill”标为待核验，不得伪装成确定结论。

## 权限边界

- `audit` 不写 source 或远端。
- `create/repair/remap` 的在线查询和下载是只读操作，可以用于形成方案。
- 修改 source 前必须给出逐文件方案并取得明确确认。
- 用户确认 source 修改不等于授权修改钉钉知识库、安装运行时 Skill、删除目录或批量修复其他能力。
