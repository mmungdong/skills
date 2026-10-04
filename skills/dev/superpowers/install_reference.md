# Superpowers

- **来源**: https://github.com/obra/superpowers
- **类型**: git
- **版本**: 6.4.2

## 安装

**Claude Code**：可通过 Superpowers plugin marketplace 安装；如果本机未配置 marketplace，也可使用下面的 vendor 软链方式。

**Codex / OpenCode / 通用方式：vendor 软链**

克隆到本仓库 `vendor/` 目录（已被 `.gitignore` 排除），再把各子 skill 软链接到目标 Agent 的 skills 目录：

```bash
# 克隆源仓库到 vendor/（已克隆则跳过，pull 更新）
git clone https://github.com/obra/superpowers.git vendor/superpowers

# 以 Codex 为例；OpenCode 可将目标目录替换为 ~/.opencode/skills
mkdir -p ~/.codex/skills
for skill in vendor/superpowers/skills/*; do
  ln -s "$(pwd)/$skill" ~/.codex/skills/"$(basename "$skill")"
done
```

## Skills 列表

> 集合仓库，包含以下子 skill；“已集成”状态按本仓库当前安装情况维护。

| Skill | Description | 已集成 |
|-------|-------------|--------|
| brainstorming | You MUST use this before any creative work - creating features, building components, adding functionality, or modifying behavior. Explores user intent, requirements and design before implementation. | ✅ |
| diagnosing-superpowers | Use when a superpowers session went wrong and your human partner wants to know why — repeated work, ignored plans, stumbles, poor results, a skill that didn't fire, "it took too long", "why is it so expensive", "what is it doing" — or wants to build a bug report for the superpowers maintainers, for the current session or a past one identified by id or path, on any harness. | ✅ |
| dispatching-parallel-agents | Use when facing 2+ independent tasks that can be worked on without shared state or sequential dependencies | ✅ |
| executing-plans | Use when executing an implementation plan in the current session as the implementer yourself — your human partner chose inline execution, or no subagent tool is available | ✅ |
| finishing-a-development-branch | Use when implementation is complete, all tests pass, and you need to decide how to integrate the work | ✅ |
| receiving-code-review | Use when receiving code review feedback, before implementing suggestions, especially if feedback seems unclear or technically questionable - requires technical rigor and verification, not performative agreement or blind implementation | ✅ |
| requesting-code-review | Use when completing tasks, implementing major features, or before merging to verify work meets requirements | ✅ |
| subagent-driven-development | Use when executing implementation plans with independent tasks in the current session | ✅ |
| systematic-debugging | Use when encountering any bug, test failure, or unexpected behavior, before proposing fixes | ✅ |
| test-driven-development | Use when implementing any feature or bugfix, before writing implementation code | ✅ |
| using-git-worktrees | Use when starting feature work that needs isolation from current workspace or before executing implementation plans - ensures an isolated workspace exists via native tools or git worktree fallback | ✅ |
| using-superpowers | Use when starting any conversation - establishes how to find and use skills, requiring skill invocation before ANY response including clarifying questions | ✅ |
| verification-before-completion | Use when about to claim work is complete, fixed, or passing, before committing or creating PRs - requires running verification commands and confirming output before making any success claims; evidence before assertions always | ✅ |
| writing-plans | Use when you have a spec or requirements for a multi-step task, before touching code | ✅ |
| writing-skills | Use when creating new skills, editing existing skills, or verifying skills work before deployment | ✅ |
