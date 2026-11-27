"""The checker stage in _execute: accept and diff parsing, a pass, one correction through the same history, and FAILED with the checker output."""
import asyncio
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import config, events, server, store
from router.workspace import load_workspace
from router.workspace import load_workspace

FLAG_CHECK = "import os, sys\nsys.exit(0 if os.path.exists('fixed') else 1)\n"


def _make_repo(root):
    repo = os.path.join(root, "repo")
    os.makedirs(repo)
    for args in (("init", "-q"), ("config", "user.email", "t@example.com"), ("config", "user.name", "T"),
                 ("config", "commit.gpgsign", "false")):
        subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)
    return repo


class ParseTest(unittest.TestCase):
    def test_accept_from_task_takes_last_accept_line(self):
        text = "do the thing\nAccept: python -m unittest\nmore\nAccept: python check.py"
        self.assertEqual(server.checker.accept_from_task(text, "", load_workspace(os.getcwd())).spec.argv, ("python", "check.py"))

    def test_accept_none_without_line_or_empty_line(self):
        self.assertIsNone(server.checker.accept_from_task("no accept here", "", load_workspace(os.getcwd())).spec)
        self.assertIsNone(server.checker.accept_from_task("Accept:   ", "", load_workspace(os.getcwd())).spec)

    def test_diff_block_extracts_body(self):
        reply = "here\n```diff\n--- a/x\n+++ b/x\n```\nend"
        self.assertEqual(server.diff_block(reply), "--- a/x\n+++ b/x\n")
        self.assertIsNone(server.diff_block("no diff"))


class StageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.repo = _make_repo(self.tmp)
        Path(self.repo, "check.py").write_text(FLAG_CHECK, encoding="utf-8")
        self.patches = [
            mock.patch.object(store, "DB_PATH", Path(self.tmp) / "t.db"),
            mock.patch.object(server, "WORKSPACE", self.repo),
            mock.patch.object(config, "HOST_ACCEPT_PATHS", frozenset({os.path.normcase(os.path.realpath(self.repo))})),
            mock.patch.object(events, "emit", lambda *a, **k: None),
        ]
        for p in self.patches:
            p.start()
        self.role = {"role": "builder", "model": "m", "max_steps": 4, "timeout_s": 60, "tools": [], "skills": []}
        self.exe = sys.executable

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()

    def _run(self, fake, task):
        tid = store.create("builder-agent", "builder", task)
        with mock.patch.object(server, "run", fake):
            reply = asyncio.run(server._execute(tid, "builder-agent", self.role, task))
        return tid, reply

    def test_no_accept_and_no_diff_skips_checks(self):
        calls = []

        async def fake(agent, role, prompt, messages=None, tid=None, guard=None):
            calls.append(prompt)
            return "plain answer", list(messages or [])

        tid, reply = self._run(fake, "explain the parser")
        self.assertEqual(len(calls), 1)
        self.assertIn("checks: none (no accept command)", reply)
        self.assertEqual(store.get(tid)["status"], "done")

    def test_passing_accept_reports_checks_and_judgement(self):
        async def fake(agent, role, prompt, messages=None, tid=None, guard=None):
            return "changed nothing", list(messages or [])

        Path(self.repo, "fixed").write_text("", encoding="utf-8")  # the accept command passes from the start
        tid, reply = self._run(fake, f"Accept: {shlex.join([self.exe, 'check.py'])}\nadd the fix")
        self.assertIn("checks: ok (accept, lint)", reply)
        self.assertIn("Judge (client):", reply)
        self.assertLess(reply.index("files_changed:"), reply.index("checks:"))
        self.assertLess(reply.index("checks:"), reply.index("Judge (client):"))
        self.assertLess(reply.index("Judge (client):"), reply.index("status="))
        self.assertEqual(store.get(tid)["status"], "done")

    def test_one_correction_then_pass(self):
        calls = []

        async def fake(agent, role, prompt, messages=None, tid=None, guard=None):
            calls.append(prompt)
            if len(calls) == 2:  # the correction run makes the accept command pass
                Path(self.repo, "fixed").write_text("", encoding="utf-8")
            return f"reply {len(calls)}", list(messages or []) + [{"role": "user", "content": prompt}]

        tid, reply = self._run(fake, f"Accept: {shlex.join([self.exe, 'check.py'])}\nadd the fix")
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[1].startswith("Checker failed: accept:"), calls[1])
        self.assertIn("checks: ok (accept, lint)", reply)
        row = store.get(tid)
        self.assertEqual(row["status"], "done")
        self.assertEqual(len(row["messages"]), 2)  # the correction continued the first run's history

    def test_fails_after_one_correction_with_checker_output(self):
        calls = []

        async def fake(agent, role, prompt, messages=None, tid=None, guard=None):
            calls.append(prompt)
            return "still wrong", list(messages or [])

        tid, reply = self._run(fake, f"Accept: {shlex.join([self.exe, 'check.py'])}\nadd the fix")
        self.assertEqual(len(calls), 2)
        self.assertIn("FAILED (builder/m) reason=checker error_kind=accept_failed", reply)
        self.assertIn("accept:", reply)
        self.assertIn("Re-scope", reply)
        row = store.get(tid)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["error_kind"], "accept_failed")
        self.assertLess(reply.index("FAILED (builder/m)"), reply.index("checks:"))
        self.assertLess(reply.index("checks:"), reply.index("status="))
        self.assertNotIn("FAILED (builder/m) reason=checker error_kind=accept_failed\n\nchecks:", reply)

    def test_out_of_time_verdict_still_gets_correction_attempt(self):
        calls = []
        async def fake(agent, role, prompt, messages=None, tid=None, guard=None):
            calls.append(prompt)
            return "reply", list(messages or [])
        first = {"passed": False, "stop": "out_of_time", "items": [{"name": "accept", "passed": False, "detail": "time"}]}
        second = {"passed": True, "items": [{"name": "lint", "passed": True, "detail": "clean"}]}
        tid = store.create("builder-agent", "builder", "retry after out of time")
        with mock.patch.object(server, "run", fake), mock.patch.object(server, "_check", side_effect=[first, second]):
            asyncio.run(server._execute(tid, "builder-agent", self.role, "retry after out of time"))
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[1].startswith("Checker failed:"))

    def test_declared_new_module_failure_is_accept_failed_not_env_missing(self):
        async def fake(agent, role, prompt, messages=None, tid=None, guard=None):
            return "still missing module", list(messages or [])
        task = f"Create newmod.py\nAccept: {shlex.join([self.exe, '-c', 'import newmod'])}"
        tid, reply = self._run(fake, task)
        self.assertIn("error_kind=accept_failed", reply)
        self.assertNotIn("error_kind=env_missing", reply)
        self.assertEqual(store.get(tid)["error_kind"], "accept_failed")

    def test_refused_accept_reason_is_preserved_with_and_without_other_checks(self):
        reason = "refused: accept must be one command"
        skipped = server._report({"accept_note": reason, "items": [
            {"name": "lint", "passed": True, "detail": "clean"},
            {"name": "files_changed", "passed": True, "detail": "none"},
        ]}, self.role)
        self.assertIn("checks: none (refused: accept must be one command)", skipped)
        checked = server._report({"accept_note": reason, "items": [
            {"name": "lint", "passed": True, "detail": "clean"},
            {"name": "diff_applies", "passed": True, "detail": ""},
            {"name": "files_changed", "passed": True, "detail": "none"},
        ]}, self.role)
        self.assertIn("checks: ok (lint, diff_applies; accept none: refused: accept must be one command)", checked)

    def test_accept_argument_runs_when_task_has_no_accept_line(self):
        calls = []
        async def fake(agent, role, prompt, messages=None, tid=None, guard=None):
            calls.append(prompt)
            if len(calls) == 2:
                Path(self.repo, "fixed").write_text("", encoding="utf-8")
            return "reply", list(messages or [])
        task = "make the check pass"
        tid = store.create("builder-agent", "builder", task)
        parsed = server.checker.parse_accept(shlex.join([self.exe, "check.py"]), "argument", load_workspace(self.repo))
        with mock.patch.object(server, "run", fake):
            reply = asyncio.run(server._execute(tid, "builder-agent", self.role, task, accept=parsed, task_text=task))
        self.assertEqual(len(calls), 2)
        self.assertIn("checks: ok (accept, lint)", reply)

    def test_host_accept_off_skips_command_but_keeps_lint(self):
        async def fake(agent, role, prompt, messages=None, tid=None, guard=None):
            return "plain answer", list(messages or [])
        task = "make a change"
        tid = store.create("builder-agent", "builder", task)
        parsed = server.checker.parse_accept(shlex.join([self.exe, "check.py"]), "argument", load_workspace(self.repo))
        with mock.patch.object(config, "HOST_ACCEPT_PATHS", frozenset()), mock.patch.object(server, "run", fake):
            reply = asyncio.run(server._execute(tid, "builder-agent", self.role, task, accept=parsed, task_text=task))
        self.assertIn("checks: ok (lint; accept none: host accept off)", reply)

    def test_long_accept_error_uses_300_token_trim(self):
        async def fake(agent, role, prompt, messages=None, tid=None, guard=None):
            return "still wrong", list(messages or [])

        failed_verdict = {"passed": False, "items": [
            {"name": "accept", "passed": False, "detail": "x" * 1600},
        ]}
        tid = store.create("builder-agent", "builder", "long accept failure")
        with mock.patch.object(server, "run", fake), mock.patch.object(server, "_check", return_value=failed_verdict):
            asyncio.run(server._execute(tid, "builder-agent", self.role, "long accept failure"))
        error = store.get(tid)["error"]
        self.assertGreater(len(error), 480)
        # 300-token class: the cut keeps 300 * 4 - 12 = 1188 characters, then " [trimmed]" (not the 120-class cut of 468)
        self.assertEqual(len(error), 300 * 4 - 12 + len(" [trimmed]"))
        self.assertTrue(error.endswith("x [trimmed]"), error[-40:])
        self.assertIn("[trimmed]", error)

    def test_checks_line_sits_before_status_without_accept(self):
        async def fake(agent, role, prompt, messages=None, tid=None, guard=None):
            return "plain answer", list(messages or [])

        tid, reply = self._run(fake, "explain the parser")
        self.assertLess(reply.index("checks: none (no accept command)"), reply.index("status="))


if __name__ == "__main__":
    unittest.main()
