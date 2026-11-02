"""Content stage agents: slug -> role -> Ollama tag resolution, env switches, unknown slugs and the preflight model report."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router.config import check_agent, load_tf_roles, resolve_role
from router.preflight import stage_model_gaps

STAGES = {
    "content-outline": ("content-research", "ts-qwen3-8b-40960:latest"),
    "content-factcheck": ("content-editor", "ts-llama3-1-8b-65536:latest"),
    "content-draft": ("content-writer", "ts-hf-co-bandtor-gemma-4-E4B-it-GGUF-65536:latest"),
    "content-critic": ("content-editor", "ts-llama3-1-8b-65536:latest"),
    "content-humanize": ("content-writer", "ts-hf-co-bandtor-gemma-4-E4B-it-GGUF-65536:latest"),
    "content-antislop": ("content-editor", "ts-llama3-1-8b-65536:latest"),
    "content-executive": ("content-writer", "ts-qwen3-8b-40960:latest"),
}
SWITCHES = ["TOKENFRUGAL_TF_ROLES_MODELS", "TOKENFRUGAL_AGENT_MODELS", "TOKENFRUGAL_PERSONA_MODELS"]


class ContentStageTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        for k in SWITCHES + [k for k in os.environ if k.startswith("TOKENFRUGAL_MODEL_")]:
            os.environ.pop(k, None)
        tmp = tempfile.mkdtemp()  # no user model file: only the yaml defaults apply
        p = mock.patch("router.config.TF_ROLES_MODELS_FILE", Path(tmp) / "none.json")
        p.start()
        self.addCleanup(p.stop)

    def test_seven_slugs_resolve_to_role_and_model(self):
        cfg = load_tf_roles()
        for slug, (role, tag) in STAGES.items():
            r = resolve_role(slug, cfg)
            self.assertEqual(r["role"], role, slug)
            self.assertEqual(r["model"], tag, slug)

    def test_stage_skill_is_attached(self):
        cfg = load_tf_roles()
        self.assertIn("stage-content-draft", resolve_role("content-draft", cfg)["skills"])
        self.assertIn("stage-content-factcheck", resolve_role("content-factcheck", cfg)["skills"])

    def test_all_seven_slugs_are_accepted(self):
        cfg = load_tf_roles()
        for slug in STAGES:
            self.assertEqual(check_agent(slug, cfg), "", slug)

    def test_unknown_stage_slug_is_rejected(self):
        cfg = load_tf_roles()
        self.assertTrue(check_agent("content-bogus", cfg).startswith("unknown agent"))

    def test_tf_roles_models_zero_disables_mapping_but_keeps_slugs(self):
        os.environ["TOKENFRUGAL_TF_ROLES_MODELS"] = "0"
        cfg = load_tf_roles()
        self.assertEqual(cfg["agent_models"], {})
        role = STAGES["content-draft"][0]
        default = cfg["models"][cfg["roles"][role]["model"]]
        self.assertEqual(resolve_role("content-draft", cfg)["model"], default)
        self.assertEqual(check_agent("content-draft", cfg), "")

    def test_model_env_pin_disables_mapping(self):
        os.environ["TOKENFRUGAL_MODEL_BUILDER"] = "some-model:1b"
        cfg = load_tf_roles()
        self.assertEqual(cfg["agent_models"], {})

    def test_gap_report_lists_only_missing_stage_tags(self):
        cfg = load_tf_roles()
        gaps = stage_model_gaps(cfg, {"ts-qwen3-8b-40960:latest"})
        self.assertEqual({tag for _, tag in gaps}, {"ts-hf-co-bandtor-gemma-4-E4B-it-GGUF-65536:latest", "ts-llama3-1-8b-65536:latest"})
        self.assertEqual(len(gaps), 5)  # draft, humanize (gemma4); factcheck, critic, antislop (llama3.1)
        self.assertNotIn("content-outline", {a for a, _ in gaps})

    def test_gap_report_is_empty_when_all_installed(self):
        cfg = load_tf_roles()
        installed = {"ts-qwen3-8b-40960:latest", "ts-hf-co-bandtor-gemma-4-E4B-it-GGUF-65536:latest", "ts-llama3-1-8b-65536:latest"}
        self.assertEqual(stage_model_gaps(cfg, installed), [])


if __name__ == "__main__":
    unittest.main()
