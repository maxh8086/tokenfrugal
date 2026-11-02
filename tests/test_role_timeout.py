import unittest

from router import loop, server
from router.config import resolve_role
from scripts.bench_team_tasks import TEAM_TASKS

FROZEN = {"code-l1": 240, "code-l2": 225, "code-l3": 270, "code-l4": 450, "code-l5": 450, "code-l6": 450}


class RoleTimeout(unittest.TestCase):
    def test_frozen_values(self):
        for role, t in FROZEN.items():
            self.assertEqual(resolve_role(role.replace("code-", "coding-"), server.CFG).get("timeout_s"), t, role)

    def test_non_coding_values_by_agent(self):
        # verified p95 x 1.5, rounded up to 10, floor 60; a shared role takes its slowest case.
        # engineering-sre (debugger) is a user-approved raise to 300 (2026-10-27), not derived.
        expect = {
            "engineering-backend-architect": 130, "gis-analyst": 80, "engineering-software-architect": 90,
            "security-auditor": 300, "testing-code-reviewer": 90, "engineering-sre": 300,
            "engineering-technical-writer": 150, "design-ui-designer": 300,  # designer raised 240 -> 300 (2026-10-29)
            "testing-evidence-collector": 120,  # browser role raised 80 -> 120 (2026-10-29)
            "project-management-project-shepherd": 60, "support-docs-writer": 90,
        }
        for agent, t in expect.items():
            self.assertEqual(resolve_role(agent, server.CFG).get("timeout_s"), t, agent)

    def test_read_only_thinker_roles_have_explicit_timeout(self):
        # set 2026-10-28: read-only roles that fell back to the global TASK_TIMEOUT
        for role in ("github-read", "github-actions-read", "finance"):
            self.assertEqual(server.CFG["roles"][role].get("timeout_s"), 90, role)

    def test_every_team_task_agent_has_a_timeout(self):
        # devops has no explicit timeout_s in router/tf-roles.yaml (its role falls back to the global TASK_TIMEOUT);
        # it predates the retire-suites change and is listed here so the gap stays visible
        no_explicit_timeout = {"engineering-devops-automator"}
        for role, tasks in TEAM_TASKS.items():
            for agent, _prompt, _check in tasks:
                if agent in no_explicit_timeout:
                    continue
                self.assertIsNotNone(resolve_role(agent, server.CFG).get("timeout_s"), f"{role}: {agent}")

    def test_loop_uses_role_value_else_global(self):
        self.assertEqual(loop.role_timeout({"timeout_s": 120}), 120.0)
        self.assertEqual(loop.role_timeout({}), loop.TASK_TIMEOUT)


if __name__ == "__main__":
    unittest.main()
