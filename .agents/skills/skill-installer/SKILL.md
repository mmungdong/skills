---
name: skill-installer
description: 检查本项目中所有 skill 的安装状态并支持交互式安装。扫描 skills/<category>/ 下的可安装 skill，检查各 Agent 中已安装的情况，并通过创建符号链接或执行安装命令完成安装。适用于查看 skill 状态、安装 skill 或管理本地 skill 安装。
metadata:
  version: 1.2.0
---

# Skill Installer

## Overview

Check installation status of all skills in this project and support interactive installation. Only manages skill directories under `skills/<category>/` — `github/` is not installable.

## Trigger

"看看 skill 安装状态", "安装 skill", "check skill status", "install skills"

## Agent Skills Directories

| Agent | Global | Project |
|-------|--------|---------|
| Claude Code | `~/.claude/skills/` | `<project>/.claude/skills/` |
| Codex | `~/.codex/skills/` | `<project>/.agents/skills/` |
| DeepSeek Harness | `~/.dsh/skills/` | `<project>/.dsh/skills/` or shared `<project>/.agents/skills/` |
| OpenCode | `~/.opencode/skills/` | `<project>/.opencode/skills/` |
| Other | Ask user for custom path | Ask user for custom path |

Resolve configurable home directories before checking or installing:

```bash
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
DSH_ROOT="${DSH_HOME:-$HOME/.dsh}"
```

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
find ./skills -mindepth 2 -maxdepth 2 -type d | sort
```

For each skill directory, determine its type:
- **Custom skill**: has `SKILL.md` → will be installed via symlink
- **Referenced skill**: has `install_reference.md` → will be installed per its instructions
- **Other directory**: has neither file → ignore it

#### 2. Check Status Per Agent

For each skill, check each Agent's skills directories:

```bash
# Example: check if skill exists in Claude Code global
ls -la ~/.claude/skills/<skill-name> 2>/dev/null

# Check if skill exists in Codex global
ls -la "$CODEX_ROOT/skills/<skill-name>" 2>/dev/null

# Check if skill exists in DeepSeek Harness global
ls -la "$DSH_ROOT/skills/<skill-name>" 2>/dev/null

# Check if skill exists in Claude Code project-level
ls -la <project>/.claude/skills/<skill-name> 2>/dev/null

# DeepSeek Harness project-level: inspect both roots separately
ls -la <project>/.dsh/skills/<skill-name> 2>/dev/null
ls -la <project>/.agents/skills/<skill-name> 2>/dev/null
```

For DeepSeek Harness project skills, `.dsh/skills` has higher discovery priority than `.agents/skills`. Default to `.agents/skills` for a skill shared with other compatible agents; use `.dsh/skills` only when the installation is intentionally DSH-specific. Report both locations separately during status checks.

**Status determination (priority order, evaluated separately for each requested scope):**
1. Symlink exists pointing to this repo's skill directory → ✅ 已安装（来自本仓库）
2. Valid symlink exists pointing elsewhere → ✅ 已安装（其他来源）
3. Same-name file or directory exists but is not a symlink → ✅ 已安装（其他来源）
4. Broken symlink exists → ⚠️ 损坏链接（安装前询问是否替换）
5. No filesystem entry exists → ❌ 未安装

A project-level installation does not satisfy a global installation request, and vice versa. Determine “missing” only from the target scope requested by the user.

#### 3. Display Status Table

Group by category, show status for each Agent:

```
### dev

| Skill | Description | Claude Code | Codex | DeepSeek Harness | OpenCode |
|-------|-------------|-------------|-------|------------------|----------|
| superpowers | Practical development workflow skills | ✅ 全局 | ✅ 全局 | ✅ 全局 | ❌ |
| my-skill | My custom skill | ✅ 项目:~/foo | ❌ | ✅ 项目 | ✅ 全局(其他来源) |
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
- Codex
- DeepSeek Harness
- OpenCode
- 其他（请输入 skills 目录路径）

For a DeepSeek Harness project-level install, ask whether the skill is shared (`<project>/.agents/skills`, recommended) or DSH-only (`<project>/.dsh/skills`).

#### 3. Scan & Deduplicate Source Repos (Batch Clone Plan)

**Before cloning anything**, scan all selected skills' `install_reference.md` and build a deduplicated list of source repos to clone. This avoids re-cloning the same collection repo (e.g. `mattpocock/skills`) once per skill.

For each selected referenced skill, extract from its `install_reference.md`:
- `<source-url>` — the git remote (e.g. `https://github.com/mattpocock/skills.git`)
- `<source-repo-name>` — short name for the `vendor/` subdirectory (e.g. `mattpocock-skills`)
- `<path-to-skill-inside-repo>` — subdirectory within the source repo holding this skill

Group skills by `<source-url>` and build the clone plan table:

```
| source-url                         | vendor dir          | skills covered                          | already cloned? |
|------------------------------------|---------------------|-----------------------------------------|-----------------|
| https://github.com/mattpocock/skills.git | vendor/mattpocock-skills | grill-me, grilling, domain-modeling | yes / no        |
| https://github.com/davila7/claude-code-templates.git | vendor/claude-code-templates | code-reviewer, ui-ux-pro-max | yes / no |
```

Determine `already cloned?` by checking `vendor/<source-repo-name>/.git`:

```bash
[ -d "$REPO/vendor/<source-repo-name>/.git" ] && echo yes || echo no
```

Display the table to the user and state the action plan:
- Repos marked **yes** → `git -C vendor/<dir> pull --ff-only` to refresh, **no re-clone**
- Repos marked **no** → `git clone <source-url> vendor/<source-repo-name>` exactly **once**, shared by all skills in that group

> 💡 One `vendor/<source-repo-name>/` backs every skill in its group. For a collection repo with N sub-skills, there is ever only 1 clone, not N.

#### 4. Execute Installation

**Step A — Clone/refresh each unique source repo** (run once per repo, not per skill):

```bash
REPO=<this-repo>   # absolute path to this skills repo

for each unique repo in the clone plan:
  VENDOR_DIR="$REPO/vendor/<source-repo-name>"
  if [ -d "$VENDOR_DIR/.git" ]; then
    git -C "$VENDOR_DIR" pull --ff-only       # already cloned → just refresh
  else
    git clone <source-url> "$VENDOR_DIR"      # clone once for the whole group
  fi
done
```

**Step B — Symlink each skill into the Agent directory** (per skill, reusing the cloned repo):

```bash
# Ensure the selected global or project skills directory exists:
mkdir -p <target-dir>

# Custom skill (has SKILL.md, lives in this repo — no clone needed):
ln -s "$REPO/skills/<category>/<skill-name>" <target-dir>/<skill-name>

# Referenced skill (reuses the vendor/ clone from Step A):
ln -s "$REPO/vendor/<source-repo-name>/<path-to-skill-inside-repo>" <target-dir>/<skill-name>
```

**Notes on referenced skill install:**
- Read `install_reference.md` for the `<source-url>` and the `<path-to-skill-inside-repo>` (the subdirectory within the source repo that holds the skill).
- For collection repos (e.g. `mattpocock/skills`), one clone in `vendor/` backs multiple skills — reuse the existing `vendor/<source-repo-name>/` for sibling skills instead of re-cloning; Step 3's dedup table makes this explicit.
- For npm-based skills whose installer (`npx claude-code-templates@latest --skill ...`) hits GitHub API rate limits, fall back to cloning the upstream source repo (e.g. `davila7/claude-code-templates`) into `vendor/` and symlinking, which bypasses the API entirely.
- If `install_reference.md` records a different install method (e.g. `git clone` directly into `~/.claude/skills/`), still redirect the clone into `vendor/` and symlink — keep all third-party code under `vendor/`.

#### 5. Verify and Refresh

After installation, re-check status for installed skills:

```bash
ls -la <target-dir>/<skill-name>
```

Display updated status table.

## Important Notes

- Only skill directories immediately below `skills/<category>/` are scanned for installation; `github/` is excluded
- **Always scan & deduplicate source repos before cloning** — when installing multiple referenced skills, first build a per-`<source-url>` clone plan so each source repo (especially collection repos) is cloned at most once, then symlink skills in a separate pass
- All third-party source repos live under `vendor/` (git-ignored) — never clone into `~/` or Agent directories directly; always clone into `vendor/` then symlink
- `vendor/` is local-only and never committed; on a fresh machine it is rebuilt by re-running installs
- For collection repos (e.g. mattpocock/skills with 18 sub-skills), one clone in `vendor/` backs many skills — reuse it for siblings instead of re-cloning; the Step 3 dedup table surfaces this automatically
- Before creating symlinks, ensure the selected Agent's global or project skills directory exists
- If a skill is already installed (✅), ask the user whether to reinstall/overwrite before proceeding
- Never replace a broken symlink automatically; show its current target and ask the user before removing or replacing it
- Symlink targets should use absolute paths to avoid broken links when working directories change
- Codex global paths follow `CODEX_HOME`, defaulting to `~/.codex`
- DeepSeek Harness global paths follow `DSH_HOME`, defaulting to `~/.dsh`; project skills may use `.dsh/skills` or the shared `.agents/skills`
