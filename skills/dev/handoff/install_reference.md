# Handoff

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.2.3
- **路径**: skills/productivity/handoff

## 安装

mattpocock/skills 是集合仓库，需克隆到本仓库 `vendor/` 目录后软链接单个 skill（`vendor/` 已被 `.gitignore` 排除）：

```bash
# 克隆集合仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/mattpocock/skills.git vendor/mattpocock-skills

# 软链接单个 skill；此处以 Codex 为例，DSH 可改为 ~/.dsh/skills/handoff
ln -s "$(pwd)/vendor/mattpocock-skills/skills/productivity/handoff" ~/.codex/skills/handoff
```

## 说明

Compact the current conversation into a handoff document for another agent to pick up.

将当前对话压缩为结构化交接文档，让另一个 Agent 能快速理解目标、进展、关键决策、未完成事项与下一步操作并继续工作。

## 选型定位

适用于切换 Agent、切换 harness、会话上下文过长或需要暂停后继续的场景。它负责保存可执行的工作上下文，不替代实现或代码审查流程。
