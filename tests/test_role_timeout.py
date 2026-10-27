import unittest

from router import loop, server
from router.config import resolve_role
from scripts import bench_real

FROZEN = {"code-l1": 180, "code-l2": 225, "code-l3": 270, "code-l4": 450, "code-l5": 450, "code-l6": 450}


class RoleTimeout(unittest.TestCase):
    def test_frozen_values(self):
        for role, t in FROZEN.items():
            self.assertEqual(resolve_role(role.replace("code-", "coding-"), server.CFG).get("timeout_s"), t, role)

    def test_non_coding_values_by_agent(self):
        # verified p95 x 1.5, rounded up to 10, floor 60; a shared role takes its slowest case
        expect = {
            "engineering-backend-architect": 90, "gis-analyst": 60, "engineering-software-architect": 60,
            "security-auditor": 300, "testing-code-reviewer": 60, "engineering-sre": 220,
            "engineering-technical-writer": 100, "design-ui-designer": 160, "testing-evidence-collector": 80,
            "project-management-project-shepherd": 60, "support-docs-writer": 60,
        }
        for agent, t in expect.items():
            self.assertEqual(resolve_role(agent, server.CFG).get("timeout_s"), t, agent)

    def test_every_bench_case_agent_has_a_timeout(self):
        for case in bench_real.cases() + bench_real.hard_cases():
            agent = case[1]
            self.assertIsNotNone(bench_real.case_limits(agent)[0], agent)

    def test_loop_uses_role_value_else_global(self):
        self.assertEqual(loop.role_timeout({"timeout_s": 120}), 120.0)
        self.assertEqual(loop.role_timeout({}), loop.TASK_TIMEOUT)

    def test_bench_limits_replace_case_timeout(self):
        t, wd = bench_real.case_limits("coding-l4")
        self.assertEqual((t, wd), (450.0, 450.0 + bench_real.WATCHDOG_GRACE))
        t, wd = bench_real.case_limits("engineering-devops-automator")
        self.assertIsNone(t)
        self.assertEqual(wd, bench_real.CASE_TIMEOUT)


if __name__ == "__main__":
    unittest.main()
