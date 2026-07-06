---
name: skill-installer
description: 检查本项目中所有 skill 的安装状态并支持交互式安装。扫描 skills/skills/ 下的可安装 skill，检查各 Agent 中已安装的情况，并通过创建符号链接或执行安装命令完成安装。适用于查看 skill 状态、安装 skill 或管理本地 skill 安装。
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

## Third-Party Repo Directory

All external skill source repos are cloned into a single **`vendor/`** directory at this project's root, then symlinked into Agent skills directories. This keeps third-party code集中管理, isolated from `~/`, and git-ignored.

- Directory: `<this-repo>/vendor/`
- Git-ignored via `.gitignore` (`/vendor/`) — never committed
- One subdirectory per source repo, e.g. `vendor/mattpocock-skills/`, `vendor/claude-code-templates/`
- Symlinks always point into `vendor/`, never into `~/` or other scattered locations

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

Custom skills live in this repo, so no cloning is needed — symlink directly.

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

Two-step flow: **clone the source repo into `vendor/` first, then symlink the target skill into the Agent directory.** Never clone into `~/` or the Agent directory directly.

```bash
REPO=<this-repo>   # absolute path to this skills repo

# Step 1: Clone source repo into vendor/ (skip if already cloned)
# Derive a short name for the vendor subdirectory from the source repo.
VENDOR_DIR="$REPO/vendor/<source-repo-name>"
if [ -d "$VENDOR_DIR/.git" ]; then
  git -C "$VENDOR_DIR" pull --ff-only
else
  git clone <source-url> "$VENDOR_DIR"
fi

# Step 2: Symlink the target skill into the Agent skills directory
ln -s "$VENDOR_DIR/<path-to-skill-inside-repo>" <target-dir>/<skill-name>
```

**Notes on referenced skill install:**
- Read `install_reference.md` for the `<source-url>` and the `<path-to-skill-inside-repo>` (the subdirectory within the source repo that holds the skill).
- For collection repos (e.g. `mattpocock/skills`), one clone in `vendor/` backs multiple skills — reuse the existing `vendor/<source-repo-name>/` for sibling skills instead of re-cloning.
- For npm-based skills whose installer (`npx claude-code-templates@latest --skill ...`) hits GitHub API rate limits, fall back to cloning the upstream source repo (e.g. `davila7/claude-code-templates`) into `vendor/` and symlinking, which bypasses the API entirely.
- If `install_reference.md` records a different install method (e.g. `git clone` directly into `~/.claude/skills/`), still redirect the clone into `vendor/` and symlink — keep all third-party code under `vendor/`.

#### 4. Verify and Refresh

After installation, re-check status for installed skills:

```bash
ls -la <target-dir>/<skill-name>
```

Display updated status table.

## Important Notes

- Only `skills/skills/` is scanned for installation; `github/` is excluded
- All third-party source repos live under `vendor/` (git-ignored) — never clone into `~/` or Agent directories directly; always clone into `vendor/` then symlink
- `vendor/` is local-only and never committed; on a fresh machine it is rebuilt by re-running installs
- For collection repos (e.g. mattpocock/skills with 18 sub-skills), one clone in `vendor/` backs many skills — reuse it for siblings instead of re-cloning
- When installing to project-level, ensure the project's `.claude/skills/` directory exists before creating symlinks
- If a skill is already installed (✅), ask the user whether to reinstall/overwrite before proceeding
- Symlink targets should use absolute paths to avoid broken links when working directories change
