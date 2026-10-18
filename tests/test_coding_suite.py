import os
import unittest

from router import config
from scripts import bench_real


class CodingSuite(unittest.TestCase):
    def test_six_levels_each_own_role(self):
        cases = bench_real.coding_cases()
        self.assertEqual([c[1] for c in cases], [f"coding-l{i}" for i in range(1, 7)])
        cfg = config.load_agents()
        for _cid, agent, _seed, task, _check in cases:
            role = config.resolve_role(agent, cfg)
            self.assertIn("run_tests", role["tools"])
            self.assertLessEqual(len(role["tools"]), 6)
            self.assertIn("Do not edit the test files", task)

    def test_active_cases_switch(self):
        old = os.environ.get("BENCH_SUITE")
        os.environ["BENCH_SUITE"] = "coding"
        try:
            self.assertEqual(bench_real.active_cases()[0][0], "code_l1_clamp")
        finally:
            if old is None:
                os.environ.pop("BENCH_SUITE")
            else:
                os.environ["BENCH_SUITE"] = old


if __name__ == "__main__":
    unittest.main()
