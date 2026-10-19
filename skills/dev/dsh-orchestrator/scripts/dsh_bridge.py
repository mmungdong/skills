#!/usr/bin/env python3
"""Run one DSH implementation turn; acceptance remains with the supervisor."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from protocol import ContractError, build_prompt, parse_report, validate_checks, validate_review, validate_task


SUMMARY_LIMIT = 1000
LIST_LIMIT = 20
ENTRY_LIMIT = 500
TAIL_LIMIT = 4000

USAGE_FIELDS = {
    "inputTokens": "input_tokens",
    "outputTokens": "output_tokens",
    "cacheReadTokens": "cache_read_tokens",
    "cacheWriteTokens": "cache_write_tokens",
    "totalTokens": "total_tokens",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def emit(value):
    print(json.dumps(value, ensure_ascii=False), flush=True)


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ContractError("cannot read JSON input; check the supplied file") from None


def save_state(path, state):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=".state-", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(state, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(path):
    import fcntl
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ContractError("another bridge holds this state or workspace lock; observe it instead of starting another writer") from None
        yield
    finally:
        os.close(descriptor)


def workspace_lock(workdir):
    digest = hashlib.sha256(str(Path(workdir).resolve()).encode()).hexdigest()
    return Path.home() / ".cache" / "dsh-orchestrator" / "locks" / (digest + ".lock")


def alive(pid):
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def process_identity(pid):
    try:
        result = subprocess.run(["ps", "-p", str(pid), "-o", "lstart="], capture_output=True, text=True, timeout=3, env={**os.environ, "LC_ALL": "C"})
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def worker_active(record):
    if not isinstance(record, dict) or not alive(record.get("worker_pid")):
        return False
    recorded = record.get("worker_identity")
    current = process_identity(record["worker_pid"])
    return not recorded or not current or recorded == current


def check_workspace_owner(owner_path):
    if owner_path.exists() and worker_active(read_json(owner_path)):
        raise ContractError("an earlier workspace worker may still be active; inspect the workspace owner state before starting or reviewing work")


def stop_worker(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def interrupted(signum, frame):
    raise KeyboardInterrupt


def log_progress(stream, record):
    if stream is None:
        return
    try:
        stream.write(json.dumps(record, ensure_ascii=False) + "\n")
        stream.flush()
    except (OSError, ValueError):
        pass


def normalize_counter(value):
    if type(value) is int and value >= 0:
        return value
    return None


def record_usage(collector, event):
    if event.get("phase") != "step_end":
        return
    turn = event.get("turn")
    step = event.get("step")
    if type(turn) is not int or type(step) is not int:
        return
    key = (turn, step)
    if key in collector["steps"]:
        return
    raw = event.get("usage")
    entry = {"turn": turn, "step": step}
    for camel, snake in USAGE_FIELDS.items():
        entry[snake] = normalize_counter(raw.get(camel)) if isinstance(raw, dict) else None
    collector["steps"][key] = entry


def finalize_usage(collector, run_started, turn_started):
    finished = time.monotonic()
    steps = list(collector["steps"].values())
    turns = {}
    for entry in steps:
        turn = entry["turn"]
        aggregate = turns.get(turn)
        if aggregate is None:
            aggregate = {"turn": turn, "elapsed_seconds": None}
            for field in USAGE_FIELDS.values():
                aggregate[field] = None
            turns[turn] = aggregate
        for field in USAGE_FIELDS.values():
            value = entry.get(field)
            if value is not None:
                aggregate[field] = (aggregate[field] or 0) + value
    turn_list = []
    for turn in sorted(turns):
        entry = turns[turn]
        entry["elapsed_seconds"] = max(0.0, round(finished - turn_started.get(turn, run_started), 3))
        turn_list.append(entry)
    usage = {"turns": turn_list, "elapsed_seconds": max(0.0, round(finished - run_started, 3))}
    total_steps = len(steps)
    coverage = {}
    for field in USAGE_FIELDS.values():
        available = [entry[field] for entry in steps if entry.get(field) is not None]
        usage[field] = sum(available) if available else None
        coverage[field] = len(available)
    usage["coverage"] = {"turns": len(turn_list), "steps": total_steps, "counters": coverage}
    usage["partial"] = any(coverage[field] < total_steps for field in USAGE_FIELDS.values())
    return usage


def truncate_text(value, limit):
    if not isinstance(value, str):
        return "", False
    if len(value) <= limit:
        return value, False
    return value[:limit] + " ... [truncated; full report saved in state]", True


def truncate_list(values, limit, entry_limit=ENTRY_LIMIT):
    if not isinstance(values, list):
        return [], False
    clipped = len(values) > limit
    result = []
    for value in values[:limit]:
        if isinstance(value, str) and len(value) > entry_limit:
            result.append(value[:entry_limit] + " ... [truncated; full entry saved in state]")
            clipped = True
        else:
            result.append(value)
    return result, clipped


def compact_report(state):
    report = state.get("report") if isinstance(state.get("report"), dict) else {}
    summary, summary_cut = truncate_text(report.get("summary", ""), SUMMARY_LIMIT)
    artifacts, artifacts_cut = truncate_list(report.get("artifacts"), LIST_LIMIT)
    blockers, blockers_cut = truncate_list(report.get("blockers"), LIST_LIMIT)
    decisions, decisions_cut = truncate_list(report.get("decision_required"), LIST_LIMIT)
    return {
        "summary": summary,
        "artifacts": artifacts,
        "blockers": blockers,
        "decision_required": decisions,
        "truncated": summary_cut or artifacts_cut or blockers_cut or decisions_cut,
    }


def compact_usage(usage):
    if not isinstance(usage, dict):
        usage = {}
    compact = {field: usage.get(field) for field in USAGE_FIELDS.values()}
    compact["elapsed_seconds"] = usage.get("elapsed_seconds")
    compact["coverage"] = usage.get("coverage")
    compact["partial"] = usage.get("partial")
    return compact


def result_event(state, path):
    return {
        "type": "result",
        "status": state.get("status"),
        "state": str(path),
        "session_id": state.get("session_id"),
        "task_id": (state.get("task") or {}).get("task_id"),
        "progress_log": state.get("progress_log"),
        "usage": compact_usage(state.get("usage")),
        **compact_report(state),
    }


def compact_status(state, diagnostics):
    return {
        "version": state.get("version"),
        "status": state.get("status"),
        "task_id": (state.get("task") or {}).get("task_id"),
        "session_id": state.get("session_id"),
        "started_at": state.get("started_at"),
        "finished_at": state.get("finished_at"),
        "worker_exit_code": state.get("worker_exit_code"),
        "error": state.get("error"),
        "last_progress": state.get("last_progress"),
        "progress_log": state.get("progress_log"),
        "usage": compact_usage(state.get("usage")),
        **compact_report(state),
        **diagnostics,
    }


def consume_line(line, state, final, progress_stream, usage, turn_started, verbose):
    try:
        event = json.loads(line)
    except ValueError:
        return
    if not isinstance(event, dict):
        return
    kind = event.get("type")
    if kind == "session":
        session_id = event.get("sessionId")
        if isinstance(session_id, str) and re.fullmatch(r"[A-Za-z0-9._:-]{1,200}", session_id):
            if state["session_id"] and state["session_id"] != session_id:
                raise ContractError("DSH returned a different session than requested")
            state["session_id"] = session_id
            record = {"type": "session", "session_id": session_id}
            log_progress(progress_stream, record)
            if verbose:
                emit(record)
    elif kind == "status":
        phase = event.get("phase")
        if isinstance(phase, str) and re.fullmatch(r"[a-z_]{1,40}", phase):
            turn = event.get("turn")
            if type(turn) is int:
                turn_started.setdefault(turn, time.monotonic())
            record_usage(usage, event)
            progress = {"type": "progress", "phase": phase}
            for key in ("turn", "step"):
                if type(event.get(key)) is int:
                    progress[key] = event[key]
            state["last_progress"] = progress
            log_progress(progress_stream, progress)
            if verbose:
                emit(progress)
    elif kind == "text" and isinstance(event.get("text"), str):
        for progress_line in event["text"].splitlines():
            if not progress_line.startswith("DSH_PROGRESS "):
                continue
            try:
                item = json.loads(progress_line[len("DSH_PROGRESS "):])
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("step_id") in {step["id"] for step in state["task"]["steps"]} and item.get("status") in ("started", "completed", "blocked"):
                state["milestone"] = {"step_id": item["step_id"], "status": item["status"]}
                record = {"type": "milestone", **state["milestone"]}
                log_progress(progress_stream, record)
                if verbose:
                    emit(record)
    elif kind == "final":
        final["text"] = event.get("text")


def observe(process, state, state_path, timeout, progress_stream, usage, turn_started, verbose):
    final = {}
    buffers = {}
    discard_line = False
    deadline = time.monotonic() + timeout
    with selectors.DefaultSelector() as selector:
        for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
            buffers[name] = b""
        while selector.get_map():
            if time.monotonic() >= deadline:
                raise TimeoutError
            for key, _ in selector.select(timeout=min(0.2, max(0, deadline - time.monotonic()))):
                chunk = os.read(key.fileobj.fileno(), 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    if key.data == "stdout" and buffers["stdout"]:
                        consume_line(buffers["stdout"].decode("utf-8", "replace"), state, final, progress_stream, usage, turn_started, verbose)
                    continue
                if key.data == "stderr":
                    state["diagnostic_bytes"] += len(chunk)
                    continue
                if discard_line:
                    if b"\n" not in chunk:
                        continue
                    chunk = chunk.split(b"\n", 1)[1]
                    discard_line = False
                buffers["stdout"] += chunk
                while b"\n" in buffers["stdout"]:
                    line, buffers["stdout"] = buffers["stdout"].split(b"\n", 1)
                    if len(line) <= 262144:
                        consume_line(line.decode("utf-8", "replace"), state, final, progress_stream, usage, turn_started, verbose)
                        save_state(state_path, state)
                if len(buffers["stdout"]) > 262144:
                    buffers["stdout"] = b""
                    discard_line = True
        remaining = max(0.01, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            raise TimeoutError from None
    return final.get("text")


def run(args):
    task = validate_task(read_json(args.task_file))
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ContractError("timeout must be a positive finite number")
    binary = shutil.which("dsh")
    if binary is None:
        raise ContractError("dsh is not on PATH; install/configure DSH separately")
    path = Path(args.state).expanduser().resolve()
    owner_path = Path(str(workspace_lock(task["workdir"])) + ".owner.json")
    with locked(Path(str(path) + ".lock")), locked(workspace_lock(task["workdir"])):
        check_workspace_owner(owner_path)
        previous = read_json(path) if path.exists() else None
        if previous is not None:
            if not args.resume:
                raise ContractError("state exists; inspect it and use --resume explicitly")
            if not isinstance(previous, dict) or not previous.get("session_id"):
                raise ContractError("state has no resumable DSH session")
            if Path(previous["task"]["workdir"]).resolve() != Path(task["workdir"]).resolve():
                raise ContractError("resume must keep the original workdir")
            if worker_active(previous):
                raise ContractError("previous worker PID still exists; reconcile it before resuming")
            if previous.get("status") not in ("accepted", "changes_requested", "blocked"):
                raise ContractError("supervisor must inspect the previous turn and record review before resuming")
        elif args.resume:
            raise ContractError("--resume requires an existing state")
        history = list(previous.get("history", [])) if previous else []
        if previous:
            history.append({key: value for key, value in previous.items() if key != "history"})
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor, progress_name = tempfile.mkstemp(prefix=".progress-", suffix=".jsonl", dir=str(path.parent))
        progress_path = Path(progress_name)
        state = {"version": 1, "status": "running", "task": task, "session_id": previous["session_id"] if previous else None, "started_at": now(), "bridge_pid": os.getpid(), "diagnostic_bytes": 0, "history": history, "progress_log": str(progress_path)}
        save_state(path, state)
        command = [binary, "headless", "--json"]
        if state["session_id"]:
            command += ["--session-id", state["session_id"]]
        command.append("-")
        process = None
        code = 1
        run_started = time.monotonic()
        turn_started = {}
        usage = {"steps": {}}
        handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
        progress_stream = None
        try:
            progress_stream = os.fdopen(descriptor, "w", encoding="utf-8")
            descriptor = None
            os.chmod(progress_path, 0o600)
            with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as prompt:
                prompt.write(build_prompt(task))
                prompt.seek(0)
                process = subprocess.Popen(command, cwd=task["workdir"], stdin=prompt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                state["worker_pid"] = process.pid
                save_state(owner_path, {"worker_pid": process.pid, "state": str(path)})
                state["worker_identity"] = process_identity(process.pid)
                save_state(owner_path, {"worker_pid": process.pid, "worker_identity": state["worker_identity"], "state": str(path)})
                save_state(path, state)
                text = observe(process, state, path, args.timeout, progress_stream, usage, turn_started, args.verbose)
                state["worker_exit_code"] = process.returncode
                if process.returncode != 0:
                    state["status"] = "failed"
                    state["error"] = "DSH exited unsuccessfully; inspect workspace effects before retrying"
                else:
                    try:
                        if not state["session_id"]:
                            raise ContractError("DSH did not identify a session")
                        state["report"] = parse_report(text, task)
                        state["status"] = "awaiting_review"
                        code = 0
                    except ContractError as error:
                        state["status"] = "report_invalid"
                        state["error"] = str(error)
        except TimeoutError:
            state["status"] = "timed_out"
            code = 124
        except KeyboardInterrupt:
            state["status"] = "interrupted"
            code = 130
        except (OSError, ContractError):
            state["status"] = "failed"
            state["error"] = "DSH transport failed; inspect workspace effects before retrying"
        finally:
            if progress_stream is not None:
                progress_stream.close()
            if descriptor is not None:
                os.close(descriptor)
            if process is not None:
                stop_worker(process)
                state["worker_exit_code"] = process.returncode
                process.stdout.close()
                process.stderr.close()
            for sig, handler in handlers.items():
                signal.signal(sig, handler)
            state["finished_at"] = now()
            state["usage"] = finalize_usage(usage, run_started, turn_started)
            save_state(path, state)
            save_state(owner_path, {"worker_pid": None, "state": str(path)})
        emit(result_event(state, path))
    return code


def review(args):
    path = Path(args.state).expanduser().resolve()
    with locked(Path(str(path) + ".lock")):
        state = read_json(path)
        with locked(workspace_lock(state["task"]["workdir"])):
            check_workspace_owner(Path(str(workspace_lock(state["task"]["workdir"])) + ".owner.json"))
            if worker_active(state):
                raise ContractError("worker PID still exists; stop or reconcile it before review")
            verdict = validate_review(read_json(args.review_file), state["task"])
            state["review"] = {**verdict, "reviewed_at": now(), "reviewer": "supervisor"}
            state["status"] = verdict["verdict"]
            save_state(path, state)
            emit({"type": "review", "status": state["status"], "state": str(path)})
    return 0


def run_check_command(argv, cwd, timeout, log_path, owner_path, state_path):
    started = time.monotonic()
    log_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    process = None
    tail = bytearray()
    status = "failed"
    exit_code = None
    try:
        try:
            process = subprocess.Popen(argv, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
        except OSError:
            try:
                log_path.write_text("")
                os.chmod(log_path, 0o600)
            except OSError:
                pass
            return {"status": "error", "exit_code": None, "elapsed_seconds": 0.0, "log": str(log_path), "error": "command could not start; inspect argv and PATH"}
        save_state(owner_path, {"worker_pid": process.pid, "state": str(state_path), "kind": "check"})
        save_state(owner_path, {"worker_pid": process.pid, "worker_identity": process_identity(process.pid), "state": str(state_path), "kind": "check"})
        with open(log_path, "wb") as log:
            os.chmod(log_path, 0o600)
            try:
                with selectors.DefaultSelector() as selector:
                    os.set_blocking(process.stdout.fileno(), False)
                    selector.register(process.stdout, selectors.EVENT_READ)
                    deadline = started + timeout
                    while selector.get_map():
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError
                        for key, _ in selector.select(timeout=min(0.2, remaining)):
                            chunk = os.read(key.fileobj.fileno(), 65536)
                            if not chunk:
                                selector.unregister(key.fileobj)
                                continue
                            log.write(chunk)
                            tail.extend(chunk)
                            if len(tail) > TAIL_LIMIT:
                                del tail[:len(tail) - TAIL_LIMIT]
                    try:
                        process.wait(timeout=max(0.01, deadline - time.monotonic()))
                    except subprocess.TimeoutExpired:
                        raise TimeoutError from None
                exit_code = process.returncode
                status = "passed" if exit_code == 0 else "failed"
            except TimeoutError:
                status = "timeout"
    except KeyboardInterrupt:
        status = "interrupted"
    finally:
        if process is not None:
            stop_worker(process)
            if exit_code is None:
                exit_code = process.returncode
            try:
                process.stdout.close()
            except OSError:
                pass
            save_state(owner_path, {"worker_pid": None, "state": str(state_path)})
    entry = {"status": status, "exit_code": exit_code, "elapsed_seconds": round(max(0.0, time.monotonic() - started), 3), "log": str(log_path)}
    if status != "passed":
        entry["tail"] = tail.decode("utf-8", "replace")
    return entry


def compact_check_entry(entry):
    compact = {"id": entry["id"], "status": entry["status"], "exit_code": entry.get("exit_code"), "log": entry.get("log")}
    if entry.get("tail"):
        compact["tail"] = entry["tail"]
    if entry.get("error"):
        compact["error"] = entry["error"]
    return compact


def check(args):
    state_path = Path(args.state).expanduser().resolve()
    checks_config = read_json(args.checks_file)
    results = []
    code = 0
    task_id = None
    handlers = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        with locked(Path(str(state_path) + ".lock")):
            state = read_json(state_path)
            task = state.get("task") if isinstance(state, dict) else None
            if not isinstance(task, dict):
                raise ContractError("state has no task to check")
            task_id = task.get("task_id")
            workdir = task.get("workdir")
            if not isinstance(workdir, str) or not Path(workdir).is_dir():
                raise ContractError("state task workdir is unavailable")
            checks = validate_checks(checks_config, task_id)
            owner_path = Path(str(workspace_lock(workdir)) + ".owner.json")
            with locked(workspace_lock(workdir)):
                check_workspace_owner(owner_path)
                if worker_active(state):
                    raise ContractError("worker PID still exists; stop or reconcile it before checking")
                log_dir = Path(str(state_path) + ".checks") / ("%d-%d" % (int(time.time()), os.getpid()))
                log_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
                try:
                    for index, item in enumerate(checks):
                        safe_id = re.sub(r"[^A-Za-z0-9._-]", "_", item["id"])[:40]
                        log_path = log_dir / ("%d-%s.log" % (index, safe_id))
                        entry = run_check_command(item["argv"], workdir, item["timeout"], log_path, owner_path, state_path)
                        entry["id"] = item["id"]
                        entry["argv"] = item["argv"]
                        results.append(entry)
                        if entry["status"] == "interrupted":
                            code = 130
                            break
                        if entry["status"] != "passed":
                            code = 1
                except KeyboardInterrupt:
                    code = 130
                state.setdefault("checks", [])
                state["checks"].append({"task_id": task_id, "state": str(state_path), "finished_at": now(), "passed": code == 0, "results": results})
                state["checks_updated_at"] = now()
                save_state(state_path, state)
    except KeyboardInterrupt:
        code = 130
    finally:
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
    emit({"type": "checks", "task_id": task_id, "passed": code == 0, "results": [compact_check_entry(entry) for entry in results]})
    return code


def status(args):
    state = read_json(args.state)
    owner_path = Path(str(workspace_lock(state["task"]["workdir"])) + ".owner.json")
    diagnostics = {
        "worker_pid_exists": alive(state.get("worker_pid")),
        "worker_may_be_running": worker_active(state),
        "workspace_owner_file": str(owner_path),
        "workspace_owner": read_json(owner_path) if owner_path.exists() else None,
    }
    if args.full:
        emit({**state, **diagnostics})
    else:
        emit(compact_status(state, diagnostics))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    runner = sub.add_parser("run", help="execute exactly one detailed implementation dispatch")
    runner.add_argument("--task-file", required=True)
    runner.add_argument("--state", required=True)
    runner.add_argument("--resume", action="store_true")
    runner.add_argument("--verbose", action="store_true", help="forward sanitized native events on stdout")
    runner.add_argument("--timeout", type=float, default=900, help="turn deadline in seconds (default: 900)")
    reviewer = sub.add_parser("review", help="record checks and verdict supplied by the supervisor")
    reviewer.add_argument("--state", required=True)
    reviewer.add_argument("--review-file", required=True)
    checker = sub.add_parser("check", help="run supervisor-owned argv checks against a saved state")
    checker.add_argument("--state", required=True)
    checker.add_argument("--checks-file", required=True)
    status_parser = sub.add_parser("status", help="inspect saved state without starting DSH")
    status_parser.add_argument("--state", required=True)
    status_parser.add_argument("--full", action="store_true", help="include full task/history and recovery diagnostics")
    validator = sub.add_parser("validate", help="validate a detailed task without invoking DSH")
    validator.add_argument("--task-file", required=True)
    args = parser.parse_args()
    if os.name != "posix":
        parser.error("this bridge currently supports macOS and Linux")
    try:
        if args.command == "run":
            return run(args)
        if args.command == "review":
            return review(args)
        if args.command == "check":
            return check(args)
        if args.command == "validate":
            task = validate_task(read_json(args.task_file))
            emit({"valid": True, "task_id": task["task_id"]})
            return 0
        return status(args)
    except (ContractError, OSError, KeyError, TypeError):
        error = sys.exc_info()[1]
        message = str(error) if isinstance(error, ContractError) else "invalid state or inaccessible local file; inspect the supplied paths"
        print(message, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
