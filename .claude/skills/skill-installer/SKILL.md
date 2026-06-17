---
name: skill-installer
description: Check installation status of all skills in this project and support interactive installation. Scans skills/skills/ for installable skills, checks which are installed across agents, and creates symlinks or runs install commands. Use when you want to check skill status, install skills, or manage local skill installations.
metadata:
  version: 1.0.0
---

# Skill Installer

## Overview

Check installation status of all skills in this project and support interactive installation. Only manages skills under `skills/skills/` — `github/` is not installable.

## Trigger

"看看 skill 安装状态", "安装 skill", "check skill status", "install skills"

## Agent Skills Directories

| Agent | Global | Project |
|-------|--------|---------|
| Claude Code | `~/.claude/skills/` | `<project>/.claude/skills/` |
| OpenCode | `~/.opencode/skills/` | `<project>/.opencode/skills/` |
| Other | Ask user for custom path | Ask user for custom path |

## Process

### Phase 1: Check Installation Status

#### 1. Scan Installable Skills

```bash
find ./skills/skills -mindepth 1 -maxdepth 3 -type d | sort
```

For each skill directory, determine its type:
- **Custom skill**: has `SKILL.md` → will be installed via symlink
- **Referenced skill**: has `install_reference.md` → will be installed per its instructions

#### 2. Check Status Per Agent

For each skill, check each Agent's skills directories:

```bash
# Example: check if skill exists in Claude Code global
ls -la ~/.claude/skills/<skill-name> 2>/dev/null

# Check if skill exists in Claude Code project-level
ls -la <project>/.claude/skills/<skill-name> 2>/dev/null
```

**Status determination (priority order):**
1. Symlink exists pointing to this repo's skill directory → ✅ 已安装（来自本仓库）
2. Same-name directory exists but not a symlink → ✅ 已安装（其他来源）
3. Neither exists → ❌ 未安装

#### 3. Display Status Table

Group by category, show status for each Agent:

```
### dev

| Skill | Description | Claude Code | OpenCode |
|-------|-------------|-------------|----------|
| superpowers | Practical Claude Code superpowers | ✅ 全局 | ❌ |
| my-skill | My custom skill | ✅ 项目:~/foo | ✅ 全局(其他来源) |
```

### Phase 2: Install Skills

#### 1. Ask What to Install

List all installable skills with current status and ask:

> 要安装哪些 skill？
> 1. 全部安装
> 2. 部分安装（请列出要安装的 skill）

#### 2. For Each Skill, Ask Installation Parameters

Three questions per skill (or per batch if installing all to same target):

**a) 安装范围？**
- 全局 (global)
- 项目级 (project)

**b) 如果项目级，项目路径？**
> 请输入项目绝对路径：

**c) 安装到哪个 Agent？**
- Claude Code
- OpenCode
- 其他（请输入 skills 目录路径）

#### 3. Execute Installation

**Custom skill (has SKILL.md):**

```bash
# Determine target directory based on answers
# Global Claude Code: ~/.claude/skills/<skill-name>
# Project Claude Code: <project>/.claude/skills/<skill-name>
# Global OpenCode: ~/.opencode/skills/<skill-name>
# Project OpenCode: <project>/.opencode/skills/<skill-name>
# Other: <custom-path>/<skill-name>

# Create symlink
ln -s <this-repo>/skills/skills/<category>/<skill-name> <target-dir>/<skill-name>
```

**Referenced skill (has install_reference.md):**

Read `install_reference.md` for the install command (e.g., `git clone ...`) and execute it, installing to the same target directory.

```bash
# Example from install_reference.md:
git clone https://github.com/obra/superpowers.git ~/.claude/skills/superpowers
```

Adjust the target path based on the user's chosen scope, project, and agent.

#### 4. Verify and Refresh

After installation, re-check status for installed skills:

```bash
ls -la <target-dir>/<skill-name>
```

Display updated status table.

## Important Notes

- Only `skills/skills/` is scanned for installation; `github/` is excluded
- For collection repos (e.g., mattpocock/skills with 18 sub-skills), user must first cherry-pick skills into `skills/skills/` before they become installable
- When installing to project-level, ensure the project's `.claude/skills/` directory exists before creating symlinks
- If a skill is already installed (✅), ask the user whether to reinstall/overwrite before proceeding
- Symlink targets should use absolute paths to avoid broken links when working directories change
