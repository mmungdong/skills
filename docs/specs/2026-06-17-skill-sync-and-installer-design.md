# Skill Sync & Installer Design

Date: 2026-06-17

## Overview

Two project-level skills for managing this skill repository: one checks if external skill references are up-to-date, the other tracks installation status and supports interactive installation.

Both skills live in `.claude/skills/` — they are tools for managing this repository itself, not distributable skills.

## Skill 1: skill-sync

**Location**: `.claude/skills/skill-sync/SKILL.md`

**Purpose**: Scan all referenced skill repositories in the project, check for updates on GitHub, show diffs, and optionally update local `install_reference.md` files.

### Trigger

"检查 skill 更新", "看看外部 skill 有没有变化", etc.

### Scan Scope

All `install_reference.md` files in the project:

- `github/<user>/<repo>/install_reference.md` — external repos not yet integrated into workspace
- `skills/skills/<category>/<skill>/install_reference.md` — referenced skills already under management

### Core Flow

1. Scan all `install_reference.md` files, parse source repo URL from each
2. For each repo, fetch latest state:
   - **Primary**: `gh` CLI — use `gh api` to get directory structure and skill metadata
   - **Fallback**: `git clone --depth 1` to `/tmp/skill-sync-<timestamp>/`, clean up after use
3. Compare local `install_reference.md` skill list vs source repo actual skills
4. Display diff:
   - 🆕 New skills (in source, not in local)
   - 📝 Changed skills (description differs)
   - ❌ Removed skills (in local, not in source)
5. If diffs exist, ask user:
   - Update all / Selective update / Skip
6. Update `install_reference.md`, preserving "已集成" (❌/✅) column status

### Key Details

- Temp clone dir: `/tmp/skill-sync-<timestamp>/`, deleted after comparison
- Comparison key: skill name; comparison field: description
- Preserve the "已集成" status column when rewriting install_reference.md
- Handle both single-skill repos and collection repos (like mattpocock/skills with 18 sub-skills)

## Skill 2: skill-installer

**Location**: `.claude/skills/skill-installer/SKILL.md`

**Purpose**: Check installation status of all skills and support interactive installation. Only manages skills under `skills/skills/` — `github/` is not installable.

### Trigger

"看看 skill 安装状态", "安装 skill", etc.

### Status Check

Scan `skills/skills/` for all skill directories. For each skill, check across all known Agent skill directories:

- **Claude Code**: `~/.claude/skills/` (global) or `<project>/.claude/skills/` (project-level)
- **OpenCode**: corresponding paths
- **Other**: user-provided custom skills directory path

Installation status determination (priority order):

1. Symlink exists pointing to this repo → ✅ Installed (from this repo)
2. Same-name directory exists but not a symlink → ✅ Installed (other source)
3. Neither exists → ❌ Not installed

### Display Format

```
### dev

| Skill | Description | Claude Code | OpenCode |
|-------|-------------|-------------|----------|
| superpowers | ... | ✅ 全局 | ❌ |
| my-skill | ... | ✅ 项目:~/foo | ❌ |
```

### Installation Flow

1. List all skills under `skills/skills/` with current installation status
2. Ask user: Install all / Install selected
   - If selected: user picks which skills to install
3. For each skill to install, ask three parameters:
   - **Scope**: Global / Project-level
   - **Project path** (if project-level): which project directory
   - **Agent**: Claude Code / OpenCode / Other (custom path)
4. Execute installation based on skill type:
   - **Custom skill** (has SKILL.md): create symlink → `<agent-skills-dir>/<skill-name>` points to this repo's skill directory
   - **Referenced skill** (has install_reference.md): read install command from file and execute (e.g., `git clone`)
5. After installation, refresh status and display updated results

### Key Details

- Only `skills/skills/` is scanned for installation; `github/` is excluded
- For collection repos (e.g., mattpocock/skills), user must first cherry-pick skills into `skills/skills/` before they become installable
- Agent paths:
  - Claude Code global: `~/.claude/skills/`
  - Claude Code project: `<project>/.claude/skills/`
  - OpenCode global: `~/.opencode/skills/` (to be confirmed)
  - OpenCode project: `<project>/.opencode/skills/` (to be confirmed)
  - Other: user provides custom path
