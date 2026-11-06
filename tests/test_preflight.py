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
                         "native": ["mystery"], "tools": [f"t{i}" for i in range(preflight.MAX_TOOLS + 1)]}}
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


class MediahouseRoles(unittest.TestCase):
    NAMES = ("content-writer", "content-analyst", "media-generator", "media-motion")

    def setUp(self):
        from router.config import ROOT, load_tf_roles
        cfg = load_tf_roles()
        self.root = ROOT
        self.roles = {n: cfg["roles"][n] for n in self.NAMES}
        self.contracts = cfg.get("contracts") or {}

    def test_each_role_has_its_profile_file(self):
        for name, role in self.roles.items():
            self.assertTrue((self.root / "profiles" / f"{role['profile']}.yaml").exists(), name)

    def test_roles_pass_static_checks(self):
        self.assertEqual(preflight.role_errors(self.roles, self.root), {})

    def test_tools_are_served_and_within_limit(self):
        # These native servers are built from upstream sources outside the repo, so their tools are "unverified" offline.
        off_repo = {"native reddit", "native hn", "native rss", "native youtube", "native qdrant", "native postgres"}
        for name, role in self.roles.items():
            missing, unverified = preflight.tool_gaps(role, self.root)
            self.assertEqual(missing, [], name)
            self.assertLessEqual(set(unverified), off_repo, name)
            # content-analyst is the documented exception to the recommended 6 (docs/content-analyst.md); MAX_TOOLS still applies.
            limit = preflight.MAX_TOOLS if name == "content-analyst" else preflight.RECOMMENDED_TOOLS
            self.assertLessEqual(len(role["tools"]), limit, name)

    def test_media_generator_native_tools_parse_from_source(self):
        self.assertEqual(preflight._native_tools(self.root, "media-generator"), {"list_raw", "list_renders", "mgen", "render_film"})

    def test_media_motion_native_tools_parse_from_source(self):
        self.assertEqual(preflight._native_tools(self.root, "media-briefing"), {"brief"})

    def test_contracts_present(self):
        self.assertEqual(preflight.contract_errors(self.roles, {n: self.contracts.get(n) for n in self.NAMES}), {})
