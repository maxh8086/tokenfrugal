"""Pre-rename agent_* config names (env vars, override files, yaml keys) still resolve until
config.LEGACY_REMOVE_AFTER (2027-03-31).

TestLegacyRemovalTripwire fails once that date has passed: delete the agent_* fallback in router/config.py,
these tests and the matching CHANGELOG.md entry together.
"""

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from router import config

ROUTER = Path(config.__file__).resolve().parent
ENV_KEYS = [
    "TOKENFRUGAL_TF_ROLES_MODELS_FILE", "TOKENFRUGAL_TF_ROLES_MCPS_FILE",
    "TOKENFRUGAL_AGENT_MODELS_FILE", "TOKENFRUGAL_AGENT_MCPS_FILE",
    "TOKENFRUGAL_PERSONA_MODELS_FILE", "TOKENFRUGAL_PERSONA_MCPS_FILE",
    "TOKENFRUGAL_TF_ROLES_MODELS", "TOKENFRUGAL_AGENT_MODELS", "TOKENFRUGAL_PERSONA_MODELS",
    "TOKENFRUGAL_MODEL_BUILDER", "TOKENFRUGAL_MODEL_THINKER",
]
AGENT_ONLY = (("TOKENFRUGAL_AGENT_MODELS_FILE", "agent_models.json"),)


def _clean_env(**extra):
    env = {k: "" for k in ENV_KEYS}
    env.update(extra)
    return mock.patch.dict(os.environ, env)


def _file(env=None, legacy=AGENT_ONLY) -> Path:
    with _clean_env(**(env or {})):
        return config._tf_roles_file("TOKENFRUGAL_TF_ROLES_MODELS_FILE", "tf-roles_models.json", legacy)


class AgentFileFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.patch_file = mock.patch.object(config, "__file__", str(self.dir / "config.py"))
        self.patch_file.start()

    def tearDown(self):
        self.patch_file.stop()
        self.tmp.cleanup()

    def test_agent_file_used_when_tf_roles_absent(self):
        (self.dir / "agent_models.json").write_text("{}", encoding="utf-8")
        self.assertEqual(_file(), self.dir / "agent_models.json")

    def test_tf_roles_file_wins_over_agent(self):
        (self.dir / "agent_models.json").write_text("{}", encoding="utf-8")
        (self.dir / "tf-roles_models.json").write_text("{}", encoding="utf-8")
        self.assertEqual(_file(legacy=(("TOKENFRUGAL_AGENT_MODELS_FILE", "agent_models.json"),)),
                         self.dir / "tf-roles_models.json")

    def test_new_path_when_neither_exists(self):
        self.assertEqual(_file(), self.dir / "tf-roles_models.json")

    def test_agent_env_var_honoured(self):
        self.assertEqual(_file(env={"TOKENFRUGAL_AGENT_MODELS_FILE": "/x/am.json"}), Path("/x/am.json"))

    def test_tf_roles_env_var_wins_over_agent(self):
        path = _file(env={"TOKENFRUGAL_TF_ROLES_MODELS_FILE": "/new/tr.json",
                          "TOKENFRUGAL_AGENT_MODELS_FILE": "/x/am.json"})
        self.assertEqual(path, Path("/new/tr.json"))


MODELS = {"gis-analyst": "llama3.2:3b-16k", "engineering-backend-architect": "qwen2.5-coder-yarn:3b"}


def _write_tf_roles_yaml(d: Path, models_key: str, skills_key: str) -> None:
    text = (ROUTER / "tf-roles.yaml").read_text(encoding="utf-8")
    text = text.replace("\ntf_roles_models: {}", "")
    text = text.replace("\ntf_roles_skills:", f"\n{skills_key}:", 1)
    body = "".join(f"  {k}: {v}\n" for k, v in MODELS.items())
    text += f"\n{models_key}:\n{body}"
    (d / "tf-roles.yaml").write_text(text, encoding="utf-8")


def _load(d: Path, env=None) -> dict:
    patches = [
        mock.patch.object(config, "__file__", str(d / "config.py")),
        mock.patch.object(config, "TF_ROLES_MODELS_FILE", d / "none.json"),
        mock.patch.object(config, "TF_ROLES_MCPS_FILE", d / "none.json"),
    ]
    for p in patches:
        p.start()
    try:
        with _clean_env(**(env or {})):
            return config.load_tf_roles()
    finally:
        for p in patches:
            p.stop()


class AgentYaml(unittest.TestCase):
    """tf-roles.yaml with the pre-rename agent_models / agent_skills keys."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.legacy_dir = self.dir / "legacy"
        self.current_dir = self.dir / "current"
        for d, models_key, skills_key in ((self.legacy_dir, "agent_models", "agent_skills"),
                                          (self.current_dir, "tf_roles_models", "tf_roles_skills")):
            d.mkdir()
            shutil.copy(ROUTER / "mcp_catalog.yaml", d / "mcp_catalog.yaml")
            _write_tf_roles_yaml(d, models_key, skills_key)

    def tearDown(self):
        self.tmp.cleanup()

    def test_agent_models_key_read(self):
        self.assertEqual(_load(self.legacy_dir)["agent_models"], _load(self.current_dir)["agent_models"])
        self.assertEqual(_load(self.legacy_dir)["agent_models"], MODELS)

    def test_agent_env_disables_model_mapping(self):
        self.assertEqual(_load(self.legacy_dir, env={"TOKENFRUGAL_AGENT_MODELS": "0"})["agent_models"], {})


class AgentDeprecationWarning(unittest.TestCase):
    def setUp(self):
        config._LEGACY_SEEN.clear()

    def test_warning_printed_for_agent_env(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            _file(env={"TOKENFRUGAL_AGENT_MODELS_FILE": "/x/am.json"})
        self.assertIn("deprecated; rename to tf-roles", buf.getvalue())
        self.assertIn("(fallback removed after 2027-03-31)", buf.getvalue())


class LegacyRemovalTripwire(unittest.TestCase):
    def test_legacy_fallback_not_past_removal_date(self):
        self.assertLessEqual(
            date.today(), config.LEGACY_REMOVE_AFTER,
            f"agent_* fallback was due for removal after {config.LEGACY_REMOVE_AFTER}: "
            "delete it from router/config.py, this module, and its CHANGELOG.md entry.",
        )


if __name__ == "__main__":
    unittest.main()
