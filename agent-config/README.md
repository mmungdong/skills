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
| **DeepSeek Harness** | `~/.dsh/AGENTS.md` | 可用 `DSH_HOME` 改变 Harness 主目录，路径变为 `$DSH_HOME/AGENTS.md` |
| **OpenCode** | `~/.config/opencode/AGENTS.md` | OpenCode 会 fallback 到 `~/.claude/CLAUDE.md`；若两者并存，`AGENTS.md` 优先 |

**路径核实**：安装前用 `echo $CODEX_HOME`、`echo $DSH_HOME`、`ls ~/.config/opencode/` 等确认实际路径。

---

## 2. 安装步骤（软链方式）

### 2.1 安装命令

在本仓库根目录执行以下命令：

```bash
# 源文件（解析为绝对路径，避免工作目录变化导致链接失效）
REPO_ROOT="$(git rev-parse --show-toplevel)"
SOURCE="$REPO_ROOT/agent-config/README.md"
CODEX_ROOT="${CODEX_HOME:-$HOME/.codex}"
DSH_ROOT="${DSH_HOME:-$HOME/.dsh}"

# Claude Code
mkdir -p ~/.claude
ln -s "$SOURCE" ~/.claude/CLAUDE.md

# Codex (OpenAI)
mkdir -p "$CODEX_ROOT"
ln -s "$SOURCE" "$CODEX_ROOT/AGENTS.md"

# DeepSeek Harness
mkdir -p "$DSH_ROOT"
ln -s "$SOURCE" "$DSH_ROOT/AGENTS.md"

# OpenCode
mkdir -p ~/.config/opencode
ln -s "$SOURCE" ~/.config/opencode/AGENTS.md
```

### 2.2 验证安装

```bash
# 确认软链指向正确
ls -l ~/.claude/CLAUDE.md "$CODEX_ROOT/AGENTS.md" "$DSH_ROOT/AGENTS.md" ~/.config/opencode/AGENTS.md
# 确认内容可读
head -3 "$DSH_ROOT/AGENTS.md"
```

### 2.3 注意事项

- **目标文件已存在时**：若目标文件已有其他内容，**先备份再软链**：
  ```bash
  TARGET=~/.claude/CLAUDE.md
  BASE_BACKUP="$TARGET.bak.$(date +%Y%m%d%H%M%S)"
  BACKUP="$BASE_BACKUP"
  INDEX=0
  while [ -e "$BACKUP" ] || [ -L "$BACKUP" ]; do
    INDEX=$((INDEX + 1))
    BACKUP="$BASE_BACKUP.$INDEX"
  done
  mv "$TARGET" "$BACKUP"
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

### 3.6 跨平台工具约束（macOS / Windows 必须都能跑）

**立场**：本文档涉及的脚本、插件与技能，对**外部命令**的依赖必须在 macOS 与 Windows 上都有明确落点。
不允许出现「只在某一个平台成立的工具假设」；一旦某个工具在某平台不可得，
**必须给出该平台的替代工具或明确的降级/失败路径**，不允许静默失败、不允许重试空转。

**为什么立这条**（真实事故，2026-10-14 资产评估审核本地链路）：

- 案例工作区在 **Windows + exFAT（`D:`）**，而知识库取数调用的外部命令把"安全下载"实现为**硬链接发布**
  （`linkat`）。Windows 硬链接要求**同卷 + NTFS/ReFS**，exFAT 直接返回 `Incorrect function`，
  于是 **70 个条目 100% 失败**；同一条命令换到 NTFS 的 `C:` 上 14.5 秒即可成功。
  这次失败**串行跑完了全部 70 项才聚合报错**，并且**紧接着又重复重试了 2 次**（199.9s + 226.2s），
  三轮全部不可恢复 —— 单次会话在"必然失败的重试"上烧掉 13.4 分钟（占工具耗时 65%）。
- 同一链路里，旧版 `.doc`（OLE）**只有一条读取通道，且是 macOS 专有的 `textutil`**。
  在 Windows 上必然 `FileNotFoundError [WinError 2]`；该失败被记录为"材料不可读"，
  而不是"换一条读取路径"，导致两份**最关键的**报告文件在另一轮审核中整件未读。
- 结论：**外部工具的平台可用性是能力门禁的一部分，不是运行期偶发故障。**

**规则（每条都要可操作、可验证）**

1. **先探测再使用（capability-first）。** 任何外部命令在首次调用前先做可用性探测
   （优先走宿主提供的 capability 自检；没有则做一次真实副作用探测），并把探测结果写进运行记录。
   未探测就调用 = 违规。
2. **探测失败必须结构化上报，不得静默降级。** 区分三态：**本平台不存在** / **存在但执行失败** /
   **状态探测失败**。三态的理由文案不同，**不得**统一写成一个模糊的"不可用"，
   也**不得**在探测失败时改用同名命令或猜测路径继续。
3. **不存在的工具一律查本节的平台映射表**取替代实现；表里没有的，**停下来问**，
   不要"搜系统目录找一个能用的"、不要临时安装依赖、不要改走 shell 逃生路径。
4. **平台工具映射表（新增外部依赖时必须补一行）**

   | 能力 | macOS | Windows | 注意事项 |
   | --- | --- | --- | --- |
   | 文档格式转换 / 缩放（`.doc`/`.docx`/`.xls` → 可读文本或 `.docx`） | 系统 `textutil`；或 LibreOffice `soffice` | **DSH 自带 LibreOffice Kit**；或内置只读解析 | 禁止把 `textutil` 当跨平台方案；Kit 对非 512 字节对齐的 CFB 容器会报 `invalid or truncated compound-file header`，此时走内置解析 |
   | 旧版 Office 二进制（OLE/CFB：`.doc`/`.xls`）文本与内嵌媒体 | `textutil`；`soffice` | LibreOffice Kit；内置最小 CFB/OLE 解析（FIB + 分片表）；`xlrd` | 不要把"该平台读不出"写成"材料不存在/为空" |
   | PDF 文本层 / 渲染 | `pypdf`；`pdftoppm`；`mutool` | `pypdf`；LibreOffice Kit / `pdftoppm`（若可用） | 无文本层（扫描件）不能判"读不到"了事，须走渲染 + 多模态判读并写明"第 X/Y 页已判读" |
   | 表格（`.xlsx`/`.xls`）读写 | `openpyxl` / `xlrd` | 同 macOS（纯 Python，无平台差异） | 这两个是首选；缺包属环境门禁，须在**任务开始前**判出 |
   | 文本抽取（Deword/白板等） | 视工具自身文档 | 视工具自身文档 | 使用前先确认该工具作者声明的支持平台 |
   | 文件类型识别 | `file` | DSH 内置 magic 探测；不得依赖 `file` | Windows 无 `file` |
   | 硬链接 / 原子发布 | `link` / `rename`（同卷） | `CreateHardLink` 或 no-replace rename，**要求同卷 + NTFS/ReFS** | **exFAT/FAT32/网络盘不支持硬链接**；跨卷必失败。凡实现"原子发布"必须准备"暂存 + 普通复制"降级通道 |
   | 路径与临时目录 | POSIX 路径；`$TMPDIR` | 盘符 + `\`；`%LOCALAPPDATA%\Temp` | 不得硬编码 `/tmp` 或 `C:\`；跨卷操作要先判卷类型与文件系统 |
   | 控制台编码 | UTF-8 默认 | 必须显式设 UTF-8（`chcp 65001` / `[Console]::OutputEncoding`） | 否则中文输出乱码，会被误读成"文件损坏" |

5. **失败即熔断，禁止串行空转。** 同一批处理里**首个**失败若属于"环境级/整类不可用"
   （平台不存在、文件系统不支持、凭据未配置等），**立即停止剩余项**并上报：
   已完成的 job 标识、失败计数、根因、可恢复动作。**禁止**把整批跑完才聚合报错。
6. **重试必须有依据。** 同一手段最多重试一次，且必须换条件（换通道 / 换 job / 换工具）；
   环境级失败的重复调用 = 空转。若某个 job 已经产出、只是发布失败，**优先按该 job 恢复重取**，
   而不是重新提交整批。
7. **错误报告必须给出路。** 每条工具错误都要说清：**影响的组件** + **平台/环境事实** + **下一步动作**。
   禁止以下两类误导性报告：
   ① 只写"某能力不可用"却不给替代路径；
   ② 明明可换通道恢复，却标成"不可重试"，使调用方放弃恢复。
8. **交付/结论层面的能力缺口要和过程一致。** 因平台限制未读到的对象，必须在结果里逐条显式登记为
   "未核"并给出**员工可执行的动作**（例如"另存为 .docx 或 PDF 后重送"），
   **不得**计成"材料缺失"，**不得**用一个笼统的"不支持"掩盖。

**验收（缺一不可）**

- 涉及外部命令的新功能，必须在 **macOS 与 Windows 各跑一次**（CI matrix 或人工各一台），
  并把实际执行的命令与平台写进变更说明。无法两端验证的，显式标注"仅 `<平台>` 验证"，
  **不得**写成"跨平台可用"。
- 新增/修改外部依赖时，同一变更内更新上表；漏更新视为未完成。

---

## 4. 扩展指南

主人后续新增规范时，建议：

- 在「3. 规范内容」下新增子章节（如 `3.7 测试规范`、`3.8 PR 规范`）
- 保持每条规范**可操作、可验证**，避免模糊表述（"尽量写好"不可取，"函数不超过 80 行"可取）
- 规范若有项目特定性，注明应放在项目级配置而非全局
- 更新本文件后，所有 agent 全局配置**自动同步**（软链特性），无需重新安装
