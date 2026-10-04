---
name: agent-config
description: 根据 agent-config/README.md 把个人全局规范软链安装到各 agent 工具（Claude Code、Codex、DeepSeek Harness、OpenCode）的全局配置文件。支持安装、状态检查、卸载、备份现有配置。适用于初始化 agent 全局规范、检查软链状态、同步规范更新到全局。
metadata:
  version: 1.1.0
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
| DeepSeek Harness | `~/.dsh/AGENTS.md` | 可用 `DSH_HOME` 改变 Harness 主目录 |
| OpenCode | `~/.config/opencode/AGENTS.md` | OpenCode 会 fallback 到 `~/.claude/CLAUDE.md` |

在仓库根目录运行时解析源文件：
```
REPO_ROOT="$(git rev-parse --show-toplevel)"
SOURCE="$REPO_ROOT/agent-config/README.md"
```

## Process

### Phase 1: 确认操作意图

询问主人要执行哪种操作：

1. **安装**（install）—— 软链源文件到目标路径
2. **状态检查**（status）—— 查看各 agent 当前软链状态
3. **卸载**（uninstall）—— 移除软链
4. **重新安装**（reinstall）—— 卸载后重新安装

再确认**目标 agent**：Claude Code / Codex / DeepSeek Harness / OpenCode，或全部。

### Phase 2: 状态检查

对每个目标 agent，检查目标路径当前状态：

```bash
# 解析可配置的 Agent 主目录
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
DSH_ROOT="${DSH_HOME:-$HOME/.dsh}"
REPO_ROOT="$(git rev-parse --show-toplevel)"
SOURCE="$REPO_ROOT/agent-config/README.md"
echo "CODEX_ROOT=$CODEX_ROOT"
echo "DSH_ROOT=$DSH_ROOT"

# 检查目标路径；不要使用 ls -L，因为它无法区分软链和普通文件
check_target() {
  TARGET="$1"
  if [ -L "$TARGET" ]; then
    if [ ! -e "$TARGET" ]; then
      echo "⚠️ 损坏软链: $TARGET -> $(readlink "$TARGET")"
    elif [ "$(realpath "$TARGET")" = "$SOURCE" ]; then
      echo "✅ 已安装（本仓库）: $TARGET"
    else
      echo "⚠️ 已安装（其他来源）: $TARGET -> $(readlink "$TARGET")"
    fi
  elif [ -e "$TARGET" ]; then
    echo "⚠️ 普通文件（需备份）: $TARGET"
  else
    echo "❌ 未安装: $TARGET"
  fi
}

check_target ~/.claude/CLAUDE.md
check_target "$CODEX_ROOT/AGENTS.md"
check_target "$DSH_ROOT/AGENTS.md"
check_target ~/.config/opencode/AGENTS.md
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
| DeepSeek Harness | ~/.dsh/AGENTS.md | ✅ 已安装(本仓库) |
| OpenCode | ~/.config/opencode/AGENTS.md | ❌ 未安装 |
```

若是 status 操作，到此结束。

### Phase 3: 安装

⚠️ 安装会修改全局配置，影响该 agent 所有会话。执行前向主人确认目标 agent 范围。

#### 1. 处理已存在的目标文件

若目标路径已存在（包括普通文件、其他来源软链或损坏软链），**先备份**：

```bash
TARGET="<target>"
if [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
  BASE_BACKUP="$TARGET.bak.$(date +%Y%m%d%H%M%S)"
  BACKUP="$BASE_BACKUP"
  INDEX=0
  while [ -e "$BACKUP" ] || [ -L "$BACKUP" ]; do
    INDEX=$((INDEX + 1))
    BACKUP="$BASE_BACKUP.$INDEX"
  done
  mv "$TARGET" "$BACKUP"
  echo "已备份: $BACKUP"
fi
```

若已是本仓库软链，跳过（无需重装）；若主人坚持重装，先删旧软链再建。

#### 2. 创建软链

```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
SOURCE="$REPO_ROOT/agent-config/README.md"
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
DSH_ROOT="${DSH_HOME:-$HOME/.dsh}"
# 必须用绝对路径，否则工作目录变化时软链失效

mkdir -p ~/.claude
ln -s "$SOURCE" ~/.claude/CLAUDE.md

mkdir -p "$CODEX_ROOT"
ln -s "$SOURCE" "$CODEX_ROOT/AGENTS.md"

mkdir -p "$DSH_ROOT"
ln -s "$SOURCE" "$DSH_ROOT/AGENTS.md"

mkdir -p ~/.config/opencode
ln -s "$SOURCE" ~/.config/opencode/AGENTS.md
```

（按主人选定的目标 agent 执行对应命令，不必全部执行。）

#### 3. 验证

```bash
ls -l ~/.claude/CLAUDE.md "$CODEX_ROOT/AGENTS.md" "$DSH_ROOT/AGENTS.md" ~/.config/opencode/AGENTS.md
head -3 "$DSH_ROOT/AGENTS.md"   # 确认内容可读、软链有效
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
- **DeepSeek Harness 路径受 `DSH_HOME` 影响**——未设置时使用 `~/.dsh`，全局规范文件为 `$DSH_HOME/AGENTS.md`
