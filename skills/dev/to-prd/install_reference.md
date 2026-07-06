# To PRD

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.0.1
- **路径**: skills/engineering/to-prd

## 安装

mattpocock/skills 是集合仓库，需克隆到本仓库 `vendor/` 目录后软链接单个 skill（`vendor/` 已被 `.gitignore` 排除）：

```bash
# 克隆集合仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/mattpocock/skills.git vendor/mattpocock-skills

# 软链接单个 skill 到 Claude Code
ln -s vendor/mattpocock-skills/skills/engineering/to-prd ~/.claude/skills/to-prd
```

## 说明

Turn the current conversation into a PRD and publish it to the project issue tracker — no interview, just synthesis of what you've already discussed.

适用于需求澄清后：把讨论结果整理成 PRD，写清目标、非目标、用户路径、约束、验收标准和风险，让后续每个 agent 都能读懂。

## 选型定位

探索期需求落文档工具。承接 grill-with-docs 的澄清结果，产出可被 to-issues 拆分的 PRD。
