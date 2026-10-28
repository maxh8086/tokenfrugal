"""The checker stage in _execute: accept and diff parsing, a pass, one correction through the same history, and FAILED with the checker output."""
import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import events, server, store

FLAG_CHECK = "import os, sys\nsys.exit(0 if os.path.exists('fixed') else 1)\n"


def _make_repo(root):
    repo = os.path.join(root, "repo")
    os.makedirs(repo)
    for args in (("init", "-q"), ("config", "user.email", "t@example.com"), ("config", "user.name", "T")):
        subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)
    return repo


class ParseTest(unittest.TestCase):
    def test_accept_cmd_takes_last_accept_line(self):
        text = "do the thing\nAccept: python -m unittest\nmore\nAccept: python check.py"
        self.assertEqual(server.accept_cmd(text), ["python", "check.py"])

    def test_accept_cmd_none_without_line_or_with_empty_line(self):
        self.assertIsNone(server.accept_cmd("no accept here"))
        self.assertIsNone(server.accept_cmd("Accept:   "))

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
        if " " in self.exe:
            self.skipTest("accept command is split on spaces; this interpreter path has one")
        tid = store.create("builder-agent", "builder", task)
        with mock.patch.object(server, "run", fake):
            reply = asyncio.run(server._execute(tid, "builder-agent", self.role, task))
        return tid, reply

    def test_no_accept_and_no_diff_skips_checks(self):
        calls = []

        async def fake(agent, role, prompt, messages=None, tid=None):
            calls.append(prompt)
            return "plain answer", list(messages or [])

        tid, reply = self._run(fake, "explain the parser")
        self.assertEqual(len(calls), 1)
        self.assertNotIn("Checks:", reply)
        self.assertEqual(store.get(tid)["status"], "done")

    def test_passing_accept_reports_checks_and_judgement(self):
        async def fake(agent, role, prompt, messages=None, tid=None):
            return "changed nothing", list(messages or [])

        Path(self.repo, "fixed").write_text("", encoding="utf-8")  # the accept command passes from the start
        tid, reply = self._run(fake, f"Accept: {self.exe} check.py\nadd the fix")
        self.assertIn("accept ok", reply)
        self.assertIn("Judge (client):", reply)
        self.assertEqual(store.get(tid)["status"], "done")

    def test_one_correction_then_pass(self):
        calls = []

        async def fake(agent, role, prompt, messages=None, tid=None):
            calls.append(prompt)
            if len(calls) == 2:  # the correction run makes the accept command pass
                Path(self.repo, "fixed").write_text("", encoding="utf-8")
            return f"reply {len(calls)}", list(messages or []) + [{"role": "user", "content": prompt}]

        tid, reply = self._run(fake, f"Accept: {self.exe} check.py\nadd the fix")
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[1].startswith("Checker failed: accept:"), calls[1])
        self.assertIn("accept ok", reply)
        row = store.get(tid)
        self.assertEqual(row["status"], "done")
        self.assertEqual(len(row["messages"]), 2)  # the correction continued the first run's history

    def test_fails_after_one_correction_with_checker_output(self):
        calls = []

        async def fake(agent, role, prompt, messages=None, tid=None):
            calls.append(prompt)
            return "still wrong", list(messages or [])

        tid, reply = self._run(fake, f"Accept: {self.exe} check.py\nadd the fix")
        self.assertEqual(len(calls), 2)
        self.assertIn("FAILED (builder/m) reason=checker error_kind=checker", reply)
        self.assertIn("accept:", reply)
        self.assertIn("Re-scope", reply)
        row = store.get(tid)
        self.assertEqual(row["status"], "failed")
        self.assertEqual(row["error_kind"], "checker")


if __name__ == "__main__":
    unittest.main()
