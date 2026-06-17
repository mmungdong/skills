# Skill Sync & Installer Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create two project-level skills (`skill-sync` and `skill-installer`) in `.claude/skills/` to manage external skill references and local installation status.

**Architecture:** Two independent SKILL.md files in `.claude/skills/`, each containing structured instructions for Claude Code. No code files — these are prompt-driven skills that guide the agent through bash operations (gh CLI, git clone, symlink creation). The skills read from `install_reference.md` and `SKILL.md` files already defined in the project.

**Tech Stack:** Claude Code SKILL.md format, bash (gh CLI, git, ln -s)

---

## Chunk 1: Skill Sync

### File Structure

```
.claude/skills/skill-sync/
└── SKILL.md
```

### Task 1: Create skill-sync SKILL.md

**Files:**
- Create: `.claude/skills/skill-sync/SKILL.md`

- [ ] **Step 1: Create directory**
  ```bash
  mkdir -p .claude/skills/skill-sync
  ```

- [ ] **Step 2: Write SKILL.md with frontmatter and core instructions**

  The SKILL.md must contain:
  - Frontmatter: `name: skill-sync`, `description`, `metadata.version: 1.0.0`
  - Scan section: how to find all `install_reference.md` files (both `github/` and `skills/skills/`)
  - Fetch section: `gh` CLI primary → `git clone --depth 1` fallback
  - Compare section: parse local skill list vs remote, identify 🆕📝❌
  - Update section: ask user (all / selective / skip), rewrite `install_reference.md` preserving 已集成 status
  - Cleanup section: remove temp clone dirs

- [ ] **Step 3: Verify SKILL.md frontmatter is valid**

  Read the file back and confirm frontmatter parses correctly.

- [ ] **Step 4: Commit**
  ```bash
  git add .claude/skills/skill-sync/SKILL.md
  git commit -m "feat(skill-sync): add skill-sync project skill"
  ```

---

## Chunk 2: Skill Installer

### File Structure

```
.claude/skills/skill-installer/
└── SKILL.md
```

### Task 2: Create skill-installer SKILL.md

**Files:**
- Create: `.claude/skills/skill-installer/SKILL.md`

- [ ] **Step 1: Create directory**
  ```bash
  mkdir -p .claude/skills/skill-installer
  ```

- [ ] **Step 2: Write SKILL.md with frontmatter and core instructions**

  The SKILL.md must contain:
  - Frontmatter: `name: skill-installer`, `description`, `metadata.version: 1.0.0`
  - Status check section:
    - Scan `skills/skills/` only (not `github/`)
    - Check each Agent's skills directory for symlinks/directories
    - Agent paths: Claude Code (`~/.claude/skills/` global, `<project>/.claude/skills/` project), OpenCode (corresponding paths), Other (ask user)
    - Status logic: symlink to this repo → ✅, same-name dir → ✅ (other source), missing → ❌
    - Display as table grouped by category with columns: Skill | Description | Claude Code | OpenCode
  - Install section:
    - List all installable skills with status
    - Ask: 全部安装 / 部分安装
    - For each skill to install, ask 3 params: scope (global/project) → project path (if project) → agent (Claude Code / OpenCode / Other)
    - Install logic: custom skill (has SKILL.md) → `ln -s`; referenced skill (has install_reference.md) → read install command and execute
  - Post-install: refresh status display

- [ ] **Step 3: Verify SKILL.md frontmatter is valid**

  Read the file back and confirm frontmatter parses correctly.

- [ ] **Step 4: Commit**
  ```bash
  git add .claude/skills/skill-installer/SKILL.md
  git commit -m "feat(skill-installer): add skill-installer project skill"
  ```

---

## Chunk 3: Update Documentation

### Task 3: Update README.md directory structure

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add `.claude/skills/` to directory structure diagram**

  Add between `CLAUDE.md` and `github/` lines:
  ```
  ├── .claude/skills/         # Project-level skills (not distributable)
  │   └── <skill-name>/
  │       └── SKILL.md
  ```

- [ ] **Step 2: Commit**
  ```bash
  git add README.md
  git commit -m "docs(readme): add .claude/skills to directory structure"
  ```

### Task 4: Update README_zh.md directory structure

**Files:**
- Modify: `README_zh.md`

- [ ] **Step 1: Add `.claude/skills/` to directory structure diagram (Chinese)**

  Same structure change as README.md but in Chinese:
  ```
  ├── .claude/skills/         # 项目级 skill（非分发）
  │   └── <skill-name>/
  │       └── SKILL.md
  ```

- [ ] **Step 2: Commit**
  ```bash
  git add README_zh.md
  git commit -m "docs(readme-zh): add .claude/skills to directory structure"
  ```
