"""Offline tests for the scratch folder as the tools see it (scripts/bench_checks.tool_paths) and the workspace
folder check (router/config.py)."""
import tempfile
import unittest
from pathlib import Path

from scripts import bench_checks


class ToolPaths(unittest.TestCase):
    def test_workspace_is_repo_parent(self):
        ws = Path("/x/Projects")
        self.assertEqual(bench_checks.tool_paths(ws / "tokenfrugal" / "bench" / "scratch", ws),
                         "/workspace/tokenfrugal/bench/scratch")

    def test_workspace_is_repo_root(self):
        ws = Path("/x/Projects/tokenfrugal")
        self.assertEqual(bench_checks.tool_paths(ws / "bench" / "scratch", ws), "/workspace/bench/scratch")

    def test_folder_outside_workspace_is_refused(self):
        with self.assertRaises(ValueError):
            bench_checks.tool_paths(Path("/x/elsewhere/bench/scratch"), Path("/x/Projects/tokenfrugal"))


class WorkspaceFolder(unittest.TestCase):
    def setUp(self):
        self.ws = tempfile.mkdtemp()
        (Path(self.ws) / "bench").mkdir()

    def test_existing_top_folder_passes(self):
        from router.config import missing_workspace_folder
        self.assertEqual(missing_workspace_folder("Read /workspace/bench/scratch/a.py.", self.ws), "")

    def test_new_file_in_existing_folder_passes(self):
        from router.config import missing_workspace_folder
        self.assertEqual(missing_workspace_folder("write /workspace/bench/new/out.txt", self.ws), "")

    def test_missing_top_folder_is_refused(self):
        from router.config import missing_workspace_folder
        err = missing_workspace_folder("Read /workspace/nope/x.py", self.ws)
        self.assertIn("/workspace/nope", err)

    def test_no_workspace_path_passes(self):
        from router.config import missing_workspace_folder
        self.assertEqual(missing_workspace_folder("summarize the project", self.ws), "")


if __name__ == "__main__":
    unittest.main()
