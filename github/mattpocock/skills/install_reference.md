# MattPocock Skills

- **来源**: https://github.com/mattpocock/skills
- **类型**: git

## 安装

```bash
git clone https://github.com/mattpocock/skills.git ~/.claude/skills/mattpocock-skills
```

## Skills 列表

### engineering

| Skill | Description | 已集成 |
|-------|-------------|--------|
| ask-matt | Ask which skill or flow fits your situation. A router over the skills in this repo | ✅ |
| code-review | Review changes since a fixed point along two axes — Standards and Spec. Runs both reviews in parallel sub-agents and reports them side by side | ❌ |
| codebase-design | Shared vocabulary for designing deep modules. Use when designing or improving a module's interface, finding deepening opportunities, or deciding where a seam goes | ❌ |
| diagnosing-bugs | Diagnosis loop for hard bugs and performance regressions. Use when the user says "diagnose"/"debug this", or reports something broken/throwing/failing/slow | ❌ |
| domain-modeling | Build and sharpen a project's domain model. Use when pinning down domain terminology, recording an architectural decision, or maintaining the domain model | ❌ |
| grill-with-docs | A relentless interview to sharpen a plan or design, which also creates docs (ADR's and glossary) as we go | ✅ |
| implement | Implement a piece of work based on a PRD or set of issues | ❌ |
| improve-codebase-architecture | Scan a codebase for deepening opportunities, present them as a visual HTML report, then grill through whichever one you pick | ❌ |
| prototype | Build a throwaway prototype to answer a design question. Use to sanity-check whether a state model or logic feels right, or explore what a UI should look like | ❌ |
| research | Investigate a question against high-trust primary sources and capture the findings as a Markdown file in the repo | ❌ |
| resolving-merge-conflicts | Use when you need to resolve an in-progress git merge/rebase conflict | ❌ |
| setup-matt-pocock-skills | Configure this repo for the engineering skills — issue tracker, triage label vocabulary, and domain doc layout. Run once before first use of the other engineering skills | ❌ |
| tdd | Test-driven development. Use when building features or fixing bugs test-first, mentions "red-green-refactor", or wants integration tests | ❌ |
| to-issues | Break a plan, spec, or PRD into independently-grabbable issues on the project issue tracker using tracer-bullet vertical slices | ✅ |
| to-prd | Turn the current conversation into a PRD and publish it to the project issue tracker — no interview, just synthesis of what you've already discussed | ✅ |
| triage | Move issues and external PRs through a state machine of triage roles — categorise, verify, grill if needed, and write agent-ready briefs | ❌ |

### misc

| Skill | Description | 已集成 |
|-------|-------------|--------|
| git-guardrails-claude-code | Set up Claude Code hooks to block dangerous git commands (push, reset --hard, clean, branch -D, etc.) before they execute | ❌ |
| migrate-to-shoehorn | Migrate test files from `as` type assertions to @total-typescript/shoehorn | ❌ |
| scaffold-exercises | Create exercise directory structures with sections, problems, solutions, and explainers that pass linting | ❌ |
| setup-pre-commit | Set up Husky pre-commit hooks with lint-staged (Prettier), type checking, and tests in the current repo | ❌ |

### personal

| Skill | Description | 已集成 |
|-------|-------------|--------|
| edit-article | Edit and improve articles by restructuring sections, improving clarity, and tightening prose | ❌ |
| obsidian-vault | Search, create, and manage notes in the Obsidian vault with wikilinks and index notes | ❌ |

### productivity

| Skill | Description | 已集成 |
|-------|-------------|--------|
| grill-me | A relentless interview to sharpen a plan or design | ❌ |
| grilling | Grill the user relentlessly about a plan or design. Use to stress-test a plan before building, or on any 'grill' trigger phrases | ❌ |
| handoff | Compact the current conversation into a handoff document for another agent to pick up | ❌ |
| teach | Teach the user a new skill or concept, within the workspace | ❌ |
| writing-great-skills | Reference for writing and editing skills well — the vocabulary and principles that make a skill predictable | ❌ |

### deprecated

> 已废弃的 skill，不建议集成。

| Skill | Description | 已集成 |
|-------|-------------|--------|
| design-an-interface | Generate multiple radically different interface designs for a module using parallel sub-agents | ❌ |
| qa | Interactive QA session where user reports bugs or issues conversationally, and the agent files GitHub issues | ❌ |
| request-refactor-plan | Create a detailed refactor plan with tiny commits via user interview, then file it as a GitHub issue | ❌ |
| ubiquitous-language | Extract a DDD-style ubiquitous language glossary from the current conversation, flagging ambiguities and proposing canonical terms | ❌ |

### in-progress

> 开发中的 skill，尚未稳定。

| Skill | Description | 已集成 |
|-------|-------------|--------|
| claude-handoff | Hand the current conversation off to a fresh background agent that picks up the work immediately | ❌ |
| loop-me | Grill me about specs for the workflows I want to build, within this workspace | ❌ |
| wayfinder | Plan a huge chunk of work as a shared map of investigation tickets on your issue tracker, and resolve them one at a time | ❌ |
| wizard | Generate an interactive bash wizard that walks a human through a manual procedure — third-party setup, a one-off migration, an A→B state transition | ❌ |
| writing-beats | Writing, exploit — assemble raw material into a journey of beats, grounding each term before a beat leans on it | ❌ |
| writing-fragments | Writing, explore — mine raw fragments, no structure yet | ❌ |
| writing-shape | Writing, exploit — shape raw material into an article, paragraph by paragraph | ❌ |
