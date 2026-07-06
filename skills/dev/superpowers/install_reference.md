# Superpowers

- **来源**: https://github.com/obra/superpowers
- **类型**: git
- **版本**: 6.1.1

## 安装

**当前实际集成方式：Claude Code plugin marketplace**（见 `~/.claude/plugins/marketplaces/superpowers-marketplace`），无需 vendor 软链。

**备选：vendor 软链方式**（不通过 plugin marketplace 时使用）

克隆到本仓库 `vendor/` 目录（已被 `.gitignore` 排除）后软链接：

```bash
# 克隆源仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/obra/superpowers.git vendor/superpowers

# 软链接到 Claude Code
ln -s vendor/superpowers ~/.claude/skills/superpowers
```

## Skills 列表

> 集合仓库，包含以下子 skill。本仓库已通过 `.claude/skills` 集成全部 superpowers skill。

| Skill | Description | 已集成 |
|-------|-------------|--------|
| brainstorming | You MUST use this before any creative work — creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation | ✅ |
| dispatching-parallel-agents | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies | ✅ |
| executing-plans | Use when you have a written implementation plan to execute in a separate session with review checkpoints | ✅ |
| finishing-a-development-branch | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work — merge, PR, or cleanup | ✅ |
| receiving-code-review | Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable | ✅ |
| requesting-code-review | Use when completing tasks, implementing major features, or before merging to verify work meets requirements | ✅ |
| subagent-driven-development | Use when executing implementation plans with independent tasks in the current session | ✅ |
| systematic-debugging | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes | ✅ |
| test-driven-development | Use when implementing any feature or bugfix, before writing implementation code | ✅ |
| using-git-worktrees | Use when starting feature work that needs isolation from current workspace or before executing implementation plans | ✅ |
| using-superpowers | Use when starting any conversation — establishes how to find and use skills, requiring skill invocation before ANY response | ✅ |
| verification-before-completion | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs — evidence before assertions always | ✅ |
| writing-plans | Use when you have a spec or requirements for a multi-step task, before touching code | ✅ |
| writing-skills | Use when creating new skills, editing existing skills, or verifying skills work before deployment | ✅ |
