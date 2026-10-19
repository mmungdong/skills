# Dispatch and review protocol

## Prepare a concrete assignment

Read the actual project before constructing a dispatch. Fill the example with observed facts; its illustrative project path is not executable as supplied.

| Required field | Content |
| --- | --- |
| `task_id` | Stable identifier for this assignment; use a new ID for a new stage |
| `objective` | One observable implementation outcome |
| `workdir` | Existing absolute project directory |
| `scope` | Explicit workspace-relative files or directories DSH may change; no globs, traversal, or workspace root |
| `steps` | Ordered objects with unique `id`, precise `action`, and affected `paths` within scope |
| `deliverables` | Concrete files/results to return, including required report contents |
| `acceptance` | Unique criterion `id` and exact `check` for the supervisor to perform |
| `constraints` | Existing-change preservation, decisions already made, permissions and exclusions |

Optional `context` supplies relevant existing interfaces, facts, prior failures, or short snippets. Reference large existing documents by path and section. Do not paste credentials or full conversation histories.

Every implementation step must name what changes, where it changes, and the required behavior. Include edge cases, compatibility requirements, existing utilities to reuse, and an exact before/after example when they affect correctness. The supervisor resolves design choices before dispatch. If discovery is necessary, scope one specific read-only investigation and require the missing fact as its deliverable; then give explicit implementation instructions.

Examples of insufficient actions: “fix the bugs,” “improve the UI,” “follow the plan,” and “do the rest.” Replace these with file-specific changes and the evidence the supervisor will inspect. The validator checks fields and scope, not the semantic quality of the instructions.

DSH may read necessary dependencies and project instructions; `scope` controls intended modifications. The bridge is orchestration, not a filesystem sandbox. Inspect the real diff to detect scope drift.

## Starting a run

1. Confirm `dsh headless --help` supports `--json` and `--session-id`; do not guess a `run` or desktop-control command. Respect the configured headless model and tools; do not modify DSH credentials or configuration.
2. Confirm required capabilities in that profile. If uncertain, send a bounded read-only discovery task before dependent implementation. A capability claim still needs evidence from the actual task.
3. Choose a private run directory, such as `$HOME/.local/state/dsh-orchestrator/<goal-id>/`. Keep runtime files outside both the project and the installed skill. Record the overall goal, acceptance criteria, initial changes, decisions, and next action in `supervisor-notes.md` there.
4. Write one detailed task JSON and invoke `run`; it validates the dispatch before launching, so the normal loop needs no separate `validate` or `status` call. The default per-turn deadline is 900 seconds; select a larger explicit deadline for justified work. Host tool calls may yield earlier while the same process continues.
5. Preserve the bridge's state path and the host's running-process handle. Wait on the existing handle in bounded intervals and keep the user informed; avoid repeated `status` polling. Never start another turn simply because a tool call yielded.

The bridge uses argument arrays and stdin, not shell interpolation. State writes are atomic with private file permissions. Per-state and per-workspace advisory locks prevent concurrent bridge writers. Workspace ownership records under `$HOME/.cache/dsh-orchestrator/locks/` also identify a worker left after its bridge exits unexpectedly, including when another state path is supplied. They do not protect against unrelated DSH invocations or desktop sessions.

## Progress and worker report

Native `session` events supply the persisted session ID. Native `status` events indicate engine activity, including `step_end` usage. A worker can emit `DSH_PROGRESS {"step_id":"S1","status":"completed"}` at useful milestones; status can be `started`, `completed`, or `blocked`. These are worker claims, not acceptance evidence.

By default `run` prints only one bounded final result and writes sanitized `session`/`status`/milestone records to a private per-turn progress JSONL (see its `progress_log` path). Every run creates a new unique private progress file, so earlier turns' logs preserved in history stay readable. `--verbose` additionally forwards those sanitized events on stdout. The bridge drops internal reasoning, raw tool results, arbitrary text, and raw stderr. A diagnostic byte count indicates whether stderr existed. It does not archive the raw event stream or guarantee removal of secrets a worker puts in an otherwise valid report. Keep sensitive content out of tasks, reports and supervisor evidence.

The compact result and default `status` bound the summary and artifact/blocker/decision lists, clip oversized individual entries, and add a truncation marker; the complete report, task and history remain on disk. Use `status --full` only when the compact current-turn view is insufficient.

Usage telemetry is normalized from native `step_end` events per unique turn+step: duplicate `step_end` events are counted once, `turn_end` usage is ignored, nonnegative integer counters are summed per turn, and missing/invalid counters stay unavailable/null. Coverage counts observed unique steps and each valid counter per step (a step that reported no usage still counts), so incomplete turns are flagged partial rather than looking complete; no total, model rate, cost or supervisor-host usage is fabricated.

The final report is one JSON object:

```json
{
  "task_id": "greeting-implementation-1",
  "status": "completed",
  "summary": "Implemented name validation, trimming and greeting punctuation",
  "artifacts": ["greeting.py"],
  "completed_steps": ["S1"],
  "blockers": [],
  "decision_required": []
}
```

`completed` accounts for every dispatched step with no unresolved blocker. `blocked` requires a concrete blocker. `needs_decision` requires a specific question for the supervisor. DSH reports implementation facts; tests and acceptance belong to the supervisor.

The bridge parses the native `final.text`; a single JSON code fence is tolerated. It validates task identity, status, step IDs and artifact scope. A valid report yields `awaiting_review`, including when the worker reports a blocker or question.

## Supervisor batch checks

`check --state STATE --checks-file JSON` runs explicit supervisor-owned commands from the task workdir, sequentially and without a shell. The checks file is:

```json
{
  "task_id": "greeting-implementation-1",
  "checks": [
    {"id": "unit", "argv": ["python3", "-m", "unittest", "test_greeting"], "timeout": 300}
  ]
}
```

Each `argv` is a string array; `id`s must be unique and `timeout` (optional, default 300 seconds) must be a positive finite number. The bridge re-reads and validates the saved state, task identity and the whole checks file under the acquired state lock before starting any command. Complete combined stdout/stderr is kept in collision-free private per-check logs with the exact argv, exit code, status and duration; stdout stays compact and failed entries carry a bounded tail plus the log path. A failing, timed-out or unstartable command does not stop later checks. The bridge takes the workspace/state locks, refuses active or orphan workers, and records process ownership for running commands.

SIGINT/SIGTERM during a batch stop the current command's process group, record that command as `interrupted`, start no later checks, and return `130`; completed commands have leftover descendants in their process group cleaned up too.

Exit codes: `0` all passed, `1` any command failed, `2` invalid input or locking refusal, `130` interrupted. `check` never accepts a task file and never records acceptance; that remains the supervisor's `review`.

## Supervisor checks and verdict

Inspect actual files, scope changes and outcomes. Run relevant tests, type checks, builds or other verification directly through your own tools. Check each acceptance criterion. Avoid a separate DSH “review your work” task. When tests must be written first, task DSH with creating test source, run the red check yourself, then task it with implementation and run green yourself.

Create `review.json` using actual supervisor evidence:

```json
{
  "task_id": "greeting-implementation-1",
  "verdict": "accepted",
  "criteria": [
    {"id": "AC1", "passed": true, "evidence": "Actual diff inspection: describe the observed changes"},
    {"id": "AC2", "passed": true, "evidence": "Actual command, exit code and observed result or evidence path"}
  ],
  "findings": []
}
```

The strings above illustrate the shape, not evidence to copy. `review` records the supervisor's supplied judgment; it cannot prove that an evidence string is truthful or authenticate the calling model. Only the supervisor should invoke it, and its path should not be given to DSH.

`accepted` requires all acceptance IDs exactly once, positive results, non-empty evidence, and no unresolved findings. `changes_requested` or `blocked` requires concrete findings; criteria may include only the checks already performed. For an interrupted turn, findings must record inspection of partial effects and what remains safe to do.

Only an explicitly recorded supervisor verdict enables `--resume`. Use the same state path and workspace; provide the next detailed task. The state retains previous reports and reviews. A new stage can have a new task ID. Keep a correction focused on the observed failure, expected behavior, and affected paths.

The overall goal is complete only after every stage and overall criterion has evidence. Update `supervisor-notes.md`; accepting one assignment does not certify the entire goal.

## Failure and recovery

| State | Meaning and next action |
| --- | --- |
| `running` | A bridge turn was started; use the host handle and inspect `status` |
| `awaiting_review` | Valid worker report; supervisor must inspect and decide |
| `report_invalid` | Missing/malformed report; inspect artifacts first, then request report-only repair if needed |
| `failed` | Nonzero worker exit or transport failure; inspect partial effects before retry |
| `timed_out` / `interrupted` | Bridge stopped its worker process group; inspect remaining effects before review/resume |
| `accepted` | Supervisor accepted this assignment |
| `changes_requested` / `blocked` | Supervisor recorded the next correction or blocking condition |

Exit codes: `0` means the bridge operation succeeded, `1` means worker/report failure or a failed check command, `2` means input/locking/recovery refusal, `124` means deadline reached, and `130` means interrupted. `run` returning `0` never means the task was accepted.

To cancel, use the host's interrupt operation or signal the recorded bridge PID after verifying its identity. SIGINT/SIGTERM stops the worker process group and records `interrupted`. A changed user instruction that affects active writing requires stopping the old turn, inspecting partial changes, and issuing a revised task. DSH is not presumed to receive mid-turn input through the headless interface.

If the host handle is lost, inspect saved state and processes with `status --full`. It includes workspace ownership and its file path. `worker_pid_exists` means a PID exists, not proof that it still identifies the original worker. The bridge compares the recorded start time with the system `ps` result to avoid confusing a reused PID with its old worker; when identity is unavailable it conservatively treats an existing PID as active. An active worker or held workspace lock blocks review/resume; verify process identity before stopping anything. Do not delete lock files to bypass a held advisory lock. A bridge killed with SIGKILL may leave its worker alive; reconcile that worker before continuing. Processes that escape the worker process group need explicit inspection.

After confirming no old writer remains, inspect artifacts and external effects, record `changes_requested` with reconciliation findings, and resume only unfinished actions. Do not automatically repeat a task that may already have had side effects. If a session ID was never obtained or is no longer available in the current DSH context, start a new state/session only after reconciliation and supply a concise handoff of verified work.

For malformed reports, acceptance can use independently verified artifacts if all criteria pass; otherwise send a report-only or focused correction turn after recording the supervisor's findings. Do not redo implementation solely to recover reporting format.

At three attempts with the same unresolved failure, diagnose and revise the plan before dispatching again. Ask the user only when missing information or authorization prevents progress. Preserve an accurate checkpoint instead of claiming completion.
