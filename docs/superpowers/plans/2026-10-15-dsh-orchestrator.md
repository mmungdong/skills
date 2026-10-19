# DSH Orchestrator Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task by task. User authorized creation in this checkout and Codex symlink installation; do not commit or push.

**Goal:** Deliver a self-contained, host-independent skill for a supervisor model to direct local DSH implementation and personally perform review and acceptance.

**Architecture:** The skill owns supervisor decisions. A standard-library Python bridge validates detailed dispatches, executes one DSH turn, filters native events, persists session state, and records a separate supervisor verdict. It never implements or automatically retries work.

**Tech Stack:** Python 3.9+, macOS/Linux, unittest, local `dsh` from PATH, Markdown, JSON.

**Spec:** Design approved in the 2026-10-15 conversation, amended by the user: Codex/the supervisor performs checks; DSH receives detailed instructions to avoid slow exploration.

## Global Constraints

- Create `skills/dev/dsh-orchestrator/` with `SKILL.md` and `skill.json`.
- Keep the workflow model-independent; Codex is the current supervisor.
- Supervisor performs review, testing, and acceptance; DSH implements explicit steps.
- Require scope, ordered steps, concrete paths, deliverables, acceptance criteria, and constraints before dispatch.
- Preserve existing changes in README files and other skills; no commits or pushes.
- DSH and Python are external prerequisites, not installed by the skill.
- Symlink the skill into the configured Codex skills directory using an absolute target.

## Review Focus

- Exit code zero and a worker report must never automatically accept a task.
- Timeout, interruption, and lost handles must not cause duplicate writing processes.
- Prompt text and diagnostics may contain shell syntax or sensitive material.
- Report repair and session resume must preserve work and workspace identity.
- A copied or symlinked skill must work without the source repository.

## Task 1: Bridge and observable contracts

- [x] Write CLI integration tests with a controlled external DSH executable; run them and observe missing-feature failures.
- [x] Implement `scripts/dsh_bridge.py` and `scripts/protocol.py` using only the standard library.
- [x] Validate dispatches before launching, stream compact status, reject malformed reports, handle process-group timeout/interruption, preserve state and require explicit resume.
- [x] Record supervisor review separately; require evidence for every criterion before acceptance.
- [x] Run the complete skill test suite.

## Task 2: Agent instructions and packaging

- [x] Run a no-skill behavioral baseline before writing instructions.
- [x] Write concise `SKILL.md`, detailed dispatch/recovery guidance, a concrete task example, metadata, and Codex UI metadata.
- [x] Verify the instructions with an independent agent; supervisor retains the actual acceptance decision.
- [x] Add one catalog entry to each existing README without altering other work.

## Task 3: Real execution and installation

- [x] Run real DSH implementation in a temporary workspace; supervisor checks the artifact and records its own verdict.
- [x] Exercise an additional turn through the persisted session.
- [x] Validate the copied skill, frontmatter, metadata, links, and final diff.
- [x] Create and resolve the absolute Codex symlink; report usage and verification.

## Progress

- Planning: approved conversation supplies the spec; working in the user-requested checkout and preserving its dirty baseline.

## Verification record

- Behavioral baseline honored supervisor-owned checking; no additional pressure-specific rules were needed.
- Bridge tests were observed failing before implementation; regression failures were reproduced before fixes.
- Final suite: 23 tests passed in the source directory and in a standalone copied skill.
- Real DSH: two successive implementation turns reused one persisted session; supervisor separately inspected and accepted both, covering 16 input cases.
- Independent review found the normalized workspace-root scope issue; its regression test now passes.
- Additional verified recovery covers orphan workers, PID reuse, and large ignored tool events.
- Codex symlink resolves to this checkout; the linked bridge and frontmatter validator run successfully.
- No commits, pushes, publication, or unrelated-file changes were performed.
