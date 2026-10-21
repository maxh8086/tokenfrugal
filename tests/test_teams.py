import json
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

import yaml

from router import config
from scripts import tf_roles_ui as ui

TF_ROLES = Path(config.__file__).parent / "tf-roles.yaml"


class TeamPartition(unittest.TestCase):
    def setUp(self):
        self.base = yaml.safe_load(TF_ROLES.read_text(encoding="utf-8"))
        self.roles = set(self.base["roles"]) | set(self.base.get("pending_roles") or {})
        self.assigned = [r for t in self.base["teams"].values() for r in t["roles"]]

    def test_every_role_in_exactly_one_team(self):
        self.assertEqual(set(self.assigned), self.roles)
        self.assertEqual([r for r, n in Counter(self.assigned).items() if n > 1], [])

    def test_teams_name_only_known_roles(self):
        self.assertEqual(set(self.assigned) - self.roles, set())

    def test_ui_roles_share_one_team(self):
        cfg = config.load_tf_roles()
        teams = {config.team_of(r, cfg) for r in self.roles if r.startswith("ui-")}
        self.assertEqual(teams, {"ui-ux"})


class TeamListing(unittest.TestCase):
    def test_list_roles_names_orchestrator_and_each_lead(self):
        from router import server
        text = server.list_roles()
        cfg = config.load_tf_roles()
        self.assertIn(f"orchestrator: {cfg['orchestrator']}", text)
        for name, team in cfg["teams"].items():
            self.assertIn(f"team {name}: lead {team['lead']} | {team['description']}", text)


class TeamDefaults(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.picks = Path(self._tmp.name) / "teams.json"
        self.patch = mock.patch.object(config, "TF_ROLES_TEAMS_FILE", self.picks)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self._tmp.cleanup()

    def test_defaults_without_pick_file(self):
        cfg = config.load_tf_roles()
        self.assertEqual(cfg["orchestrator"], "claude-sonnet-5-5")
        self.assertEqual(config.lead_for("ui-ux", cfg), "claude-haiku-5-5")
        self.assertEqual(config.team_of("builder", cfg), "development")
        self.assertIsNone(config.team_of("no-such-role", cfg))

    def test_pick_file_overrides_orchestrator_and_one_lead(self):
        self.picks.write_text(json.dumps({"orchestrator": "claude-opus-5-5", "leads": {"ops": "claude-sonnet-5-5"}}), encoding="utf-8")
        cfg = config.load_tf_roles()
        self.assertEqual(cfg["orchestrator"], "claude-opus-5-5")
        self.assertEqual(config.lead_for("ops", cfg), "claude-sonnet-5-5")
        self.assertEqual(config.lead_for("ui-ux", cfg), "claude-haiku-5-5")

    def test_save_stores_only_differences(self):
        out = ui.save_teams({"orchestrator": "claude-sonnet-5-5",
                             "leads": {"ops": "claude-haiku-5-5", "ui-ux": "claude-opus-5-5"}})
        self.assertEqual(out, {"leads": {"ui-ux": "claude-opus-5-5"}})
        self.assertEqual(json.loads(self.picks.read_text(encoding="utf-8")), out)

    def test_save_rejects_unknown_team_and_model(self):
        with self.assertRaises(ValueError):
            ui.save_teams({"orchestrator": "claude-sonnet-5-5", "leads": {"nope": "claude-haiku-5-5"}})
        with self.assertRaises(ValueError):
            ui.save_teams({"orchestrator": "builder", "leads": {}})
        self.assertFalse(self.picks.exists())


if __name__ == "__main__":
    unittest.main()
