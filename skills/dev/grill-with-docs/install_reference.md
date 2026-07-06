# Grill With Docs

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.0.1
- **路径**: skills/engineering/grill-with-docs

## 安装

mattpocock/skills 是集合仓库，需克隆到本仓库 `vendor/` 目录后软链接单个 skill（`vendor/` 已被 `.gitignore` 排除）：

```bash
# 克隆集合仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/mattpocock/skills.git vendor/mattpocock-skills

# 软链接单个 skill 到 Claude Code
ln -s vendor/mattpocock-skills/skills/engineering/grill-with-docs ~/.claude/skills/grill-with-docs
```

## 说明

Relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go.

适用于从 0 到 1 的探索项目：当第一版边界、核心场景、非目标和验收标准还不清楚时，用它反复追问模糊点，并把术语、边界和决策沉淀到 CONTEXT.md、ADR 或 PRD，减少后续返工。

## 选型定位

探索期需求澄清工具。来自 mattpocock/skills 澄清链路：`grill-with-docs → to-prd → to-issues → ask-matt → implement`。
