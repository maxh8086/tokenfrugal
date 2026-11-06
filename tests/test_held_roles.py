"""Held content-analyst collectors and the retired content-analyst alias (docs/designs/studio-and-collector-roles.md, Piece 1)."""
import unittest

from router import preflight
from router.config import ROOT, load_tf_roles, resolve_role

CFG = load_tf_roles()
HELD = ("content-analyst-linkedin", "content-analyst-meta", "content-analyst-x")
LIVE = ("content-analyst-reddit-hn", "content-analyst-rss", "content-analyst-youtube", "content-analyst-curator")


class HeldRolesTest(unittest.TestCase):
    def test_held_roles_carry_a_reason(self):
        for name in HELD:
            r = resolve_role(name, CFG)
            self.assertTrue(r["held"], name)
            self.assertTrue(r["held"].startswith("Held:"), name)

    def test_live_roles_are_not_held(self):
        for name in LIVE:
            self.assertIsNone(resolve_role(name, CFG)["held"], name)

    def test_held_roles_pass_static_checks_without_a_contract(self):
        held_roles = {n: CFG["roles"][n] for n in HELD}
        self.assertEqual(preflight.role_errors(held_roles, ROOT), {})
        self.assertEqual(preflight.contract_errors(held_roles, {}), {})

    def test_live_collectors_and_curator_are_within_the_recommended_tool_count(self):
        for name in LIVE:
            self.assertLessEqual(len(CFG["roles"][name]["tools"]), 6, name)


class RetiredAliasTest(unittest.TestCase):
    def test_old_slug_resolves_to_the_curator(self):
        self.assertEqual(resolve_role("content-analyst", CFG)["role"], "content-analyst-curator")

    def test_old_slug_no_longer_falls_back_to_builder(self):
        self.assertNotEqual(resolve_role("content-analyst", CFG)["role"], "builder")


if __name__ == "__main__":
    unittest.main()
