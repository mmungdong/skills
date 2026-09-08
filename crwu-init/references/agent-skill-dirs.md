# crwu-init · 各 Agent skills 安装目录参考

> 维护纪律：本表是**缓存/默认值**。每次对 workbuddy / codex / opencode 或其它
> 不熟悉的 agent 安装前，用 `web_search` 核实官方文档；路径有变 → **以官方为准**
> 并回写本表（含链接、日期）。deepseek harness 以本机 dsh 的 skills 根为准。

## 目录表

| Agent | 用户级 skills 目录 | 环境变量覆盖 | 官方文档（核实用） |
| --- | --- | --- | --- |
| workbuddy | `~/.workbuddy/skills/` | — | https://www.workbuddy.cn/docs/cli/skills |
| codex | `~/.codex/skills/` | — | Codex CLI 官方文档 skills 一节 |
| opencode | `~/.config/opencode/skills/` | — | https://opencode.ai/docs/skills/ |
| deepseek harness (dsh) | `$DSH_HOME/skills/`（默认 `~/.dsh/skills/`） | `$DSH_HOME` | 本机 DSH `@deepseek-ai/dsh-skill-filesystem`（user-dsh 根） |

## 补充说明

- **codex**：还有项目级 `.codex/skills/`、系统级 `/usr/local/share/codex/skills/`；
  用户级默认装到 `~/.codex/skills/`。
- **opencode**：额外兼容 `~/.claude/skills/`、`~/.agents/skills/`；opencode **原生**
  用户级目录是 `~/.config/opencode/skills/`。
- **deepseek harness (dsh)**：技能根发现顺序（rank 由高到低）= 项目 `.dsh/skills` →
  项目 `.agents/skills` → 自定义 → 用户 `~/.dsh/skills` → 共享 `~/.agents/skills`；
  用户级优先装 `~/.dsh/skills/`。

## 技能格式兼容性

本仓库技能均为 `<name>/SKILL.md`（frontmatter 含 `name` + `description`，可选
`references/` 子文件夹），上述 agent 均按此格式发现（`<root>/<name>/SKILL.md`），
无需转换。

## 覆盖语义（重要）

- **更新模式 = 同名技能全量替换**：`rm -rf <TARGET>/<name>` 后再 `cp -R`，保证
  `references/` 等子文件夹也被覆盖、旧文件不残留。
- 顶层非技能文件（如 `skills/README.md`）不安装；只安装含 `SKILL.md` 的子目录。
