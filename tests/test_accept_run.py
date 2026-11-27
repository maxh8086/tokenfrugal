import os
import errno
import ctypes
import shutil
import sys
import tempfile
import threading
from unittest import mock
import time
import unittest
from pathlib import Path
from router.checker import AcceptSpec, run_accept_spec
from router.checker import _first_error, _resolve_argv0
from router.workspace import load_workspace


class AcceptRunTest(unittest.TestCase):
    def test_windows_close_handle_declares_handle_argtype(self):
        close = mock.Mock()
        kernel = mock.Mock(CloseHandle=close)
        proc = mock.Mock()
        proc.poll.return_value = None
        proc._tf_job = 123
        with mock.patch("router.checker.os.name", "nt"), mock.patch.object(ctypes, "WinDLL", return_value=kernel, create=True):
            from router.checker import _kill_tree
            _kill_tree(proc)
        self.assertEqual(close.argtypes, [ctypes.wintypes.HANDLE])
        self.assertIsNone(proc._tf_job)

    def test_first_error_uses_exception_after_workspace_frame(self):
        with tempfile.TemporaryDirectory() as root:
            out = f'  File "{root}/x.py", line 7, in <module>\n    run()\nValueError: useful failure\nFAILED (errors=1)'
            self.assertEqual(_first_error(out, root), "x.py:7: ValueError: useful failure")

    def test_declared_new_task_file_is_an_ordinary_accept_failure(self):
        with tempfile.TemporaryDirectory() as root:
            ws = load_workspace(root)
            result = run_accept_spec(AcceptSpec((sys.executable, "-c", "import newmod"), {}, "argument"),
                                     ws, 5, task_files=("newmod.py",))
            self.assertFalse(result.ok)
            self.assertIsNone(result.stop)

    def test_non_python_program_env_kind_is_valid(self):
        with tempfile.TemporaryDirectory() as root:
            ws = load_workspace(root)
            with mock.patch("router.checker.shutil.which", return_value=None):
                _argv, env_kind = _resolve_argv0(["missing-program"], ws)
            self.assertEqual(env_kind, "missing")

    def test_absolute_python_runs(self):
        with tempfile.TemporaryDirectory() as root:
            ws = load_workspace(root)
            result = run_accept_spec(AcceptSpec((sys.executable, "-c", "print('ok')"), {}, "argument"), ws, 5, None)
            self.assertTrue(result.ok)

    def test_unknown_program_and_missing_module_are_environment_stops(self):
        with tempfile.TemporaryDirectory() as root:
            ws = load_workspace(root)
            result = run_accept_spec(AcceptSpec(("no-such-tf-command",), {}, "argument"), ws, 5)
            self.assertEqual(result.stop, "env_missing")
            result = run_accept_spec(AcceptSpec((sys.executable, "-c", "import tf_missing_987654"), {}, "argument"), ws, 5)
            self.assertEqual(result.stop, "env_missing")

    def test_task_file_module_is_ordinary_accept_failure(self):
        with tempfile.TemporaryDirectory() as root:
            ws = load_workspace(root)
            result = run_accept_spec(AcceptSpec((sys.executable, "-c", "import tf_new_task_module"), {}, "argument"), ws, 5,
                                     task_files=("tf_new_task_module.py",))
            self.assertFalse(result.ok)
            self.assertIsNone(result.stop)

    def test_venv_interpreter_substitution_and_output_cap(self):
        with tempfile.TemporaryDirectory() as root:
            bindir = Path(root) / ".venv" / ("Scripts" if os.name == "nt" else "bin")
            bindir.mkdir(parents=True)
            target = bindir / ("python.exe" if os.name == "nt" else "python")
            shutil.copy2(sys.executable, target)
            (Path(root) / ".venv" / "pyvenv.cfg").write_text(f"home = {Path(sys.executable).parent}\n", encoding="utf-8")
            ws = load_workspace(root)
            result = run_accept_spec(AcceptSpec(("python", "-c", "print('a'*3000)"), {}, "argument"), ws, 5)
            self.assertTrue(result.ok)
            self.assertEqual(result.env_kind, "venv")
            self.assertLessEqual(len(result.out), 1610)

    def test_cancel_event_stops_child(self):
        with tempfile.TemporaryDirectory() as root:
            ws = load_workspace(root)
            cancel = threading.Event()
            timer = threading.Timer(.2, cancel.set)
            timer.start()
            result = run_accept_spec(AcceptSpec((sys.executable, "-c", "import time; time.sleep(10)"), {}, "argument"), ws, 5, cancel)
            timer.cancel()
            self.assertEqual(result.stop, "out_of_time")

    def test_timeout_kills_grandchild_process(self):
        import subprocess
        import time
        with tempfile.TemporaryDirectory() as root:
            ws = load_workspace(root)
            child = "import os,time; open('grand.pid','w').write(str(os.getpid())); time.sleep(30)"
            parent = ("import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); "
                      "time.sleep(30)")
            # 3 s leaves room for the grandchild to write grand.pid before the timeout fires.
            result = run_accept_spec(AcceptSpec((sys.executable, "-c", parent), {}, "argument"), ws, 3)
            self.assertEqual(result.stop, "out_of_time")
            pid_file = Path(root) / "grand.pid"
            self.assertTrue(pid_file.exists(), "grandchild never started")
            pid = int(pid_file.read_text(encoding="utf-8"))
            # Windows: os.kill(pid, 0) would TerminateProcess, so ask tasklist instead of probing.
            # POSIX: signal 0 only probes; poll briefly because a killed child can linger as a zombie.
            deadline = time.monotonic() + 3.0
            while True:
                if os.name == "nt":
                    out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
                    alive = str(pid) in out
                else:
                    try:
                        os.kill(pid, 0)
                        alive = True
                    except OSError:
                        alive = False
                if not alive or time.monotonic() >= deadline:
                    break
                time.sleep(0.05)
            self.assertFalse(alive, f"grandchild {pid} is still running")

    def test_environment_allowlist_and_spec_variables(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.dict(os.environ, {"TF_TEST_SECRET": "hidden", "LANG": "allowed"}):
            ws = load_workspace(root)
            code = "import os; print(repr(os.getenv('TF_TEST_SECRET')), os.getenv('LANG'), os.getenv('TF_SPEC_VALUE'))"
            result = run_accept_spec(AcceptSpec((sys.executable, "-c", code), {"TF_SPEC_VALUE": "yes"}, "argument"), ws, 5)
            self.assertTrue(result.ok)
            self.assertIn("None allowed yes", result.out)


if __name__ == "__main__":
    unittest.main()
