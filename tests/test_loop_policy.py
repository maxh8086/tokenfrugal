import asyncio
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from router import checker, loop, server, store
from router.loop_policy import AcceptPolicy
from router.outcomes import Stop
from tests import test_checker_stage as stage
from tests import test_forced_answer as forced


def result(ok):
    return checker.AcceptResult(ok, int(not ok), 0, "" if ok else "bad file", "", "", None if ok else "accept_failed")


class PolicyTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_and_dry_run_edits_do_not_count_as_writes(self):
        for extra, output in [({}, "tool error: denied"), ({"dryRun": True}, "preview")]:
            with self.subTest(extra=extra, output=output):
                accept = mock.Mock(return_value=result(True))
                policy = AcceptPolicy(["a", "b"], accept, loop.Budget(5))
                await policy.after_tool("edit_file", {"path": "a", **extra}, output)
                await policy.after_tool("write_file", {"path": "b"}, "ok")
                accept.assert_not_called()
                self.assertEqual(await policy.after_tool("write_file", {"path": "a"}, "ok"),
                                 "ok\naccept: PASS")
                for _ in range(2):
                    self.assertIsNone(policy.before_call("read", {}))
                await policy.after_tool("edit_file", {"path": "a", **extra}, output)
                self.assertFalse(policy.stale)
                self.assertIsNotNone(policy.before_call("read", {}))
                accept.assert_called_once_with()

    async def test_repeat_guard(self):
        policy = AcceptPolicy(["a"], lambda: result(True), loop.Budget(5))
        for _ in range(2):
            self.assertIsNone(policy.before_call("read", {"a": 1, "b": 2}))
        await policy.after_tool("write_file", {"path": "other"}, "ok")
        for _ in range(2):
            self.assertIsNone(policy.before_call("read", {"b": 2, "a": 1}))
        await policy.after_tool("edit_file", {"path": "other"}, "tool error: denied")
        self.assertEqual(policy.before_call("read", {"a": 1, "b": 2}),
                         "tool error: same call repeated 3 times with no write; change approach")
        self.assertEqual(policy.stop(), Stop.REPEAT_GUARD)

    async def test_all_files_and_budget(self):
        tick = threading.Event()
        event_loop = asyncio.get_running_loop()
        clock = self.enterContext(mock.patch.object(loop, "time")).monotonic
        clock.return_value = 10
        budget = loop.Budget(5)
        def accept():
            spent = budget.spent()
            clock.return_value = 30
            event_loop.call_soon_threadsafe(tick.set)
            self.assertTrue(tick.wait(2))
            self.assertEqual(spent, budget.spent())
            return result(False)
        policy = AcceptPolicy(["a", "b"], accept, budget)
        self.assertEqual(await policy.after_tool("edit_file", {"path": "a"}, "ok"), "ok")
        self.assertFalse(tick.is_set())
        out = await policy.after_tool("move_file", {"source": "c", "destination": "b"}, "ok")
        self.assertEqual(out, "ok\naccept: FAIL bad file")
        clock.return_value = 31
        self.assertEqual(budget.remaining(), 4)
        self.assertFalse(policy.stale)
        self.assertEqual(await policy.after_tool("write_file", {"path": "a"}, "ok"), "ok")
        self.assertTrue(policy.stale)

    async def test_guard_trail_and_accept_precede_forcing(self):
        for name, max_steps in [("read_file", 4), ("write_file", 2), ("write_file", 1)]:
            policy = AcceptPolicy(["/workspace/a.py"], lambda: result(True), loop.Budget(5))
            calls = [forced._call(i) for i in range(3 if name == "read_file" else 1)]
            for call in calls:
                call.function.name = name
            replies = [forced._reply(tool_call=c) for c in calls] + [forced._reply("finished")]
            role = dict(role="builder", model="m", tools=[name], max_steps=max_steps)
            messages = [{"role": "user", "content": "work"}]
            with ExitStack() as stack:
                for attr, value in [("open_role", forced._open_role), ("backends", forced._no_backends),
                                    ("to_openai_tools", lambda *a: [{"function": {"name": name, "parameters": forced.PARAMS}}]),
                                    ("result_text", lambda r: "ok"), ("lint_written", lambda p: "")]:
                    stack.enter_context(mock.patch.object(loop, attr, value))
                stack.enter_context(mock.patch.object(loop.events, "emit"))
                stack.enter_context(mock.patch.object(loop.mcp_reap, "sweep"))
                create = stack.enter_context(mock.patch.object(loop._client.chat.completions, "create", side_effect=replies))
                if name == "read_file":
                    with self.assertRaises(loop.LoopError) as raised:
                        await loop._run("b", role, messages, "t", policy=policy)
                    self.assertEqual(raised.exception.stop, Stop.REPEAT_GUARD)
                    self.assertEqual(create.call_count, 3)
                    self.assertEqual(messages[-1], {"role": "tool", "tool_call_id": "c2", "content":
                                     "tool error: same call repeated 3 times with no write; change approach"})
                else:
                    answer, _ = await loop._run("b", role, messages, "t", policy=policy)
                    self.assertEqual(answer, "finished")
                    self.assertEqual(create.call_count, 2)
                    self.assertIn("tools", create.call_args.kwargs)
                    self.assertTrue(any("accept: PASS" in m.get("content", "") for m in messages))


class DispatchTests(unittest.TestCase):
    configure_commits = False
    setUp = stage.StageTest.setUp
    tearDown = stage.StageTest.tearDown

    def dispatch(self, first, later, expected_reads, expected_status):
        path = Path(self.repo, "target.txt")
        reads = []
        policies = []
        async def model(*args, policy=None, **kwargs):
            policies.append(policy)
            if len(policies) == 1:
                path.write_text(first)
                await policy.after_tool("write_file", {"path": "/workspace/target.txt"}, "ok")
                if later:
                    path.write_text(later)
                    await policy.after_tool("edit_file", {"path": "/workspace/target.txt"}, "ok")
            else:
                self.assertIsNone(policy)
                path.write_text("good")
            return "finished", []
        def accept(*args, **kwargs):
            reads.append(path.read_text())
            return result(reads[-1] == "good")
        with mock.patch.object(checker, "run_accept_spec", side_effect=accept):
            tid, reply = stage.StageTest._run(self, model, "write target.txt\nAccept: python -V")
        self.assertEqual(reads, expected_reads, reply)
        self.assertLessEqual(len(reads), server.config.MAX_ACCEPT_RUNS)
        row = store.get(tid)
        self.assertEqual(row["status"], expected_status)
        self.assertEqual(len(policies), 2 if first == "bad" else 1)
        if later:
            self.assertEqual(row["error_kind"], Stop.ACCEPT_FAILED)

    def test_pass_reused(self):
        self.dispatch("good", None, ["good"], "done")

    def test_stale_pass_fails_without_correction(self):
        self.dispatch("good", "bad", ["good", "bad"], "failed")

    def test_fail_reused_then_correction_checked(self):
        self.dispatch("bad", None, ["bad", "good"], "done")

    def test_missing_file_defers_accept(self):
        async def model(*args, policy, **kwargs):
            for name in ("a.txt", "b.txt"):
                out = await policy.after_tool("write_file", {"path": name}, "ok")
                self.assertEqual(out, "ok")
            for name in ("a.txt", "b.txt"):
                Path(self.repo, name).touch()
            self.assertEqual(await policy.after_tool("edit_file", {"path": "b.txt"}, "ok"), "ok\naccept: PASS")
            return "finished", []
        with mock.patch.object(checker, "run_accept_spec", return_value=result(True)) as accept:
            tid, reply = stage.StageTest._run(self, model, "write a.txt and b.txt\nAccept: python -V")
        self.assertEqual(store.get(tid)["status"], "done", reply)
        accept.assert_called_once()
