"""Step 8a wiring: saved baselines and lint scoped to changed files."""
import asyncio
import os
import shutil
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest import mock

from router import checker, config, events, plan, server, store, workspace
from router import packet as packet_mod


class VerifiedCompletionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
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


class PacketStartTest(unittest.TestCase):
    """Step 8e part A: start_packet_task, the _admit split of dispatch_task and the packet write guard."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = Path(self.tmp) / "tasks.db"
        self.workspace = Path(self.tmp) / "workspace"
        self.workspace.mkdir()
        self.ws_key = workspace._key(str(self.workspace))
        self.role = {"role": "builder", "model": "fake", "max_steps": 2,
                     "timeout_s": 60, "tools": ["write_file"], "skills": []}
        patches = [
            mock.patch.object(store, "DB_PATH", self.db),
            mock.patch.object(server, "WORKSPACE", str(self.workspace)),
            mock.patch.object(events, "emit", lambda *args, **kwargs: None),
            mock.patch.object(server, "task_error", return_value=None),
            mock.patch.object(server, "resolve_role", side_effect=lambda *args, **kwargs: dict(self.role)),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def packet(self, **changes):
        fields = {"v": 1, "goal": "add a helper", "kind": "edit", "files": [{"path": "a.py"}]}
        fields.update(changes)
        return packet_mod.Packet.model_validate(fields)

    def live_edit_row(self):
        return store.create("other-agent", "builder", "held by another task", workspace=self.ws_key, kind="edit")

    def row_count(self):
        with closing(store._db()) as c:  # _db creates the schema when the test has not written a row yet
            return c.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]

    def busy_reply(self, holder):
        return f"workspace_busy: edit task {holder} is running in this workspace; retry later"

    def run_patches(self, run=None, changes=None, verdict=None):
        async def fake_run(*args, **kwargs):
            return "answer", []
        passed = verdict or {"passed": True, "items": [], "stop": None, "accept_note": ""}
        patches = [
            mock.patch.object(server, "run", run or fake_run),
            mock.patch.object(server, "_check", return_value=passed),
            mock.patch.object(checker, "baseline", return_value=checker.Baseline("hash", None, {}, False)),
            mock.patch.object(checker, "changes", return_value=changes or checker.Changes((), (), (), (), False)),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_busy_workspace_refuses_edit_packet_without_row(self):
        holder = self.live_edit_row()
        before = self.row_count()
        tid, reply = asyncio.run(server.start_packet_task("builder-agent", self.packet(), "fix bug"))
        self.assertIsNone(tid)
        self.assertEqual(reply, self.busy_reply(holder))
        self.assertEqual(self.row_count(), before)

    def test_analyze_packet_is_not_blocked_by_busy_workspace(self):
        self.live_edit_row()
        self.run_patches()
        tid, _ = asyncio.run(server.start_packet_task("builder-agent", self.packet(kind="analyze"), "explain code"))
        self.assertIsNotNone(tid)
        self.assertEqual(store.get(tid)["kind"], "analyze")

    def test_held_role_refuses_without_row_or_plan_claim(self):
        recorder = mock.AsyncMock(return_value=(True, ""))
        held = dict(self.role, held="owner hold")
        with mock.patch.object(server, "resolve_role", return_value=held), \
             mock.patch.object(server, "_plan", recorder):
            result = asyncio.run(server.start_packet_task("builder-agent", self.packet(), "fix bug", plan_id=7))
        self.assertEqual(result, (None, "role 'builder' is held: owner hold"))
        recorder.assert_not_awaited()
        self.assertEqual(self.row_count(), 0)

    def test_busy_workspace_with_plan_reverts_the_plan_claim(self):
        holder = self.live_edit_row()
        recorder = mock.AsyncMock(return_value=(True, ""))
        with mock.patch.object(server, "_plan", recorder):
            result = asyncio.run(server.start_packet_task("builder-agent", self.packet(), "fix bug", plan_id=7))
        self.assertEqual(result, (None, self.busy_reply(holder)))
        self.assertEqual([c.args[0] for c in recorder.call_args_list], [plan.claim, plan.revert])
        self.assertEqual(recorder.call_args_list[1].args[1:], (7, "router"))
        self.assertEqual(self.row_count(), 1)

    def test_packet_task_with_plan_records_run_and_marks_plan_done(self):
        recorder = mock.AsyncMock(return_value=(True, ""))
        self.run_patches(changes=checker.Changes(("a.py",), ("a.py",), (), (), False))
        with mock.patch.object(server, "_plan", recorder):
            tid, _ = asyncio.run(server.start_packet_task("builder-agent", self.packet(), "fix bug", plan_id=7))
        self.assertEqual(store.get(tid)["status"], "done")
        calls = [c.args for c in recorder.call_args_list]
        record = next(args for args in calls if args[0] is plan.record_run)
        self.assertEqual(record[1:5], (7, tid, "builder-agent", "builder"))
        self.assertEqual(record[5], "done")
        self.assertTrue(any(args[0] is plan.done and args[1] == 7 for args in calls))

    def test_packet_satisfied_with_plan_records_run_and_marks_plan_done(self):
        recorder = mock.AsyncMock(return_value=(True, ""))
        accepted = {"passed": True, "items": [{"name": "accept", "tag": "deterministic", "passed": True, "detail": "ok"}],
                    "stop": None, "accept_note": ""}
        self.run_patches(verdict=accepted)
        with mock.patch.object(server, "_plan", recorder):
            tid, _ = asyncio.run(server.start_packet_task("builder-agent", self.packet(), "fix bug", plan_id=7))
        row = store.get(tid)
        self.assertEqual((row["status"], row["outcome"]), ("done", "satisfied"))
        calls = [c.args for c in recorder.call_args_list]
        record = next(args for args in calls if args[0] is plan.record_run)
        self.assertEqual(record[1:6], (7, tid, "builder-agent", "builder", "done"))
        self.assertTrue(any(args[0] is plan.done and args[1] == 7 for args in calls))

    def test_edit_row_stores_rendered_prompt_packet_and_kind(self):
        pkt = self.packet(goal="add a helper", files=[{"path": "a.py"}])
        self.run_patches()
        tid, _ = asyncio.run(server.start_packet_task("builder-agent", pkt, "fix bug"))
        row = store.get(tid)
        self.assertEqual(row["prompt"], packet_mod.render(pkt))
        self.assertEqual(row["prompt_sent"], store.with_templates("builder", packet_mod.render(pkt), "fix bug"))
        self.assertEqual(row["kind"], "edit")
        self.assertEqual(row["contract_json"]["packet"], pkt.model_dump(mode="json"))

    def test_write_guard_allows_only_the_packet_files(self):
        pkt = self.packet(files=[{"path": "a.py"}, {"path": "pkg/b.py"}])
        captured = {}

        async def capture_run(agent, role, prompt, messages, tid, guard=None, budget=None):
            captured["guard"] = guard
            return "answer", []

        self.run_patches(capture_run)
        with mock.patch.object(workspace, "denied", wraps=workspace.denied) as denied:
            asyncio.run(server.start_packet_task("builder-agent", pkt, "fix bug"))
            captured["guard"](str(self.workspace / "pkg" / "b.py"))
            allowed = denied.call_args.args[1]
        self.assertEqual(allowed, {"a.py", "pkg/b.py"})


NO_CHANGE = checker.Changes((), (), (), (), False)
EXPECTED_RESULT_KEYS = {"accept", "files", "outside_scope", "first_error", "note"}


class OutcomeRulesTest(unittest.TestCase):
    """Step 8e part B: no-accept packets, contract_json result, outcome rules and packet resume."""

    def setUp(self):
        self.tmp = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.db = Path(self.tmp) / "tasks.db"
        self.workspace = Path(self.tmp) / "workspace"
        self.workspace.mkdir()
        self.ws_key = workspace._key(str(self.workspace))
        self.role = {"role": "builder", "model": "fake", "max_steps": 2,
                     "timeout_s": 60, "tools": ["write_file"], "skills": []}
        patches = [
            mock.patch.object(store, "DB_PATH", self.db),
            mock.patch.object(server, "WORKSPACE", str(self.workspace)),
            mock.patch.object(events, "emit", lambda *args, **kwargs: None),
            mock.patch.object(server, "task_error", return_value=None),
            mock.patch.object(server, "resolve_role", side_effect=lambda *args, **kwargs: dict(self.role)),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def packet(self, **changes):
        fields = {"v": 1, "goal": "add a helper", "kind": "edit", "files": [{"path": "a.py"}]}
        fields.update(changes)
        return packet_mod.Packet.model_validate(fields)

    def verdict(self, passed=True, note="", stop=None):
        item = {"name": "accept", "tag": "deterministic", "passed": passed, "detail": "ok" if passed else "exit 1"}
        return {"passed": passed, "items": [item], "stop": stop, "accept_note": note}

    def fake_run(self, write=None, calls=None):
        async def run(agent, role, prompt, messages, tid, guard=None, budget=None):
            if calls is not None:
                calls.append(prompt)
            if write:
                (self.workspace / write[0]).write_text(write[1], encoding="utf-8")
            return "answer", []
        return run

    def patch_run(self, run=None, verdict=None, changes=NO_CHANGE, baseline=None):
        """Fake model, mocked accept verdict, and fixed baseline and changes; keeps the mocks on self."""
        self.check_mock = self.start_patch(mock.patch.object(server, "_check", return_value=verdict))
        self.baseline_mock = self.start_patch(mock.patch.object(
            checker, "baseline", return_value=baseline or checker.Baseline("hash", None, {}, False)))
        self.changes_mock = self.start_patch(mock.patch.object(checker, "changes", return_value=changes))
        self.start_patch(mock.patch.object(server, "run", run or self.fake_run()))

    def start_patch(self, patcher):
        self.addCleanup(patcher.stop)
        return patcher.start()

    def start(self, pkt=None):
        return asyncio.run(server.start_packet_task("builder-agent", pkt or self.packet(), "fix bug"))

    def legacy(self, role=None):
        tid = store.create("builder-agent", "builder", "fix bug")
        reply = asyncio.run(server._execute(tid, "builder-agent", role or self.role, "fix bug"))
        return tid, reply

    def test_packet_without_accept_ignores_accept_line_in_context(self):
        self.patch_run(verdict=None)
        pkt = self.packet(context="Notes.\nAccept: python -c \"import sys; sys.exit(1)\"")
        self.start(pkt)
        accept = self.check_mock.call_args.args[4]
        self.assertIsNotNone(accept)
        self.assertIsNone(accept.spec)
        self.assertEqual(accept.note, "no accept")

    def test_packet_result_is_written_with_accept_pass(self):
        self.patch_run(verdict=self.verdict(True))
        tid, _ = self.start()
        contract = store.get(tid)["contract_json"]
        self.assertIn("packet", contract)
        self.assertEqual(set(contract["result"]), EXPECTED_RESULT_KEYS)
        self.assertEqual(contract["result"]["accept"], "pass")

    def test_legacy_result_is_written_with_accept_none(self):
        self.patch_run(verdict=None)
        tid, _ = self.legacy()
        result = store.get(tid)["contract_json"]["result"]
        self.assertEqual(set(result), EXPECTED_RESULT_KEYS)
        self.assertEqual(result["accept"], "none")

    def test_packet_edit_with_no_change_and_accept_passing_is_satisfied(self):
        self.patch_run(verdict=self.verdict(True))
        tid, reply = self.start()
        row = store.get(tid)
        self.assertEqual((row["status"], row["outcome"], row["error_kind"]), ("done", "satisfied", None))
        self.assertIn("status=done", reply)

    def test_packet_edit_with_no_change_and_no_accept_fails_no_change(self):
        self.patch_run(verdict=None)
        tid, reply = self.start()
        row = store.get(tid)
        self.assertEqual((row["status"], row["outcome"], row["error_kind"]), ("failed", "failed", "no_change"))
        self.assertIn("status=failed", reply)

    def test_must_not_change_hit_fails_with_scope(self):
        hit = checker.Changes(("a.py",), ("a.py",), (), ("a.py",), False)
        self.patch_run(verdict=self.verdict(True), changes=hit)
        tid, _ = self.start(self.packet(must_not_change=["a.py"]))
        row = store.get(tid)
        self.assertEqual((row["outcome"], row["error_kind"]), ("failed", "scope"))

    def test_failed_accept_after_correction_fails_for_packet_and_legacy(self):
        changed = checker.Changes(("a.py",), ("a.py",), (), (), False)  # a change, so the outcome rules pass to the checker
        self.patch_run(verdict=self.verdict(False), changes=changed)
        tid, _ = self.start()
        self.assertEqual(tuple(store.get(tid)[k] for k in ("status", "outcome", "error_kind")),
                         ("failed", "failed", "accept_failed"))
        legacy_tid, _ = self.legacy()
        self.assertEqual(tuple(store.get(legacy_tid)[k] for k in ("status", "outcome", "error_kind")),
                         ("failed", "failed", "accept_failed"))

    def test_partial_baseline_with_unchanged_files_fails_even_when_accept_passes(self):
        partial = checker.Baseline("hash", None, {}, True)
        self.patch_run(verdict=self.verdict(True), changes=checker.Changes((), (), (), (), True), baseline=partial)
        tid, _ = self.start()
        row = store.get(tid)
        self.assertEqual((row["outcome"], row["error_kind"]), ("failed", "no_change"))
        self.assertIn("scope unchecked", row["error"])

    def test_packet_reply_lists_outside_scope_and_legacy_reply_does_not(self):
        outside = checker.Changes(("a.py", "b.py"), ("a.py",), ("b.py",), (), False)
        self.patch_run(verdict=self.verdict(True), changes=outside)
        _, reply = self.start()
        self.assertIn("outside_scope: b.py", reply)
        _, legacy_reply = self.legacy()
        self.assertNotIn("outside_scope:", legacy_reply)

    def test_partial_baseline_with_failing_accept_keeps_scope_note(self):
        partial = checker.Baseline("hash", None, {}, True)
        changed = checker.Changes(("a.py",), ("a.py",), (), (), True)
        self.patch_run(verdict=self.verdict(False), changes=changed, baseline=partial)
        tid, _ = self.start()
        row = store.get(tid)
        self.assertEqual((row["outcome"], row["error_kind"]), ("failed", "accept_failed"))
        self.assertEqual(row["contract_json"]["result"]["note"], "scope unchecked")

    def test_rule_failure_calls_changes_once_after_the_model_run(self):
        hit = checker.Changes(("a.py",), ("a.py",), (), ("a.py",), False)
        self.patch_run(verdict=self.verdict(True), changes=hit)
        tid, _ = self.start(self.packet(must_not_change=["a.py"]))
        self.assertEqual(store.get(tid)["error_kind"], "scope")
        self.assertEqual(self.changes_mock.call_count, 1)

    def test_error_path_changes_failure_still_writes_failed_row_with_result(self):
        async def boom(*args, **kwargs):
            raise RuntimeError("model broke")
        self.patch_run(run=boom, verdict=self.verdict(True))
        self.changes_mock.side_effect = RuntimeError("diff broke")
        recorder = mock.AsyncMock(return_value=(True, ""))
        with mock.patch.object(server, "_plan", recorder):
            tid, _ = asyncio.run(server.start_packet_task("builder-agent", self.packet(), "fix bug", plan_id=7))
        row = store.get(tid)
        self.assertEqual((row["status"], row["outcome"]), ("failed", "failed"))
        self.assertEqual(set(row["contract_json"]["result"]), EXPECTED_RESULT_KEYS)
        self.assertIn(plan.record_run, [c.args[0] for c in recorder.call_args_list])

    def test_deadline_exit_writes_result_with_empty_file_list(self):
        async def slow(*args, **kwargs):
            await asyncio.sleep(5)
            return "answer", []
        self.patch_run(run=slow, verdict=self.verdict(True))
        with mock.patch.object(config, "deadline", return_value=0.05):
            tid, _ = self.start()
        row = store.get(tid)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["contract_json"]["result"]["files"], [])

    def test_infra_failed_exit_writes_result(self):
        tid = store.create("builder-agent", "builder", "fix bug")
        asyncio.run(server._infra_failed(tid, "builder-agent", self.role, "fix bug", 0, "ollama", 0.0, "down"))
        row = store.get(tid)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(set(row["contract_json"]["result"]), EXPECTED_RESULT_KEYS)

    def run_with_real_scan(self, write, cap_patch=False):
        (self.workspace / "a.py").write_text("x=1", encoding="utf-8")
        patchers = [mock.patch.object(server, "_check", return_value=self.verdict(True)),
                    mock.patch.object(server, "run", self.fake_run(write=write))]
        if cap_patch:
            patchers += [mock.patch.object(checker, "MAX_BASELINE_BYTES", 3),
                         mock.patch.object(checker, "_untracked_bytes", return_value=10)]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        tid, reply = self.start()
        return store.get(tid), reply

    def test_non_git_workspace_reports_scope_unchecked(self):
        row, _ = self.run_with_real_scan(write=None)
        self.assertEqual((row["outcome"], row["error_kind"]), ("failed", "no_change"))
        self.assertIn("scope unchecked", row["error"])
        self.assertEqual(row["contract_json"]["result"]["note"], "scope unchecked")
        row, reply = self.run_with_real_scan(write=("a.py", "x=2"))
        self.assertEqual(row["outcome"], "done")
        self.assertIn("scope unchecked", reply)

    def test_size_capped_workspace_reports_scope_unchecked(self):
        row, _ = self.run_with_real_scan(write=None, cap_patch=True)
        self.assertEqual((row["outcome"], row["error_kind"]), ("failed", "no_change"))
        self.assertIn("scope unchecked", row["error"])
        self.assertEqual(row["contract_json"]["result"]["note"], "scope unchecked")
        row, reply = self.run_with_real_scan(write=("a.py", "x=2"), cap_patch=True)
        self.assertEqual(row["outcome"], "done")
        self.assertIn("scope unchecked", reply)

    def test_legacy_edit_and_packet_analyze_with_no_change_are_done_not_satisfied(self):
        self.patch_run(verdict=self.verdict(True))
        tid, _ = self.start(self.packet(kind="analyze"))
        self.assertEqual(store.get(tid)["outcome"], "done")
        legacy_tid, _ = self.legacy()
        self.assertEqual(store.get(legacy_tid)["outcome"], "done")

    def test_no_write_role_with_failing_checks_ends_done(self):
        self.role = dict(self.role, tools=["read_file"])
        calls = []
        changed = checker.Changes(("a.py",), ("a.py",), (), (), False)
        self.patch_run(run=self.fake_run(calls=calls), verdict=self.verdict(False), changes=changed)
        tid, reply = self.start()
        row = store.get(tid)
        self.assertEqual((row["status"], row["outcome"]), ("done", "done"))
        self.assertIn("checks: FAILED (", reply)
        self.assertEqual(len(calls), 1)

    def test_legacy_no_write_role_with_failing_checks_ends_done(self):
        self.role = dict(self.role, tools=["read_file"])
        calls = []
        self.patch_run(run=self.fake_run(calls=calls), verdict=self.verdict(False))
        tid, reply = self.legacy()
        row = store.get(tid)
        self.assertEqual((row["status"], row["outcome"], row["error_kind"]), ("done", "done", None))
        self.assertIn("checks: FAILED (", reply)
        self.assertEqual(len(calls), 1)

    def test_write_role_checks_still_failing_after_correction_scope_wins(self):
        hit = checker.Changes(("a.py",), ("a.py",), (), ("a.py",), False)
        self.patch_run(verdict=self.verdict(False), changes=hit)
        tid, _ = self.start(self.packet(must_not_change=["a.py"]))
        row = store.get(tid)
        self.assertEqual((row["status"], row["outcome"], row["error_kind"]), ("failed", "failed", "scope"))

    def test_write_role_checks_still_failing_with_no_change_is_no_change(self):
        self.patch_run(verdict=self.verdict(False), changes=NO_CHANGE)
        tid, _ = self.start()
        row = store.get(tid)
        self.assertEqual((row["outcome"], row["error_kind"]), ("failed", "no_change"))

    def test_write_role_checks_still_failing_with_partial_baseline_is_no_change(self):
        partial = checker.Changes((), (), (), (), True)
        self.patch_run(verdict=self.verdict(False), changes=partial)
        tid, _ = self.start()
        row = store.get(tid)
        self.assertEqual((row["outcome"], row["error_kind"]), ("failed", "no_change"))
        self.assertIn("scope unchecked", row["error"])

    def test_no_time_for_correction_with_scope_hit_stays_out_of_time(self):
        hit = checker.Changes(("a.py",), ("a.py",), (), ("a.py",), False)
        self.patch_run(verdict=self.verdict(False), changes=hit)
        with mock.patch.object(config, "CORRECTION_FLOOR_S", 10 ** 9):
            tid, _ = self.start(self.packet(must_not_change=["a.py"]))
        row = store.get(tid)
        self.assertEqual((row["status"], row["error_kind"]), ("failed", "out_of_time"))
        self.assertEqual(self.check_mock.call_count, 1)

    def test_env_missing_and_out_of_time_keep_their_stop(self):
        self.patch_run(verdict=self.verdict(False, stop="env_missing"))
        tid, _ = self.start()
        self.assertEqual(store.get(tid)["error_kind"], "env_missing")
        self.patch_run(verdict=self.verdict(False, note="out of time", stop="out_of_time"))
        tid, _ = self.start()
        self.assertEqual(store.get(tid)["error_kind"], "out_of_time")

    def test_packet_resume_reuses_stored_packet_and_first_baseline(self):
        pkt = self.packet(context="Notes.\nAccept: python -c \"import sys; sys.exit(1)\"")
        self.patch_run(verdict=None)
        tid, _ = self.start(pkt)
        self.assertEqual(store.get(tid)["error_kind"], "no_change")
        first_prompt = store.get(tid)["prompt_sent"]
        self.check_mock.return_value = self.verdict(True)
        calls = []
        self.start_patch(mock.patch.object(server, "run", self.fake_run(calls=calls)))
        asyncio.run(server.resume_task(tid))
        row = store.get(tid)
        self.assertEqual(self.baseline_mock.call_count, 1)
        self.assertEqual(calls, [first_prompt])
        self.assertEqual(self.check_mock.call_args.args[4].note, "no accept")
        self.assertEqual(row["outcome"], "satisfied")
        self.assertEqual(row["contract_json"]["packet"]["files"][0]["path"], "a.py")

    def test_packet_resume_refused_when_another_edit_task_holds_workspace(self):
        self.patch_run(verdict=None)
        tid, _ = self.start()
        holder = store.create("other-agent", "builder", "held by another task", workspace=self.ws_key, kind="edit")
        before = store.get(tid)
        reply = asyncio.run(server.resume_task(tid))
        self.assertEqual(reply, f"workspace_busy: edit task {holder} is running in this workspace; retry later")
        after = store.get(tid)
        for key in ("status", "attempts", "heartbeat", "error_kind", "messages"):
            self.assertEqual(after[key], before[key], key)


if __name__ == "__main__":
    unittest.main()
