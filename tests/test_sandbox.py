import os
import tempfile
import unittest
from unittest import mock

from router import sandbox_mcp as s


class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = mock.patch.dict(os.environ, {"CC_WORKSPACE": self.tmp.name})
        self.env.start()
        os.makedirs(os.path.join(self.tmp.name, "proj"))

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_outside_workspace_refused(self):
        self.assertIn("outside the workspace", s.run_tests(".."))

    def test_bad_test_file_refused(self):
        self.assertIn("bad test_file", s.run_tests("proj", "x; rm -rf /"))

    def test_argv_is_isolated(self):
        argv = s._docker_argv(s.Path(self.tmp.name), ["-m", "unittest"])
        for flag in ("--network", "none", "--rm", "no-new-privileges"):
            self.assertIn(flag, argv)
        self.assertTrue(any(a.endswith(":/work:ro") for a in argv))

    def test_discover_and_module_args(self):
        with mock.patch.object(s.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="OK", stderr="")
            self.assertTrue(s.run_tests("proj").startswith("exit=0"))
            self.assertIn("discover", run.call_args[0][0])
            s.run_tests("proj", "test_m.py")
            self.assertEqual(run.call_args[0][0][-1], "test_m")


if __name__ == "__main__":
    unittest.main()
