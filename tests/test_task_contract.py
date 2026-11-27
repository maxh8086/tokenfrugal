import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from router import checker, server, store


class TaskContractTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.tmp.name)
        self.db_patch = mock.patch.object(store, "DB_PATH", self.root / "tasks.db")
        self.db_patch.start()
        self.ws_patch = mock.patch.object(server, "WORKSPACE", str(self.root))
        self.ws_patch.start()

    def tearDown(self):
        self.ws_patch.stop()
        self.db_patch.stop()
        self.tmp.cleanup()

    def test_dispatch_persists_task_contract_metadata(self):
        parsed = checker.AcceptParse(checker.AcceptSpec(("pytest", "-q"), {}, "argument"))
        role = {"role": "builder", "tools": ["write_file"], "model": "test"}
        with mock.patch.object(server, "task_error", return_value=None), \
             mock.patch.object(server, "resolve_role", return_value=role), \
             mock.patch.object(server.checker, "parse_accept", return_value=parsed), \
             mock.patch.object(server, "_plan", new=mock.AsyncMock(return_value=(True, ""))), \
             mock.patch.object(store, "with_templates", return_value="rendered prompt") as templates, \
             mock.patch.object(server, "_execute", new=mock.AsyncMock(return_value="ok")):
            with mock.patch.object(store, "create", wraps=store.create) as create:
                reply = asyncio.run(server.dispatch_task(agent="builder", task="do thing", task_type="fix bug", plan_id=7,
                                                         accept="pytest -q"))
        self.assertEqual(reply, "ok")
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["task_type"], "fix bug")
        self.assertEqual(kwargs["prompt_sent"], "rendered prompt")
        self.assertEqual(kwargs["contract_json"], {"accept": parsed.spec.to_json(), "packet": None})
        self.assertEqual(kwargs["workspace"], os.path.normcase(os.path.realpath(self.root)))
        self.assertEqual(kwargs["plan_id"], 7)
        self.assertEqual(kwargs["kind"], "edit")
        templates.assert_called_once()

    def test_resume_uses_stored_accept_and_prompt_without_retemplating(self):
        accept_json = {"argv": ["pytest", "-q"], "env": {"A": "b"}, "source": "argument"}
        tid = store.create("builder", "builder", "original task", task_type="fix bug",
                           prompt_sent="stored prompt", contract_json={"accept": accept_json, "packet": None},
                           workspace=os.path.normcase(os.path.realpath(self.root)), plan_id=7, kind="edit")
        store.update(tid, status="failed", messages=[{"role": "assistant", "content": "old result"}])
        with mock.patch.object(server, "resolve_role", return_value={"role": "builder"}), \
             mock.patch.object(store, "with_templates") as templates, \
             mock.patch.object(server, "_execute", new=mock.AsyncMock(return_value="resumed")) as execute:
            self.assertEqual(asyncio.run(server.resume_task(tid)), "resumed")
        templates.assert_not_called()
        self.assertEqual(execute.call_args.args[3], "stored prompt")
        self.assertEqual(execute.call_args.kwargs["plan_id"], 7)
        self.assertEqual(execute.call_args.kwargs["task_text"], "original task")
        self.assertEqual(execute.call_args.kwargs["accept"].spec, checker.AcceptSpec.from_json(accept_json))

    def test_resume_stored_null_accept_never_uses_task_line_command(self):
        tid = store.create("builder", "builder", "Accept: destructive-command\ntask",
                           contract_json={"accept": None, "packet": None},
                           workspace=os.path.normcase(os.path.realpath(self.root)))
        store.update(tid, status="failed")
        parsed_spec = checker.AcceptParse(checker.AcceptSpec(("destructive-command",), {}, "task_line"))
        with mock.patch.object(server, "resolve_role", return_value={"role": "builder"}), \
             mock.patch.object(server.checker, "accept_from_task", return_value=parsed_spec) as parse, \
             mock.patch.object(server, "_execute", new=mock.AsyncMock(return_value="ok")) as execute:
            asyncio.run(server.resume_task(tid))
        parse.assert_called_once()
        self.assertEqual(execute.call_args.kwargs["accept"], checker.AcceptParse(None, "no accept"))

    def test_resume_followup_child_disables_checks_and_correction(self):
        tid = store.create("builder", "builder", "question", parent_id="parent",
                           workspace=os.path.normcase(os.path.realpath(self.root)))
        store.update(tid, status="failed")
        with mock.patch.object(server, "resolve_role", return_value={"role": "builder"}), \
             mock.patch.object(server, "_execute", new=mock.AsyncMock(return_value="ok")) as execute:
            asyncio.run(server.resume_task(tid))
        self.assertFalse(execute.call_args.kwargs["checks"])
        self.assertFalse(execute.call_args.kwargs["correction"])

    def test_legacy_null_columns_use_documented_fallbacks(self):
        task = "Accept: python -m unittest\nlegacy task"
        tid = store.create("builder", "builder", task)
        store.update(tid, status="failed")
        with mock.patch.object(server, "resolve_role", return_value={"role": "builder"}), \
             mock.patch.object(server, "_execute", new=mock.AsyncMock(return_value="ok")) as execute:
            asyncio.run(server.resume_task(tid))
        self.assertEqual(execute.call_args.args[3], task)
        self.assertEqual(execute.call_args.kwargs["plan_id"], 0)
        self.assertEqual(execute.call_args.kwargs["task_text"], task)
        self.assertEqual(execute.call_args.kwargs["accept"].spec.argv, ("python", "-m", "unittest"))
        self.assertEqual(execute.call_args.kwargs["accept"].spec.source, "task_line")

    def test_resume_refuses_running_task(self):
        tid = store.create("builder", "builder", "task")
        with mock.patch.object(server, "_execute", new=mock.AsyncMock()) as execute:
            reply = asyncio.run(server.resume_task(tid))
        self.assertIn("running", reply.lower())
        execute.assert_not_awaited()

    def test_resume_refuses_different_workspace_and_names_both(self):
        old = os.path.normcase(os.path.realpath(self.root / "old"))
        current = os.path.normcase(os.path.realpath(self.root))
        tid = store.create("builder", "builder", "task", workspace=old)
        store.update(tid, status="failed")
        with mock.patch.object(server, "_execute", new=mock.AsyncMock()) as execute:
            reply = asyncio.run(server.resume_task(tid))
        self.assertIn(old, reply)
        self.assertIn(current, reply)
        execute.assert_not_awaited()

    def test_followup_refuses_failed_task(self):
        tid = store.create("builder", "builder", "task")
        store.update(tid, status="failed", messages=[{"role": "assistant", "content": "old"}])
        with mock.patch.object(server, "_execute", new=mock.AsyncMock()) as execute:
            reply = asyncio.run(server.ask_followup(tid, "why?"))
        self.assertIn("done", reply.lower())
        execute.assert_not_awaited()

    def test_followup_creates_child_without_changing_parent(self):
        tid = store.create("builder", "builder", "task", task_type="fix bug", workspace="/tmp/ws", kind="edit")
        store.update(tid, status="done", outcome="done", summary="parent summary",
                     messages=[{"role": "assistant", "content": "parent answer"}])
        role = {"role": "builder"}
        with mock.patch.object(server, "resolve_role", return_value=role), \
             mock.patch.object(server, "_execute", new=mock.AsyncMock(return_value="child result")) as execute:
            self.assertEqual(asyncio.run(server.ask_followup(tid, "why?")), "child result")
        parent = store.get(tid)
        child_id = execute.call_args.args[0]
        child = store.get(child_id)
        self.assertNotEqual(child_id, tid)
        self.assertEqual(child["parent_id"], tid)
        self.assertEqual((child["agent"], child["task_type"], child["workspace"], child["kind"]),
                         (parent["agent"], parent["task_type"], parent["workspace"], "analyze"))
        self.assertEqual(child["prompt"], "why?")
        self.assertEqual(execute.call_args.kwargs, {"task_text": "why?", "checks": False, "correction": False})
        self.assertEqual(parent["status"], "done")
        self.assertEqual(parent["outcome"], "done")
        self.assertEqual(parent["summary"], "parent summary")
        self.assertEqual(parent["messages"], [{"role": "assistant", "content": "parent answer"}])

    def test_get_detail_shows_error_and_messages_when_detail_missing(self):
        tid = store.create("builder", "builder", "task")
        store.update(tid, status="failed", error="boom", messages=[
            {"role": "user", "content": "first"}, {"role": "assistant", "content": "second"}])
        self.assertEqual(server.get_detail(tid), "boom\nuser: first\nassistant: second")

    def test_dispatch_stores_effective_task_accept_when_argument_omitted(self):
        parsed = checker.AcceptParse(checker.AcceptSpec(("pytest", "-q"), {}, "task_line"))
        role = {"role": "builder", "tools": ["write_file"], "model": "test"}
        with mock.patch.object(server, "task_error", return_value=None), \
             mock.patch.object(server, "resolve_role", return_value=role), \
             mock.patch.object(server.checker, "accept_from_task", return_value=parsed), \
             mock.patch.object(store, "with_templates", return_value="rendered"), \
             mock.patch.object(server, "_execute", new=mock.AsyncMock(return_value="ok")):
            with mock.patch.object(store, "create", wraps=store.create) as create:
                asyncio.run(server.dispatch_task(agent="builder", task="Accept: pytest -q", task_type="fix bug"))
        self.assertEqual(create.call_args.kwargs["contract_json"]["accept"], parsed.spec.to_json())

    def test_failed_execution_persists_messages_from_exception(self):
        tid = store.create("builder", "builder", "task")
        failure_messages = [{"role": "assistant", "content": "partial answer"}]

        async def fail_run(*args, **kwargs):
            error = RuntimeError("model failed")
            error.msgs = failure_messages
            raise error

        ws = SimpleNamespace(host_accept=True)
        role = {"role": "builder", "model": "test", "max_steps": 2, "tools": [], "skills": []}
        with mock.patch.object(server.workspace, "load_workspace", return_value=ws), \
             mock.patch.object(server.workspace, "to_rel", side_effect=lambda p, *_: p), \
             mock.patch.object(server.workspace, "denied", return_value=False), \
             mock.patch.object(server.gpu_lease, "guard_ollama"), \
             mock.patch.object(server, "run", side_effect=fail_run):
            asyncio.run(server._execute(tid, "builder", role, "task"))
        self.assertEqual(store.get(tid)["messages"], failure_messages)

    def test_failed_execution_persists_leaf_messages_from_exception_group(self):
        tid = store.create("builder", "builder", "task")
        failure_messages = [{"role": "assistant", "content": "group failure"}]

        async def fail_run(*args, **kwargs):
            error = RuntimeError("wrapped failure")
            error.msgs = failure_messages
            raise ExceptionGroup("x", [error])

        ws = SimpleNamespace(host_accept=True)
        role = {"role": "builder", "model": "test", "max_steps": 2, "tools": [], "skills": []}
        with mock.patch.object(server.workspace, "load_workspace", return_value=ws), \
             mock.patch.object(server.workspace, "to_rel", side_effect=lambda p, *_: p), \
             mock.patch.object(server.workspace, "denied", return_value=False), \
             mock.patch.object(server.gpu_lease, "guard_ollama"), \
             mock.patch.object(server, "run", side_effect=fail_run):
            asyncio.run(server._execute(tid, "builder", role, "task"))
        self.assertEqual(store.get(tid)["messages"], failure_messages)

    def test_cancelled_execution_persists_messages_attached_to_cancel(self):
        tid = store.create("builder", "builder", "task")
        failure_messages = [{"role": "assistant", "content": "cancelled response"}]
        entered = []

        async def cancel_run(*args, **kwargs):
            entered.append(True)
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError as exc:
                exc.msgs = failure_messages
                raise

        ws = SimpleNamespace(host_accept=True)
        role = {"role": "builder", "model": "test", "max_steps": 2, "tools": [], "skills": []}
        baseline = checker.Baseline("hash", None, {}, False)
        with mock.patch.object(server.workspace, "load_workspace", return_value=ws), \
             mock.patch.object(server.workspace, "to_rel", side_effect=lambda p, *_: p), \
             mock.patch.object(server.workspace, "denied", return_value=False), \
             mock.patch.object(server, "role_timeout", return_value=1), \
             mock.patch.object(server.config, "deadline", return_value=1), \
             mock.patch.object(server.checker, "baseline", return_value=baseline), \
             mock.patch.object(server.gpu_lease, "guard_ollama"), \
             mock.patch.object(server, "run", side_effect=cancel_run):
            asyncio.run(server._execute(tid, "builder", role, "task"))
        self.assertEqual(entered, [True], "the patched run was never entered")
        self.assertEqual(store.get(tid)["messages"], failure_messages)

    def test_get_detail_handles_null_tool_call_content(self):
        tid = store.create("builder", "builder", "task")
        store.update(tid, status="failed", messages=[{"role": "assistant", "content": None}])
        self.assertEqual(server.get_detail(tid), "assistant: ")

    def test_failed_correction_persists_correction_messages(self):
        tid = store.create("builder", "builder", "task")
        first = [{"role": "assistant", "content": "first response"}]
        corrected = [{"role": "assistant", "content": "corrected response"}]
        runs = [("first", first), ("corrected", corrected)]

        async def fake_run(*args, **kwargs):
            return runs.pop(0)

        failed = {"passed": False, "items": [{"name": "accept", "passed": False, "detail": "rejected"}]}
        ws = SimpleNamespace(host_accept=True)
        role = {"role": "builder", "model": "test", "max_steps": 2, "tools": ["write_file"], "skills": []}
        with mock.patch.object(server.workspace, "load_workspace", return_value=ws), \
             mock.patch.object(server.workspace, "to_rel", side_effect=lambda p, *_: p), \
             mock.patch.object(server.workspace, "denied", return_value=False), \
             mock.patch.object(server.gpu_lease, "guard_ollama"), \
             mock.patch.object(server, "run", side_effect=fake_run), \
             mock.patch.object(server, "_check", side_effect=[failed, failed]), \
             mock.patch.object(server, "_can_write", return_value=True):
            reply = asyncio.run(server._execute(tid, "builder", role, "task"))
        self.assertIn("rejected", reply)
        self.assertEqual(store.get(tid)["messages"], corrected)

    def test_followup_child_runs_with_parent_history_and_question(self):
        tid = store.create("builder", "builder", "task", workspace="/tmp/ws", kind="edit")
        history = [{"role": "assistant", "content": "parent answer"}]
        store.update(tid, status="done", outcome="done", summary="s", messages=history)
        with mock.patch.object(server, "resolve_role", return_value={"role": "builder"}), \
             mock.patch.object(server, "_execute", new=mock.AsyncMock(return_value="child result")) as execute:
            asyncio.run(server.ask_followup(tid, "why?"))
        self.assertEqual(execute.call_args.args[4], history + [{"role": "user", "content": "why?"}])
        self.assertEqual(store.get(tid)["messages"], history)

    def test_resume_runs_done_task(self):
        tid = store.create("builder", "builder", "task", workspace=os.path.normcase(os.path.realpath(self.root)))
        store.update(tid, status="done", outcome="done")
        with mock.patch.object(server, "resolve_role", return_value={"role": "builder"}), \
             mock.patch.object(server, "_execute", new=mock.AsyncMock(return_value="again")) as execute:
            self.assertEqual(asyncio.run(server.resume_task(tid)), "again")
        execute.assert_awaited_once()

    def test_get_detail_without_error_lists_messages_in_stored_order(self):
        tid = store.create("builder", "builder", "task")
        store.update(tid, status="done", messages=[{"role": "user", "content": "a"},
                                                   {"role": "assistant", "content": "b"}])
        self.assertEqual(server.get_detail(tid), "user: a\nassistant: b")

    def test_get_detail_prefers_stored_detail_over_messages(self):
        tid = store.create("builder", "builder", "task")
        store.update(tid, status="done", detail="full text",
                     messages=[{"role": "assistant", "content": "ignored"}])
        self.assertEqual(server.get_detail(tid), "full text")

    def test_get_detail_cuts_head_to_max_chars(self):
        tid = store.create("builder", "builder", "task")
        store.update(tid, status="failed", error="e" * 50)
        self.assertEqual(server.get_detail(tid, max_chars=10), "e" * 10)


if __name__ == "__main__":
    unittest.main()
