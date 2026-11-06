"""Offline checks for the skill gate's case map: scripts/skill_gate_live.py calls dev-coding roles by name.

No Docker, no model: the YAML is parsed directly, the bench output is a small fake JSON in a temp folder.
"""
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from router.config import ROOT
from scripts import skill_gate_live
from scripts.bench_team_tasks import TEAM_TASKS


class SkillGateRolesTests(unittest.TestCase):
    def test_every_case_is_a_dev_coding_role(self):
        cfg = yaml.safe_load((ROOT / "router" / "tf-roles.yaml").read_text(encoding="utf-8"))
        dev_coding = cfg["teams"]["dev-coding"]["roles"]
        for skill, role in skill_gate_live.CASES.items():
            self.assertIn(role, dev_coding, f"{skill} -> {role} is not in teams['dev-coding']")
            self.assertIn(role, cfg["roles"], f"{role} is not a key under roles:")

    def test_every_case_has_a_bench_task(self):
        for skill, role in skill_gate_live.CASES.items():
            self.assertTrue(TEAM_TASKS.get(role), f"{role} (for {skill}) has no task in TEAM_TASKS")

    def test_reader_counts_only_non_infra_runs(self):
        data = {"results": {"roles": {"code-l2": {"runs": [
            {"ok": True, "infra": False},
            {"ok": False, "infra": False},
            {"ok": True, "infra": False},
            {"ok": False, "infra": True},  # infra: left out of both counts
            {"ok": True, "infra": True},
        ]}, "code-l4": {"runs": [{"ok": True, "infra": False}]}}}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "20260101-000000-gate.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(skill_gate_live._role_runs(loaded, "code-l2"), (2, 3))
        self.assertEqual(skill_gate_live._role_runs(loaded, "code-l4"), (1, 1))

    def test_reader_raises_for_missing_role(self):
        data = {"results": {"roles": {"code-l4": {"runs": []}}}}
        with self.assertRaisesRegex(RuntimeError, "code-l6"):
            skill_gate_live._role_runs(data, "code-l6")
        with self.assertRaisesRegex(RuntimeError, "code-l6"):
            skill_gate_live._role_runs({"results": {"roles": {"error": "timeout"}}}, "code-l6")

    def test_gate_source_has_no_suite_env(self):
        source = Path(skill_gate_live.__file__).read_text(encoding="utf-8")
        self.assertNotIn("BENCH_SUITE", source)
        self.assertNotIn("BENCH_CASES", source)


if __name__ == "__main__":
    unittest.main()
