import unittest

from router.config import load_tf_roles, resolve_role


class AgentSkillsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_tf_roles()

    def test_tracker_role_has_planning_skill(self):
        r = resolve_role("project-management-project-shepherd", self.cfg)
        self.assertIn("planning", r["skills"])

    def test_agent_skill_mapping_applies_to_agent(self):
        r = resolve_role("project-management-project-shepherd", self.cfg)
        self.assertIn("planning", r["skills"])

    def test_unmapped_agent_gets_only_its_role_skill(self):
        r = resolve_role("engineering-backend-architect", self.cfg)
        self.assertEqual(r["skills"], ["role-builder"])


if __name__ == "__main__":
    unittest.main()
