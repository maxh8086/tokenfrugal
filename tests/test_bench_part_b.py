"""Offline tests for the Part B team tasks and their checks. No Docker, model or router is contacted."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import bench_checks
from scripts.bench_team_tasks import EXPECT_ROOT, SEEDS, TEAM_TASKS

SEEDED_CHECKS = {"sql_injection_review", "two_vulns", "compare_functions", "debug_crash", "trace_root_cause",
                 "long_summary", "rename_done"}


class TaskTable(unittest.TestCase):
    def test_every_check_name_is_known(self):
        for role, tasks in TEAM_TASKS.items():
            for agent, prompt, check in tasks:
                self.assertIn(check, bench_checks.CHECKS, f"{role}: {check!r}")

    def test_every_seeded_task_has_a_seed_entry(self):
        for role, tasks in TEAM_TASKS.items():
            for idx, (_agent, _prompt, check) in enumerate(tasks):
                if check in SEEDED_CHECKS:
                    self.assertIn((role, idx), SEEDS, f"{role}#{idx} checks {check} but has no SEEDS entry")

    def test_seed_and_expect_keys_point_at_real_tasks(self):
        for role, idx in list(SEEDS) + list(EXPECT_ROOT):
            self.assertIn(role, TEAM_TASKS)
            self.assertLess(idx, len(TEAM_TASKS[role]))

    def test_seed_files_are_flat_names_with_text(self):
        for files in SEEDS.values():
            for name, text in files.items():
                self.assertEqual(Path(name).name, name)
                self.assertTrue(text.strip())

    def test_part_b_roles_have_the_new_tasks(self):
        self.assertEqual(len(TEAM_TASKS["builder"]), 6)
        self.assertEqual(len(TEAM_TASKS["reviewer"]), 5)
        self.assertEqual(len(TEAM_TASKS["debugger"]), 6)
        self.assertEqual(len(TEAM_TASKS["docs"]), 4)
        self.assertEqual(len(TEAM_TASKS["code-l6"]), 3)


class TextChecks(unittest.TestCase):
    def check(self, name, good, bad):
        self.assertTrue(bench_checks.check_passes(name, good), f"{name} should pass: {good!r}")
        self.assertFalse(bench_checks.check_passes(name, bad), f"{name} should fail: {bad!r}")

    def test_sql_injection_review(self):
        self.check("sql_injection_review",
                   "The query is an f-string, so it is open to SQL injection. Use a parameter placeholder instead.",
                   "The function looks fine and returns every row.")

    def test_two_vulns(self):
        self.check("two_vulns",
                   "There is SQL injection in the query and a hardcoded password in the module.",
                   "Only a naming style issue in the variables.")

    def test_compare_functions(self):
        self.check("compare_functions",
                   "total_loop and total_builtin differ: the loop skips None while total_builtin raises TypeError.",
                   "total_loop and total_builtin are the same, so nothing to report.")

    def test_debug_crash(self):
        self.check("debug_crash",
                   "lookup.py raises KeyError because the item pear is missing from the dict.",
                   "lookup.py has a problem with the dict somewhere.")

    def test_trace_root_cause(self):
        self.check_root("pricing_run.py",
                        "The root cause is in pricing_run.py: it passes pct before price.",
                        "The bug is probably in scale_calc.py.")

    def check_root(self, expect, good, bad):
        self.assertTrue(bench_checks.check_passes("trace_root_cause", good, None, expect))
        self.assertFalse(bench_checks.check_passes("trace_root_cause", bad, None, expect))

    def test_long_summary(self):
        good = "retry timeout backoff " + "word " * 90  # 93 words
        bad = "retry timeout backoff"  # far too short
        self.check("long_summary", good, bad)

    def test_rename_done(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "rn_a.py").write_text("def total_of(xs):\n    return sum(xs)\n", encoding="utf-8")
            (folder / "rn_b.py").write_text("from rn_a import total_of\n", encoding="utf-8")
            self.assertTrue(bench_checks.check_passes("rename_done", "done", folder))
            (folder / "rn_b.py").write_text("from rn_a import tally\n", encoding="utf-8")
            self.assertFalse(bench_checks.check_passes("rename_done", "done", folder))


class SandboxCheck(unittest.TestCase):
    def test_missing_test_file_is_false_without_running_docker(self):
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(bench_checks.subprocess, "run", side_effect=AssertionError("no docker")) as run:
            self.assertFalse(bench_checks.check_passes("sandbox_tests", "reply", Path(tmp)))
            run.assert_not_called()

    def test_no_scratch_folder_is_false(self):
        self.assertFalse(bench_checks.check_passes("sandbox_tests", "reply", None))


class SeedFiles(unittest.TestCase):
    def test_writes_and_verifies(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(bench_checks.seed_files(Path(tmp), {"a.py": "x = 1\n"}), "")
            self.assertTrue((Path(tmp) / "a.py").is_file())

    def test_missing_folder_is_an_error_string(self):
        with tempfile.TemporaryDirectory() as tmp:
            err = bench_checks.seed_files(Path(tmp) / "absent", {"a.py": "x = 1\n"})
            self.assertTrue(err)


if __name__ == "__main__":
    unittest.main()
