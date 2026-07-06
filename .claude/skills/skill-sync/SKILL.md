---
name: skill-sync
description: 检查本项目中外部 skill 引用是否为最新。扫描所有 install_reference.md 文件，从 GitHub 获取最新状态，与本地记录对比，并可选地更新本地记录。适用于检查 skill 更新、查看外部 skill 仓库的变化，或同步本地引用。
metadata:
  version: 1.0.0
---

# Skill Sync

## Overview

Scan all referenced skill repositories in this project, check for updates on GitHub, show diffs, and optionally update local `install_reference.md` files.

## Trigger

"检查 skill 更新", "看看外部 skill 有没有变化", "sync skills", "check skill updates"

## Process

### 1. Scan All install_reference.md Files

Find every `install_reference.md` in the project:

```bash
find . -name "install_reference.md" -not -path "./.git/*"
```

This covers both:
- `github/<user>/<repo>/install_reference.md` — external repos not yet integrated into workspace
- `skills/skills/<category>/<skill>/install_reference.md` — referenced skills already under management

### 2. Parse Source Repo URL

For each `install_reference.md`, extract the source repo URL from the `**来源**` or `**Source**` line:

```bash
grep -E '\*\*来源\*\*|\*\*Source\*\*' install_reference.md
```

Example output: `https://github.com/mattpocock/skills`

Convert to owner/repo format: `mattpocock/skills`

### 3. Fetch Latest State from GitHub

**Primary method: `gh` CLI**

```bash
# Get repo default branch
gh repo view <owner/repo> --json defaultBranchRef -q '.defaultBranchRef.name'

# Get directory listing of skills folder
gh api repos/<owner/repo>/contents/skills --jq '.[].name'

# Get each skill's SKILL.md frontmatter for name and description
gh api repos/<owner/repo>/contents/skills/<skill-name>/SKILL.md --jq '.content' | base64 -d | head -10
```

**Fallback: shallow clone**

```bash
TMPDIR="/tmp/skill-sync-$(date +%s)"
git clone --depth 1 https://github.com/<owner/repo>.git "$TMPDIR"
# Read skill directories and SKILL.md files from $TMPDIR
rm -rf "$TMPDIR"
```

If `gh` CLI is not available or returns an error, automatically fall back to shallow clone.

### 4. Compare Local vs Remote

Parse the local `install_reference.md` skill list (the tables under each category heading).

For each remote skill, compare against local records:
- **🆕 New**: Skill exists in remote but not in local `install_reference.md`
- **📝 Changed**: Skill exists in both but description differs
- **❌ Removed**: Skill exists in local but not in remote
- **✅ Unchanged**: Skill exists in both and description matches

### 5. Display Diff

Show results grouped by source repo:

```
## github/mattpocock/skills

🆕 New skills:
  - new-skill: Description of the new skill

📝 Changed:
  - tdd: "old desc" → "new desc"

❌ Removed:
  - deprecated-skill

✅ 15 skills unchanged
```

If no diffs found, report: "All skill references are up-to-date."

### 6. Ask User Whether to Update

If diffs exist, ask:

> 发现以上差异，是否更新本地的 install_reference.md？
> 1. 全部更新
> 2. 选择性更新
> 3. 跳过

For selective update, let user pick which changes to apply.

### 7. Update install_reference.md

Rewrite the `install_reference.md` file with updated skill list, **preserving the "已集成" column status** (❌/✅ values must not change for existing skills). New skills default to ❌.

Maintain the original format:
- Category headings (`### engineering`, etc.)
- Tables with columns: Skill | Description | 已集成

### 8. Cleanup

If shallow clone was used, ensure temp directory is removed:

```bash
rm -rf /tmp/skill-sync-*
```

## Important Notes

- Always preserve the "已集成" (❌/✅) status when updating — this is manually maintained by the user
- New skills added from remote default to ❌ (not integrated)
- For collection repos (like mattpocock/skills with sub-categories), maintain the same category structure as the remote repo
- Handle rate limiting: if `gh` CLI returns 403/429, fall back to shallow clone
