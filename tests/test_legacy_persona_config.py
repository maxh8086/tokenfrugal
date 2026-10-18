"""Pre-rename persona_* config names still resolve until config.LEGACY_REMOVE_AFTER (2027-03-31).

TestLegacyRemovalTripwire fails once that date has passed: delete the fallback in router/config.py,
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

import router
from router import config

ROUTER = Path(config.__file__).resolve().parent
ENV_KEYS = [
    "TOKENFRUGAL_TF_ROLES_MODELS_FILE", "TOKENFRUGAL_TF_ROLES_MCPS_FILE",
    "TOKENFRUGAL_AGENT_MODELS_FILE", "TOKENFRUGAL_AGENT_MCPS_FILE",
    "TOKENFRUGAL_PERSONA_MODELS_FILE", "TOKENFRUGAL_PERSONA_MCPS_FILE",
    "TOKENFRUGAL_TF_ROLES_MODELS", "TOKENFRUGAL_AGENT_MODELS", "TOKENFRUGAL_PERSONA_MODELS",
    "TOKENFRUGAL_MODEL_BUILDER", "TOKENFRUGAL_MODEL_THINKER",
]
PERSONA_ONLY = (("TOKENFRUGAL_PERSONA_MODELS_FILE", "persona_models.json"),)
CHAIN = config._LEGACY_MODELS_FILES  # agent_* then persona_*, after the tf-roles name


def _clean_env(**extra):
    env = {k: "" for k in ENV_KEYS}
    env.update(extra)
    return mock.patch.dict(os.environ, env)


def _file(d: Path, env=None, legacy=CHAIN) -> Path:
    with _clean_env(**(env or {})):
        return config._tf_roles_file("TOKENFRUGAL_TF_ROLES_MODELS_FILE", "tf-roles_models.json", legacy)


class PersonaFileFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.patch_file = mock.patch.object(config, "__file__", str(self.dir / "config.py"))
        self.patch_file.start()

    def tearDown(self):
        self.patch_file.stop()
        self.tmp.cleanup()

    def test_persona_file_used_when_nothing_newer_exists(self):
        (self.dir / "persona_models.json").write_text("{}", encoding="utf-8")
        self.assertEqual(_file(self.dir, legacy=PERSONA_ONLY), self.dir / "persona_models.json")

    def test_agent_file_wins_over_persona(self):
        (self.dir / "persona_models.json").write_text("{}", encoding="utf-8")
        (self.dir / "agent_models.json").write_text("{}", encoding="utf-8")
        self.assertEqual(_file(self.dir), self.dir / "agent_models.json")

    def test_tf_roles_file_wins_over_both(self):
        for n in ("persona_models.json", "agent_models.json", "tf-roles_models.json"):
            (self.dir / n).write_text("{}", encoding="utf-8")
        self.assertEqual(_file(self.dir), self.dir / "tf-roles_models.json")

    def test_new_path_when_nothing_exists(self):
        self.assertEqual(_file(self.dir), self.dir / "tf-roles_models.json")

    def test_persona_env_var_honoured(self):
        self.assertEqual(_file(self.dir, env={"TOKENFRUGAL_PERSONA_MODELS_FILE": "/x/pm.json"}), Path("/x/pm.json"))

    def test_tf_roles_env_var_wins_over_legacy(self):
        path = _file(self.dir, env={"TOKENFRUGAL_TF_ROLES_MODELS_FILE": "/new/tr.json",
                                    "TOKENFRUGAL_PERSONA_MODELS_FILE": "/x/pm.json"})
        self.assertEqual(path, Path("/new/tr.json"))


MODELS = {"gis-analyst": "llama3.2:3b-16k", "engineering-backend-architect": "qwen2.5-coder-yarn:3b"}
SKILLS = {"gis-analyst": ["browser"]}


def _write_tf_roles_yaml(d: Path, models_key: str, skills_key: str) -> None:
    """Minimal tf-roles.yaml copy with the given keys; the rest is the shipped file."""
    text = (ROUTER / "tf-roles.yaml").read_text(encoding="utf-8")
    text = text.replace("\ntf_roles_models: {}", "")
    text = text.replace("\ntf_roles_skills:", f"\n{skills_key}:", 1)
    body = "".join(f"  {k}: {v}\n" for k, v in MODELS.items())
    text += f"\n{models_key}:\n{body}"
    skills = "".join(f"  {k}: [{', '.join(v)}]\n" for k, v in SKILLS.items())
    text = text.replace(f"\n{skills_key}:\n", f"\n{skills_key}:\n{skills}", 1)
    (d / "tf-roles.yaml").write_text(text, encoding="utf-8")


def _load(d: Path, env=None) -> dict:
    """load_tf_roles() reading tf-roles.yaml from d, with no user override files."""
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


class PersonaYaml(unittest.TestCase):
    """tf-roles.yaml with the pre-rename persona_models / persona_skills keys."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.legacy_dir = self.dir / "legacy"
        self.current_dir = self.dir / "current"
        for d, models_key, skills_key in ((self.legacy_dir, "persona_models", "persona_skills"),
                                          (self.current_dir, "tf_roles_models", "tf_roles_skills")):
            d.mkdir()
            shutil.copy(ROUTER / "mcp_catalog.yaml", d / "mcp_catalog.yaml")
            _write_tf_roles_yaml(d, models_key, skills_key)

    def tearDown(self):
        self.tmp.cleanup()

    def test_persona_models_key_read(self):
        legacy = _load(self.legacy_dir)
        current = _load(self.current_dir)
        self.assertEqual(legacy["agent_models"], MODELS)
        self.assertEqual(legacy["agent_models"], current["agent_models"])

    def test_persona_skills_key_read(self):
        legacy = _load(self.legacy_dir)
        current = _load(self.current_dir)
        self.assertEqual(legacy["agent_skills"], current["agent_skills"])
        for slug, skills in SKILLS.items():
            self.assertEqual(legacy["agent_skills"][slug], skills)

    def test_legacy_env_disables_model_mapping(self):
        cfg = _load(self.legacy_dir, env={"TOKENFRUGAL_PERSONA_MODELS": "0"})
        self.assertEqual(cfg["agent_models"], {})

    def test_new_env_disables_model_mapping(self):
        cfg = _load(self.current_dir, env={"TOKENFRUGAL_TF_ROLES_MODELS": "0"})
        self.assertEqual(cfg["agent_models"], {})


class PersonaOverrideFiles(unittest.TestCase):
    def test_persona_models_json_applied(self):
        with tempfile.TemporaryDirectory() as d, _clean_env():
            d = Path(d)
            (d / "persona_models.json").write_text('{"gis-analyst": "llama3.2:3b-16k"}', encoding="utf-8")
            with mock.patch.object(config, "__file__", str(d / "config.py")):
                path = config._tf_roles_file("TOKENFRUGAL_TF_ROLES_MODELS_FILE", "tf-roles_models.json", PERSONA_ONLY)
            with mock.patch.object(config, "TF_ROLES_MODELS_FILE", path), \
                 mock.patch.object(config, "TF_ROLES_MCPS_FILE", d / "none.json"):
                cfg = config.load_tf_roles()
        self.assertEqual(cfg["agent_models"]["gis-analyst"], "llama3.2:3b-16k")


class PersonaDeprecationWarning(unittest.TestCase):
    def setUp(self):
        config._LEGACY_SEEN.clear()

    def test_warning_printed_once_for_legacy_env(self):
        buf = io.StringIO()
        with _clean_env(TOKENFRUGAL_PERSONA_MODELS_FILE="/x/pm.json"), contextlib.redirect_stderr(buf):
            _file(None)
            _file(None, env={"TOKENFRUGAL_PERSONA_MODELS_FILE": "/x/pm.json"})
        self.assertEqual(buf.getvalue().count("deprecated; rename to tf-roles"), 1)
        self.assertIn("(fallback removed after 2027-03-31)", buf.getvalue())

    def test_no_warning_when_new_name_used(self):
        buf = io.StringIO()
        with _clean_env(TOKENFRUGAL_TF_ROLES_MODELS_FILE="/new/tr.json"), contextlib.redirect_stderr(buf):
            _file(None, env={"TOKENFRUGAL_TF_ROLES_MODELS_FILE": "/new/tr.json"})
        self.assertEqual(buf.getvalue(), "")


class LegacyRemovalTripwire(unittest.TestCase):
    def test_legacy_fallback_not_past_removal_date(self):
        self.assertLessEqual(
            date.today(), config.LEGACY_REMOVE_AFTER,
            f"persona_* fallback was due for removal after {config.LEGACY_REMOVE_AFTER}: "
            "delete it from router/config.py, this module, and its CHANGELOG.md entry.",
        )


class VersionConsistency(unittest.TestCase):
    def test_package_version_matches_pyproject(self):
        import tomllib
        pyproject = Path(router.__file__).resolve().parent.parent / "pyproject.toml"
        with pyproject.open("rb") as fh:
            declared = tomllib.load(fh)["project"]["version"]
        self.assertEqual(router.__version__, declared)


if __name__ == "__main__":
    unittest.main()
