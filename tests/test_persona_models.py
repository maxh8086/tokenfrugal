import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gateway import config
from gateway.config import load_personas, resolve_role

CLEAN = {"TOKENFRUGAL_MODEL_BUILDER": "", "TOKENFRUGAL_MODEL_THINKER": "", "TOKENFRUGAL_PERSONA_MODELS": ""}


def load(override=None):
    with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, CLEAN):
        f = Path(d) / "pm.json"
        if override is not None:
            f.write_text(json.dumps(override), encoding="utf-8")
        with mock.patch.object(config, "PERSONA_MODELS_FILE", f):
            return load_personas()


class PersonaModelTests(unittest.TestCase):
    def test_yaml_default_is_a_tag(self):
        cfg = load()
        self.assertEqual(resolve_role("engineering-backend-architect", cfg)["model"], "ts-gemma4-e4b-16384")
        self.assertEqual(resolve_role("engineering-sre", cfg)["model"], "ts-qwen25c-7b-16384")

    def test_logical_name_resolves_to_role_model(self):
        cfg = load()
        self.assertEqual(resolve_role("gis-analyst", cfg)["model"], cfg["models"]["builder"])
        self.assertEqual(resolve_role("design-ui-designer", cfg)["model"], cfg["models"]["thinker"])

    def test_unmapped_persona_keeps_role_model(self):
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
            with mock.patch.object(config, "PERSONA_MODELS_FILE", f):
                self.assertEqual(resolve_role("engineering-sre", load_personas())["model"], "ts-qwen25c-7b-16384")

    def test_model_env_pins_everything(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {**CLEAN, "TOKENFRUGAL_MODEL_BUILDER": "pin:1b"}), \
             mock.patch.object(config, "PERSONA_MODELS_FILE", Path(d) / "none.json"):
            cfg = load_personas()
        self.assertEqual(resolve_role("engineering-backend-architect", cfg)["model"], "pin:1b")

    def test_disable_switch(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {**CLEAN, "TOKENFRUGAL_PERSONA_MODELS": "0"}), \
             mock.patch.object(config, "PERSONA_MODELS_FILE", Path(d) / "none.json"):
            cfg = load_personas()
        self.assertEqual(resolve_role("engineering-sre", cfg)["model"], cfg["models"]["thinker"])


class EditorTests(unittest.TestCase):
    def test_save_keeps_only_changes_and_roundtrips(self):
        from scripts import persona_ui
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, CLEAN),              mock.patch.object(config, "PERSONA_MODELS_FILE", Path(d) / "pm.json"):
            diff = persona_ui.save({"engineering-sre": "ts-qwen25c-7b-16384", "finance-analyst": "other:3b", "engineering-technical-writer": ""})
            self.assertEqual(diff, {"finance-analyst": "other:3b", "engineering-technical-writer": ""})
            cfg = load_personas()
            self.assertEqual(resolve_role("finance-analyst", cfg)["model"], "other:3b")
            self.assertEqual(resolve_role("engineering-technical-writer", cfg)["model"], cfg["models"]["thinker"])
            rows = {r["persona"]: r for r in persona_ui.state()["rows"]}
            self.assertEqual(rows["finance-analyst"]["override"], "other:3b")
            self.assertEqual(rows["engineering-sre"]["default"], "ts-qwen25c-7b-16384")


if __name__ == "__main__":
    unittest.main()
