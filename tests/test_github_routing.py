import unittest
from pathlib import Path

import yaml

from gateway.config import load_personas, resolve_role

ROOT = Path(__file__).resolve().parent.parent
READ_ONLY_WRITES = {"merge_pull_request", "update_pull_request", "issue_write", "actions_run_trigger"}


class GithubRouting(unittest.TestCase):
    def setUp(self):
        self.cfg = load_personas()

    def test_github_ops_routes_to_read_role_with_github_profile(self):
        role = resolve_role("github-ops", self.cfg)
        self.assertEqual(role["role"], "github-read")
        self.assertEqual(role["profile"], "github")
        self.assertIn("list_pull_requests", role["tools"])

    def test_github_actions_ops_routes_to_actions_role(self):
        role = resolve_role("github-actions-ops", self.cfg)
        self.assertEqual(role["role"], "github-actions-read")
        self.assertEqual(role["profile"], "github")
        self.assertIn("actions_list", role["tools"])

    def test_github_roles_never_allow_write_tools(self):
        for slug in ("github-ops", "github-actions-ops"):
            role = resolve_role(slug, self.cfg)
            self.assertFalse(READ_ONLY_WRITES & set(role["tools"]), slug)

    def test_github_role_tools_exist_in_profile(self):
        profile = yaml.safe_load((ROOT / "profiles" / "github.yaml").read_text(encoding="utf-8"))
        allowed = set(profile["servers"][0]["tools"])
        for slug in ("github-ops", "github-actions-ops"):
            role = resolve_role(slug, self.cfg)
            self.assertTrue(set(role["tools"]) <= allowed, slug)


if __name__ == "__main__":
    unittest.main()
