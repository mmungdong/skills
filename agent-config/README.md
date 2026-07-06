# Agent 全局配置规范

> 本文档是一份**全局指令模板**，定义了适用于所有项目的个人代码规范与 Git 规范。
>
> **安装方式**：通过软链（`ln -s`）将本文件链接到各 agent 工具的全局配置路径。源文件改一处，所有 agent 自动生效，无需复制粘贴。

---

## 1. 目标全局配置文件

不同 agent 工具的全局指令文件路径不同，把本文件软链到对应路径即可。

| Agent 工具 | 软链目标路径 | 备注 |
|-----------|------------|------|
| **Claude Code** | `~/.claude/CLAUDE.md` | Windows 路径：`%USERPROFILE%\.claude\CLAUDE.md` |
| **Codex (OpenAI)** | `~/.codex/AGENTS.md` | 若 `~/.codex/AGENTS.override.md` 存在则其优先；可用 `CODEX_HOME` 改变家目录，路径变为 `$CODEX_HOME/AGENTS.md` |
| **OpenCode** | `~/.config/opencode/AGENTS.md` | OpenCode 会 fallback 到 `~/.claude/CLAUDE.md`；若两者并存，`AGENTS.md` 优先 |

**路径核实**：安装前用 `echo $CODEX_HOME`、`ls ~/.config/opencode/` 等确认实际路径。

---

## 2. 安装步骤（软链方式）

### 2.1 安装命令

本仓库源文件路径示例：`/home/mungdong/workspace/skills/agent-config/README.md`（按实际仓库位置调整）。

```bash
# 源文件（用绝对路径，避免工作目录变化导致链接失效）
SOURCE="/home/mungdong/workspace/skills/agent-config/README.md"

# Claude Code
mkdir -p ~/.claude
ln -sf "$SOURCE" ~/.claude/CLAUDE.md

# Codex (OpenAI)
mkdir -p ~/.codex
ln -sf "$SOURCE" ~/.codex/AGENTS.md

# OpenCode
mkdir -p ~/.config/opencode
ln -sf "$SOURCE" ~/.config/opencode/AGENTS.md
```

### 2.2 验证安装

```bash
# 确认软链指向正确
ls -l ~/.claude/CLAUDE.md ~/.codex/AGENTS.md ~/.config/opencode/AGENTS.md
# 确认内容可读
head -3 ~/.claude/CLAUDE.md
```

### 2.3 注意事项

- **目标文件已存在时**：`ln -sf` 的 `-f` 会强制覆盖。若目标文件已有其他内容，**先备份再软链**：
  ```bash
  mv ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.bak
  ```
  若已有内容需要保留，先把其合并进本文件「3. 规范内容」后再软链。
- **绝对路径**：软链必须用绝对路径，相对路径会在工作目录变化时失效。
- **自动同步**：修改本文件后，所有软链处自动生效，**无需重新安装**——这是软链相对复制粘贴的核心优势。
- **项目级优先**：项目级 `CLAUDE.md` / `AGENTS.md` 的约定优先于本全局文件，本文件不声明"覆盖项目级"。

> ⚠️ 软链后本文件即为该 agent 的全局指令，影响其所有会话。安装前确认目标路径无误。

---

## 3. 规范内容

> 以下为各 agent 应遵守的本体规范。维护原则：保持通用、跨项目适用；项目特定的约束不放在这里，放在项目级配置。

### 3.1 Git 提交规范

- commit 时**不要**添加 `Co-Authored-By` 行
- 使用英文 Angular 规范提交，格式：`<type>(<scope>): <subject>`
  - type：`feat | fix | docs | style | refactor | perf | test | chore | ci | build | revert`
  - scope 可选，表示影响范围
  - subject 简短描述，不加句号
- 提交前确认变更已通过验证（测试 / 类型检查 / 构建按项目实际约定）
- 不要自动提交和推送，除非用户明确要求

### 3.2 代码风格

- 保持与现有代码一致的风格、命名和缩进
- 注释密度和风格对齐周围代码
- 修改前先阅读目标文件，理解上下文
- 优先复用现有工具函数和模式，避免引入重复实现

### 3.3 工作习惯

- 不确定时主动询问，不要猜测
- 完成后确认结果，不要含糊其辞
- 基于事实而非猜测，充分使用工具收集信息
- 先读后写，理解现有代码再修改
- 每次操作前充分规划，深思熟虑后行动

### 3.4 响应语言

- 默认使用简体中文回复

### 3.5 注释规范

- 代码中**不要有过多的注释**，注释应当**简明精要**
- 代码注释**使用英文**撰写
- 优先让代码自解释（清晰的命名、合理的结构），而非用注释解释晦涩代码
- 注释只标注"为什么这样做"的设计意图或非显而易见的约束，不重复代码已表达的内容
- 公共 API、复杂算法、workaround 等可加注释；显而易见的逻辑不需要

---

## 4. 扩展指南

主人后续新增规范时，建议：

- 在「3. 规范内容」下新增子章节（如 `3.5 测试规范`、`3.6 PR 规范`）
- 保持每条规范**可操作、可验证**，避免模糊表述（"尽量写好"不可取，"函数不超过 80 行"可取）
- 规范若有项目特定性，注明应放在项目级配置而非全局
- 更新本文件后，所有 agent 全局配置**自动同步**（软链特性），无需重新安装
