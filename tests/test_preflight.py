import tempfile
import unittest
from pathlib import Path

from router import preflight


class TaskError(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        (Path(self.ws) / "bench").mkdir()
        self.cfg = {"members": {"engineering": ["engineering-code-reviewer"]}}

    def test_known_agent_and_existing_folder_pass(self):
        self.assertEqual(preflight.task_error("engineering-code-reviewer", "Read /workspace/bench/a.py", self.cfg, self.ws), "")

    def test_unknown_agent_is_refused(self):
        self.assertIn("unknown agent", preflight.task_error("no-such-agent", "x", self.cfg, self.ws))

    def test_missing_folder_is_refused(self):
        err = preflight.task_error("engineering-code-reviewer", "Read /workspace/nope/a.py", self.cfg, self.ws)
        self.assertIn("/workspace/nope", err)


class SkillError(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.file = self.dir / "SKILL.md"

    def test_matching_baseline_passes(self):
        self.file.write_text("base\n", encoding="utf-8")
        self.assertEqual(preflight.skill_error(self.file, "base\n"), "")

    def test_crlf_on_disk_still_matches(self):
        self.file.write_bytes(b"base\r\n")
        self.assertEqual(preflight.skill_error(self.file, "base\n"), "")

    def test_changed_baseline_is_refused(self):
        self.file.write_text("candidate\n", encoding="utf-8")
        self.assertIn("differs", preflight.skill_error(self.file, "base\n"))

    def test_missing_file_is_refused(self):
        self.assertIn("missing", preflight.skill_error(self.dir / "none.md", "base\n"))


class RoleErrors(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "profiles").mkdir()
        (self.root / "profiles" / "build.yaml").write_text(
            "servers:\n- type: image\n  tools:\n  - read_file\n", encoding="utf-8")
        (self.root / "profiles" / "open.yaml").write_text(
            "servers:\n- type: image\n  snapshot:\n    server:\n      name: x\n", encoding="utf-8")
        (self.root / "router" / "skills" / "role-b").mkdir(parents=True)
        (self.root / "router" / "skills" / "role-b" / "SKILL.md").write_text("x\n", encoding="utf-8")
        (self.root / "docker-compose.yml").write_text("services:\n  neo4j:\n    image: x\n", encoding="utf-8")

    def test_good_role_passes(self):
        roles = {"ok": {"model": "builder", "profile": "build", "skills": ["role-b"], "compose": ["neo4j"],
                        "native": ["sandbox"], "tools": ["read_file"]}}
        self.assertEqual(preflight.role_errors(roles, self.root), {})

    def test_tool_missing_from_readable_sources_is_flagged(self):
        roles = {"r": {"model": "builder", "profile": "build", "tools": ["read_file", "nope_tool"]}}
        probs = preflight.role_errors(roles, self.root)["r"]
        self.assertEqual(probs, ["tool 'nope_tool' is not provided by any of its profiles or native servers"])

    def test_native_tool_is_found_in_the_server_source(self):
        roles = {"r": {"model": "builder", "native": ["sandbox"], "tools": ["run_tests", "run_python"]}}
        self.assertEqual(preflight.role_errors(roles, self.root), {})

    def test_unfiltered_profile_is_unverified_not_failed(self):
        roles = {"r": {"model": "builder", "profile": "open", "tools": ["anything"]}}
        self.assertEqual(preflight.role_errors(roles, self.root), {})
        self.assertEqual(preflight.unverified_roles(roles, self.root), {"r": ["profile open"]})

    def test_each_broken_field_is_reported(self):
        roles = {"bad": {"model": "gpt", "profile": "nope", "skills": ["gone"], "compose": ["db-x"],
                         "native": ["mystery"], "tools": [f"t{i}" for i in range(7)]}}
        probs = preflight.role_errors(roles, self.root)["bad"]
        self.assertEqual(len(probs), 6)


class HealSkill(unittest.TestCase):
    def setUp(self):
        self.file = Path(tempfile.mkdtemp()) / "SKILL.md"

    def test_drifted_file_is_restored(self):
        self.file.write_text("candidate\n", encoding="utf-8")
        self.assertIn("restored", preflight.heal_skill(self.file, "base\n"))
        self.assertEqual(self.file.read_text(encoding="utf-8"), "base\n")

    def test_missing_file_is_recreated(self):
        self.assertIn("restored", preflight.heal_skill(self.file, "base\n"))
        self.assertTrue(self.file.exists())

    def test_clean_file_needs_no_action(self):
        self.file.write_text("base\n", encoding="utf-8")
        self.assertEqual(preflight.heal_skill(self.file, "base\n"), "")


if __name__ == "__main__":
    unittest.main()
