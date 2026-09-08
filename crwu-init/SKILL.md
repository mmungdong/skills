---
name: crwu-init
description: >-
  初始化 / 安装 / 更新 crwu（crwu-ai）环境的技能。当用户说"初始化 crwu 环境""安装/
  部署/分发 crwu skills""把 crwu 的 skills 装到 XX（workbuddy/codex/opencode/deepseek
  harness）""更新/同步 crwu skills""覆盖我的 crwu skills"等时自动使用。流程：①确定目标
  agent（未说明则给选项：workbuddy / codex / deepseek harness，都没有则请用户提供安装
  目录）②联网核实该 agent 的 skills 安装目录 ③从 https://gitee.com/mengdong123/crwu-ai
  拉取 skills/ 目录 ④按"安装全部 / 安装指定 / 更新（同名覆盖含子文件夹）"写入 agent 的
  skills 目录 ⑤校验并汇报。不用于 crwu 审核（crwu-audit*）、钉钉知识库（crwu-dws）、
  氚云（h3yun-*）等业务技能本身的执行。
---

# crwu 环境初始化 / 技能安装（crwu-init）

把 crwu 仓库（`https://gitee.com/mengdong123/crwu-ai`）`skills/` 目录下的技能，
安装/更新到用户指定的 AI agent 的 skills 目录。本技能是**安装器/分发器**：不改技能
正文，只做"确定目标 → 联网核实目录 → 拉取 → 复制 → 校验"。

## 0. 自动触发 / 不触发

- **触发**：初始化 crwu 环境、安装/部署/分发 crwu skills、更新/同步 crwu skills、
  把 crwu skills 装到某个 agent。
- **不触发**：跑 `crwu-audit*` 审核、`crwu-dws` 钉钉知识库、`h3yun-*` 氚云等业务
  （这些是别的技能）；也不负责 `crwu` CLI 二进制本身的编译/安装。

## 1. 确定目标 agent

先看用户是否已点名 agent（workbuddy / codex / opencode / deepseek harness / 其它）。
**没点名**时，向用户提问并给出选项（用当前 agent 自带的提问能力，如 DSH 的
`ask_user_question`），默认顺序：

1. workbuddy
2. codex
3. deepseek harness

若以上都不匹配，请用户直接提供**目标 skills 目录的绝对路径**（例如某个自研 agent 的
`~/.xxx/skills`），拿到路径后跳到第 3 步。

## 2. 解析目标 skills 目录（联网核实）

按目标 agent 查表（完整表 + 官方文档链接见
[`references/agent-skill-dirs.md`](references/agent-skill-dirs.md)）：

| Agent | 用户级 skills 目录（默认） |
| --- | --- |
| workbuddy | `~/.workbuddy/skills/` |
| codex | `~/.codex/skills/` |
| opencode | `~/.config/opencode/skills/` |
| deepseek harness (dsh) | `$DSH_HOME/skills/`（默认 `~/.dsh/skills/`） |

> 表内是**默认值/缓存**。对 workbuddy / codex / opencode 或其它不熟悉的 agent，
> 执行安装前用 `web_search` 搜官方文档（关键词如
> "`<agent>` skills directory location / skills 安装目录"），确认当前 skills 目录；
> 这些路径可能随版本变化。若官方路径与表不一致，**以官方为准**，并把差异回写到
> `references/agent-skill-dirs.md`。deepseek harness 则直接用本机 dsh 的 skills 根
> （`$DSH_HOME/skills`，默认 `~/.dsh/skills`）。

最终目录解析规则：

- 展开 `~` 为 `$HOME`；
- 目标 agent 支持环境变量覆盖时（如 dsh 的 `$DSH_HOME`）优先用环境变量；
- 写目标目录前，向用户**确认最终绝对路径**（用户已明确给出则跳过确认）。

## 3. 确定模式

| 用户说法 | 模式 | 行为 |
| --- | --- | --- |
| 初始化 / 安装全部 / 安装所有 skills | install-all | 把仓库 `skills/` 下**全部**技能复制进目标目录（同名先删后拷，幂等） |
| 安装 X、Y…（点名若干） | install-some | 只复制点名的技能（含其 `references/` 等子文件夹） |
| 更新 / 同步 / 覆盖 | update | 只覆盖目标目录里**已存在的同名**技能，全量替换（含子文件夹）；目标里没有的**不新增** |

未明确模式时默认按 **install-all**（"初始化"语义），执行前口头确认一句。

## 4. 拉取源仓库

```bash
SRC="$(mktemp -d)"
git clone --depth 1 https://gitee.com/mengdong123/crwu-ai.git "$SRC/crwu-ai"
SKILLS_SRC="$SRC/crwu-ai/skills"
```

- 只把**包含 `SKILL.md` 的子目录**当作技能；顶层文件（如 `skills/README.md`）一律跳过。
- 列出可用技能名：

```bash
for d in "$SKILLS_SRC"/*/; do
  [ -f "$d/SKILL.md" ] && basename "$d"
done
```

## 5. 执行安装

统一约定：目标目录为 `TARGET`；每个技能目录名为 `S`（含其下所有子文件/子文件夹）。

```bash
mkdir -p "$TARGET"

# install-all / install-some：对每个要装的 S
rm -rf "$TARGET/$S"; cp -R "$SKILLS_SRC/$S" "$TARGET/$S"

# update：只对"目标目录已存在"的 S 执行上面 rm+cp；其余跳过并记录
```

- **覆盖一律 `rm -rf` + `cp -R`**（先删后拷）：保证 `references/` 等子文件夹被完整
  替换、不残留旧文件——这正是"更新=同名覆盖含子文件夹"的要求。
- 复制后检查目标技能目录下不得残留 `.git`（源里 `skills/` 下本就没有；若有先删）。

## 6. 校验与汇报

```bash
ls -1 "$TARGET"
for d in "$TARGET"/*/; do
  [ -f "$d/SKILL.md" ] || echo "缺 SKILL.md: $d"
done
```

汇报要点：目标 agent + 最终绝对目录；本次模式；装了/更新了哪些技能（逐条列出）；
update 模式下跳过的（目标里原本没有的）或非技能目录；联网核实到的任何目录变更。

## 附注

- 本技能自身也在源仓库 `skills/` 下：install-all 会把 `crwu-init` 一并装进目标，
  这样以后在该 agent 里还能继续"初始化/更新"。
- 只做文件复制，不改技能正文、不改 agent 配置文件（`settings.json` 等）。
