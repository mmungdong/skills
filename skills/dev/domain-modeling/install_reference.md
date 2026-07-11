# Domain Modeling

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.0.1
- **路径**: skills/engineering/domain-modeling

## 安装

mattpocock/skills 是集合仓库，需克隆到本仓库 `vendor/` 目录后软链接单个 skill（`vendor/` 已被 `.gitignore` 排除）：

```bash
# 克隆集合仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/mattpocock/skills.git vendor/mattpocock-skills

# 软链接单个 skill 到 Claude Code
ln -s vendor/mattpocock-skills/skills/engineering/domain-modeling ~/.claude/skills/domain-modeling
```

## 说明

Build and sharpen a project's domain model. Use when pinning down domain terminology or a ubiquitous language, record an architectural decision, or when another skill needs to maintain the domain model.

适用于项目进入实现期：统一团队术语（ubiquitous language），记录架构决策（ADR），让领域知识从对话沉淀为可维护的模型文档。

## 选型定位

实现期领域建模工具。承接 `grill-with-docs` 澄清出的术语与边界，产出长期可维护的领域模型，供 `implement`、`code-review` 等后续 skill 引用。
