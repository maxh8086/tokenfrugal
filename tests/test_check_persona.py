import unittest

from router.config import check_agent


class CheckAgentTest(unittest.TestCase):
    cfg = {
        "overrides": {"engineering-sre": "builder"},
        "members": {"engineering": ["engineering-sre-lead"]},
    }

    def test_override_slug_is_known(self):
        self.assertEqual(check_agent("engineering-sre", self.cfg), "")

    def test_member_slug_is_known(self):
        self.assertEqual(check_agent("engineering-sre-lead", self.cfg), "")

    def test_unknown_slug_returns_error_with_slug(self):
        err = check_agent("no-such-agent", self.cfg)
        self.assertTrue(err)
        self.assertIn("no-such-agent", err)


if __name__ == "__main__":
    unittest.main()
