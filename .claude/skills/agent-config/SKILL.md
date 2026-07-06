---
name: agent-config
description: 根据 agent-config/README.md 把个人全局规范软链安装到各 agent 工具（Claude Code、Codex、OpenCode）的全局配置文件。支持安装、状态检查、卸载、备份现有配置。适用于初始化 agent 全局规范、检查软链状态、同步规范更新到全局。
metadata:
  version: 1.0.0
---

# Agent Config

## Overview

根据本仓库 `agent-config/README.md`，把全局规范通过**软链**安装到各 agent 工具的全局配置文件。源文件改一处，所有 agent 自动同步，无需复制粘贴。

只管理本仓库 `agent-config/README.md` 的软链安装；不修改规范内容本身（规范编辑直接改 `agent-config/README.md`）。

## Trigger

"配置 agent 全局规范", "安装全局规范", "初始化 agent 配置", "setup agent global config", "check agent config status"

## 目标配置文件

| Agent 工具 | 软链目标路径 | 备注 |
|-----------|------------|------|
| Claude Code | `~/.claude/CLAUDE.md` | |
| Codex (OpenAI) | `~/.codex/AGENTS.md` | 若 `~/.codex/AGENTS.override.md` 存在则其优先；可用 `CODEX_HOME` 改变家目录 |
| OpenCode | `~/.config/opencode/AGENTS.md` | OpenCode 会 fallback 到 `~/.claude/CLAUDE.md` |

源文件（绝对路径，按实际仓库位置调整）：
```
/home/mungdong/workspace/skills/agent-config/README.md
```

## Process

### Phase 1: 确认操作意图

询问主人要执行哪种操作：

1. **安装**（install）—— 软链源文件到目标路径
2. **状态检查**（status）—— 查看各 agent 当前软链状态
3. **卸载**（uninstall）—— 移除软链
4. **重新安装**（reinstall）—— 卸载后重新安装

再确认**目标 agent**：Claude Code / Codex / OpenCode，或全部。

### Phase 2: 状态检查

对每个目标 agent，检查目标路径当前状态：

```bash
# 解析 CODEX_HOME（影响 Codex 路径）
echo "CODEX_HOME=${CODEX_HOME:-<未设置，使用 ~/.codex>}"

# 检查目标路径
ls -lL ~/.claude/CLAUDE.md 2>/dev/null
ls -lL ~/.codex/AGENTS.md 2>/dev/null
ls -lL ~/.config/opencode/AGENTS.md 2>/dev/null
```

判断状态（优先级）：
1. 软链且指向本仓库源文件 → ✅ 已安装（本仓库）
2. 软链但指向其他文件 → ⚠️ 已安装（其他来源）
3. 普通文件存在 → ⚠️ 普通文件（非软链，需备份后才能软链）
4. 不存在 → ❌ 未安装

输出状态表：

```
| Agent | 目标路径 | 状态 |
|-------|---------|------|
| Claude Code | ~/.claude/CLAUDE.md | ✅ 已安装(本仓库) |
| Codex | ~/.codex/AGENTS.md | ⚠️ 普通文件 |
| OpenCode | ~/.config/opencode/AGENTS.md | ❌ 未安装 |
```

若是 status 操作，到此结束。

### Phase 3: 安装

⚠️ 安装会修改全局配置，影响该 agent 所有会话。执行前向主人确认目标 agent 范围。

#### 1. 处理已存在的目标文件

若目标路径已存在（普通文件或指向其他的软链），**先备份**：

```bash
# 备份命名带时间戳，避免覆盖已有备份
BACKUP="<target>.bak.$(date +%Y%m%d%H%M%S)"
mv "<target>" "$BACKUP"
echo "已备份: $BACKUP"
```

若已是本仓库软链，跳过（无需重装）；若主人坚持重装，先删旧软链再建。

#### 2. 创建软链

```bash
SOURCE="/home/mungdong/workspace/skills/agent-config/README.md"
# 必须用绝对路径，否则工作目录变化时软链失效

mkdir -p ~/.claude
ln -sf "$SOURCE" ~/.claude/CLAUDE.md

mkdir -p ~/.codex
ln -sf "$SOURCE" ~/.codex/AGENTS.md

mkdir -p ~/.config/opencode
ln -sf "$SOURCE" ~/.config/opencode/AGENTS.md
```

（按主人选定的目标 agent 执行对应命令，不必全部执行。）

#### 3. 验证

```bash
ls -l ~/.claude/CLAUDE.md
head -3 ~/.claude/CLAUDE.md   # 确认内容可读、软链有效
```

#### 4. 回报

向主人确认每个 agent 的安装结果、备份路径。

### Phase 4: 卸载

```bash
# 只移除指向本仓库源文件的软链；其他来源的文件/软链不处理
TARGET="<target>"
if [ -L "$TARGET" ]; then
  LINK=$(readlink "$TARGET")
  if [[ "$LINK" == *"/skills/agent-config/README.md" ]]; then
    rm "$TARGET"
    echo "已移除软链: $TARGET"
  else
    echo "跳过（指向其他来源）: $TARGET -> $LINK"
  fi
fi
```

卸载后询问主人是否恢复之前的备份。

## Important Notes

- **软链必须用绝对路径**——相对路径在工作目录变化时失效
- **绝对路径以实际仓库位置为准**——若仓库迁移，需更新本 skill 中的 SOURCE 路径并重装软链
- **备份优先**——目标路径已有内容时，先 `mv` 备份再软链，绝不直接 `-f` 覆盖主人已有的全局配置
- **规范编辑不在此 skill**——改规范直接编辑 `agent-config/README.md`，软链处自动同步，无需重新安装
- **项目级优先**——全局规范是默认值，项目级 `CLAUDE.md`/`AGENTS.md` 约定优先；本 skill 不处理项目级配置
- **Codex 路径受 `CODEX_HOME` 影响**——执行前用 `echo $CODEX_HOME` 确认实际家目录
