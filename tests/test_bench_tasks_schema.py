"""Schema guard for scripts/bench_team_tasks.py: every role holds a non-empty list of (agent, prompt, check) tuples
whose check names exist in scripts/bench_checks.CHECKS. Offline; bench_team_tasks has no imports, and bench_checks
only imports router.preflight."""
import unittest

from scripts import bench_checks
from scripts.bench_team_tasks import TEAM_TASKS


class TeamTaskSchema(unittest.TestCase):
    def test_every_role_is_a_non_empty_list(self):
        for role, tasks in TEAM_TASKS.items():
            with self.subTest(role=role):
                self.assertIsInstance(tasks, list)
                self.assertTrue(tasks, f"{role} has no tasks")

    def test_every_entry_is_a_str_str_str_triple(self):
        for role, tasks in TEAM_TASKS.items():
            for entry in tasks:
                with self.subTest(role=role, entry=entry):
                    self.assertIsInstance(entry, tuple)
                    self.assertEqual(len(entry), 3)
                    for part in entry:
                        self.assertIsInstance(part, str)

    def test_every_check_name_is_known(self):
        for role, tasks in TEAM_TASKS.items():
            for _agent, _prompt, check in tasks:
                with self.subTest(role=role, check=check):
                    self.assertIn(check, bench_checks.CHECKS)


if __name__ == "__main__":
    unittest.main()
