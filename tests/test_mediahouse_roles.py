"""Offline checks for the ten mediahouse roles: team membership, wiring, skills, profiles and style files.

No model is called here. The live per-role behaviour is measured by the benchmark, not by these tests.
"""
import unittest
from pathlib import Path

from router.config import load_tf_roles
from router.preflight import contract_errors

ROOT = Path(__file__).resolve().parent.parent
CFG = load_tf_roles()
ROLES = CFG["roles"]
MEDIAHOUSE = [
    "kalamanch", "content-research", "content-factcheck", "content-writer", "content-editor",
    "content-analyst", "media-generator", "media-motion", "manim-style", "voice-artist",
]


class MediahouseMembershipTest(unittest.TestCase):
    def test_team_lists_exactly_the_ten_roles(self):
        self.assertEqual(CFG["teams"]["mediahouse"]["roles"], MEDIAHOUSE)

    def test_every_mediahouse_role_is_defined_and_routed_to_its_team(self):
        for name in MEDIAHOUSE:
            with self.subTest(role=name):
                self.assertIn(name, ROLES)
                self.assertEqual(CFG["team_of_role"].get(name), "mediahouse")

    def test_every_mediahouse_role_has_a_valid_contract(self):
        errors = contract_errors(ROLES, CFG["contracts"])
        self.assertEqual({n: errors[n] for n in MEDIAHOUSE if n in errors}, {})


class MediahouseWiringTest(unittest.TestCase):
    def test_tool_cap_and_required_tool(self):
        for name in MEDIAHOUSE:
            role = ROLES[name]
            with self.subTest(role=name):
                self.assertLessEqual(len(role["tools"]), 12)
                if "required_tool" in role:
                    self.assertIn(role["required_tool"], role["tools"])

    def test_each_role_skill_file_exists(self):
        for name in MEDIAHOUSE:
            for skill in ROLES[name].get("skills", []):
                with self.subTest(role=name, skill=skill):
                    self.assertTrue((ROOT / "router" / "skills" / skill / "SKILL.md").is_file())

    def test_each_role_profile_file_exists(self):
        for name in MEDIAHOUSE:
            profile = ROLES[name]["profile"]
            with self.subTest(role=name, profile=profile):
                self.assertTrue((ROOT / "profiles" / f"{profile}.yaml").is_file())

    def test_style_roles_are_read_only(self):
        for name in ("manim-style", "voice-artist"):
            with self.subTest(role=name):
                self.assertEqual(ROLES[name]["tools"], ["read_file"])
                self.assertNotIn("native", ROLES[name])


class StyleRoleFilesTest(unittest.TestCase):
    def test_manim_style_profile_file_exists(self):
        self.assertTrue((ROOT / "docs" / "designs" / "manim-style-profile.md").is_file())

    def test_manim_style_skill_forbids_invented_settings(self):
        text = (ROOT / "router" / "skills" / "role-manim-style" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Do not invent settings", text)

    def test_voice_artist_skill_requires_consent_note(self):
        text = (ROOT / "router" / "skills" / "role-voice-artist" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("consent", text.lower())

    @unittest.expectedFailure  # known gap: no voice profile exists yet; voice-artist can only report "missing"
    def test_voice_artist_profile_file_exists(self):
        self.assertTrue((ROOT / "docs" / "designs" / "voice-artist-profile.md").is_file())


if __name__ == "__main__":
    unittest.main()
