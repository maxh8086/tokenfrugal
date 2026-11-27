"""Step 8a wiring: saved baselines and lint scoped to changed files."""
import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from router import checker, config, events, server, store


class VerifiedCompletionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = Path(self.tmp) / "tasks.db"
        self.workspace = Path(self.tmp) / "workspace"
        self.workspace.mkdir()
        self.patches = [
            mock.patch.object(store, "DB_PATH", self.db),
            mock.patch.object(server, "WORKSPACE", str(self.workspace)),
            mock.patch.object(events, "emit", lambda *args, **kwargs: None),
        ]
        for patcher in self.patches:
            patcher.start()
        self.role = {"role": "builder", "model": "fake", "max_steps": 2,
                     "timeout_s": 60, "tools": ["write_file"], "skills": []}

    def tearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()

    def test_legacy_no_change_check_passes_and_lints_only_changed_files(self):
        ws = mock.Mock(root=str(self.workspace))
        (self.workspace / "changed.py").touch()
        changes = checker.Changes(("changed.py",), ("changed.py",), (), (), False)
        with mock.patch.object(checker, "lint_python", return_value=[]) as lint:
            result = checker.check_deterministic(ws, None, None, 1, changes=changes)
        self.assertTrue(result["passed"])
        self.assertEqual(lint.call_args.args[0], ["changed.py"])
        item = next(i for i in result["items"] if i["name"] == "files_changed")
        self.assertTrue(item["passed"])
        self.assertEqual(item["detail"], "changed.py")

    def test_dispatch_snapshots_the_test_workspace(self):
        tid = store.create("builder-agent", "builder", "check workspace")
        with mock.patch.object(checker, "baseline", side_effect=RuntimeError("snapshot intercepted")) as snapshot:
            reply = asyncio.run(server._execute(tid, "builder-agent", self.role, "check workspace"))
            self.assertIn("snapshot intercepted", reply)
        self.assertEqual(Path(snapshot.call_args.args[0].root), self.workspace)

    def test_deleted_python_file_is_listed_but_does_not_count_as_linted(self):
        ws = mock.Mock(root=str(self.workspace))
        changed = checker.Changes(("gone.py",), (), (), (), False)
        verdict = checker.check_deterministic(ws, checker.AcceptParse(None, "host accept off"),
                                              None, 1, changes=changed)
        self.assertIn("checks: none (host accept off)", server._report(verdict, self.role))
        self.assertEqual(checker.manifest_from(changed, False), "files_changed: gone.py")

    def test_legacy_no_change_is_not_failed_by_deterministic_checks(self):
        ws = mock.Mock(root=str(self.workspace))
        empty = checker.Changes((), (), (), (), False)
        with mock.patch.object(checker, "lint_python", return_value=[]) as lint:
            result = checker.check_deterministic(ws, None, None, 1, changes=empty)
        self.assertTrue(result["passed"])
        self.assertEqual(lint.call_args.args[0], [])
        item = next(i for i in result["items"] if i["name"] == "files_changed")
        self.assertTrue(item["passed"])
        self.assertEqual(item["detail"], "none")
        self.assertEqual(checker.manifest_from(empty, False), "files_changed: none")

    def test_external_cancel_during_baseline(self):
        self._check_interrupted_baseline(external=True)

    def test_deadline_during_baseline(self):
        self._check_interrupted_baseline(external=False)

    def _check_interrupted_baseline(self, external):
        tid = store.create("builder-agent", "builder", "slow snapshot")
        store.update(tid, status="failed")
        release = threading.Event()

        async def exercise():
            entered = asyncio.Event()
            loop = asyncio.get_running_loop()

            def slow_baseline(*args):
                loop.call_soon_threadsafe(entered.set)
                if not release.wait(1):
                    raise AssertionError("test did not release baseline")
                return checker.Baseline("hash", None, {}, True)

            with mock.patch.object(checker, "baseline", slow_baseline), \
                 mock.patch.object(config, "deadline", return_value=10 if external else 0.2), \
                 mock.patch.object(events, "emit") as emit, \
                 mock.patch.object(store, "update", wraps=store.update) as update, \
                 mock.patch.object(server, "run", new_callable=mock.AsyncMock) as run:
                task = asyncio.create_task(server._execute(tid, "builder-agent", self.role, "slow snapshot"))
                try:
                    await asyncio.wait_for(entered.wait(), 0.8)
                    status_during = store.get(tid)["status"]
                    if external:
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                    else:
                        reply = await asyncio.wait_for(task, 0.8)
                        self.assertIn("checks: none (out of time)", reply)
                    self.assertEqual(store.get(tid)["status"], "failed")
                    self.assertEqual(status_during, "running")
                    self.assertEqual(sum(c.kwargs.get("status") == "failed" for c in update.call_args_list), 1)
                    self.assertEqual(sum(c.args[0] == "task_failed" for c in emit.call_args_list), 1)
                    self.assertIsNone(store.get(tid)["baseline_json"])
                    run.assert_not_awaited()
                finally:
                    release.set()
                    task.cancel()
                    await asyncio.gather(task, return_exceptions=True)

        asyncio.run(exercise())

    def test_resume_reuses_baseline_from_first_dispatch(self):
        tid = store.create("builder-agent", "builder", "make a small change")
        base = checker.Baseline("git-tree", "first-tree", {}, False)
        changed = checker.Changes(("new.py",), ("new.py",), (), (), False)
        baseline = mock.Mock(return_value=base)
        change_scan = mock.Mock(return_value=changed)
        async def fake_run(*args, **kwargs):
            return "answer", []

        passed = {"passed": True, "items": [], "stop": None, "accept_note": ""}
        with mock.patch.object(checker, "baseline", baseline), \
             mock.patch.object(checker, "changes", change_scan), \
             mock.patch.object(server, "run", fake_run), \
             mock.patch.object(server, "_check", return_value=passed), \
             mock.patch.object(server, "resolve_role", return_value=self.role):
            asyncio.run(server._execute(tid, "builder-agent", self.role, "first dispatch"))
            self.assertEqual(baseline.call_count, 1)
            store.update(tid, status="failed")
            asyncio.run(server.resume_task(tid))

        self.assertEqual(baseline.call_count, 1)
        self.assertEqual(change_scan.call_count, 2)
        row = store.get(tid)
        self.assertEqual(row["baseline_json"], {"kind": "git-tree", "tree": "first-tree", "files": {}, "partial": False})


if __name__ == "__main__":
    unittest.main()
