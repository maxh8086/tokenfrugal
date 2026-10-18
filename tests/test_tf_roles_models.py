import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import config
from router.config import load_tf_roles, resolve_role

CLEAN = {"TOKENFRUGAL_MODEL_BUILDER": "", "TOKENFRUGAL_MODEL_THINKER": "", "TOKENFRUGAL_TF_ROLES_MODELS": ""}


def load(override=None):
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, CLEAN):
        f = Path(d) / "pm.json"
        if override is not None:
            f.write_text(json.dumps(override), encoding="utf-8")
        with mock.patch.object(config, "TF_ROLES_MODELS_FILE", f):
            return load_tf_roles()


class AgentModelTests(unittest.TestCase):
    def test_yaml_default_is_empty_so_role_model_applies(self):
        cfg = load()
        self.assertEqual(cfg["agent_models"], {})
        self.assertEqual(resolve_role("engineering-backend-architect", cfg)["model"], cfg["models"]["builder"])
        self.assertEqual(resolve_role("gis-analyst", cfg)["model"], cfg["models"]["builder"])

    def test_logical_name_resolves_to_role_model(self):
        cfg = load()
        self.assertEqual(resolve_role("gis-analyst", cfg)["model"], cfg["models"]["builder"])
        self.assertEqual(resolve_role("design-ui-designer", cfg)["model"], cfg["models"]["thinker"])

    def test_unmapped_agent_keeps_role_model(self):
        cfg = load()
        self.assertEqual(resolve_role("zzz-unknown", cfg)["model"], cfg["models"]["builder"])

    def test_user_file_overrides_yaml(self):
        cfg = load({"engineering-sre": "my-model:7b"})
        self.assertEqual(resolve_role("engineering-sre", cfg)["model"], "my-model:7b")
        self.assertEqual(resolve_role("engineering-sre", cfg)["role"], "debugger")

    def test_blank_override_means_role_default(self):
        cfg = load({"engineering-sre": ""})
        self.assertEqual(resolve_role("engineering-sre", cfg)["model"], cfg["models"]["thinker"])

    def test_bad_user_file_is_ignored(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, CLEAN):
            f = Path(d) / "pm.json"
            f.write_text("{not json", encoding="utf-8")
            with mock.patch.object(config, "TF_ROLES_MODELS_FILE", f):
                self.assertEqual(resolve_role("gis-analyst", load_tf_roles())["model"], load_tf_roles()["models"]["builder"])

    def test_model_env_pins_everything(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {**CLEAN, "TOKENFRUGAL_MODEL_BUILDER": "pin:1b"}), \
             mock.patch.object(config, "TF_ROLES_MODELS_FILE", Path(d) / "none.json"):
            cfg = load_tf_roles()
        self.assertEqual(resolve_role("engineering-backend-architect", cfg)["model"], "pin:1b")

    def test_disable_switch(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {**CLEAN, "TOKENFRUGAL_TF_ROLES_MODELS": "0"}), \
             mock.patch.object(config, "TF_ROLES_MODELS_FILE", Path(d) / "none.json"):
            cfg = load_tf_roles()
        self.assertEqual(resolve_role("engineering-sre", cfg)["model"], cfg["models"]["thinker"])


class EditorTests(unittest.TestCase):
    def test_save_keeps_only_changes_and_roundtrips(self):
        from scripts import tf_roles_ui
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, CLEAN), \
             mock.patch.object(config, "TF_ROLES_MCPS_FILE", Path(d) / "pc.json"), \
             mock.patch.object(config, "TF_ROLES_MODELS_FILE", Path(d) / "pm.json"):
            diff = tf_roles_ui.save({"models": {"engineering-backend-architect": "other:7b", "finance-analyst": "other:3b", "engineering-technical-writer": ""}})["models"]
            self.assertEqual(diff, {"engineering-backend-architect": "other:7b", "finance-analyst": "other:3b"})
            cfg = load_tf_roles()
            self.assertEqual(resolve_role("finance-analyst", cfg)["model"], "other:3b")
            self.assertEqual(resolve_role("engineering-technical-writer", cfg)["model"], cfg["models"]["thinker"])
            rows = tf_roles_ui.state()["rows"]
            self.assertEqual(rows["finance-analyst"]["override"], "other:3b")
            self.assertEqual(rows["engineering-backend-architect"]["override"], "other:7b")


if __name__ == "__main__":
    unittest.main()
