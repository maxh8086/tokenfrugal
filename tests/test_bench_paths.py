import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import bench_real


class ToolPaths(unittest.TestCase):
    def test_workspace_is_repo_parent(self):
        ws = Path("/x/Projects")
        ws_path, ast = bench_real.tool_paths(ws / "tokenfrugal" / "bench" / "scratch", ws)
        self.assertEqual(ws_path, "/workspace/tokenfrugal/bench/scratch")
        self.assertEqual(ast, "/src/tokenfrugal/bench/scratch")

    def test_workspace_is_repo_root(self):
        ws = Path("/x/Projects/tokenfrugal")
        ws_path, ast = bench_real.tool_paths(ws / "bench" / "scratch", ws)
        self.assertEqual(ws_path, "/workspace/bench/scratch")
        self.assertEqual(ast, "/src/bench/scratch")

    def test_folder_outside_workspace_is_refused(self):
        with self.assertRaises(ValueError):
            bench_real.tool_paths(Path("/x/elsewhere/bench/scratch"), Path("/x/Projects/tokenfrugal"))


class L6Split(unittest.TestCase):
    def test_plain_l6_does_not_need_the_graph(self):
        plain = next(c for c in bench_real.coding_cases() if c[0] == "code_l6_callers")
        self.assertNotIn("code graph", plain[3])
        self.assertNotIn("code_l6_callers", bench_real.SYNAPTREE_CASES)

    def test_graph_variant_keeps_graph_requirement(self):
        graph = next(c for c in bench_real.coding_cases() if c[0] == "code_l6_callers_graph")
        self.assertIn("code graph", graph[3])
        self.assertIn("code_l6_callers_graph", bench_real.SYNAPTREE_CASES)


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


class Preflight(unittest.TestCase):
    def test_matching_mount_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "tokenfrugal"
            scratch = root / "bench" / "scratch"
            with mock.patch.object(bench_real, "SCRATCH", scratch), \
                    mock.patch.object(bench_real, "WS", "/workspace/bench/scratch"), \
                    mock.patch.dict(os.environ, {"CC_WORKSPACE": str(root)}):
                bench_real.path_preflight()  # no error: /workspace/bench/scratch resolves to SCRATCH

    def test_wrong_mount_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "tokenfrugal"
            scratch = root / "bench" / "scratch"
            with mock.patch.object(bench_real, "SCRATCH", scratch), \
                    mock.patch.object(bench_real, "WS", "/workspace/tokenfrugal/bench/scratch"), \
                    mock.patch.dict(os.environ, {"CC_WORKSPACE": str(root)}):
                with self.assertRaises(Exception):  # resolves to root/tokenfrugal/bench/scratch, which is not SCRATCH
                    bench_real.path_preflight()


if __name__ == "__main__":
    unittest.main()
