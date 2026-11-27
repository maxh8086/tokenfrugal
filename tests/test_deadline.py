"""Per-role dispatch deadlines and model budgets."""
import asyncio
import math
import os
import sys
import tempfile
import time
import threading
from contextlib import asynccontextmanager
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest import mock

from router import checker, config, events, loop, server, store
from router.outcomes import Stop


class DeadlineConfigTests(unittest.TestCase):
    def test_worked_example(self):
        role = {"timeout_s": 225}
        self.assertEqual(config.deadline(role, 225), 488)
        self.assertEqual(config.model_budget(role, 225), 337.5)

    def test_all_roles_have_finite_deadline_above_timeout(self):
        for role in server.CFG["roles"].values():
            timeout = float(role.get("timeout_s") or loop.TASK_TIMEOUT)
            deadline = config.deadline(role, timeout)
            self.assertTrue(math.isfinite(deadline))
            self.assertGreater(deadline, timeout)

    def test_override_ignores_nonnumeric_and_floors_low_values(self):
        role = {"timeout_s": 60}
        value, warning = config._parse_task_deadline_override("not a number")
        self.assertIsNone(value)
        self.assertIn("not a number", warning)
        with mock.patch.object(config, "TASK_DEADLINE_OVERRIDE", None):
            self.assertEqual(config.deadline(role, 60), 240)
        with mock.patch.object(config, "TASK_DEADLINE_OVERRIDE", 2):
            self.assertEqual(config.deadline(role, 60), 75)


class BudgetTests(unittest.TestCase):
    def test_pause_excludes_accept_time_from_model_spend(self):
        budget = loop.Budget(20)
        with budget.pause():
            pass
        self.assertGreaterEqual(budget.remaining(), 0)
        self.assertLessEqual(budget.spent(), 20)

    def test_model_call_is_cut_at_budget_remaining(self):
        class Session:
            async def list_tools(self):
                return SimpleNamespace(tools=[])

        @asynccontextmanager
        async def open_role(*args, **kwargs):
            yield Session()

        def slow_thread(*args, **kwargs):
            return asyncio.create_task(asyncio.sleep(30))

        role = {"role": "builder", "model": "m", "tools": [], "max_steps": 1, "timeout_s": 1}
        patches = (mock.patch.object(loop, "backends", open_role),
                   mock.patch.object(loop, "open_role", open_role),
                   mock.patch.object(loop, "to_openai_tools", lambda *a, **k: []),
                   mock.patch.object(loop.asyncio, "to_thread", slow_thread))
        with patches[0], patches[1], patches[2], patches[3]:
            with self.assertRaises(loop.LoopError) as caught:
                asyncio.run(loop.run("a", role, "task", budget=loop.Budget(.03)))
        self.assertIn("timed out", str(caught.exception))


class ServerDeadlineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_patch = mock.patch.object(store, "DB_PATH", Path(self.tmp) / "tasks.db")
        self.ws_patch = mock.patch.object(server, "WORKSPACE", self.tmp)
        self.events = []
        self.event_patch = mock.patch.object(events, "emit", lambda name, **kw: self.events.append((name, kw)))
        for patcher in (self.db_patch, self.ws_patch, self.event_patch):
            patcher.start()
        self.role = {"role": "builder", "model": "m", "max_steps": 1, "timeout_s": 0.02,
                     "tools": [], "skills": []}

    def tearDown(self):
        for patcher in (self.event_patch, self.ws_patch, self.db_patch):
            patcher.stop()

    def test_accept_gets_configured_timeout_after_elapsed_role_timeout(self):
        ws = mock.Mock(host_accept=True)
        parsed = checker.AcceptParse(checker.AcceptSpec((sys.executable, "-c", "pass"), {}, "argument"), "")
        with mock.patch.object(server.checker, "check_deterministic", return_value={"passed": True}) as check, \
             mock.patch.object(config, "ACCEPT_TIMEOUT", 0.25):
            server._check(self.role, "Accept: x", "answer", 0, accept=parsed, ws=ws,
                          deadline_at=time.monotonic() + 30)
        self.assertEqual(check.call_args.kwargs["timeout"], 0.25)

    def test_skipped_accept_still_runs_checks_and_fails_out_of_time(self):
        ws = mock.Mock(host_accept=True)
        parsed = checker.AcceptParse(checker.AcceptSpec((sys.executable, "-c", "pass"), {}, "argument"), "")
        result = {"passed": True, "items": [{"name": "lint", "passed": True}]}
        with mock.patch.object(server.checker, "check_deterministic", return_value=result) as check, \
             mock.patch.object(config, "MIN_ACCEPT_S", 15):
            verdict = server._check(self.role, "Accept: x", "answer", 0, accept=parsed, ws=ws,
                                    deadline_at=time.monotonic() + 0.01)
        sent_parse = check.call_args.args[1]
        self.assertIsNone(sent_parse.spec)
        self.assertEqual(sent_parse.note, "out of time")
        self.assertFalse(verdict["passed"])
        self.assertEqual(verdict["stop"], Stop.OUT_OF_TIME)

    def test_short_budget_does_not_gate_diff_without_accept_command(self):
        ws = mock.Mock(host_accept=True)
        parsed = checker.AcceptParse(None, "no accept")
        diff = "diff --git a/a b/a\n"
        with mock.patch.object(server.checker, "check_deterministic", return_value={"passed": True}) as check, \
             mock.patch.object(config, "MIN_ACCEPT_S", 15):
            verdict = server._check(self.role, "task", f"```diff\n{diff}```", 0, accept=parsed, ws=ws,
                                    deadline_at=time.monotonic() + 0.01)
        self.assertIs(check.call_args.args[1], parsed)
        self.assertEqual(check.call_args.args[2], diff)
        self.assertTrue(verdict["passed"])

    def test_skipped_accept_does_not_get_a_correction_run(self):
        calls = []
        async def fake(*args, **kwargs):
            calls.append(args[2])
            return "answer", list(args[3] or [])
        verdict = {"passed": False, "stop": Stop.OUT_OF_TIME, "accept_note": "out of time",
                   "items": [{"name": "lint", "passed": False, "detail": "lint issue"},
                             {"name": "files_changed", "passed": True, "detail": "router/a.py"}]}
        tid = store.create("a", "builder", "skip accept")
        with (mock.patch.object(server, "run", fake),
              mock.patch.object(config, "deadline", return_value=100),
              mock.patch.object(server, "_check", return_value=verdict)):
            reply = asyncio.run(server._execute(tid, "a", self.role, "skip accept"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(store.get(tid)["error"], "lint: lint issue; accept: out of time")
        self.assertEqual(store.get(tid)["error_kind"], Stop.OUT_OF_TIME)
        self.assertIn("checks: FAILED (lint: lint issue; accept none: out of time)", reply)

    def test_deadline_expiry_returns_failed_and_emits_once(self):
        async def hang(*args, **kwargs):
            await asyncio.sleep(1)
        tid = store.create("a", "builder", "long")
        with mock.patch.object(server, "run", hang), mock.patch.object(config, "deadline", return_value=0.02):
            reply = asyncio.run(server._execute(tid, "a", self.role, "long"))
        self.assertIn("error_kind=out_of_time", reply)
        self.assertEqual(store.get(tid)["status"], "failed")
        self.assertEqual(sum(name == "task_failed" for name, _ in self.events), 1)

    def test_cancelled_execute_persists_failed_row(self):
        entered = asyncio.Event()
        accept_cancel = threading.Event()
        async def hang(*args, **kwargs):
            entered.set()
            await asyncio.sleep(30)
        async def scenario():
            tid = store.create("a", "builder", "cancel")
            with (mock.patch.object(server, "run", hang),
                  mock.patch.object(config, "deadline", return_value=30),
                  mock.patch.object(server, "threading", mock.Mock(Event=lambda: accept_cancel))):
                task = asyncio.create_task(server._execute(tid, "a", self.role, "cancel"))
                await entered.wait()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            return tid
        tid = asyncio.run(scenario())
        self.assertEqual(store.get(tid)["status"], "failed")
        self.assertEqual(store.get(tid)["error_kind"], "out_of_time")
        self.assertTrue(accept_cancel.is_set())
        self.assertEqual(sum(name == "task_failed" for name, _ in self.events), 1)

    def test_stray_timeout_from_check_is_normal_failure(self):
        tid = store.create("a", "builder", "check timeout")
        async def fake(*args, **kwargs):
            return "answer", []
        with mock.patch.object(server, "run", fake), mock.patch.object(config, "deadline", return_value=10), \
             mock.patch.object(server, "_check", side_effect=TimeoutError("check timeout")):
            asyncio.run(server._execute(tid, "a", self.role, "check timeout"))
        self.assertEqual(store.get(tid)["status"], "failed")
        self.assertEqual(sum(name == "task_failed" for name, _ in self.events), 1)

    def test_timeout_during_plan_after_success_keeps_done_row(self):
        tid = store.create("a", "builder", "success")
        async def fake(*args, **kwargs):
            return "answer", []
        async def slow(*args, **kwargs):
            await asyncio.sleep(3)
            return True, "ok"
        with mock.patch.object(server, "run", fake), mock.patch.object(config, "deadline", return_value=1), \
             mock.patch.object(server, "_check", return_value={"passed": True, "items": []}), \
             mock.patch.object(server, "_plan", slow):
            reply = asyncio.run(server._execute(tid, "a", self.role, "success", plan_id=1))
        self.assertEqual(store.get(tid)["status"], "done")
        self.assertEqual(sum(name == "task_failed" for name, _ in self.events), 0)
        self.assertIn("status=done", reply)

    def test_outside_cancel_during_plan_after_success_keeps_done_row(self):
        tid = store.create("a", "builder", "success")
        entered_plan = asyncio.Event()
        async def fake(*args, **kwargs):
            return "answer", []
        async def slow(*args, **kwargs):
            entered_plan.set()
            await asyncio.sleep(3)
            return True, "ok"
        async def scenario():
            with (mock.patch.object(server, "run", fake),
                  mock.patch.object(config, "deadline", return_value=1),
                  mock.patch.object(server, "_check", return_value={"passed": True, "items": []}),
                  mock.patch.object(server, "_plan", slow)):
                task = asyncio.create_task(server._execute(tid, "a", self.role, "success", plan_id=1))
                await entered_plan.wait()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
        asyncio.run(scenario())
        self.assertEqual(store.get(tid)["status"], "done")
        self.assertEqual(sum(name == "task_failed" for name, _ in self.events), 0)
    def test_cancel_error_distinguishes_external_cancel_from_deadline(self):
        entered = asyncio.Event()
        async def hang(*args, **kwargs):
            entered.set()
            await asyncio.sleep(30)
        async def outside_cancel():
            tid = store.create("a", "builder", "cancel")
            with mock.patch.object(server, "run", hang), mock.patch.object(config, "deadline", return_value=30):
                task = asyncio.create_task(server._execute(tid, "a", self.role, "cancel"))
                await entered.wait()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            return tid
        cancelled_tid = asyncio.run(outside_cancel())
        self.assertEqual(store.get(cancelled_tid)["error"], "task cancelled")

        timeout_tid = store.create("a", "builder", "deadline")
        with mock.patch.object(server, "run", hang), mock.patch.object(config, "deadline", return_value=0.02):
            asyncio.run(server._execute(timeout_tid, "a", self.role, "deadline"))
        self.assertIn("timed out", store.get(timeout_tid)["error"])

    def test_deadline_expiry_with_plan_returns_blocked_lines_and_records_failure(self):
        tid = store.create("a", "builder", "planned timeout")
        calls = []
        async def hang(*args, **kwargs):
            await asyncio.sleep(1)
        async def fake_plan(fn, *args):
            calls.append((fn, args))
            return (True, "ok")
        with mock.patch.object(server, "run", hang), \
             mock.patch.object(config, "deadline", return_value=0.02), \
             mock.patch.object(server, "_plan", fake_plan):
            reply = asyncio.run(server._execute(tid, "a", self.role, "planned timeout", plan_id=7))
        lines = reply.splitlines()
        self.assertTrue(lines[0].startswith("[" + tid + "] FAILED"), reply)
        self.assertEqual(lines[1], "checks: none (out of time)")
        self.assertIn("status=failed", lines[2])
        self.assertEqual([args[0] for _, args in calls], [7, 7])
        self.assertEqual(calls[0][1][4:6], ("failed", ""))
        self.assertEqual(calls[1][1][:4], (7, "blocked", "router", store.get(tid)["error"]))
    def test_accept_through_execute_gets_full_accept_timeout_after_long_run(self):
        key = os.path.normcase(os.path.realpath(self.tmp))
        role = dict(self.role, timeout_s=0.2)
        async def long_run(*args, **kwargs):
            await asyncio.sleep(0.15)  # most of the 0.2 s role timeout
            return "answer", []
        parsed = checker.AcceptParse(checker.AcceptSpec((sys.executable, "-c", "pass"), {}, "argument"), "")
        tid = store.create("a", "builder", "slow accept")
        with mock.patch.object(config, "HOST_ACCEPT_PATHS", {key}), \
             mock.patch.object(config, "ACCEPT_TIMEOUT", 0.25), \
             mock.patch.object(server, "run", long_run), \
             mock.patch.object(server.checker, "check_deterministic",
                               return_value={"passed": True, "items": []}) as check:
            asyncio.run(server._execute(tid, "a", role, "slow accept", accept=parsed))
        self.assertEqual(check.call_args.kwargs["timeout"], 0.25)
        self.assertEqual(store.get(tid)["status"], "done")

    def test_correction_is_skipped_below_floor(self):
        # This test covers the correction budget floor; the correction requires a write-capable role.
        self.role["tools"] = ["write_file"]
        calls = []
        async def fake(*args, **kwargs):
            calls.append(args[2])
            return "answer", list(args[3] or [])
        verdict = {"passed": False, "items": [{"name": "accept", "passed": False, "detail": "failed"}]}
        tid = store.create("a", "builder", "fix it")
        with (mock.patch.object(server, "run", fake),
              mock.patch.object(config, "deadline", return_value=100),
              mock.patch.object(server, "_check", return_value=verdict)):
            reply = asyncio.run(server._execute(tid, "a", self.role, "fix it"))
        self.assertEqual(len(calls), 1)
        self.assertEqual(store.get(tid)["error"], "accept: failed; no time for a correction run")
        self.assertIn("checks: FAILED (accept: failed)", reply)
        self.assertIn("error_kind=out_of_time", reply)


if __name__ == "__main__":
    unittest.main()



