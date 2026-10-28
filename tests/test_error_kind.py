"""error_kind on failed tasks: classification, the tool-call counter, the store migration, and the FAILED hint per kind.

Model and MCP calls are mocked; no live model is used."""
import asyncio
import contextlib
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import openai

from router import events, loop, server, store

PARAMS = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
TOOLS = [{"type": "function", "function": {"name": "read_file", "parameters": PARAMS}}]


def _reply(content=None, tool_call=None):
    calls = [tool_call] if tool_call else None
    msg = SimpleNamespace(content=content, tool_calls=calls, reasoning_content=None, reasoning=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)


def _call(i):
    fn = SimpleNamespace(name="read_file", arguments='{"path": "/workspace/a.py"}')
    return SimpleNamespace(id=f"c{i}", function=fn)


class _Session:
    async def list_tools(self):
        return SimpleNamespace(tools=[])

    async def call_tool(self, name, args):
        return SimpleNamespace(isError=False, content=[])


@contextlib.asynccontextmanager
async def _open_role(*a, **k):
    yield _Session()


@contextlib.asynccontextmanager
async def _no_backends(*a, **k):
    yield


def _scripted(items):
    """Model stand-in: each item is a reply, an exception to raise, or a callable run on call (e.g. to sleep)."""
    it = iter(items)

    def create(**kw):
        item = next(it)
        if callable(item):
            return item()
        if isinstance(item, BaseException):
            raise item
        return item
    return create


def _patches(create):
    return [
        mock.patch.object(loop, "backends", _no_backends),
        mock.patch.object(loop, "open_role", _open_role),
        mock.patch.object(loop, "to_openai_tools", lambda *a, **k: TOOLS),
        mock.patch.object(loop, "result_text", lambda res: "file body"),
        mock.patch.object(loop, "_count", lambda *a, **k: None),
        mock.patch.object(loop.events, "emit", lambda *a, **k: None),
        mock.patch.object(loop._client.chat.completions, "create", mock.Mock(side_effect=create)),
    ]


def _run_sync(items, role_extra=None, tid="kind1"):
    role = {"role": "reviewer", "model": "m", "tools": ["read_file"], "max_steps": 4}
    role.update(role_extra or {})
    patches = _patches(_scripted(items))
    for p in patches:
        p.start()
    try:
        return asyncio.run(loop.run("reviewer", role, "check", None, tid))
    finally:
        for p in reversed(patches):
            p.stop()


class Classify(unittest.TestCase):
    def test_step_timeout_is_the_role_time_limit(self):
        self.assertEqual(loop.error_kind("LoopError: task timed out after 300s"), "step_timeout")

    def test_request_timeout_is_one_model_request(self):
        self.assertEqual(loop.error_kind("APITimeoutError: Request timed out."), "request_timeout")

    def test_no_tool_call(self):
        self.assertEqual(loop.error_kind(
            "LoopError: you answered without calling any tool; call a tool to read real data first"), "no_tool_call")

    def test_max_steps(self):
        self.assertEqual(loop.error_kind("LoopError: no final answer in 12 steps"), "max_steps")

    def test_everything_else_is_error(self):
        for text in ("ValueError: something else", "MCPError: Connection closed",
                     "LoopError: empty answer", ""):
            self.assertEqual(loop.error_kind(text), "error", text)

    def test_infra_text_is_infra_kind(self):
        for text in ("LoopError: infra: Error code: 500 - internal error", "infra: task timed out after 5s, Connection closed"):
            self.assertEqual(loop.error_kind(text), "infra", text)

    def test_timeout_error_class_is_request_timeout(self):
        self.assertEqual(loop.failure_reason("TimeoutError: slow"), "timeout")
        self.assertEqual(loop.error_kind("TimeoutError: slow"), "request_timeout")


class ToolCallCounter(unittest.TestCase):
    def test_counts_tool_calls_sent_to_the_server(self):
        items = [_reply(tool_call=_call(1)), _reply(tool_call=_call(2)), _reply(content="Final: fine.")]
        out = _run_sync(items, tid="cnt1")
        self.assertEqual(out[0], "Final: fine.")  # run() returns (answer, messages)
        self.assertEqual(loop.take_started("cnt1"), 2)
        self.assertEqual(loop.take_started("cnt1"), 0)  # taken once, then cleared

    def test_timeout_keeps_the_count_made_before_it(self):
        def slow():
            time.sleep(0.6)
            return _reply(content="late")
        items = [_reply(tool_call=_call(1)), slow]
        with self.assertRaises(loop.LoopError) as cm:
            _run_sync(items, role_extra={"timeout_s": 0.2}, tid="cnt2")
        self.assertIn("task timed out", str(cm.exception))
        self.assertEqual(loop.take_started("cnt2"), 1)
        self.assertEqual(loop.error_kind(f"LoopError: {cm.exception}"), "step_timeout")

    def test_run_resets_the_count(self):
        loop.STARTED["reset1"] = 7
        with self.assertRaises(loop.LoopError):
            _run_sync([_reply(content="I cannot read files.")] * 3, tid="reset1")
        self.assertEqual(loop.take_started("reset1"), 0)


class StoreMigration(unittest.TestCase):
    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "old.db"
        c = sqlite3.connect(self.path)  # schema from before trail, heartbeat and error_kind
        c.execute("""CREATE TABLE tasks(id TEXT PRIMARY KEY, agent TEXT, role TEXT, prompt TEXT, status TEXT,
            summary TEXT, detail TEXT, messages TEXT, error TEXT, attempts INTEGER DEFAULT 0)""")
        c.execute("INSERT INTO tasks(id,agent,role,prompt,status) VALUES('old1','a','builder','p','failed')")
        c.commit()
        c.close()
        self.patch = mock.patch.object(store, "DB_PATH", self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_column_added_to_old_db_and_value_round_trips(self):
        self.assertIsNone(store.get("old1")["error_kind"])
        with store._db() as c:
            cols = [r[1] for r in c.execute("PRAGMA table_info(tasks)")]
        self.assertIn("error_kind", cols)
        store.update("old1", status="failed", error_kind="max_steps")
        self.assertEqual(store.get("old1")["error_kind"], "max_steps")

    def test_migration_is_idempotent(self):
        store._db()
        store._db()
        store.update("old1", error_kind="request_timeout")
        self.assertEqual(store.get("old1")["error_kind"], "request_timeout")

    def test_sweep_marks_stale_rows_as_error(self):
        tid = store.create("a", "builder", "p")
        store.update(tid, heartbeat=0.0)
        self.assertEqual(store.sweep_stale("gone"), 1)
        self.assertEqual(store.get(tid)["error_kind"], "error")


class Hints(unittest.TestCase):
    role = {"role": "analyze", "model": "m"}

    def msg(self, kind, started=0, reason="timeout"):
        return server.failure_message("t1", self.role, "LoopError: x", reason, kind, started)

    def test_timeout_before_any_tool_call(self):
        for kind in ("step_timeout", "request_timeout"):
            self.assertTrue(self.msg(kind, 0).endswith(
                "Timed out before any tool call. Split the task into smaller tasks. Do not resume_task."), kind)

    def test_timeout_after_tool_calls(self):
        for kind in ("step_timeout", "request_timeout"):
            self.assertTrue(self.msg(kind, 3).endswith(
                "Timed out after 3 tool calls. Call resume_task once, or split the task."), kind)

    def test_no_tool_call(self):
        self.assertTrue(self.msg("no_tool_call", 0, "no-tool-call").endswith(
            "The model answered without calling a tool. Name the exact tool and path in the task."))

    def test_max_steps(self):
        self.assertTrue(self.msg("max_steps", 5, "out-of-steps").endswith(
            "Step budget used up. Narrow the scope of the task."))

    def test_error_has_no_kind_hint(self):
        msg = self.msg("error", 0, "infra")
        self.assertTrue(msg.endswith("Call resume_task('t1') to retry."), msg)
        self.assertIn("error_kind=error", msg)

    def test_kind_is_in_reply(self):
        self.assertIn("reason=timeout error_kind=request_timeout:", self.msg("request_timeout", 0))


class ExecuteEndToEnd(unittest.TestCase):
    """A real run with a mocked model: one tool call, then the model request times out."""

    def setUp(self):
        self.path = Path(tempfile.mkdtemp()) / "e2e.db"
        self.patch = mock.patch.object(store, "DB_PATH", self.path)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()

    def test_request_timeout_after_one_tool_call(self):
        timeout = openai.APITimeoutError(request=None)  # str is "Request timed out.", as the SDK raises it
        emitted = []
        role = {"role": "builder", "model": "m", "tools": ["read_file"], "skills": [], "max_steps": 4}
        tid = store.create("builder-agent", "builder", "check")
        patches = _patches(_scripted([_reply(tool_call=_call(1)), timeout]))
        # loop.events and server.events are the same module: one patch covers both, so nothing is left behind
        patches[5] = mock.patch.object(events, "emit", lambda kind, **kw: emitted.append((kind, kw)))
        for p in patches:
            p.start()
        try:
            reply = asyncio.run(server._execute(tid, "builder-agent", role, "check"))
        finally:
            for p in reversed(patches):
                p.stop()
        self.assertIn("FAILED (builder/m) reason=timeout error_kind=request_timeout", reply)
        self.assertIn("Timed out after 1 tool calls. Call resume_task once, or split the task.", reply)
        self.assertRegex(reply.splitlines()[-1], r"^status=failed role=builder model=m calls=1 elapsed=\d+\.\d+s$")
        row = store.get(tid)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["error_kind"], "request_timeout")
        failed = [kw for kind, kw in emitted if kind == "task_failed"]
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["error_kind"], "request_timeout")
        self.assertEqual(loop.take_started(tid), 0)  # cleared by the router after the failure


if __name__ == "__main__":
    unittest.main()
