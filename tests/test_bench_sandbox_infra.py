"""Offline tests for run_sandbox infra vs model-fail handling (scripts/bench_checks.py). No Docker is run:
subprocess.run is patched in scripts.bench_checks."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from scripts import bench_checks

PATCH = "scripts.bench_checks.subprocess.run"


def _proc(returncode, stdout="", stderr=""):
    return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)


class RunSandboxInfra(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_docker_binary_is_infra(self):
        with mock.patch(PATCH, side_effect=FileNotFoundError("docker")):
            with self.assertRaises(bench_checks.InfraFailure) as cm:
                bench_checks.run_sandbox(self.folder)
        self.assertIn("docker not available", str(cm.exception))

    def test_os_error_is_infra(self):
        with mock.patch(PATCH, side_effect=OSError("boom")):
            with self.assertRaises(bench_checks.InfraFailure):
                bench_checks.run_sandbox(self.folder)

    def test_exit_125_is_infra_with_first_stderr_line(self):
        err = "docker: Error response from daemon: bad mount\nsecond line"
        with mock.patch(PATCH, return_value=_proc(125, stderr=err)):
            with self.assertRaises(bench_checks.InfraFailure) as cm:
                bench_checks.run_sandbox(self.folder)
        self.assertEqual(str(cm.exception), "docker: Error response from daemon: bad mount")

    def test_exit_1_is_model_fail_not_infra(self):
        with mock.patch(PATCH, return_value=_proc(1, stdout="FAILED (failures=1)")):
            passed, tail = bench_checks.run_sandbox(self.folder)
        self.assertFalse(passed)
        self.assertIn("FAILED", tail)

    def test_exit_2_is_model_fail_not_infra(self):
        with mock.patch(PATCH, return_value=_proc(2, stderr="usage error")):
            passed, _ = bench_checks.run_sandbox(self.folder)
        self.assertFalse(passed)

    def test_exit_0_passes(self):
        with mock.patch(PATCH, return_value=_proc(0, stdout="OK")):
            passed, tail = bench_checks.run_sandbox(self.folder)
        self.assertTrue(passed)
        self.assertEqual(tail, "OK")

    def test_timeout_is_model_fail(self):
        with mock.patch(PATCH, side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=90)):
            passed, tail = bench_checks.run_sandbox(self.folder)
        self.assertFalse(passed)
        self.assertTrue(tail.startswith("timeout"))

    def test_check_passes_propagates_infra(self):
        (self.folder / "test_x.py").write_text("import unittest\n", encoding="utf-8")
        with mock.patch(PATCH, side_effect=FileNotFoundError("docker")):
            with self.assertRaises(bench_checks.InfraFailure):
                bench_checks.check_passes("sandbox_tests", "reply text here", self.folder)


if __name__ == "__main__":
    unittest.main()
