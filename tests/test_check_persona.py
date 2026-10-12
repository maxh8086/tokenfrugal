import unittest

from gateway.config import check_persona


class CheckPersonaTest(unittest.TestCase):
    cfg = {
        "overrides": {"engineering-sre": "builder"},
        "members": {"engineering": ["engineering-sre-lead"]},
    }

    def test_override_slug_is_known(self):
        self.assertEqual(check_persona("engineering-sre", self.cfg), "")

    def test_member_slug_is_known(self):
        self.assertEqual(check_persona("engineering-sre-lead", self.cfg), "")

    def test_unknown_slug_returns_error_with_slug(self):
        err = check_persona("no-such-persona", self.cfg)
        self.assertTrue(err)
        self.assertIn("no-such-persona", err)


if __name__ == "__main__":
    unittest.main()
