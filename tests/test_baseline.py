import hashlib
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from router import checker
from router.workspace import load_workspace


def git(repo, *args, env=None):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=env)


class BaselineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "config", "commit.gpgsign", "false")
        (self.repo / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        (self.repo / "tracked.py").write_text("base = 1\n", encoding="utf-8")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "initial")
        self.ws = load_workspace(str(self.repo))

    def tearDown(self):
        self.temp.cleanup()

    def test_detects_edit_to_already_dirty_file(self):
        p = self.repo / "tracked.py"
        p.write_text("dirty = 2\n", encoding="utf-8")
        base = checker.baseline(self.ws, ["tracked.py"])
        p.write_text("later = 3\n", encoding="utf-8")
        got = checker.changes(self.ws, base, ["tracked.py"], [])
        self.assertEqual(got.changed, ("tracked.py",))
        self.assertEqual(got.task_changed, ("tracked.py",))

    def test_does_not_credit_untouched_dirty_file(self):
        (self.repo / "tracked.py").write_text("dirty = 2\n", encoding="utf-8")
        base = checker.baseline(self.ws, ["tracked.py"])
        self.assertEqual(checker.changes(self.ws, base, ["tracked.py"], []).changed, ())

    def test_detects_untracked_but_not_ignored(self):
        base = checker.baseline(self.ws, ["tracked.py"])
        (self.repo / "new.txt").write_text("new\n", encoding="utf-8")
        (self.repo / "ignored.txt").write_text("ignored\n", encoding="utf-8")
        got = checker.changes(self.ws, base, ["tracked.py"], [])
        self.assertEqual(got.changed, ("new.txt",))

    def test_temporary_index_uses_git_path_index_plain_and_worktree(self):
        for repo in (self.repo, self.root / "linked"):
            if repo.name == "linked":
                git(self.repo, "worktree", "add", "-q", "-b", "linked", str(repo), "HEAD")
            ws = load_workspace(str(repo))
            index = git(repo, "rev-parse", "--git-path", "index").stdout.decode().strip()
            index_path = Path(index) if Path(index).is_absolute() else repo / index
            original = index_path.read_bytes()
            checker.baseline(ws, ["tracked.py"])
            self.assertEqual(index_path.read_bytes(), original)

    def test_unborn_repo_without_index_has_baseline(self):
        repo = self.root / "unborn"
        repo.mkdir()
        git(repo, "init", "-q")
        (repo / "x.py").write_text("x=1\n", encoding="utf-8")
        result = checker.baseline(load_workspace(str(repo)), ["x.py"])
        self.assertEqual(result.kind, "git-tree")
        self.assertIsNotNone(result.tree)

    def test_non_git_hash_baseline_has_scope_note(self):
        folder = self.root / "plain"
        folder.mkdir()
        (folder / "x.py").write_text("x=1\n", encoding="utf-8")
        ws = load_workspace(str(folder))
        base = checker.baseline(ws, ["x.py"])
        self.assertEqual(base.kind, "hash")
        self.assertTrue(base.partial)
        self.assertTrue(checker.changes(ws, base, ["x.py"], []).partial)

    def test_size_cap_is_partial(self):
        (self.repo / "large.py").write_bytes(b"x" * 10)
        with patch.object(checker, "MAX_BASELINE_BYTES", 5):
            got = checker.baseline(self.ws, ["large.py"])
        self.assertTrue(got.partial)

    def test_hash_resume_compares_only_original_keys_and_uses_current_scope(self):
        ws = load_workspace(str(self.root))
        for name in ("kept", "removed", "added"):
            (self.root / name).write_bytes(b"before")
        base = checker.baseline(ws, ["kept", "removed"])
        self.assertEqual(base.kind, "hash")
        for name in ("kept", "removed"):
            (self.root / name).write_bytes(b"after")
        got = checker.changes(ws, base, ["kept", "added"], [])
        self.assertEqual(got.changed, ("kept", "removed"))
        self.assertEqual(got.task_changed, ("kept",))
        self.assertEqual(got.outside_scope, ("removed",))

    def test_must_not_change_glob_hit(self):
        base = checker.baseline(self.ws, ["tracked.py"])
        (self.repo / "secret.cfg").write_text("change\n", encoding="utf-8")
        got = checker.changes(self.ws, base, ["tracked.py"], ["*.cfg"])
        self.assertEqual(got.scope_violation, ("secret.cfg",))

    def test_glob_matching_is_case_insensitive_on_windows_and_macos(self):
        if not (os.name == "nt" or __import__("sys").platform == "darwin"):
            self.skipTest("case-insensitive matching is platform-specific")
        base = checker.Baseline("hash", None, {"Foo.CFG": hashlib.sha256(b"a").hexdigest()}, True)
        (self.repo / "Foo.CFG").write_text("changed", encoding="utf-8")
        got = checker.changes(self.ws, base, ["tracked.py"], ["foo.cfg"])
        self.assertEqual(got.scope_violation, ("Foo.CFG",))

    def test_manifest_packet_scope_and_legacy(self):
        got = checker.Changes(("a.py", "b.txt"), ("a.py",), ("b.txt",), (), False)
        self.assertEqual(checker.manifest_from(got, True), "files_changed: a.py, b.txt\noutside_scope: b.txt")
        self.assertEqual(checker.manifest_from(got, False), "files_changed: a.py, b.txt")
        empty = checker.Changes((), (), (), (), False)
        self.assertEqual(checker.manifest_from(empty, True), "files_changed: none")

    def test_check_deterministic_uses_supplied_changes_for_lint_and_manifest(self):
        (self.repo / "changed.py").touch()
        scope = checker.Changes(("changed.py",), ("changed.py",), (), (), False)
        with patch.object(checker, "lint_python", return_value=[]) as lint, \
             patch.object(checker, "files_changed", side_effect=AssertionError("unscoped status used")):
            result = checker.check_deterministic(self.ws, None, None, 1, changes=scope)
        lint.assert_called_once_with(["changed.py"], str(self.repo))
        item = next(i for i in result["items"] if i["name"] == "files_changed")
        self.assertEqual(item["detail"], "changed.py")
        self.assertTrue(item["passed"])

    def test_git_failure_falls_back_to_partial_hash_then_empty_changes(self):
        with patch.object(checker.subprocess, "run", side_effect=OSError("git unavailable")):
            base = checker.baseline(self.ws, ["tracked.py"])
            got = checker.changes(self.ws, base, ["tracked.py"], [])
        self.assertEqual(base.kind, "hash")
        self.assertTrue(base.partial)
        self.assertEqual(got.changed, ())
        self.assertTrue(got.partial)

    def test_subfolder_workspace_paths_are_relative_to_workspace(self):
        sub = self.repo / "sub"
        sub.mkdir()
        (sub / "a.py").write_text("base = 1\n", encoding="utf-8")
        git(self.repo, "add", "sub/a.py")
        git(self.repo, "commit", "-qm", "add subfolder")
        ws = load_workspace(str(sub))
        base = checker.baseline(ws, ["a.py"])
        (sub / "a.py").write_text("changed = 2\n", encoding="utf-8")
        (sub / "new.txt").write_text("new\n", encoding="utf-8")
        got = checker.changes(ws, base, ["a.py"], [])
        self.assertEqual(got.changed, ("a.py", "new.txt"))
        self.assertEqual(got.task_changed, ("a.py",))
        self.assertEqual(got.outside_scope, ("new.txt",))

    def test_git_operations_do_not_rewrite_real_index(self):
        base = checker.baseline(self.ws, ["tracked.py"])
        index = Path(git(self.repo, "rev-parse", "--git-path", "index").stdout.decode().strip())
        if not index.is_absolute():
            index = self.repo / index
        before_bytes = index.read_bytes()
        before_mtime = index.stat().st_mtime_ns
        tracked = self.repo / "tracked.py"
        os.utime(tracked, None)
        checker.baseline(self.ws, ["tracked.py"])
        checker.changes(self.ws, base, ["tracked.py"], [])
        self.assertEqual(index.read_bytes(), before_bytes)
        self.assertEqual(index.stat().st_mtime_ns, before_mtime)

    def test_renames_report_both_old_and_new_paths(self):
        base = checker.baseline(self.ws, ["tracked.py"])
        git(self.repo, "mv", "tracked.py", "renamed.py")
        got = checker.changes(self.ws, base, ["renamed.py"], [])
        self.assertEqual(got.changed, ("renamed.py", "tracked.py"))

    def test_double_star_glob_edges_and_single_star_and_question(self):
        self.assertTrue(checker._glob_matches("secrets.env", "**/secrets.env"))
        self.assertTrue(checker._glob_matches("nested/secrets.env", "**/secrets.env"))
        self.assertTrue(checker._glob_matches("dir/a/b.txt", "dir/**"))
        self.assertTrue(checker._glob_matches("dir/file.txt", "dir/*"))
        self.assertFalse(checker._glob_matches("dir/sub/file.txt", "dir/*"))
        self.assertFalse(checker._glob_matches("dir/sub/file.txt", "dir/?.txt"))

    def test_changes_has_no_note_field(self):
        self.assertEqual(set(checker.Changes.__dataclass_fields__), {
            "changed", "task_changed", "outside_scope", "scope_violation", "partial"
        })


if __name__ == "__main__":
    unittest.main()
