import unittest

from gateway.config import check_persona

CFG = {
    "overrides": {"engineering-code-reviewer": "thinker"},
    "persona_models": {"engineering-test-writer": "builder"},
    "persona_skills": {},
    "members": {"engineering": ["engineering-backend-architect"]},
}


class CheckPersonaTests(unittest.TestCase):
    def test_known_override_slug_is_accepted(self):
        self.assertEqual(check_persona("engineering-code-reviewer", CFG), "")

    def test_known_member_slug_is_accepted(self):
        self.assertEqual(check_persona("engineering-backend-architect", CFG), "")

    def test_known_persona_model_slug_is_accepted(self):
        self.assertEqual(check_persona("engineering-test-writer", CFG), "")

    def test_unknown_slug_returns_error(self):
        err = check_persona("no-such-persona", CFG)
        self.assertTrue(err)
        self.assertIn("no-such-persona", err)


if __name__ == "__main__":
    unittest.main()
