# 开发工作流：superpowers 与 mattpocock/skills 选型与协作

> 本文档沉淀自《架构师必学：superpowers 与 mattpocock/skills 选型指南》一文的方法论，并结合本仓库实际集成的 skill 整理而成。
>
> 核心命题：**AI Coding 不是让 agent 自由发挥，而是给它明确上下文、验证信号和责任边界。** 工具不能替你判断项目处在哪个阶段——先判断阶段，再选择工具。

---

## 1. 核心结论

superpowers 与 mattpocock/skills **不是谁替代谁，而是适合不同阶段**。

| 工具 | 定位 | 适合阶段 |
|------|------|---------|
| **superpowers** | 一套完整的软件开发方法论（brainstorming → spec → plan → TDD → review → branch 收尾） | 已知道做什么、怎么拆、怎么验收，让 AI 按规矩把功能做出来 |
| **mattpocock/skills** | 一组可组合的工程技能（grill 澄清 / to-prd 落文档 / to-issues 拆任务 / tdd / debug / review） | 还在想清楚"到底做什么、第一版不做什么、怎么验收" |

**白话版**：
- 已经知道要做什么、怎么拆、怎么验收 → **superpowers**
- 还在想清楚"做什么、不做什么、怎么验收" → **先用 mattpocock/skills**

---

## 2. 一个踩坑教训

> 背景：一个从 0 到 1 的 AI web UI 自动化 harness 探索项目，一开始主要按 superpowers 方式推进。

**问题**：探索项目最缺的不是执行力，而是前面的判断。需求边界没问清楚，后面的每一步都可能是在错误方向上变得更"自动化"。

**典型返工循环**：
- 方案做着做着发现边界不对 → 补一层规则
- 用例生成不稳定 → 再补一层约束
- 页面抽象不够清楚 → 再调整一次模型

每次返工单次看都不大，但累积起来消耗大量上下文、时间和 token。

**关键澄清**：superpowers 的 brainstorming 是整条开发流水线的**入口**（帮 agent 进入 spec/plan/TDD/review 链路）；而 `grill-with-docs` 的重点是**反复追问模糊点**，并把术语、边界、决策沉淀到 CONTEXT.md、ADR 或 PRD。从 0 到 1 的项目最缺的不是开发入口，而是有人把"你以为已经清楚"的地方继续问下去。

**教训**：从 0 到 1 的项目，不要一上来就把自己交给执行流程。**先把问题问清楚，再让工具提高执行效率。**

---

## 3. 快速判断表

| 当前状态 | 更适合 | 原因 |
|---------|--------|------|
| 还不知道第一版到底做什么、不做什么、怎么验收 | mattpocock/skills | 先用 grill、to-prd、to-issues 把问题问清楚 |
| 项目很复杂，需要从 0 到 1 慢慢拆清楚 | mattpocock/skills | 可分阶段组织复杂项目，不是只能补小任务 |
| 已有 spec 模板、任务切片方式和验收命令 | superpowers | 项目已进入"按规格开发"阶段 |
| 明确要交付一个 issue | implement | 围绕 PRD 或 issue 做完整交付闭环 |
| 测试失败、构建失败、bug 明确 | diagnosing-bugs | 用明确失败信号驱动修复 |

---

## 4. 什么时候先用 mattpocock/skills

> 只要你还在定义问题、流程资产和任务粒度，就先用 mattpocock/skills。复杂项目不能一次性交给 agent "全做完"——先澄清需求，再沉淀 PRD，再拆 issue，再一段一段实现和验证。mattpocock/skills 的优势是把这些阶段拆开，让每一步都有产物。

### 4.1 需求还没问清楚 → `grill-with-docs`

当只知道"我要做一个 X"，但还不知道第一版边界、核心场景、非目标和验收标准时，不要急着让 agent 实现。

```
$grill-with-docs
我想做一个 X，目标是让 agent 能 ...。请结合当前仓库帮我澄清第一版边界和验收标准。
```

- 价值不是给漂亮答案，而是**逼你把模糊想法变成可执行边界**
- 会追问"为什么第一版不做这个""谁会用这个能力""怎么验收才算完成"
- 如果项目已有代码和文档，会沉淀 CONTEXT.md 和 ADR，减少后续反复解释

### 4.2 写需求文档 → `to-prd`

需求澄清完，不要马上开工，先把讨论结果整理成 PRD。

```
$to-prd
请基于刚才的讨论、CONTEXT.md 和 ADR，整理 X v0 的 PRD。
```

- PRD 不是形式主义，是把"我以为你知道"变成"后续每个 agent 都能读懂"
- 至少写清：目标、非目标、用户路径、约束、验收标准、风险

### 4.3 创建独立开发任务 → `to-issues`

PRD 后不要直接让 agent "开始实现"——一个 PRD 往往含多个方向（数据结构、运行时、UI、测试、文档、验证脚本），一次全做容易互相牵扯。

```
$to-issues .scratch/<project>/prd-v0.md
```

- 目标：每个任务能独立领取、独立验证、独立交付
- 合理粒度：一个 issue 在一个明确上下文里完成一个可验证的垂直切片
- 拆太粗 → agent 自由发挥；拆太细 → 制造协调成本

### 4.4 不知道下一步 → `ask-matt`

已有 PRD 和 issue 但不确定下一步该用 implement、tdd、review 还是 qa 时，不要靠猜。

```
$ask-matt
我现在有 PRD 和 5 个 issue，第一个 issue 涉及 ...。下一步应该怎么推进？
```

- 价值是**流程路由**，不直接写代码，而是帮你选择更合适的工作方式

---

## 5. 什么时候用 superpowers

> superpowers 官方覆盖很宽，但普通团队更适合用窄一点的标准：它适合在"按规格开发"（SpecCoding）阶段做功能开发。SpecCoding 即先有清楚的规格说明，再按规格拆任务、写代码、跑验证，而不是边想边写。

**不要用"目标/边界/验收/执行链路是否清楚"判断**——这些词太主观，agent 容易把一句模糊确认理解成可以开工。

**更可操作的判断**：看项目里有没有这些具体资产：

- [ ] 已有固定的 spec 模板或需求描述格式
- [ ] 已有功能开发的目录约定、代码生成约定和命名约定
- [ ] 已有稳定的开发切片方式（一个 spec 如何拆成若干可交付任务）
- [ ] 已有固定的验证命令、报告产物或人工验收路径
- [ ] 团队已经多次按这套流程交付过功能（不是第一次边做边定义流程）

**资产不存在 → 还没真正进入 SpecCoding 阶段。** 资产已存在 → superpowers 价值很明显：让 agent 按成熟流程执行（读 spec → 写计划 → 小步实现 → TDD/review/验证把关）。这类任务是"按已有设计增加功能/修缺陷/补切片"，不是"替你从零定义流程"。

---

## 6. 推荐工作流（探索项目更省的链路）

```
grill-with-docs
  → CONTEXT.md / ADR
  → to-prd
  → to-issues
  → ask-matt
  → implement / superpowers
  → tdd
  → review / qa
  → diagnosing-bugs（只在有明确失败信号时使用）
```

**为什么看起来更慢反而更省**：它把最容易返工的部分提前暴露——目标、边界、非目标、验收标准、任务粒度。真正进入实现时，agent 上下文更稳定，执行更少跑偏。

- superpowers 不放开头，放在 SpecCoding 资产准备好之后
- 如果只是交付一个明确 issue，`implement` 可能比 superpowers 更轻

---

## 7. 几个容易混淆的点

### 7.1 `implement` 和 `tdd` 不是一回事

| | 面向 | 适用 |
|---|---|---|
| `implement` | 交付 | 拿着 PRD 或 issue 做完一个任务（外层交付流程） |
| `tdd` | 编码 | 行为边界清楚时用红绿重构推进（内层编码方法） |

合理关系：

```
PRD + 单个 issue
  → implement
  → 在适合的行为边界上使用 tdd
  → 编码
  → 单测 / 类型检查 / 全量测试
  → review
  → commit
```

⚠️ 一开始连行为边界都没想清楚就要求 TDD，测试也可能写偏。

### 7.2 `diagnosing-bugs` 不替代前期思考

`diagnosing-bugs` 适合**有明确失败信号的持续修复**：测试失败、构建失败、类型检查过不去、明确 bug 修到验证通过。

如果目标不清楚，让它一直修，只会把 agent 推进更深的返工循环。

---

## 8. 本仓库 skill 对应关系

> 本仓库已集成 superpowers 全部 skill，并 cherry-pick 了 mattpocock/skills 探索期澄清链路的 4 个关键 skill。

### 8.1 探索期（mattpocock/skills — 本仓库已集成）

| 环节 | skill | 路径 |
|------|-------|------|
| 需求澄清 | `grill-with-docs` | `skills/dev/grill-with-docs/install_reference.md` |
| 落 PRD | `to-prd` | `skills/dev/to-prd/install_reference.md` |
| 拆 issue | `to-issues` | `skills/dev/to-issues/install_reference.md` |
| 流程路由 | `ask-matt` | `skills/dev/ask-matt/install_reference.md` |

### 8.2 执行期（superpowers — 本仓库已集成全部）

| 环节 | skill | 路径 |
|------|-------|------|
| 创意/设计前探索 | `brainstorming` | `skills/dev/superpowers/install_reference.md` |
| 写实现计划 | `writing-plans` | 同上 |
| 执行计划 | `executing-plans` | 同上 |
| TDD | `test-driven-development` | 同上 |
| 请求代码审查 | `requesting-code-review` | 同上 |
| 接收代码审查 | `receiving-code-review` | 同上 |
| 完成分支 | `finishing-a-development-branch` | 同上 |
| 完成前验证 | `verification-before-completion` | 同上 |

### 8.3 其他已集成

| 环节 | skill | 路径 |
|------|-------|------|
| 代码审查（通用） | `code-reviewer` | `skills/dev/code-reviewer/install_reference.md` |
| UI/UX 设计 | `ui-ux-pro-max` | `skills/dev/ui-ux-pro-max/install_reference.md` |

---

## 9. 最终判断标准（一句话收束）

> **探索期，用 mattpocock/skills 多问几轮。**
> 这时最重要的是目标、边界、非目标、验收和任务粒度。
>
> **已经有规格、拆分方式和验收命令后，用 superpowers 把纪律跑起来。**
> 这时最重要的是沿着既有 spec、计划、小步实现、TDD、review 和验证流程稳定交付。

更简单一点：**需要补哪个工程环节，就用 mattpocock/skills；已经决定采用整条开发纪律，再用 superpowers。**

不要让一个工具承担所有职责。真正能减少返工的，是**先判断阶段，再选择工具**。

---

## 参考资料

- [架构师必学：superpowers 与 mattpocock/skills 选型指南](https://mp.weixin.qq.com/s/1B516kGEeEuKMJSxmJ6G-A)
- [Superpowers GitHub](https://github.com/obra/superpowers)
- [mattpocock/skills GitHub](https://github.com/mattpocock/skills)
- [skills.sh/mattpocock/skills/implement](https://skills.sh/mattpocock/skills/implement)
- [Claude Code Best Practices](https://www.anthropic.com/news/claude-code-best-practices)
- [Claude Code Skills Docs](https://docs.claude.com/en/docs/claude-code/skills)
- [Simon Willison: Vibe engineering](https://simonwillison.net/)
