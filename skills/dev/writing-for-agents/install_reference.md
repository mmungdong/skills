# Writing for Agents

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.2.3
- **路径**: skills/productivity/writing-for-agents

## 安装

mattpocock/skills 是集合仓库，需克隆到本仓库 `vendor/` 目录后软链接单个 skill（`vendor/` 已被 `.gitignore` 排除）：

```bash
# 克隆集合仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/mattpocock/skills.git vendor/mattpocock-skills

# 软链接单个 skill；此处以 Codex 为例，DSH 可改为 ~/.dsh/skills/writing-for-agents
ln -s "$(pwd)/vendor/mattpocock-skills/skills/productivity/writing-for-agents" ~/.codex/skills/writing-for-agents
```

## 说明

Writing documents for agents. Use when creating or editing skills, or modifying AGENTS.md or CLAUDE.md.

为 Agent 编写清晰、可执行的文档。适用于创建或编辑 skills，以及修改 `AGENTS.md`、`CLAUDE.md` 等 Agent 指令文件。

## 选型定位

适用于面向 Agent 的规则、工作流和技能文档编写，强调指令可执行性与上下文清晰度，不用于普通用户文档或产品文案。
