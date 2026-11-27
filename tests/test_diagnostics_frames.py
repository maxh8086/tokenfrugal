import asyncio
import contextlib
import io
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from router import compose, docker_mcp, events, loop, mcp_client, preflight, server, store

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import doctor  # noqa: E402


class DiagnosticFrames(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp()
        ws_patch = mock.patch.object(server, "WORKSPACE", self.temp)
        ws_patch.start()
        self.addCleanup(ws_patch.stop)
        self.db_patch = mock.patch.object(store, "DB_PATH", Path(self.temp) / "e2e.db")
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.events = []
        self.event_patch = mock.patch.object(events, "emit", side_effect=lambda kind, **kw: self.events.append((kind, kw)))
        self.event_patch.start()
        self.addCleanup(self.event_patch.stop)

    def _run_execute(self, role=None, run_side_effect=None, extra=()):
        tid = store.create("builder-agent", "builder", "check")
        fixture = {"role": "builder", "model": "m", "tools": ["read_file"], "skills": [], "max_steps": 4}
        fixture.update(role or {})
        async def idle_heartbeat(*args, **kwargs):
            await asyncio.Event().wait()
        @contextlib.asynccontextmanager
        async def no_backends(*args, **kwargs):
            yield
        patches = [
            mock.patch.object(loop, "backends", no_backends),
            mock.patch.object(server.gpu_lease, "guard_ollama", lambda *a, **k: None),
            mock.patch.object(loop._client.chat.completions, "create", side_effect=AssertionError),
            mock.patch.object(server, "_heartbeat", idle_heartbeat),
            *extra,
        ]
        if run_side_effect is not None:
            patches.append(mock.patch.object(server, "run", side_effect=run_side_effect))
        with contextlib.ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            asyncio.run(server._execute(tid, "builder-agent", fixture, "check"))
        row = store.get(tid)
        failed = [kw for kind, kw in self.events if kind == "task_failed"]
        self.assertEqual(len(failed), 1)
        return row, failed[0]

    def _assert_failure(self, role=None, run_side_effect=None, extra=(), kind="env_missing", error=None, frame=None):
        row, event = self._run_execute(role, run_side_effect, extra)
        self.assertEqual(row["error_kind"], kind)
        if error is not None:
            self.assertEqual(row["error"], error)
        self.assertEqual(event["error_kind"], kind)
        if frame:
            self.assertTrue(any(frame in f for f in event.get("frames", [])), event.get("frames"))
        return row, event

    def test_open_role_failure_has_frames(self):
        @contextlib.asynccontextmanager
        async def no_backends(*args, **kwargs):
            yield
        @contextlib.asynccontextmanager
        async def missing(*args, **kwargs):
            raise FileNotFoundError("program not found: x")
            yield
        self._assert_failure(extra=(mock.patch.object(loop, "backends", no_backends), mock.patch.object(loop, "open_role", missing)),
                             error="program not found: x", frame="_run")

    def test_compose_launch_failure_is_diagnosable(self):
        @contextlib.asynccontextmanager
        async def safe_open(*args, **kwargs):
            yield None
        self._assert_failure(role={"compose": ["svc"]}, error="program not found: docker", frame="_launch_guard",
                             extra=(mock.patch.object(loop, "backends", compose.backends),
                                    mock.patch.object(loop, "open_role", safe_open),
                                    mock.patch.object(compose, "LEASES", Path(self.temp) / "leases"),
                                    mock.patch.object(compose.asyncio, "create_subprocess_exec", side_effect=FileNotFoundError(2, "No such file"))))


    def test_stdio_client_launch_failure_is_diagnosable(self):
        @contextlib.asynccontextmanager
        async def no_backends(*args, **kwargs):
            yield
        @contextlib.asynccontextmanager
        async def missing(*args, **kwargs):
            raise FileNotFoundError(2, "No such file")
            yield
        with mock.patch.object(mcp_client, "NATIVE_SERVERS", {"fake": {"command": "fakeprog", "args": []}}), \
             mock.patch.object(mcp_client, "stdio_client", missing):
            self._assert_failure(role={"native": ["fake"]}, extra=(mock.patch.object(loop, "backends", no_backends),),
                                 error="program not found: fakeprog", frame="_launch_guard")

    def test_docker_bin_missing_program_is_found(self):
        with mock.patch.object(docker_mcp.shutil, "which", return_value=None):
            with self.assertRaises(docker_mcp.DockerMcpError) as caught:
                docker_mcp.docker_bin()
        self.assertEqual(loop.program_missing(caught.exception), "program not found: docker")

    def test_sibling_exception_group_is_diagnosable(self):
        group = ExceptionGroup("g", [ValueError("first"), FileNotFoundError("program not found: x")])
        _, event = self._assert_failure(run_side_effect=group, error="program not found: x")
        self.assertTrue(event.get("frames"))

    def test_group_cause_is_diagnosable(self):
        err = docker_mcp.DockerMcpError("docker was not found")
        err.__cause__ = FileNotFoundError("program not found: docker")
        _, event = self._assert_failure(run_side_effect=ExceptionGroup("g", [err]), error="program not found: docker")
        self.assertTrue(event.get("frames"))

    def test_native_backend_state_failure_names_container(self):
        env = mock.patch.dict(os.environ)
        env.__enter__()
        os.environ.pop("SYNAPTREE_HOST_NODE", None)
        self.addCleanup(env.__exit__, None, None, None)
        _, event = self._assert_failure(role={"native": ["n"]}, kind="infra", error="infra: backend for n: container c is exited",
                                        extra=(mock.patch.object(server, "NATIVE_BACKENDS", {"n": ["c"]}),
                                               mock.patch.object(mcp_client, "NATIVE_BACKENDS", {"n": ["c"]}),
                                               mock.patch.object(server, "backend_state", new_callable=mock.AsyncMock, return_value="container c is exited")))
        self.assertEqual(event["error_kind"], "infra")

    def test_native_backend_missing_docker_is_diagnosable(self):
        err = docker_mcp.DockerMcpError("docker was not found")
        err.__cause__ = FileNotFoundError("program not found: docker")
        with mock.patch.dict(os.environ):
            os.environ.pop("SYNAPTREE_HOST_NODE", None)
            _, event = self._assert_failure(role={"native": ["n"]}, error="program not found: docker",
                                            extra=(mock.patch.object(server, "NATIVE_BACKENDS", {"n": ["c"]}),
                                                   mock.patch.object(mcp_client, "NATIVE_BACKENDS", {"n": ["c"]}),
                                                   mock.patch.object(mcp_client, "_docker", side_effect=err)))
        self.assertNotIn("frames", event)

    def test_unclassified_failure_has_server_frame(self):
        _, event = self._assert_failure(run_side_effect=RuntimeError("boom"), kind="error")
        self.assertTrue(any("server.py" in f and "_execute" in f for f in event.get("frames", [])))

    def test_tool_call_error_returns_to_model(self):
        from tests import test_error_kind as helpers
        class BrokenSession(helpers._Session):
            async def call_tool(self, name, args):
                raise FileNotFoundError(2, "No such file")
        @contextlib.asynccontextmanager
        async def open_broken(*args, **kwargs):
            yield BrokenSession()
        final = helpers._reply(content="The check is complete.")
        calls = helpers._scripted([helpers._reply(tool_call=helpers._call(1)), final, final, final, final, final])
        patches = helpers._patches(calls)
        patches[1] = mock.patch.object(loop, "open_role", open_broken)
        patches.append(mock.patch.object(loop.mcp_reap, "sweep", lambda *a, **k: None))
        with contextlib.ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            result = asyncio.run(loop.run("builder-agent", {"role": "builder", "model": "m", "tools": ["read_file"], "skills": [], "max_steps": 4}, "check", None, "tid"))
        messages = result[1]
        self.assertTrue(any(m.get("role") == "tool" and "tool error:" in str(m) and "No such file" in str(m) for m in messages))
        self.assertFalse(any("program not found" in str(m) for m in messages))

    def test_health_only_first_event_has_missing_programs(self):
        calls = 0
        async def sleep(_):
            nonlocal calls
            calls += 1
            if calls > 1:
                raise RuntimeError("stop")
        events_seen = []
        async def run():
            with mock.patch.object(server, "missing_programs", return_value=["docker"]), \
                 mock.patch.object(server.events, "emit", side_effect=lambda kind, **kw: events_seen.append((kind, kw))), \
                 mock.patch.object(server.asyncio, "sleep", side_effect=sleep):
                try:
                    await server._health_loop()
                except RuntimeError:
                    pass
        asyncio.run(run())
        health = [kw for kind, kw in events_seen if kind == "health"]
        self.assertTrue(health[0]["missing"])
        self.assertNotIn("missing", health[1])

    def test_launch_guard_keeps_permission_error(self):
        @contextlib.asynccontextmanager
        async def denied(*args, **kwargs):
            raise PermissionError("denied")
            yield
        async def run():
            with mock.patch.object(mcp_client, "stdio_client", denied):
                async with mcp_client._launch_guard("npx"):
                    async with mcp_client.stdio_client():
                        pass
        with self.assertRaisesRegex(PermissionError, "denied"):
            asyncio.run(run())

    def test_missing_programs_includes_native_commands(self):
        with mock.patch.object(preflight.shutil, "which", side_effect=lambda x: None if x in {"docker", "npx"} else x):
            self.assertEqual(preflight.missing_programs(), ["docker", "npx"])

    def test_frames_contain_innermost_and_router_frames(self):
        try:
            raise ValueError("boom")
        except ValueError as exc:
            frames = loop.frames_of(exc)
        self.assertTrue(frames)
        self.assertLessEqual(sum("router/" in frame.replace("\\", "/") for frame in frames), 3)

    def test_launch_guard_converts_only_missing_executable(self):
        @contextlib.asynccontextmanager
        async def missing(*args, **kwargs):
            raise FileNotFoundError(2, "No such file")
            yield
        async def run():
            with mock.patch.object(mcp_client, "stdio_client", missing):
                async with mcp_client._launch_guard("npx"):
                    async with mcp_client.stdio_client():
                        pass
        with self.assertRaisesRegex(FileNotFoundError, "program not found: npx"):
            asyncio.run(run())

    def test_launch_guard_does_not_relabel_errors_after_entry(self):
        async def run():
            async with mcp_client._launch_guard("npx"):
                pass
            raise FileNotFoundError("later operation")
        with self.assertRaisesRegex(FileNotFoundError, "later operation"):
            asyncio.run(run())

    def test_launch_guard_wraps_subprocess_awaitable(self):
        async def run():
            async with mcp_client._launch_guard("docker"):
                raise FileNotFoundError(2, "No such file")
        with self.assertRaisesRegex(FileNotFoundError, "program not found: docker"):
            asyncio.run(run())

    def test_backend_state_keeps_reason(self):
        async def run():
            with mock.patch.object(mcp_client, "NATIVE_BACKENDS", {"n": ["container"]}), \
                 mock.patch.object(mcp_client, "_docker", side_effect=FileNotFoundError("program not found: docker")):
                return await mcp_client.backend_state("n")
        self.assertEqual(asyncio.run(run()), "program not found: docker")

    def test_trail_displays_frames(self):
        self.assertIn("router/server.py:1", server._trail_line({"kind": "failed", "frames": ["router/server.py:1:f"]}))

    def test_first_health_event_only_has_missing(self):
        events_seen = []
        async def run():
            with mock.patch.object(server, "missing_programs", return_value=["docker"]), \
                 mock.patch.object(server.events, "emit", side_effect=lambda *a, **kw: events_seen.append((a, kw))), \
                 mock.patch.object(server.asyncio, "sleep", side_effect=RuntimeError("stop")):
                try:
                    await server._health_loop()
                except RuntimeError:
                    pass
        asyncio.run(run())
        self.assertEqual(events_seen[0][1]["missing"], ["docker"])


class BackendStateReasons(unittest.TestCase):
    def _state(self, docker, name="n", host_node="0"):
        async def run():
            with mock.patch.object(mcp_client, "NATIVE_BACKENDS", {"n": ["c"]}), \
                 mock.patch.object(mcp_client, "_docker", side_effect=docker):
                return await mcp_client.backend_state(name)
        with mock.patch.dict(os.environ, {"SYNAPTREE_HOST_NODE": host_node}):
            return asyncio.run(run())

    def test_healthy_container_returns_none(self):
        self.assertIsNone(self._state(lambda *a: (0, "running|healthy")))

    def test_running_without_healthcheck_returns_none(self):
        self.assertIsNone(self._state(lambda *a: (0, "running|")))

    def test_inspect_nonzero_exit_names_container(self):
        self.assertEqual(self._state(lambda *a: (1, "no such object")), "docker inspect failed for c")

    def test_inspect_exception_names_container(self):
        self.assertEqual(self._state(RuntimeError("daemon gone")), "docker inspect failed for c")

    def test_start_exception_names_container(self):
        self.assertEqual(self._state([(0, "exited|"), RuntimeError("boom")]), "docker start failed for c")

    def test_unconfigured_backend_returns_none_without_docker(self):
        self.assertIsNone(self._state(AssertionError("docker must not run"), name="other"))

    def test_host_node_returns_none_without_docker(self):
        self.assertIsNone(self._state(AssertionError("docker must not run"), host_node="1"))


class EnsureBackendWrapsState(unittest.TestCase):
    def test_true_only_when_no_reason(self):
        async def run(reason):
            with mock.patch.object(mcp_client, "backend_state", mock.AsyncMock(return_value=reason)):
                return await mcp_client.ensure_backend("n")
        self.assertTrue(asyncio.run(run(None)))
        self.assertFalse(asyncio.run(run("docker inspect failed for c")))


class LaunchGuardCases(unittest.TestCase):
    def _enter_raising(self, exc):
        @contextlib.asynccontextmanager
        async def failing(*args, **kwargs):
            raise exc
            yield
        async def run():
            with mock.patch.object(mcp_client, "stdio_client", failing):
                async with mcp_client._launch_guard("npx"):
                    async with mcp_client.stdio_client():
                        pass
        asyncio.run(run())

    def test_exception_group_member_is_relabelled(self):
        with self.assertRaisesRegex(FileNotFoundError, "program not found: npx"):
            self._enter_raising(ExceptionGroup("g", [FileNotFoundError(2, "No such file")]))

    def test_other_oserror_is_unchanged(self):
        exc = BrokenPipeError(32, "Broken pipe")
        with self.assertRaises(BrokenPipeError) as caught:
            self._enter_raising(exc)
        self.assertIs(caught.exception, exc)

    @unittest.skipUnless(os.name == "nt", "winerror is Windows only")
    def test_winerror_two_and_three_are_missing_program(self):
        for code in (2, 3):
            exc = OSError(22, "x")
            exc.winerror = code
            with self.subTest(code=code), self.assertRaisesRegex(FileNotFoundError, "program not found: npx"):
                self._enter_raising(exc)

    @unittest.skipUnless(os.name == "nt", "winerror is Windows only")
    def test_other_winerror_is_unchanged(self):
        exc = OSError(22, "x")
        exc.winerror = 5
        with self.assertRaises(OSError) as caught:
            self._enter_raising(exc)
        self.assertIs(caught.exception, exc)


def _raise_inner():
    raise ValueError("inner")


class ProgramMissingCases(unittest.TestCase):
    def test_frames_of_group_reaches_member_frames(self):
        try:
            try:
                _raise_inner()
            except ValueError as inner:
                raise ExceptionGroup("g", [inner])
        except ExceptionGroup as group:
            frames = loop.frames_of(group)
        self.assertTrue(any("_raise_inner" in frame for frame in frames), frames)

    def test_program_missing_finds_later_member(self):
        group = ExceptionGroup("g", [ValueError("first"), FileNotFoundError("program not found: x")])
        self.assertEqual(loop.program_missing(group), "program not found: x")

    def test_program_missing_is_none_for_other_errors(self):
        self.assertIsNone(loop.program_missing(ValueError("boom")))

    def test_error_kind_env_missing(self):
        self.assertEqual(loop.error_kind("program not found: docker"), "env_missing")


class DoctorReport(unittest.TestCase):
    def test_plain_script_run_imports_router(self):
        root = str(Path(__file__).resolve().parent.parent)
        clean_path = [p for p in sys.path if p not in (root, "", os.getcwd())]
        clean_meta_path = [finder for finder in sys.meta_path if "__editable__" not in repr(finder)]
        out = io.StringIO()
        with mock.patch.object(sys, "path", clean_path), mock.patch.object(sys, "meta_path", clean_meta_path):
            with mock.patch.dict(sys.modules):
                for name in list(sys.modules):
                    if name == "router" or name.startswith("router."):
                        del sys.modules[name]
                namespace = runpy.run_path(str(Path(root) / "scripts" / "doctor.py"))
                with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="", stderr="")), \
                     mock.patch("urllib.request.urlopen", side_effect=OSError("endpoint down")), \
                     contextlib.redirect_stdout(out):
                    namespace["main"]()
        self.assertNotIn("run pip install -e . first", out.getvalue())
        self.assertIn("missing programs:", out.getvalue())

    def _run(self, missing, llm_ok=True, import_ok=True):
        calls = []
        def fake_run(args, *a, **k):
            calls.append(list(args))
            return subprocess.CompletedProcess(args, 0)
        def fake_open(*a, **k):
            if not llm_ok:
                raise OSError("endpoint down")
            return io.BytesIO(b'{"data": []}')
        patches = [
            mock.patch.object(doctor, "llm_url", return_value="http://127.0.0.1:9/v1"),
            mock.patch.object(doctor, "gpu_container_ok", return_value=True),
            mock.patch.object(doctor, "driver_check", lambda report: None),
            mock.patch.object(doctor, "wslconfig_check", lambda report: None),
            mock.patch.object(doctor, "required_models", return_value=[]),
            mock.patch.object(doctor.urllib.request, "urlopen", side_effect=fake_open),
            mock.patch.object(doctor.subprocess, "run", side_effect=fake_run),
        ]
        if import_ok:
            patches += [
                mock.patch("router.preflight.missing_programs", return_value=missing),
                mock.patch("router.preflight.stage_model_gaps", return_value=[]),
                mock.patch("router.config.load_tf_roles", return_value={}),
            ]
        else:
            patches.append(mock.patch.dict(sys.modules, {"router.preflight": None}))
        out = io.StringIO()
        with contextlib.ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            with contextlib.redirect_stdout(out):
                code = doctor.main()
        return code, out.getvalue(), calls

    def test_missing_docker_skips_daemon_check(self):
        code, out, calls = self._run(["docker"])
        self.assertNotIn(["docker", "info"], calls)
        self.assertIn("[skip] docker GPU container check", out)
        self.assertIn("[MISSING] docker CLI", out)
        self.assertEqual(code, 1, out)

    def test_docker_present_runs_daemon_check(self):
        code, out, calls = self._run([])
        self.assertIn(["docker", "info"], calls)
        self.assertIn("[ok] docker daemon running", out)
        self.assertEqual(code, 0, out)

    def test_optional_programs_warn_but_do_not_fail(self):
        code, out, _ = self._run(["npx", "hyperframes"])
        self.assertIn("[warn] npx is not on PATH", out)
        self.assertIn("[warn] hyperframes is not on PATH", out)
        self.assertEqual(code, 0, out)

    def test_import_failure_falls_back_with_hint(self):
        code, out, _ = self._run([], llm_ok=False, import_ok=False)
        self.assertIn("run pip install -e . first", out)
        self.assertIn("[MISSING] LLM endpoint", out)
        self.assertEqual(code, 1, out)


if __name__ == "__main__":
    unittest.main()
