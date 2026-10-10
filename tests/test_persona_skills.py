import unittest

from gateway.config import load_personas, resolve_role


class PersonaSkillsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = load_personas()

    def test_tracker_role_has_planning_skill(self):
        r = resolve_role("project-management-project-shepherd", self.cfg)
        self.assertIn("planning", r["skills"])

    def test_persona_skill_mapping_applies_to_agent(self):
        r = resolve_role("project-management-project-shepherd", self.cfg)
        self.assertIn("planning", r["skills"])

    def test_unmapped_agent_has_no_skills(self):
        r = resolve_role("engineering-sre", self.cfg)
        self.assertEqual(r["skills"], [])


if __name__ == "__main__":
    unittest.main()
