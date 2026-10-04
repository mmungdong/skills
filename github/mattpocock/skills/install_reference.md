# MattPocock Skills

- **来源**: https://github.com/mattpocock/skills
- **类型**: git
- **版本**: 1.2.3

## 安装

```bash
git clone https://github.com/mattpocock/skills.git ~/.claude/skills/mattpocock-skills
```

## Skills 列表

> Description 统一使用简体中文；同步上游时保留中文展示，不直接写入英文原文。

### engineering

| Skill | Description | 已集成 |
|-------|-------------|--------|
| ask-matt | 询问当前情境适合使用哪个 skill 或流程，作为本仓库 skills 的路由器。 | ✅ |
| code-review | 从指定基准点（commit、branch、tag 或 merge-base）开始，按“规范”和“需求”两个维度审查变更：代码是否符合仓库规范，以及是否满足原始 issue 或 spec。两个审查由并行子 Agent 执行并列展示。适用于审查分支、PR、进行中的改动，或“审查从 X 开始的变更”。 | ❌ |
| codebase-design | 提供设计深模块的共享词汇。适用于设计或改进模块接口、寻找深化模块的机会、确定边界位置、提升代码可测试性或 AI 可导航性，以及其他 skill 需要引用深模块概念时。 | ❌ |
| diagnosing-bugs | 针对疑难 bug 和性能回归的诊断循环。适用于用户要求“诊断”或“调试”，或报告功能损坏、抛错、失败、变慢等问题。 | ✅ |
| domain-modeling | 构建并打磨项目的领域模型。适用于讨论代码库术语、编写或编辑 GLOSSARY.md，以及记录或编辑 ADR。 | ✅ |
| grill-with-docs | 通过持续追问打磨计划或设计，并在过程中同步产出 ADR、术语表等文档。 | ✅ |
| implement-spec | 将 `/to-spec` 和 `/to-tickets` 的产出实现为代码。 | ❌ |
| implement | 根据 spec 或一组 tickets 实现具体工作。 | ❌ |
| improve-codebase-architecture | 扫描代码库中可深化模块的机会，以可视化 HTML 报告展示，再针对选中的问题深入追问。 | ❌ |
| pr | 用于编写 Pull Request 正文。 | ❌ |
| prototype | 构建一次性原型来回答设计问题。适用于快速验证状态模型或逻辑是否合理，或探索 UI 应呈现的效果。 | ❌ |
| research | 基于高可信的一手资料调查问题，并将结论整理成仓库内的 Markdown 文件。适用于研究主题、收集文档或 API 事实，或把资料查阅工作委派给后台 Agent。 | ❌ |
| retro | 对一次编码会话进行复盘。 | ❌ |
| setup-matt-pocock-skills | 为工程类 skills 配置当前仓库，包括 issue tracker、分诊标签词汇和领域文档布局。在首次使用其他工程类 skills 前运行一次。 | ❌ |
| tdd | 测试驱动开发。适用于用户希望以测试优先的方式构建功能或修复 bug、提到“红—绿—重构”，或需要集成测试时。 | ❌ |
| to-spec | 将当前对话整理成 spec 并发布到项目 issue tracker；不再访谈，只综合已经讨论的内容。 | ❌ |
| to-tickets | 把计划、spec 或当前对话拆成一组纵向切片 tickets，每个 ticket 声明阻塞关系，并发布到已配置的 tracker；本地以文本记录依赖，真实 tracker 使用原生阻塞链接。 | ❌ |
| triage | 通过分诊角色状态机推进 issues 和外部 PR，完成分类、验证，必要时继续追问，并编写 Agent 可直接执行的任务简报。 | ❌ |
| wayfinder | 将超出单个 Agent 会话承载能力的大型工作规划为 issue tracker 上的决策 tickets 地图，逐项解决，直到形成通往目标的清晰路径。 | ❌ |
| wizard | 生成交互式 Bash 向导，引导用户完成只能由人工执行的步骤。适用于基础设施配置、凭据或 CI secrets 设置、陌生第三方控制台操作，以及一次性迁移或切换；Agent 能自行完成的步骤不要使用。 | ❌ |

### misc

| Skill | Description | 已集成 |
|-------|-------------|--------|
| git-guardrails-claude-code | 配置 Claude Code hooks，在危险 Git 命令（push、reset --hard、clean、branch -D 等）执行前进行阻止。适用于防止破坏性 Git 操作、添加 Git 安全 hooks，或在 Claude Code 中禁止 push/reset。 | ❌ |
| migrate-to-shoehorn | 将测试文件中的 `as` 类型断言迁移到 `@total-typescript/shoehorn`。适用于用户提到 shoehorn、希望替换测试中的 `as`，或需要构造部分测试数据时。 | ❌ |
| scaffold-exercises | 创建包含章节、题目、答案和讲解，并能通过 lint 的练习目录结构。适用于搭建练习框架、创建练习占位文件或设置新课程章节。 | ❌ |
| setup-pre-commit | 在当前仓库配置 Husky pre-commit hooks，并集成 lint-staged（Prettier）、类型检查和测试。适用于添加提交前 hooks、配置 Husky/lint-staged，或在提交时执行格式化、类型检查和测试。 | ❌ |

### productivity

| Skill | Description | 已集成 |
|-------|-------------|--------|
| grill-me | 通过持续追问打磨计划或设计。 | ✅ |
| grilling | 针对计划、决策或想法持续追问，帮助用户对其思路进行压力测试；用户使用任何 “grill” 触发短语时启用。 | ✅ |
| handoff | 将当前对话压缩成一份交接文档，供另一个 Agent 接手。 | ✅ |
| teach | 在当前工作区内向用户教授新的技能或概念。 | ❌ |
| to-questionnaire | 把当前无法完整回答的决策问题转成问卷，交由其他人填写。 | ❌ |
| wait-what | 停下来；上一条信息没有让用户理解，需要换一种方式重新说明。 | ✅ |
| writing-for-agents | 为 Agent 编写文档。适用于创建或编辑 skills，或修改 AGENTS.md、CLAUDE.md。 | ✅ |

### in-progress

> 开发中的 skill，尚未稳定。

| Skill | Description | 已集成 |
|-------|-------------|--------|
| claude-handoff | 把当前对话交接给一个新的后台 Agent，由其立即接手后续工作。 | ❌ |
| loop-me | 在当前工作区内，围绕用户想构建的工作流 spec 持续追问。 | ❌ |
| setup-ts-deep-modules | 将 dependency-cruiser 接入 TypeScript 仓库，使每个 package 成为深模块：实现隐藏在子目录中，只能通过入口文件访问。由用户主动调用。 | ❌ |
| writing-beats | 写作的收敛阶段：把原始素材组织成一段由节拍推进的旅程，并在后续内容依赖某个术语前先将其解释清楚。 | ❌ |
| writing-fragments | 写作的探索阶段：挖掘原始片段，暂不建立结构。 | ❌ |
| writing-shape | 写作的收敛阶段：逐段把原始素材塑造成文章。 | ❌ |
