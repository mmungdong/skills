"""Behavioral tests run the bridge against a controlled external DSH process.

The suite also pins the low-token supervisor contract:

* ``run`` prints one compact result by default; ``--verbose`` also forwards
  progress events, and progress is always saved to a local log.
* The default ``status`` omits ``task``/``history``; ``--full`` includes them.
* DSH ``step_end`` usage is normalized per unique turn+step; ``turn_end`` usage
  is ignored, missing/invalid counters stay unavailable, and no pricing or
  model rates are invented.
* ``check`` runs supervisor-owned argv checks from the task workdir, validates
  the whole config before any command starts, and does not accept a task.
"""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest


BRIDGE = Path(__file__).resolve().parents[1] / "scripts" / "dsh_bridge.py"
FAKE_DSH = r'''#!/usr/bin/env python3
import json, os, sys, time
from pathlib import Path

def emit(value):
    print(json.dumps(value), flush=True)

if sys.argv[1:] == ['headless', '--help']:
    print('--json --session-id <id> [task...]')
    sys.exit(0)
prompt = sys.stdin.read()
Path(os.environ['CAPTURE']).write_text(json.dumps({'args':sys.argv[1:], 'prompt':prompt, 'cwd':os.getcwd()}))
mode = os.environ.get('FAKE_MODE', 'success')
emit({'type':'session', 'sessionId':'session-test', 'cwd':os.getcwd()})
emit({'type':'status', 'phase':'step_start', 'turn':1, 'step':1})
emit({'type':'thinking', 'text':'PRIVATE_THINKING_MARKER'})
emit({'type':'tool_result', 'text':'PRIVATE_TOOL_MARKER'})
if mode == 'large_tool_output':
    emit({'type':'tool_result', 'text':'x' * 400000})
print('PRIVATE_STDERR_MARKER', file=sys.stderr, flush=True)
if mode == 'hang':
    time.sleep(20)
if mode == 'spawn':
    import subprocess
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])
    Path(os.environ['CHILD_PID']).write_text(str(child.pid))
    time.sleep(20)
if mode == 'fail':
    sys.exit(7)

def usage_event(kind, turn, step, payload):
    event = {'type': 'status', 'phase': kind, 'turn': turn, 'usage': payload}
    if step is not None:
        event['step'] = step
    emit(event)

if mode in ('usage', 'usage_gap'):
    usage_event('step_end', 1, 1, {'inputTokens':10,'outputTokens':5,'cacheReadTokens':3,'cacheWriteTokens':2,'totalTokens':20})
    usage_event('step_end', 1, 1, {'inputTokens':10,'outputTokens':5,'cacheReadTokens':3,'cacheWriteTokens':2,'totalTokens':20})
    usage_event('turn_end', 1, None, {'inputTokens':999,'outputTokens':999,'cacheReadTokens':999,'cacheWriteTokens':999,'totalTokens':999})
    usage_event('step_end', 1, 2, {'inputTokens':1} if mode == 'usage_gap' else {'inputTokens':1,'outputTokens':2,'cacheReadTokens':3,'cacheWriteTokens':4,'totalTokens':10})
elif mode == 'usage_partial':
    usage_event('step_end', 1, 1, {'inputTokens':7})
elif mode == 'usage_invalid':
    usage_event('step_end', 1, 1, {'inputTokens':-5,'outputTokens':True,'cacheReadTokens':'9','cacheWriteTokens':4,'totalTokens':None})

report = {'task_id':'T1', 'status':'completed', 'summary':'Implemented greet', 'artifacts':['greeting.py'], 'completed_steps':['S1'], 'blockers':[], 'decision_required':[]}
if mode == 'wrong_task':
    report['task_id'] = 'OTHER'
if mode == 'incomplete':
    report['completed_steps'] = []
if mode == 'large_report':
    report['summary'] = 'S' * 3000
    report['artifacts'] = ['files/%d.py' % i for i in range(400)]
if mode == 'long_blocker':
    report['status'] = 'blocked'
    report['blockers'] = ['B' * 60000]
    report['decision_required'] = ['D' * 30000]
text = json.dumps(report)
if mode == 'malformed':
    text = 'I did everything, trust me.'
if mode == 'fenced':
    text = '```json\n' + text + '\n```'
emit({'type':'text', 'text':text})
emit({'type':'status', 'phase':'turn_end', 'turn':1, 'reason':{'kind':'completed'}})
if mode != 'missing_final':
    emit({'type':'final', 'text':text})
'''


def task(workdir):
    return {
        "task_id": "T1",
        "objective": "Implement an exact greeting function",
        "workdir": str(workdir),
        "scope": ["greeting.py"],
        "steps": [{"id": "S1", "action": "Implement greet(name), trim whitespace and reject blank or non-string names with ValueError", "paths": ["greeting.py"]}],
        "deliverables": ["greeting.py with greet(name)"],
        "acceptance": [{"id": "AC1", "check": "Supervisor imports greet and checks valid, blank and non-string inputs"}],
        "constraints": ["Preserve unrelated edits; supervisor runs all checks"],
    }


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workdir = self.root / "project with spaces"
        self.workdir.mkdir()
        binary_dir = self.root / "bin"
        binary_dir.mkdir()
        binary = binary_dir / "dsh"
        binary.write_text(FAKE_DSH)
        binary.chmod(0o700)
        self.capture = self.root / "capture.json"
        self.task_file = self.root / "task.json"
        self.state_file = self.root / "run" / "state.json"
        self.env = {**os.environ, "PATH": str(binary_dir) + os.pathsep + os.environ.get("PATH", ""), "CAPTURE": str(self.capture), "PYTHONDONTWRITEBYTECODE": "1"}
        self.payload = task(self.workdir)
        self.save_task()

    def save_task(self):
        self.task_file.write_text(json.dumps(self.payload))

    def call(self, *args, mode="success"):
        return subprocess.run([sys.executable, str(BRIDGE), *args], env={**self.env, "FAKE_MODE": mode}, capture_output=True, text=True, timeout=15)

    def run_task(self, *args, mode="success"):
        return self.call("run", "--task-file", str(self.task_file), "--state", str(self.state_file), *args, mode=mode)

    def state(self):
        return json.loads(self.state_file.read_text())

    def review(self, verdict="accepted", criteria=None):
        path = self.root / "review.json"
        path.write_text(json.dumps({"task_id": self.payload["task_id"], "verdict": verdict, "criteria": criteria if criteria is not None else [{"id": "AC1", "passed": True, "evidence": "Supervisor: python -m unittest, exit 0; inspected greeting.py diff"}], "findings": [] if verdict == "accepted" else ["Supervisor inspected workspace effects; continue only the unfinished implementation"]}))
        return self.call("review", "--state", str(self.state_file), "--review-file", str(path))

    def json_stdout(self, result):
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertEqual(len(lines), 1, "expected exactly one JSON line, got: %r" % (result.stdout,))
        return json.loads(lines[0])

    def last_json(self, result):
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertTrue(lines, "no stdout JSON: " + result.stdout + result.stderr)
        return json.loads(lines[-1])

    def checks_file(self, checks, task_id="T1", name="checks.json"):
        path = self.root / name
        path.write_text(json.dumps({"task_id": task_id, "checks": checks}))
        return path

    def check(self, checks, *args, state=None):
        return self.call("check", "--state", str(state or self.state_file), "--checks-file", str(checks), *args)

    def progress_log_text(self, payload, state):
        """Find the saved local progress log without pinning an exact filename."""
        candidates = []
        for value in (payload.get("progress_log"), state.get("progress_log")):
            if value:
                candidates.append(Path(value))
        for path in self.state_file.parent.rglob("*"):
            if path.is_file() and path != self.state_file and path.stat().st_size < 1_000_000:
                candidates.append(path)
        for path in candidates:
            if not path.is_file():
                continue
            try:
                text = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            if "step_start" in text:
                return path, text
        return None, None

    def test_runs_one_turn_and_requires_separate_supervisor_review(self):
        result = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        state = self.state()
        self.assertEqual(state["status"], "awaiting_review")
        self.assertEqual(state["session_id"], "session-test")
        self.assertEqual(state["report"]["artifacts"], ["greeting.py"])
        capture = json.loads(self.capture.read_text())
        self.assertEqual(capture["args"], ["headless", "--json", "-"])
        self.assertEqual(Path(capture["cwd"]), self.workdir.resolve())

    def test_refuses_a_vague_task_before_invoking_dsh(self):
        del self.payload["steps"]
        self.save_task()
        result = self.run_task()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("steps", result.stderr)
        self.assertFalse(self.capture.exists())

    def test_rejects_step_paths_outside_scope(self):
        self.payload["steps"][0]["paths"] = ["../other.py"]
        self.save_task()
        result = self.run_task()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.capture.exists())

    def test_scope_is_a_file_boundary_not_a_prefix(self):
        self.payload["steps"][0]["paths"] = ["greeting.py.bak"]
        self.save_task()
        self.assertNotEqual(self.run_task().returncode, 0)
        self.assertFalse(self.capture.exists())

    def test_normalized_workspace_root_is_not_a_valid_scope(self):
        for scope in ["./", "././"]:
            with self.subTest(scope=scope):
                self.payload["scope"] = [scope]
                self.save_task()
                result = self.run_task()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.capture.exists())

    def test_prompt_is_stdin_data_and_no_checks_are_delegated(self):
        marker = self.root / "SHELL_EXECUTED"
        self.payload["objective"] += " $(touch " + str(marker) + ") `echo dangerous`"
        self.save_task()
        result = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        prompt = json.loads(self.capture.read_text())["prompt"]
        self.assertIn(self.payload["objective"], prompt)
        self.assertIn("supervisor", prompt.lower())
        self.assertFalse(marker.exists())

    def test_drops_thinking_tool_output_and_raw_stderr(self):
        result = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        content = result.stdout + result.stderr + self.state_file.read_text()
        for marker in ["PRIVATE_THINKING_MARKER", "PRIVATE_TOOL_MARKER", "PRIVATE_STDERR_MARKER"]:
            self.assertNotIn(marker, content)

    def test_large_ignored_tool_event_does_not_abort_implementation(self):
        result = self.run_task(mode="large_tool_output")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["status"], "awaiting_review")

    def test_rejects_invalid_or_incomplete_worker_reports(self):
        for mode in ["malformed", "wrong_task", "incomplete", "missing_final"]:
            with self.subTest(mode=mode):
                state = self.root / mode / "state.json"
                result = self.call("run", "--task-file", str(self.task_file), "--state", str(state), mode=mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(json.loads(state.read_text())["status"], "report_invalid")

    def test_accepts_a_single_json_code_fence(self):
        result = self.run_task(mode="fenced")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["status"], "awaiting_review")

    def test_nonzero_exit_is_failed_even_with_a_session(self):
        result = self.run_task(mode="fail")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state()["status"], "failed")
        self.assertEqual(self.state()["worker_exit_code"], 7)

    def test_resume_uses_session_and_preserves_prior_review(self):
        self.assertEqual(self.run_task().returncode, 0)
        self.assertEqual(self.review().returncode, 0)
        self.assertEqual(self.state()["status"], "accepted")
        result = self.run_task("--resume")
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.capture.read_text())["args"]
        self.assertEqual(args, ["headless", "--json", "--session-id", "session-test", "-"])
        self.assertEqual(self.state()["history"][0]["review"]["verdict"], "accepted")

    def test_existing_state_needs_explicit_resume_and_review(self):
        self.assertEqual(self.run_task().returncode, 0)
        self.assertNotEqual(self.run_task().returncode, 0)
        self.assertNotEqual(self.run_task("--resume").returncode, 0)

    def test_acceptance_requires_complete_positive_supervisor_evidence(self):
        self.assertEqual(self.run_task().returncode, 0)
        for criteria in [[], [{"id": "AC1", "passed": False, "evidence": "fails"}], [{"id": "AC1", "passed": True, "evidence": ""}], [{"id": "OTHER", "passed": True, "evidence": "passes"}]]:
            with self.subTest(criteria=criteria):
                self.assertNotEqual(self.review(criteria=criteria).returncode, 0)
                self.assertEqual(self.state()["status"], "awaiting_review")
        self.assertEqual(self.review().returncode, 0)
        self.assertEqual(self.state()["status"], "accepted")

    def test_timeout_stops_worker_and_requires_review_before_resume(self):
        result = self.run_task("--timeout", "0.3", mode="hang")
        self.assertEqual(result.returncode, 124, result.stderr)
        state = self.state()
        self.assertEqual(state["status"], "timed_out")
        with self.assertRaises(ProcessLookupError):
            os.kill(state["worker_pid"], 0)
        self.assertNotEqual(self.run_task("--resume").returncode, 0)
        self.assertEqual(self.review("changes_requested").returncode, 0)
        self.assertEqual(self.run_task("--resume").returncode, 0)

    def test_concurrent_run_cannot_write_same_state(self):
        command = [sys.executable, str(BRIDGE), "run", "--task-file", str(self.task_file), "--state", str(self.state_file), "--timeout", "10"]
        process = subprocess.Popen(command, env={**self.env, "FAKE_MODE": "hang"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 4
            while not self.capture.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(self.capture.exists())
            other = self.run_task("--resume")
            self.assertNotEqual(other.returncode, 0)
            process.send_signal(signal.SIGINT)
            process.communicate(timeout=5)
            self.assertEqual(self.state()["status"], "interrupted")
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()

    def test_resume_rejects_different_workdir(self):
        self.assertEqual(self.run_task().returncode, 0)
        self.assertEqual(self.review().returncode, 0)
        another = self.root / "another"
        another.mkdir()
        self.payload["workdir"] = str(another)
        self.save_task()
        self.assertNotEqual(self.run_task("--resume").returncode, 0)

    def test_second_state_cannot_bypass_workspace_lock(self):
        command = [sys.executable, str(BRIDGE), "run", "--task-file", str(self.task_file), "--state", str(self.state_file), "--timeout", "10"]
        process = subprocess.Popen(command, env={**self.env, "FAKE_MODE": "hang"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 4
            while not self.capture.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(self.capture.exists())
            other = self.call("run", "--task-file", str(self.task_file), "--state", str(self.root / "second-state.json"))
            self.assertNotEqual(other.returncode, 0)
            self.assertFalse((self.root / "second-state.json").exists())
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
            process.communicate(timeout=5)

    def test_existing_worker_pid_blocks_review_after_a_lost_handle(self):
        self.assertEqual(self.run_task().returncode, 0)
        state = self.state()
        state["worker_pid"] = os.getpid()
        state.pop("worker_identity", None)
        state["status"] = "running"
        self.state_file.write_text(json.dumps(state))
        self.assertNotEqual(self.review().returncode, 0)
        self.assertEqual(self.state()["status"], "running")
        self.assertNotEqual(self.run_task("--resume").returncode, 0)

    def test_reused_pid_with_a_different_start_time_does_not_block_review(self):
        self.assertEqual(self.run_task().returncode, 0)
        state = self.state()
        state["worker_pid"] = os.getpid()
        state["worker_identity"] = "a different recorded process start time"
        self.state_file.write_text(json.dumps(state))
        result = self.review()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["status"], "accepted")

    def test_orphan_worker_blocks_new_state_after_bridge_is_killed(self):
        command = [sys.executable, str(BRIDGE), "run", "--task-file", str(self.task_file), "--state", str(self.state_file), "--timeout", "10"]
        process = subprocess.Popen(command, env={**self.env, "FAKE_MODE": "hang"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        worker_pid = None
        try:
            deadline = time.monotonic() + 4
            while not self.capture.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(self.capture.exists())
            worker_pid = self.state()["worker_pid"]
            process.kill()
            process.communicate(timeout=5)
            other = self.call("run", "--task-file", str(self.task_file), "--state", str(self.root / "second-state.json"))
            self.assertNotEqual(other.returncode, 0)
            self.assertFalse((self.root / "second-state.json").exists())
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
            if worker_pid is not None:
                try:
                    os.killpg(worker_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_rejects_symlink_scope_outside_workspace(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.workdir / "linked").symlink_to(outside, target_is_directory=True)
        self.payload["scope"] = ["linked"]
        self.payload["steps"][0]["paths"] = ["linked/file.py"]
        self.save_task()
        self.assertNotEqual(self.run_task().returncode, 0)
        self.assertFalse(self.capture.exists())

    def test_copied_skill_does_not_require_its_source_repository(self):
        import shutil
        installed = self.root / "copied-skill"
        shutil.copytree(BRIDGE.parent, installed)
        result = subprocess.run([sys.executable, str(installed / "dsh_bridge.py"), "--help"], env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("run", result.stdout)

    def test_default_run_is_quiet_and_saves_local_progress(self):
        result = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = self.json_stdout(result)
        self.assertEqual(payload["type"], "result")
        self.assertEqual(payload["status"], "awaiting_review")
        self.assertEqual(payload["task_id"], "T1")
        self.assertTrue(Path(payload["state"]).exists())
        state = self.state()
        self.assertIn("last_progress", state)
        self.assertEqual(state["last_progress"]["phase"], "turn_end")
        path, text = self.progress_log_text(payload, state)
        self.assertIsNotNone(path, "default run must save a local progress log")
        self.assertIn("step_start", text)
        self.assertIn("turn_end", text)

    def test_verbose_run_forwards_progress_with_exactly_one_result(self):
        result = self.run_task("--verbose")
        self.assertEqual(result.returncode, 0, result.stderr)
        types = [json.loads(line)["type"] for line in result.stdout.splitlines() if line.strip()]
        self.assertIn("progress", types)
        self.assertEqual(types.count("result"), 1)
        self.assertEqual(types[-1], "result")

    def test_result_is_compact_and_carries_supervisor_summary_and_state_path(self):
        result = self.run_task()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = self.json_stdout(result)
        for key in ("type", "status", "state", "task_id", "summary", "artifacts", "blockers", "decision_required"):
            self.assertIn(key, payload)
        self.assertEqual(payload["status"], "awaiting_review")
        self.assertEqual(payload["summary"], "Implemented greet")
        self.assertEqual(payload["artifacts"], ["greeting.py"])
        self.assertEqual(payload["blockers"], [])
        self.assertEqual(payload["decision_required"], [])
        self.assertTrue(Path(payload["state"]).exists())
        self.assertEqual(self.state()["report"]["summary"], "Implemented greet")

    def test_default_status_omits_task_and_history_and_full_includes_them(self):
        self.assertEqual(self.run_task().returncode, 0)
        compact = self.call("status", "--state", str(self.state_file))
        self.assertEqual(compact.returncode, 0, compact.stderr)
        compact_payload = json.loads(compact.stdout)
        self.assertNotIn("task", compact_payload)
        self.assertNotIn("history", compact_payload)
        self.assertEqual(compact_payload["status"], "awaiting_review")
        full = self.call("status", "--state", str(self.state_file), "--full")
        self.assertEqual(full.returncode, 0, full.stderr)
        full_payload = json.loads(full.stdout)
        self.assertIn("task", full_payload)
        self.assertIn("history", full_payload)

    def test_resume_is_quiet_reuses_session_and_keeps_supervisor_gate(self):
        self.assertEqual(self.run_task().returncode, 0)
        self.assertNotEqual(self.run_task().returncode, 0)
        self.assertEqual(self.review().returncode, 0)
        result = self.run_task("--resume")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = self.json_stdout(result)
        self.assertEqual(payload["type"], "result")
        args = json.loads(self.capture.read_text())["args"]
        self.assertEqual(args, ["headless", "--json", "--session-id", "session-test", "-"])
        self.assertEqual(self.state()["history"][0]["review"]["verdict"], "accepted")

    def test_compact_result_bounds_large_report_while_state_keeps_full_report(self):
        self.payload["scope"] = ["files"]
        self.payload["steps"][0]["paths"] = ["files/0.py"]
        self.save_task()
        result = self.run_task(mode="large_report")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = self.json_stdout(result)
        state = self.state()
        self.assertEqual(len(state["report"]["artifacts"]), 400)
        self.assertEqual(len(state["report"]["summary"]), 3000)
        self.assertLess(len(payload["artifacts"]), len(state["report"]["artifacts"]))
        self.assertLess(len(payload["summary"]), len(state["report"]["summary"]))
        self.assertLess(len(result.stdout.encode("utf-8")), 65536)

    def test_default_status_stays_bounded_with_large_history(self):
        self.assertEqual(self.run_task().returncode, 0)
        state = self.state()
        state["history"] = [{"payload": "H" * 2000} for _ in range(400)]
        self.state_file.write_text(json.dumps(state))
        compact = self.call("status", "--state", str(self.state_file))
        self.assertEqual(compact.returncode, 0, compact.stderr)
        compact_payload = json.loads(compact.stdout)
        self.assertNotIn("history", compact_payload)
        self.assertNotIn("task", compact_payload)
        self.assertLess(len(compact.stdout), 20000)
        full = self.call("status", "--state", str(self.state_file), "--full")
        self.assertEqual(full.returncode, 0, full.stderr)
        full_payload = json.loads(full.stdout)
        self.assertIn("history", full_payload)
        self.assertGreater(len(full.stdout), len(compact.stdout))

    def test_usage_aggregates_step_end_once_and_ignores_turn_end(self):
        result = self.run_task(mode="usage")
        self.assertEqual(result.returncode, 0, result.stderr)
        usage = self.state()["usage"]
        self.assertEqual(usage["input_tokens"], 11)
        self.assertEqual(usage["output_tokens"], 7)
        self.assertEqual(usage["cache_read_tokens"], 6)
        self.assertEqual(usage["cache_write_tokens"], 6)
        self.assertEqual(usage["total_tokens"], 30)
        turns = usage["turns"]
        self.assertEqual([turn["turn"] for turn in turns], [1])
        self.assertEqual(turns[0]["input_tokens"], 11)
        self.assertEqual(turns[0]["total_tokens"], 30)
        payload = self.json_stdout(result)
        self.assertEqual(payload["usage"]["input_tokens"], 11)
        self.assertEqual(payload["usage"]["total_tokens"], 30)

    def test_usage_missing_counters_stay_unavailable(self):
        result = self.run_task(mode="usage_partial")
        self.assertEqual(result.returncode, 0, result.stderr)
        usage = self.state()["usage"]
        self.assertEqual(usage["input_tokens"], 7)
        for key in ("output_tokens", "cache_read_tokens", "cache_write_tokens", "total_tokens"):
            self.assertIsNone(usage[key], key)
        self.assertIsNone(usage["turns"][0]["output_tokens"])

    def test_usage_rejects_invalid_counter_values(self):
        result = self.run_task(mode="usage_invalid")
        self.assertEqual(result.returncode, 0, result.stderr)
        usage = self.state()["usage"]
        self.assertIsNone(usage["input_tokens"])
        self.assertIsNone(usage["output_tokens"])
        self.assertIsNone(usage["cache_read_tokens"])
        self.assertEqual(usage["cache_write_tokens"], 4)
        self.assertIsNone(usage["total_tokens"])

    def test_usage_elapsed_seconds_and_no_invented_rates(self):
        self.assertEqual(self.run_task(mode="usage").returncode, 0)
        usage = self.state()["usage"]
        self.assertIsInstance(usage["elapsed_seconds"], (int, float))
        self.assertGreaterEqual(usage["elapsed_seconds"], 0)
        self.assertIsInstance(usage["turns"][0]["elapsed_seconds"], (int, float))
        self.assertGreaterEqual(usage["turns"][0]["elapsed_seconds"], 0)
        for key in ("cost_usd", "cost", "estimated_cost", "rates", "model_rates", "gpt_usage", "price", "price_per_million"):
            self.assertIsNone(usage.get(key), "usage must not invent rates or pricing for " + key)

    def test_check_runs_in_workdir_without_shell_interpolation(self):
        self.assertEqual(self.run_task().returncode, 0)
        marks = self.root / "check-marks"
        marks.mkdir()
        code = "import json,os,pathlib,sys; d=pathlib.Path(sys.argv[1]); d.joinpath('cwd.txt').write_text(os.getcwd()); d.joinpath('argv.json').write_text(json.dumps(sys.argv[2:]))"
        literal = ["$(touch pwned)", "; touch pwned", "`touch pwned`"]
        argv = [sys.executable, "-c", code, str(marks)] + literal
        result = self.check(self.checks_file([{"id": "C1", "argv": argv, "timeout": 10}]))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = self.last_json(result)
        self.assertEqual(payload["type"], "checks")
        self.assertTrue(payload["passed"])
        self.assertEqual(payload["task_id"], "T1")
        self.assertEqual([item["id"] for item in payload["results"]], ["C1"])
        self.assertEqual(payload["results"][0]["status"], "passed")
        self.assertEqual(Path((marks / "cwd.txt").read_text()).resolve(), self.workdir.resolve())
        self.assertEqual(json.loads((marks / "argv.json").read_text()), literal)
        self.assertFalse((self.workdir / "pwned").exists())
        self.assertFalse((self.root / "pwned").exists())

    def test_check_passing_output_kept_in_private_log(self):
        self.assertEqual(self.run_task().returncode, 0)
        marker = "PRIVATE_CHECK_PASS_MARKER"
        code = "print(%r * 2000)" % marker
        result = self.check(self.checks_file([{"id": "C1", "argv": [sys.executable, "-c", code], "timeout": 10}]))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = self.last_json(result)
        self.assertNotIn(marker, result.stdout)
        entry = payload["results"][0]
        self.assertEqual(entry["status"], "passed")
        self.assertTrue(entry.get("log"))
        log = Path(entry["log"])
        self.assertTrue(log.exists(), entry["log"])
        self.assertIn(marker, log.read_text())

    def test_check_failure_keeps_going_and_bounds_tail(self):
        self.assertEqual(self.run_task().returncode, 0)
        late = self.root / "late-pass-marker"
        failing_code = "import sys; sys.stdout.write('F' * 50000); sys.stdout.flush(); sys.exit(3)"
        passing_code = "open(%r, 'w').write('ok')" % str(late)
        checks = [
            {"id": "C1", "argv": [sys.executable, "-c", failing_code], "timeout": 10},
            {"id": "C2", "argv": [sys.executable, "-c", passing_code], "timeout": 10},
        ]
        result = self.check(self.checks_file(checks))
        self.assertNotEqual(result.returncode, 0)
        payload = self.last_json(result)
        self.assertFalse(payload["passed"])
        by_id = {item["id"]: item for item in payload["results"]}
        self.assertEqual(by_id["C1"]["status"], "failed")
        self.assertEqual(by_id["C1"]["exit_code"], 3)
        self.assertEqual(by_id["C2"]["status"], "passed")
        self.assertTrue(late.exists(), "a failing check must not stop later checks")
        tail = by_id["C1"].get("tail") or ""
        self.assertTrue(tail)
        self.assertLess(len(tail), 8000)
        log = Path(by_id["C1"]["log"])
        self.assertTrue(log.exists())
        self.assertGreaterEqual(len(log.read_text()), 50000)
        self.assertLess(len(result.stdout.encode("utf-8")), 40000)

    def test_check_timeout_kills_process_group(self):
        self.assertEqual(self.run_task().returncode, 0)
        pid_file = self.root / "child-pid.txt"
        child_code = "import time; time.sleep(30)"
        parent_code = ("import pathlib,subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c',%r]); "
                       "pathlib.Path(%r).write_text(str(p.pid)); time.sleep(30)") % (child_code, str(pid_file))
        result = self.check(self.checks_file([{"id": "C1", "argv": [sys.executable, "-c", parent_code], "timeout": 1.5}]))
        self.assertNotEqual(result.returncode, 0)
        payload = self.last_json(result)
        self.assertEqual(payload["results"][0]["status"], "timeout")
        self.assertTrue(pid_file.exists(), "timeout command should have started its child")
        child_pid = int(pid_file.read_text())
        deadline = time.monotonic() + 3
        alive = True
        while time.monotonic() < deadline:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                alive = False
                break
            time.sleep(0.05)
        self.assertFalse(alive, "timeout must kill the command process group")

    def test_check_records_start_error_and_continues(self):
        self.assertEqual(self.run_task().returncode, 0)
        late = self.root / "after-error-marker"
        passing_code = "open(%r, 'w').write('ok')" % str(late)
        checks = [
            {"id": "C1", "argv": ["/nonexistent/dsh-check-binary-xyz"], "timeout": 5},
            {"id": "C2", "argv": [sys.executable, "-c", passing_code], "timeout": 5},
        ]
        result = self.check(self.checks_file(checks))
        self.assertNotEqual(result.returncode, 0)
        payload = self.last_json(result)
        by_id = {item["id"]: item for item in payload["results"]}
        self.assertEqual(by_id["C1"]["status"], "error")
        self.assertTrue(by_id["C1"].get("error"))
        self.assertEqual(by_id["C2"]["status"], "passed")
        self.assertTrue(late.exists(), "a start error must not stop later checks")

    def test_check_validates_config_before_side_effects(self):
        self.assertEqual(self.run_task().returncode, 0)
        marker = self.root / "must-not-run"
        touch = [sys.executable, "-c", "open(%r, 'w').write('x')" % str(marker)]
        unknown = [sys.executable, "-c", "pass"]
        cases = {
            "duplicate": [{"id": "C1", "argv": touch, "timeout": 5}, {"id": "C1", "argv": touch, "timeout": 5}],
            "string_argv": [{"id": "C1", "argv": "python3 -c pass", "timeout": 5}, {"id": "C2", "argv": touch, "timeout": 5}],
            "empty_argv": [{"id": "C1", "argv": [], "timeout": 5}, {"id": "C2", "argv": touch, "timeout": 5}],
            "non_string_argv": [{"id": "C1", "argv": [sys.executable, 123], "timeout": 5}, {"id": "C2", "argv": touch, "timeout": 5}],
            "zero_timeout": [{"id": "C1", "argv": touch, "timeout": 0}, {"id": "C2", "argv": unknown, "timeout": 5}],
            "negative_timeout": [{"id": "C1", "argv": touch, "timeout": -1}, {"id": "C2", "argv": unknown, "timeout": 5}],
            "bool_timeout": [{"id": "C1", "argv": touch, "timeout": True}, {"id": "C2", "argv": unknown, "timeout": 5}],
            "string_timeout": [{"id": "C1", "argv": touch, "timeout": "5"}, {"id": "C2", "argv": unknown, "timeout": 5}],
        }
        for name, checks in cases.items():
            with self.subTest(name=name):
                if marker.exists():
                    marker.unlink()
                result = self.check(self.checks_file(checks, name=name + ".json"))
                self.assertNotEqual(result.returncode, 0, "%s should be rejected: %s" % (name, result.stdout))
                self.assertFalse(marker.exists(), name + " ran a command before validating the whole config")

    def test_check_rejects_mismatched_task_before_side_effects(self):
        self.assertEqual(self.run_task().returncode, 0)
        marker = self.root / "mismatch-must-not-run"
        touch = [sys.executable, "-c", "open(%r, 'w').write('x')" % str(marker)]
        checks = self.checks_file([{"id": "C1", "argv": touch, "timeout": 5}], task_id="OTHER")
        result = self.check(checks)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(marker.exists())

    def test_check_rejects_empty_list_before_side_effects(self):
        self.assertEqual(self.run_task().returncode, 0)
        result = self.check(self.checks_file([]))
        self.assertNotEqual(result.returncode, 0)

    def test_check_does_not_accept_task_or_accept_state(self):
        self.assertEqual(self.run_task().returncode, 0)
        checks = self.checks_file([{"id": "C1", "argv": [sys.executable, "-c", "pass"], "timeout": 5}])
        rejected = self.check(checks, "--task-file", str(self.task_file))
        self.assertNotEqual(rejected.returncode, 0)
        accepted = self.check(checks)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(self.state()["status"], "awaiting_review")

    def test_check_workspace_lock_blocks_during_active_run(self):
        command = [sys.executable, str(BRIDGE), "run", "--task-file", str(self.task_file), "--state", str(self.state_file), "--timeout", "10"]
        process = subprocess.Popen(command, env={**self.env, "FAKE_MODE": "hang"}, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 4
            while not self.capture.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(self.capture.exists())
            checks = self.checks_file([{"id": "C1", "argv": [sys.executable, "-c", "pass"], "timeout": 5}])
            other = self.check(checks)
            self.assertNotEqual(other.returncode, 0)
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
            process.communicate(timeout=5)

    def test_compact_result_bounds_individual_blocker_and_decision_text(self):
        result = self.run_task(mode="long_blocker")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = self.json_stdout(result)
        self.assertLess(len(result.stdout.encode("utf-8")), 16000)
        self.assertTrue(payload["truncated"])
        self.assertEqual(len(self.state()["report"]["blockers"][0]), 60000)

    def test_missing_step_usage_does_not_look_like_complete_turn_usage(self):
        result = self.run_task(mode="usage_gap")
        self.assertEqual(result.returncode, 0, result.stderr)
        usage = self.state()["usage"]
        self.assertEqual(usage["input_tokens"], 11)
        self.assertEqual(usage["output_tokens"], 5)
        self.assertTrue(usage["partial"])

    def test_resume_preserves_the_previous_turn_progress_log(self):
        self.assertEqual(self.run_task().returncode, 0)
        first = Path(self.state()["progress_log"])
        content = first.read_bytes()
        self.assertEqual(self.review().returncode, 0)
        self.assertEqual(self.run_task("--resume").returncode, 0)
        second = Path(self.state()["progress_log"])
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), content)

    def test_distinct_check_ids_cannot_overwrite_each_others_logs(self):
        self.assertEqual(self.run_task().returncode, 0)
        checks = self.checks_file([
            {"id": "a/b", "argv": [sys.executable, "-c", "print('first-result')"]},
            {"id": "a?b", "argv": [sys.executable, "-c", "print('second-result')"]},
        ])
        result = self.check(checks)
        self.assertEqual(result.returncode, 0, result.stderr)
        entries = self.last_json(result)["results"]
        self.assertNotEqual(entries[0]["log"], entries[1]["log"])
        self.assertEqual(Path(entries[0]["log"]).read_text().strip(), "first-result")
        self.assertEqual(Path(entries[1]["log"]).read_text().strip(), "second-result")

    def test_sigterm_stops_check_and_records_interruption_before_later_checks(self):
        self.assertEqual(self.run_task().returncode, 0)
        pid_file = self.root / "checking-pid"
        later = self.root / "should-not-run"
        code = "import os,pathlib,time; pathlib.Path(%r).write_text(str(os.getpid())); time.sleep(30)" % str(pid_file)
        config = self.checks_file([
            {"id": "long", "argv": [sys.executable, "-c", code]},
            {"id": "later", "argv": [sys.executable, "-c", "open(%r,'w').write('bad')" % str(later)]},
        ])
        controller = subprocess.Popen([sys.executable, str(BRIDGE), "check", "--state", str(self.state_file), "--checks-file", str(config)], env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 4
            while not pid_file.exists() and controller.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(pid_file.exists())
            controller.send_signal(signal.SIGTERM)
            stdout, stderr = controller.communicate(timeout=5)
            self.assertEqual(controller.returncode, 130, stderr)
            self.assertFalse(later.exists())
            with self.assertRaises(ProcessLookupError):
                os.kill(int(pid_file.read_text()), 0)
            self.assertFalse(json.loads(stdout)["passed"])
            self.assertEqual(self.state()["checks"][-1]["results"][0]["status"], "interrupted")
        finally:
            if controller.poll() is None:
                controller.kill()
            controller.communicate()
            if pid_file.exists():
                try:
                    os.killpg(int(pid_file.read_text()), signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == "__main__":
    unittest.main()
