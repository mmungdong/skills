# Skills

中文 | [English](README.md)

收集和制作我常用的 Claude Code Skills。

## 目录结构

```
skills/
├── README.md
├── Agents.md                # Agent 通用规范
├── CLAUDE.md                # Claude Code 项目指引
├── .claude/skills/          # 项目级 skill（非分发）
│   └── <skill-name>/
│       └── SKILL.md
└── skills/
    └── <category>/
        └── <skill-name>/
            ├── SKILL.md             # 自建 skill 主文件
            ├── skill.json           # 自建 skill 元数据
            ├── helpers/             # 辅助文件（可选）
            └── install_reference.md # 引用 skill 的来源说明
```

## Skill 类型

### 自建 Skill（完整）

自己创建并维护的 skill，包含：

- **SKILL.md**（必需）— 含 frontmatter，定义 skill 的功能和使用方式
- **skill.json**（必需）— 由 `/create-skill-json` 生成
- **helpers/**（可选）— 辅助脚本、模板等

#### SKILL.md 格式

```markdown
---
name: skill-name
description: 一句话描述 skill 的用途和触发时机
metadata:
  version: 1.0.0
---

# Skill 标题

详细说明 skill 的功能、使用方式和注意事项。
```

#### skill.json 格式

```json
{
  "version": "1.0.0",
  "name": "category/skill-name",
  "title": "skill-name",
  "aliases": ["skill-name", "category/skill-name"]
}
```

### 引用 Skill（外部）

引用他人维护的 skill（GitHub、npm 等），不需要 SKILL.md 和 skill.json，只需：

- **install_reference.md** — 说明 skill 的来源和安装方式

#### install_reference.md 格式

```markdown
# Skill Name

- **来源**: <url>
- **类型**: git | npm | other

## 安装

安装命令...
```

## 安装使用

```bash
# 自建 skill：链接到 Claude Code skills 目录
ln -s $(pwd)/skills/dev/my-skill ~/.claude/skills/my-skill

# 引用 skill：按 install_reference.md 中的说明安装
```

## 项目 Skills

`.claude/skills/` 中的 skill 是管理本仓库的项目级工具，不可分发。

| Skill | Description | Version |
|-------|-------------|---------|
| [skill-sync](.claude/skills/skill-sync/SKILL.md) | 检查外部 skill 引用是否最新，从 GitHub 获取更新并同步本地记录 | 1.0.0 |
| [skill-installer](.claude/skills/skill-installer/SKILL.md) | 检查安装状态，交互式安装 skill 到 Agent skills 目录 | 1.0.0 |
| [agent-config](.claude/skills/agent-config/SKILL.md) | 通过软链把个人全局规范（agent-config/README.md）安装到各 agent 全局配置；支持安装、状态检查、卸载、重装 | 1.0.0 |

## 已收集的 Skills

### dev

| Skill | Description | Version |
|-------|-------------|---------|
| [superpowers](skills/dev/superpowers/install_reference.md) | 实用 Claude Code 超能力，增强开发工作流 | 6.1.1 |
| [code-reviewer](skills/dev/code-reviewer/install_reference.md) | 综合代码审查 skill，支持 TypeScript/JavaScript/Python/Swift/Kotlin/Go，含自动分析、最佳实践检查、安全扫描和审查清单 | 1.29.2 |
| [ui-ux-pro-max](skills/dev/ui-ux-pro-max/install_reference.md) | UI/UX 设计智能，50 种风格、21 种配色、50 种字体搭配、20 种图表、9 种技术栈 | 1.29.2 |
| [grill-with-docs](skills/dev/grill-with-docs/install_reference.md) | 反复盘问以打磨计划或设计，过程中沉淀 ADR 和术语表等文档 | 1.0.1 |
| [to-prd](skills/dev/to-prd/install_reference.md) | 将当前对话整理成 PRD 并发布到项目 issue 跟踪器 | 1.0.1 |
| [to-issues](skills/dev/to-issues/install_reference.md) | 用 tracer-bullet 垂直切片将计划、spec 或 PRD 拆成可独立领取的 issue | 1.0.1 |
| [ask-matt](skills/dev/ask-matt/install_reference.md) | 询问哪种 skill 或流程适合当前情境——本仓库技能的路由器 | 1.0.1 |
