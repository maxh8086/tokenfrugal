import os
import unittest
from unittest import mock

from router import kalamanch_cleanup as kc


class MaybeRunTests(unittest.TestCase):
    def setUp(self):
        kc._last_started = None
        self.env = mock.patch.dict(os.environ, {"KALAMANCH_DIR": "C:/kalamanch"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        kc._last_started = None

    def test_noop_without_kalamanch_dir(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(kc.threading, "Thread") as thread:
            self.assertFalse(kc.maybe_run(now=0))
        thread.assert_not_called()

    def test_starts_background_thread_once_per_day(self):
        with mock.patch.object(kc.threading, "Thread") as thread:
            self.assertTrue(kc.maybe_run(now=1000))
            self.assertFalse(kc.maybe_run(now=1000 + 3600))  # an hour later: still skipped
            self.assertFalse(kc.maybe_run(now=1000 + 86399))  # just under a day: still skipped
            self.assertTrue(kc.maybe_run(now=1000 + 86400))  # a day later: runs again
        self.assertEqual(thread.call_count, 2)
        self.assertTrue(thread.call_args[1]["daemon"])

    def test_run_invokes_cleanup_cli_in_kalamanch_dir(self):
        with mock.patch.dict(os.environ, {"KALAMANCH_PYTHON": "py"}), \
                mock.patch.object(kc.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stderr="")
            kc._run("C:/kalamanch")
        argv = run.call_args[0][0]
        self.assertEqual(argv, ["py", "-m", "kalamanch.cli", "cleanup"])
        self.assertEqual(run.call_args[1]["cwd"], "C:/kalamanch")

    def test_run_swallows_failures(self):
        with mock.patch.object(kc.subprocess, "run", side_effect=OSError("no python")):
            kc._run("C:/kalamanch")  # must not raise
        with mock.patch.object(kc.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=1, stderr="boom")
            kc._run("C:/kalamanch")  # must not raise


if __name__ == "__main__":
    unittest.main()
