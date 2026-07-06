# Ask Matt

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.0.1
- **路径**: skills/engineering/ask-matt

## 安装

mattpocock/skills 是集合仓库，需克隆到本仓库 `vendor/` 目录后软链接单个 skill（`vendor/` 已被 `.gitignore` 排除）：

```bash
# 克隆集合仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/mattpocock/skills.git vendor/mattpocock-skills

# 软链接单个 skill 到 Claude Code
ln -s vendor/mattpocock-skills/skills/engineering/ask-matt ~/.claude/skills/ask-matt
```

## 说明

Ask which skill or flow fits your situation. A router over the skills in this repo.

适用于已有 PRD 和 issue 但不确定下一步该用 implement、tdd、review 还是 qa 时：它不直接写代码，而是帮你选择更合适的工作方式，做流程路由。

## 选型定位

探索期流程路由工具。在澄清链路中负责判断下一步该进入哪个执行环节。
