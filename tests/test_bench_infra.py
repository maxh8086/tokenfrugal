"""Offline tests for the benchmark infra checks (scripts/bench_checks.py). No Docker, model or router is contacted."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import sandbox_mcp
from scripts import bench_checks


class ScratchReady(unittest.TestCase):
    def test_creates_missing_folder_and_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "bench" / "scratch"
            self.assertFalse(folder.exists())
            with mock.patch.object(sandbox_mcp, "_resolve", return_value=folder.resolve()):
                self.assertEqual(bench_checks.scratch_ready(folder, "/workspace/bench/scratch"), "")
            self.assertTrue(folder.is_dir())


class SeedError(unittest.TestCase):
    def test_existing_non_empty_file_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "seed.txt"
            seed.write_text("x", encoding="utf-8")
            self.assertEqual(bench_checks.seed_error([seed]), "")

    def test_missing_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "missing.txt"
            self.assertEqual(bench_checks.seed_error([seed]), f"seed missing: {seed}")

    def test_empty_file_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "empty.txt"
            seed.write_text("", encoding="utf-8")
            self.assertEqual(bench_checks.seed_error([seed]), f"seed missing: {seed}")


class InfraToolError(unittest.TestCase):
    def test_missing_parent_directory_is_infra(self):
        self.assertTrue(bench_checks.is_infra_tool_error("Error: Parent directory does not exist: /workspace/bench/scratch"))

    def test_normal_reply_is_not_infra(self):
        self.assertFalse(bench_checks.is_infra_tool_error("wrote 12 bytes"))


if __name__ == "__main__":
    unittest.main()
