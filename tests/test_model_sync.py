"""Offline tests for the Hugging Face model manifest, scripts/hf_models.py and router/model_sync.py.

No docker, no network: subprocess.run is mocked, and the Hub is never called.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import model_sync

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "scripts" / "hf_models.json"


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.repos = json.loads(MANIFEST.read_text(encoding="utf-8"))["repos"]

    def test_slugs_unique(self):
        slugs = [r["slug"] for r in self.repos]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_basenames_unique_within_repo(self):
        for r in self.repos:
            names = [Path(p).name for p in r["files"]]
            self.assertEqual(len(names), len(set(names)), r["slug"])

    def test_paths_under_known_prefixes(self):
        for r in self.repos:
            self.assertTrue(r["files"], r["slug"])
            for p in r["files"]:
                self.assertTrue(p.startswith(("video_generation/", "image_generation/")), p)


class EnsureModelsTests(unittest.TestCase):
    def _marker(self, models: Path, files: dict[str, bytes]) -> None:
        for rel, data in files.items():
            p = models / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        doc = {"repos": {"demo": {"repo_id": "owner/tokenfrugal-demo",
                                  "files": {rel: len(d) for rel, d in files.items()}}},
               "pulled_at": "2026-11-05T00:00:00+00:00"}
        (models / ".hf_pulled.json").write_text(json.dumps(doc), encoding="utf-8")

    def test_returns_empty_when_marker_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            models = Path(tmp) / "models"
            self._marker(models, {"video_generation/a/x.gguf": b"12345",
                                  "image_generation/b/y.safetensors": b"abc"})
            with mock.patch.dict(os.environ, {"TF_MODELS_DIR": str(models)}), \
                    mock.patch.object(model_sync.subprocess, "run") as run:
                self.assertEqual(model_sync.ensure_models(), "")
                run.assert_not_called()

    def test_error_when_marker_missing_and_no_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            models = Path(tmp) / "models"
            models.mkdir()
            repo_root = Path(tmp) / "repo"
            repo_root.mkdir()  # no .env here
            env = {"TF_MODELS_DIR": str(models)}
            with mock.patch.object(model_sync, "REPO", repo_root), \
                    mock.patch.dict(os.environ, env), \
                    mock.patch.object(model_sync.subprocess, "run") as run:
                os.environ.pop("HF_TOKEN", None)
                os.environ.pop("HUGGINGFACE", None)
                result = model_sync.ensure_models()
                run.assert_not_called()
        self.assertTrue(result.startswith("error:"), result)
        self.assertIn("HUGGINGFACE missing from .env", result)


if __name__ == "__main__":
    unittest.main()
