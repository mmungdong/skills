<div align="center">

# 🐾 Skills

**我常用、自制与维护的 Claude Code Skills 合集。**

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](./LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Claude%20Code-7c3aed.svg)](https://claude.com/claude-code)
[![Skills](https://img.shields.io/badge/Skills-10%2B-16a34a.svg)](#-已收集的-skills)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-ff69b4.svg)](https://github.com/mmungdong/skills/pulls)

[中文](./README_zh.md) · [English](./README.md)

</div>

---

## ✨ 简介

本仓库汇集了浮浮酱日常使用的 Claude Code Skills——一部分自己编写，一部分引用自社区。每个 skill 都是自包含的，可通过软链安装到任意 agent 的 skills 目录。

- 🧩 **两种 skill 类型** — 自建（含 `SKILL.md` + `skill.json`）与引用（外部，仅 `install_reference.md`）
- 🔗 **软链友好** — 安装一次，处处同步
- 🛠️ **自托管工具** — 项目级 skill 用于管理仓库自身
- 🌐 **双语同步** — English & 中文 文档保持一致

---

## 📑 目录

- [目录结构](#-目录结构)
- [Skill 类型](#-skill-类型)
- [安装使用](#-安装使用)
- [项目 Skills](#-项目-skills)
- [已收集的 Skills](#-已收集的-skills)
- [协议](#-协议)

---

## 🗂 目录结构

```
skills/
├── README.md                # 当前文件
├── Agents.md                # Agent 通用规范
├── CLAUDE.md                # Claude Code 项目指引
├── agent-config/            # 全局 Agent 规范（可软链）
├── .claude/skills/          # 项目级 skill（非分发）
│   └── <skill-name>/
│       └── SKILL.md
├── github/                  # GitHub 来源（尚未集成）
│   └── <user>/<repo>/
│       └── install_reference.md
├── vendor/                  # 上游 skill 合集（只读）
└── skills/
    └── <category>/
        └── <skill-name>/
            ├── SKILL.md             # 自建 skill 主文件
            ├── skill.json           # 自建 skill 元数据
            ├── helpers/             # 辅助文件（可选）
            └── install_reference.md # 引用 skill 的来源说明
```

---

## 🧩 Skill 类型

### 自建 Skill（完整）

自己创建并维护的 skill，包含：

- **`SKILL.md`** *(必需)* — 含 frontmatter，定义 skill 的功能与触发时机
- **`skill.json`** *(必需)* — 由 `/create-skill-json` 生成
- **`helpers/`** *(可选)* — 辅助脚本、模板等

<details>
<summary><b>SKILL.md 格式</b></summary>

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
</details>

<details>
<summary><b>skill.json 格式</b></summary>

```json
{
  "version": "1.0.0",
  "name": "category/skill-name",
  "title": "skill-name",
  "aliases": ["skill-name", "category/skill-name"]
}
```
</details>

### 引用 Skill（外部）

引用他人维护的 skill（GitHub、npm 等），不需要 `SKILL.md` 和 `skill.json`，只需：

- **`install_reference.md`** — 说明 skill 的来源和安装方式

<details>
<summary><b>install_reference.md 格式</b></summary>

```markdown
# Skill Name

- **来源**: <url>
- **类型**: git | npm | other

## 安装

安装命令...
```
</details>

---

## 📦 安装使用

```bash
# 自建 skill：软链到 Claude Code skills 目录
ln -s "$(pwd)/skills/dev/my-skill" ~/.claude/skills/my-skill

# 引用 skill：按 install_reference.md 中的说明安装
```

> **小提示：** 软链请使用绝对路径——相对路径会在工作目录变化时失效。

---

## 🛠 项目 Skills

`.claude/skills/` 中的 skill 是管理本仓库的项目级工具，**不可分发**。

| Skill | Description | Version |
|-------|-------------|---------|
| [skill-sync](.claude/skills/skill-sync/SKILL.md) | 检查外部 skill 引用是否最新，从 GitHub 获取更新并同步本地记录 | 1.0.0 |
| [skill-installer](.claude/skills/skill-installer/SKILL.md) | 检查安装状态，交互式安装 skill 到 Agent skills 目录 | 1.0.0 |
| [agent-config](.claude/skills/agent-config/SKILL.md) | 通过软链把个人全局规范安装到各 agent 全局配置；支持安装、状态检查、卸载、重装 | 1.0.0 |

---

## 📚 已收集的 Skills

### `dev`

| Skill | Description | Version |
|-------|-------------|---------|
| [superpowers](skills/dev/superpowers/install_reference.md) | 实用 Claude Code 超能力，增强开发工作流 | 6.1.1 |
| [code-reviewer](skills/dev/code-reviewer/install_reference.md) | 综合代码审查 skill，支持 TypeScript/JavaScript/Python/Swift/Kotlin/Go，含自动分析、最佳实践检查、安全扫描和审查清单 | 1.29.2 |
| [ui-ux-pro-max](skills/dev/ui-ux-pro-max/install_reference.md) | UI/UX 设计智能，50 种风格、21 种配色、50 种字体搭配、20 种图表、9 种技术栈 | 1.29.2 |
| [grill-with-docs](skills/dev/grill-with-docs/install_reference.md) | 反复盘问以打磨计划或设计，过程中沉淀 ADR 和术语表等文档 | 1.0.1 |
| [to-prd](skills/dev/to-prd/install_reference.md) | 将当前对话整理成 PRD 并发布到项目 issue 跟踪器 | 1.0.1 |
| [to-issues](skills/dev/to-issues/install_reference.md) | 用 tracer-bullet 垂直切片将计划、spec 或 PRD 拆成可独立领取的 issue | 1.0.1 |
| [ask-matt](skills/dev/ask-matt/install_reference.md) | 询问哪种 skill 或流程适合当前情境——本仓库技能的路由器 | 1.0.1 |

---

## 📄 协议

基于 [Apache License 2.0](./LICENSE) 发布。

<div align="center">

<sub>由 <a href="https://github.com/mmungdong">@mmungdong</a> 用心维护 · Skills 让猫咪呼噜呼噜 🐱</sub>

</div>
