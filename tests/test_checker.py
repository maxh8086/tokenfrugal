import os
import subprocess
import sys
import tempfile
import unittest

from router import checker

PATCH_OK = "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-one\n+two\n"
PATCH_BAD = "--- a/a.txt\n+++ b/a.txt\n@@ -1 +1 @@\n-nope\n+two\n"


def _git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True)


def _make_repo(root):
    repo = os.path.join(root, "repo")
    os.makedirs(repo)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    with open(os.path.join(repo, "a.txt"), "w", encoding="utf-8") as f:
        f.write("one\n")
    _git(repo, "add", "a.txt")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


class CheckerTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.repo = _make_repo(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name, text):
        with open(os.path.join(self.repo, name), "w", encoding="utf-8") as f:
            f.write(text)

    def test_files_changed_sees_modified_and_untracked(self):
        self._write("a.txt", "changed\n")
        self._write("new.txt", "hi\n")
        self.assertEqual(checker.files_changed(self.repo), ["a.txt", "new.txt"])

    def test_files_changed_clean_repo(self):
        self.assertEqual(checker.files_changed(self.repo), [])

    def test_files_changed_rename_returns_new_path(self):
        _git(self.repo, "mv", "a.txt", "b.txt")
        self.assertEqual(checker.files_changed(self.repo), ["b.txt"])

    def test_diff_applies(self):
        self.assertEqual(checker.diff_applies(PATCH_OK, self.repo), (True, ""))
        ok, detail = checker.diff_applies(PATCH_BAD, self.repo)
        self.assertFalse(ok)
        self.assertTrue(detail)
        self.assertLessEqual(len(detail), 300)

    def test_lint_python(self):
        self._write("bad.py", "def f(:\n")
        self._write("good.py", "x = 1\n")
        self._write("notes.txt", "def f(:\n")
        problems = checker.lint_python(["bad.py", "good.py", "notes.txt"], self.repo)
        self.assertEqual(len(problems), 1)
        self.assertTrue(problems[0].startswith("bad.py: syntax error"))

    def test_lint_python_clean(self):
        self._write("good.py", "x = 1\n")
        self.assertEqual(checker.lint_python(["good.py"], self.repo), [])

    def test_run_accept_pass_and_fail(self):
        ok, _ = checker.run_accept([sys.executable, "-c", "import sys; sys.exit(0)"], self.repo)
        self.assertTrue(ok)
        ok, _ = checker.run_accept([sys.executable, "-c", "import sys; print('boom'); sys.exit(1)"], self.repo)
        self.assertFalse(ok)

    def test_run_accept_timeout(self):
        ok, detail = checker.run_accept(
            [sys.executable, "-c", "import time; time.sleep(5)"], self.repo, timeout=1)
        self.assertFalse(ok)
        self.assertEqual(detail, "timed out after 1s")

    def test_check_deterministic_fails_when_accept_fails(self):
        result = checker.check_deterministic(
            self.repo, [sys.executable, "-c", "import sys; sys.exit(1)"], None)
        self.assertFalse(result["passed"])
        accept = [i for i in result["items"] if i["name"] == "accept"][0]
        self.assertFalse(accept["passed"])
        self.assertEqual({i["name"] for i in result["items"]}, {"accept", "lint", "files_changed"})
        self.assertTrue(all(i["tag"] == "deterministic" for i in result["items"]))

    def test_check_deterministic_passes(self):
        result = checker.check_deterministic(
            self.repo, [sys.executable, "-c", "import sys; sys.exit(0)"], PATCH_OK)
        self.assertTrue(result["passed"])
        names = [i["name"] for i in result["items"]]
        self.assertEqual(names, ["accept", "lint", "diff_applies", "files_changed"])
        files = [i for i in result["items"] if i["name"] == "files_changed"][0]
        self.assertEqual(files["detail"], "none")

    def test_check_deterministic_no_optional_items(self):
        result = checker.check_deterministic(self.repo, None, None)
        self.assertEqual([i["name"] for i in result["items"]], ["lint", "files_changed"])
        self.assertTrue(result["passed"])


if __name__ == "__main__":
    unittest.main()
