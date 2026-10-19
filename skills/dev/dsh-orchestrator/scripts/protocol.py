"""Dispatch, worker report, and supervisor review contracts."""

import json
import math
from pathlib import Path, PurePosixPath


class ContractError(ValueError):
    pass


def nonempty(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ContractError(field + " must be a non-empty string")


def strings(value, field, allow_empty=False):
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ContractError(field + " must be a list" + ("" if allow_empty else " with entries"))
    for item in value:
        nonempty(item, field + " entry")


def relative_path(value):
    nonempty(value, "path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or path == PurePosixPath("."):
        raise ContractError("paths must be explicit workspace-relative paths without traversal")
    if any(char in value for char in "*?[]"):
        raise ContractError("paths must name files or directories, not globs")
    return path


def covered(path, scope):
    return any(path == root or root in path.parents for root in scope)


def validate_task(task):
    if not isinstance(task, dict):
        raise ContractError("task must be an object")
    for field in ("task_id", "objective", "workdir"):
        nonempty(task.get(field), field)
    workdir = Path(task["workdir"])
    if not workdir.is_absolute() or not workdir.is_dir():
        raise ContractError("workdir must be an existing absolute directory")
    for field in ("scope", "deliverables", "constraints"):
        strings(task.get(field), field)
    roots = [relative_path(item) for item in task["scope"]]
    for root in roots:
        if not (workdir / str(root)).resolve().is_relative_to(workdir.resolve()):
            raise ContractError("scope resolves outside workdir")
    for group in ("steps", "acceptance"):
        values = task.get(group)
        if not isinstance(values, list) or not values:
            raise ContractError(group + " must contain detailed entries")
        ids = set()
        for item in values:
            if not isinstance(item, dict):
                raise ContractError(group + " entry must be an object")
            nonempty(item.get("id"), group + ".id")
            if item["id"] in ids:
                raise ContractError(group + " IDs must be unique")
            ids.add(item["id"])
            nonempty(item.get("action" if group == "steps" else "check"), group + ".detail")
            if group == "steps":
                strings(item.get("paths"), "steps.paths")
                for value in item["paths"]:
                    path = relative_path(value)
                    if not covered(path, roots) or not (workdir / value).resolve().is_relative_to(workdir.resolve()):
                        raise ContractError("steps.paths must stay within scope and workdir")
    return task


def build_prompt(task):
    return """You are the DSH implementation worker. The supervisor owns decisions, all checking,
testing, code review and acceptance. Execute the ordered steps below directly.
Read the named files and applicable AGENTS.md first; preserve unrelated edits.
Use only the declared scope. Follow higher-priority host/project requirements;
if they conflict with this dispatch, report the conflict instead of silently
expanding the work. Do not run tests, linters, builds or a review on your own;
the supervisor will run them. If local rules require a check, report the need.
Only perform commits, pushes, publishing or dependency installation when the
dispatch constraints explicitly carry the user's authorization. Do not delegate
to another DSH.
Keep investigation limited to the named inputs and their necessary dependencies.
Report a concrete blocker or missing decision promptly instead of repeatedly
replanning. Do not ask the human directly; return needs_decision to the supervisor.
For long work, emit a brief milestone line like:
DSH_PROGRESS {"step_id":"S1","status":"completed"}
Keep credentials, tokens, private endpoints and raw tool outputs out of reports.
Finish with a single JSON object, without prose, using exactly these fields:
{"task_id":"TASK_ID","status":"completed|blocked|needs_decision",
 "summary":"what actually changed","artifacts":["workspace-relative paths"],
 "completed_steps":["S1"],"blockers":[],"decision_required":[]}
Completed means implementation is ready for supervisor inspection, not accepted.
Mark only steps actually completed; do not claim checks passed.

DISPATCH (JSON data):
""" + json.dumps(task, ensure_ascii=False, indent=2)


def parse_report(text, task):
    if not isinstance(text, str) or len(text) > 131072:
        raise ContractError("worker final report is missing or too large")
    text = "\n".join(line for line in text.strip().splitlines() if not line.startswith("DSH_PROGRESS ")).strip()
    if text.startswith("```json\n") and text.endswith("\n```"):
        text = text[8:-4]
    try:
        report = json.loads(text)
    except (ValueError, TypeError):
        raise ContractError("worker final report must be one JSON object") from None
    if not isinstance(report, dict) or report.get("task_id") != task["task_id"]:
        raise ContractError("worker report task_id does not match dispatch")
    if report.get("status") not in ("completed", "blocked", "needs_decision"):
        raise ContractError("worker report status is invalid")
    nonempty(report.get("summary"), "report.summary")
    if len(report["summary"]) > 4000:
        raise ContractError("report.summary must be concise")
    for field in ("artifacts", "completed_steps", "blockers", "decision_required"):
        strings(report.get(field), "report." + field, allow_empty=True)
    roots = [relative_path(item) for item in task["scope"]]
    for artifact in report["artifacts"]:
        if not covered(relative_path(artifact), roots):
            raise ContractError("report.artifacts must stay within scope")
    expected = {step["id"] for step in task["steps"]}
    completed = set(report["completed_steps"])
    if not completed <= expected:
        raise ContractError("report.completed_steps contains unknown IDs")
    if report["status"] == "completed" and (completed != expected or report["blockers"] or report["decision_required"]):
        raise ContractError("completed report must account for every step without unresolved blockers")
    if report["status"] == "blocked" and not report["blockers"]:
        raise ContractError("blocked report requires a concrete blocker")
    if report["status"] == "needs_decision" and not report["decision_required"]:
        raise ContractError("needs_decision report requires a concrete question")
    return {key: report[key] for key in ("task_id", "status", "summary", "artifacts", "completed_steps", "blockers", "decision_required")}


def validate_review(review, task):
    if not isinstance(review, dict) or review.get("task_id") != task["task_id"]:
        raise ContractError("review.task_id must match current dispatch")
    if review.get("verdict") not in ("accepted", "changes_requested", "blocked"):
        raise ContractError("review.verdict must be accepted, changes_requested or blocked")
    strings(review.get("findings"), "review.findings", allow_empty=True)
    criteria = review.get("criteria")
    if not isinstance(criteria, list):
        raise ContractError("review.criteria must be a list")
    expected = {item["id"] for item in task["acceptance"]}
    seen = set()
    for item in criteria:
        if not isinstance(item, dict) or item.get("id") not in expected or item["id"] in seen:
            raise ContractError("review.criteria must contain unique known acceptance IDs")
        if not isinstance(item.get("passed"), bool):
            raise ContractError("review.criteria.passed must be boolean")
        nonempty(item.get("evidence"), "review.criteria.evidence")
        seen.add(item["id"])
    if review["verdict"] == "accepted" and (seen != expected or not all(item["passed"] for item in criteria) or review["findings"]):
        raise ContractError("accepted requires positive supervisor evidence for every criterion and no unresolved findings")
    if review["verdict"] != "accepted" and not review["findings"]:
        raise ContractError("non-accepted review requires concrete findings or reconciliation notes")
    return review


DEFAULT_CHECK_TIMEOUT = 300


def validate_checks(config, task_id):
    """Validate the whole supervisor-owned check batch before any command starts."""
    if not isinstance(config, dict):
        raise ContractError("checks file must be an object")
    if config.get("task_id") != task_id:
        raise ContractError("checks.task_id must match current dispatch")
    checks = config.get("checks")
    if not isinstance(checks, list) or not checks:
        raise ContractError("checks must be a non-empty list")
    seen = set()
    validated = []
    for item in checks:
        if not isinstance(item, dict):
            raise ContractError("checks entry must be an object")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ContractError("checks.id must be a non-empty string")
        if identifier in seen:
            raise ContractError("checks IDs must be unique")
        seen.add(identifier)
        argv = item.get("argv")
        if not isinstance(argv, list) or not argv:
            raise ContractError("checks.argv must be a non-empty list")
        for value in argv:
            if not isinstance(value, str) or not value:
                raise ContractError("checks.argv entries must be non-empty strings")
        timeout = item.get("timeout", DEFAULT_CHECK_TIMEOUT)
        if type(timeout) is bool or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ContractError("checks.timeout must be a positive finite number")
        validated.append({"id": identifier, "argv": list(argv), "timeout": float(timeout)})
    return validated
