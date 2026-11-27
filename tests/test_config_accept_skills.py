import unittest
from copy import deepcopy
from pathlib import Path

from router import config, preflight


class HostAcceptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = config.load_tf_roles()

    def setUp(self):
        self.cfg = deepcopy(self.cfg)
        self.cfg.update(agent_mcps={}, role_mcps={}, agent_skills={})

    def test_replaces_role_skills_and_preserves_agent_skill_order(self):
        self.cfg["agent_skills"]["coding-l2"] = ["extra-b", "code-l2", "extra-a"]
        role = config.resolve_role("coding-l2", self.cfg)
        original = deepcopy(role)
        adapted = config.with_host_accept(role, self.cfg)
        self.assertEqual(adapted["skills"], ["code-l2-accept", "extra-b", "extra-a"])
        self.assertEqual(adapted["tools"], [t for t in role["tools"] if t != "run_tests"])
        self.assertEqual(role, original)

    def test_ordinary_resolution_stays_unchanged_for_every_role(self):
        for name, spec in self.cfg["roles"].items():
            with self.subTest(role=name):
                self.cfg["overrides"]["test-agent"] = name
                role = config.resolve_role("test-agent", self.cfg)
                original = deepcopy(role)
                self.assertEqual(role["skills"], spec.get("skills") or [])
                self.assertEqual(role.get("tools"), spec.get("tools"))
                adapted = config.with_host_accept(role, self.cfg)
                if not spec.get("accept_skills"):
                    self.assertEqual(adapted, original)
                self.assertEqual(role, original)
                self.assertEqual(config.resolve_role("test-agent", self.cfg), original)

    def test_fixture_role_is_copied_with_its_tools(self):
        role = {"role": "fixture", "skills": ["custom"], "tools": ["run_tests"]}
        adapted = config.with_host_accept(role, self.cfg)
        self.assertEqual(adapted, role)
        self.assertIsNot(adapted, role)

    def test_filters_run_tests_added_by_selected_toolkit(self):
        self.cfg["roles"]["code-l2"]["tools"] = ["read_file"]
        self.cfg["mcp_catalog"]["test-kit"] = {"tools": ["run_tests", "custom"]}
        self.cfg["agent_mcps"]["coding-l2"] = ["test-kit"]
        role = config.resolve_role("coding-l2", self.cfg)
        self.assertEqual(role["tools"], ["run_tests", "custom"])
        self.assertEqual(config.with_host_accept(role, self.cfg)["tools"], ["custom"])

    def test_preflight_reports_missing_accept_skill(self):
        root = Path(__file__).resolve().parents[1]
        role = dict(self.cfg["roles"]["code-l2"], accept_skills=["missing-accept"])
        errors = preflight.role_errors({"code-l2": role}, root)
        self.assertIn("skill router/skills/missing-accept/SKILL.md is missing",
                      errors.get("code-l2", []))
