import unittest

from router.config import check_agent

CFG = {
    "overrides": {"engineering-code-reviewer": "thinker"},
    "persona_models": {"engineering-test-writer": "builder"},
    "persona_skills": {},
    "members": {"engineering": ["engineering-backend-architect"]},
}


class CheckAgentTests(unittest.TestCase):
    def test_known_override_slug_is_accepted(self):
        self.assertEqual(check_agent("engineering-code-reviewer", CFG), "")

    def test_known_member_slug_is_accepted(self):
        self.assertEqual(check_agent("engineering-backend-architect", CFG), "")

    def test_known_persona_model_slug_is_accepted(self):
        self.assertEqual(check_agent("engineering-test-writer", CFG), "")

    def test_unknown_slug_returns_error(self):
        err = check_agent("no-such-agent", CFG)
        self.assertTrue(err)
        self.assertIn("no-such-agent", err)


if __name__ == "__main__":
    unittest.main()
