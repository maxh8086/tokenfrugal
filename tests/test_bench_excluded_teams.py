"""Offline check that mediahouse is kept out of the model benchmark. No Docker, model or router is contacted."""
import unittest

from router.config import load_tf_roles
from scripts.bench_team_tasks import BENCH_EXCLUDED_TEAMS, TEAM_TASKS


class ExcludedTeams(unittest.TestCase):
    def test_mediahouse_is_excluded(self):
        self.assertIn("mediahouse", BENCH_EXCLUDED_TEAMS)

    def test_excluded_team_roles_have_no_benchmark_tasks(self):
        cfg = load_tf_roles()
        excluded = {r for t in BENCH_EXCLUDED_TEAMS for r in cfg["teams"][t]["roles"]}
        self.assertTrue(excluded)
        self.assertFalse(excluded & set(TEAM_TASKS))


if __name__ == "__main__":
    unittest.main()
