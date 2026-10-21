import tempfile
import unittest
from pathlib import Path

import yaml

from scripts import role_improve as ri

DIFF = """--- a/router/skills/role-x/SKILL.md
+++ b/router/skills/role-x/SKILL.md
@@ -1 +1 @@
-a
+b
"""

OUTSIDE = """--- a/router/tf-roles.yaml
+++ b/router/tf-roles.yaml
@@ -1 +1 @@
-x
+y
"""


class RoleImproveGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        skill = self.root / "router" / "skills" / "role-x" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("a\n", encoding="utf-8", newline="\n")
        self.skill = skill
        self.store = self.root / "proposals.json"
        self.cfg = self.root / "tf-roles.yaml"
        self._write_cfg(enabled=True, gate="approval", scope=["skills"])

    def tearDown(self):
        self._tmp.cleanup()

    def _write_cfg(self, *, enabled, gate, scope):
        cfg = {
            "roles": {"role-x": {"model": "builder", "profile": "build", "skills": ["role-x"], "improve": "gated"}},
            "self_improve": {"enabled": enabled, "gate": gate, "scope": scope},
        }
        self.cfg.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    def test_diff_paths_strips_prefixes(self):
        self.assertEqual(ri.diff_paths(DIFF), {"router/skills/role-x/SKILL.md"})

    def test_propose_stores_without_touching_the_file(self):
        item = ri.propose("role-x", DIFF, "shorter", tf_roles=self.cfg, store=self.store)
        self.assertEqual(item["status"], "proposed")
        self.assertEqual(self.skill.read_text(encoding="utf-8"), "a\n")

    def test_propose_outside_role_skills_is_refused(self):
        with self.assertRaises(ValueError):
            ri.propose("role-x", OUTSIDE, "bad", tf_roles=self.cfg, store=self.store)
        self.assertFalse(self.store.exists())

    def test_disabled_gate_refuses_proposals(self):
        self._write_cfg(enabled=False, gate="approval", scope=["skills"])
        with self.assertRaises(ValueError):
            ri.propose("role-x", DIFF, "x", tf_roles=self.cfg, store=self.store)

    def test_role_without_opt_in_is_refused(self):
        cfg = yaml.safe_load(self.cfg.read_text(encoding="utf-8"))
        del cfg["roles"]["role-x"]["improve"]
        self.cfg.write_text(yaml.safe_dump(cfg), encoding="utf-8")
        with self.assertRaises(ValueError):
            ri.propose("role-x", DIFF, "x", tf_roles=self.cfg, store=self.store)

    def test_scope_without_skills_refuses_proposals(self):
        self._write_cfg(enabled=True, gate="approval", scope=["timeouts"])
        with self.assertRaises(ValueError):
            ri.propose("role-x", DIFF, "x", tf_roles=self.cfg, store=self.store)

    def test_approve_applies_once(self):
        item = ri.propose("role-x", DIFF, "x", tf_roles=self.cfg, store=self.store)
        done = ri.approve(item["id"], root=self.root, store=self.store)
        self.assertEqual(done["status"], "applied")
        self.assertEqual(self.skill.read_text(encoding="utf-8"), "b\n")
        with self.assertRaises(ValueError):
            ri.approve(item["id"], root=self.root, store=self.store)

    def test_reject_leaves_file_unchanged(self):
        item = ri.propose("role-x", DIFF, "x", tf_roles=self.cfg, store=self.store)
        self.assertEqual(ri.reject(item["id"], "no", store=self.store)["status"], "rejected")
        self.assertEqual(self.skill.read_text(encoding="utf-8"), "a\n")


if __name__ == "__main__":
    unittest.main()
