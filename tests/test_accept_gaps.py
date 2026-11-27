"""Step 4 gap cases: accept parsing, runner, workspace denylist and the guarded write path.

Offline and portable: only the interpreter running the suite is used; no Docker, network, Ollama or secrets.
"""
import contextlib
import json
import os
import shlex
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from router import config, loop, workspace
from router.checker import AcceptSpec, accept_from_task, parse_accept, run_accept_spec
from router.workspace import load_workspace

DENIED_PATHS = (".git/config", ".venv/x", "venv/x", "node_modules/.bin/tool", ".github/workflows/check.yml",
                "conftest.py", "sitecustomize.py", "usercustomize.py", "x.pth", "setup.py", "setup.cfg",
                "pyproject.toml", "pytest.ini", "tox.ini", "noxfile.py", "package.json", ".npmrc", "Makefile", ".envrc")
PARAMS = {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
          "required": ["path", "content"]}
TOOLS = [{"type": "function", "function": {"name": "write_file", "parameters": PARAMS}}]


def _key(path):
    return os.path.normcase(os.path.realpath(path))


class AcceptGapParseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ws = load_workspace(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_env_prefix_is_kept_separate_from_argv(self):
        result = parse_accept("PYTHONPATH=. python -m unittest discover -s tests -t . -q", "task_line", self.ws)
        self.assertEqual(result.note, "")
        self.assertEqual(result.spec.env, {"PYTHONPATH": "."})
        self.assertEqual(result.spec.argv, ("python", "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-q"))

    def test_windows_venv_pytest_keeps_backslashes(self):
        result = parse_accept(r".venv\Scripts\python.exe -m pytest", "task_line", self.ws)
        self.assertEqual(result.note, "")
        self.assertEqual(result.spec.argv, (r".venv\Scripts\python.exe", "-m", "pytest"))

    def test_backtick_span_is_the_accept_command(self):
        result = accept_from_task("Accept: `pytest -q`", "", self.ws)
        self.assertEqual(result.spec.argv, ("pytest", "-q"))

    def test_quoted_pipe_is_allowed_and_round_trips(self):
        argv = ["python", "-c", "print('a|b')"]
        result = parse_accept(shlex.join(argv), "argument", self.ws)
        self.assertEqual(result.note, "")
        self.assertEqual(result.spec.argv, tuple(argv))

    def test_shlex_round_trip_extra_argvs(self):
        argvs = [
            ["python", "-c", 'print("it\'s fine")'],
            ["python", "-c", "import sys; print(sys.argv[1:])", "x y", "--tag=#1"],
            ["python", "x.py", "a;b", "c>d"],
        ]
        for argv in argvs:
            with self.subTest(argv=argv):
                result = parse_accept(shlex.join(argv), "argument", self.ws)
                self.assertEqual(result.note, "")
                self.assertEqual(result.spec.argv, tuple(argv))


class AcceptGapRunTest(unittest.TestCase):
    def test_workspace_package_missing_submodule_is_not_env_missing(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / "pkg").mkdir()
            (Path(root) / "pkg" / "__init__.py").write_text("", encoding="utf-8")
            ws = load_workspace(root)
            result = run_accept_spec(AcceptSpec((sys.executable, "-c", "import pkg.missing_part"), {}, "argument"), ws, 10)
            self.assertFalse(result.ok)
            self.assertNotEqual(result.stop, "env_missing")

    def test_output_keeps_head_and_tail(self):
        with tempfile.TemporaryDirectory() as root:
            ws = load_workspace(root)
            code = "import sys; sys.stdout.write('H' * 1000 + 'M' * 2000 + 'T' * 1200)"
            result = run_accept_spec(AcceptSpec((sys.executable, "-c", code), {}, "argument"), ws, 10)
            self.assertTrue(result.ok)
            self.assertTrue(result.out.startswith("H" * 400))
            self.assertTrue(result.out.endswith("T" * 1200))
            self.assertLessEqual(len(result.out), 1610)

    def test_cancel_set_before_run_reports_cancelled(self):
        with tempfile.TemporaryDirectory() as root:
            ws = load_workspace(root)
            cancel = threading.Event()
            cancel.set()
            result = run_accept_spec(AcceptSpec((sys.executable, "-c", "import time; time.sleep(10)"), {}, "argument"),
                                     ws, 10, cancel)
            self.assertFalse(result.ok)
            self.assertEqual(result.first_error, "cancelled")


class AcceptGapWorkspaceTest(unittest.TestCase):
    def test_dashboard_override_beats_dotenv_when_not_in_real_env(self):
        environ = {"CC_WORKSPACE": "dotenv"}
        config._apply_overrides({"workspace": "dashboard"}, set(), environ)
        self.assertEqual(environ["CC_WORKSPACE"], "dashboard")

    def test_empty_host_list_means_host_accept_off(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.object(config, "HOST_ACCEPT_PATHS", frozenset()):
            self.assertFalse(load_workspace(root).host_accept)

    def test_denylist_refused_only_when_host_accept_on(self):
        with tempfile.TemporaryDirectory() as root:
            off = workspace.Workspace(root, _key(root), False, (), None)
            with mock.patch.object(config, "HOST_ACCEPT_PATHS", frozenset({_key(root)})):
                on = load_workspace(root)
            for path in DENIED_PATHS:
                with self.subTest(path=path):
                    self.assertTrue(workspace.denied(path, set(), on))
                    self.assertFalse(workspace.denied(path, {path}, on))
                    self.assertFalse(workspace.denied(path, set(), off))


class DenylistGuardTest(unittest.TestCase):
    def test_refused_write_never_reaches_the_server(self):
        with tempfile.TemporaryDirectory() as root:
            key = _key(root)
            with mock.patch.object(config, "HOST_ACCEPT_PATHS", frozenset({key})):
                ws = load_workspace(root)
            server = _FakeServer()
            role = {"role": "builder", "model": "m", "tools": ["write_file"], "max_steps": 4}
            env_path = str(Path(root) / ".env")
            replies = [_reply(tool_call=_write_call(env_path)), _reply(content="The protected file was not written."),
                       _reply(content="The protected file was not written.")]

            def guard(path):
                return workspace.denied(path, set(), ws)

            @contextlib.asynccontextmanager
            async def open_role(*args, **kwargs):
                yield server

            @contextlib.asynccontextmanager
            async def no_backends(*args, **kwargs):
                yield

            patches = [
                mock.patch.object(workspace, "PROTECTED_ALWAYS", frozenset({_key(env_path)})),
                mock.patch.object(loop, "backends", no_backends),
                mock.patch.object(loop, "open_role", open_role),
                mock.patch.object(loop, "to_openai_tools", lambda *a, **k: TOOLS),
                mock.patch.object(loop, "_count", lambda *a, **k: None),
                mock.patch.object(loop.events, "emit", lambda *a, **k: None),
                mock.patch.object(loop._client.chat.completions, "create", mock.Mock(side_effect=_scripted(replies))),
            ]
            for p in patches:
                p.start()
            try:
                import asyncio
                # The hard deadline turns a retry loop into a failure instead of a hang.
                asyncio.run(asyncio.wait_for(
                    loop._run("builder-agent", role, [{"role": "user", "content": "write the env file"}],
                              "t-guard", guard=guard), 20))
            finally:
                for p in reversed(patches):
                    p.stop()
            self.assertEqual(server.calls, [])


def _scripted(replies):
    """Yield the scripted replies, then a plain text reply forever, so the loop always terminates."""
    queue = list(replies)

    def create(*args, **kwargs):
        if queue:
            return queue.pop(0)
        return _reply(content="The protected file was not written.")

    return create


class _FakeServer:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        return SimpleNamespace(tools=[])

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        return SimpleNamespace(isError=False, content=[])


def _reply(content=None, tool_call=None):
    msg = SimpleNamespace(content=content, tool_calls=[tool_call] if tool_call else None,
                          reasoning_content=None, reasoning=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")], usage=None)


def _write_call(path):
    fn = SimpleNamespace(name="write_file", arguments=json.dumps({"path": path, "content": "x"}))
    return SimpleNamespace(id="w1", type="function", function=fn)


if __name__ == "__main__":
    unittest.main()
