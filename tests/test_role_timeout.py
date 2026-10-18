import unittest

from router import loop, server
from router.config import resolve_role
from scripts import bench_real

FROZEN = {"code-l1": 120, "code-l2": 150, "code-l3": 180, "code-l4": 300, "code-l5": 300, "code-l6": 300}


class RoleTimeout(unittest.TestCase):
    def test_frozen_values(self):
        for role, t in FROZEN.items():
            self.assertEqual(resolve_role(role.replace("code-", "coding-"), server.CFG).get("timeout_s"), t, role)

    def test_loop_uses_role_value_else_global(self):
        self.assertEqual(loop.role_timeout({"timeout_s": 120}), 120.0)
        self.assertEqual(loop.role_timeout({}), loop.TASK_TIMEOUT)

    def test_bench_limits_replace_case_timeout(self):
        t, wd = bench_real.case_limits("coding-l4")
        self.assertEqual((t, wd), (300.0, 300.0 + bench_real.WATCHDOG_GRACE))
        t, wd = bench_real.case_limits("builder")
        self.assertIsNone(t)
        self.assertEqual(wd, bench_real.CASE_TIMEOUT)


if __name__ == "__main__":
    unittest.main()
