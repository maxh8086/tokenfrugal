"""Tests for MCP gateway self-heal (docs/handoff.md, fix-first follow-up). Written before the code."""
import asyncio
import unittest

from router.mcp_client import Router, conn_error


class Tool:
    def __init__(self, name):
        self.name = name


class FakeSession:
    def __init__(self, tools=("read_file",), fail=None):
        self.tools, self.fail, self.calls = tools, fail, []

    async def list_tools(self):
        return type("T", (), {"tools": [Tool(n) for n in self.tools]})()

    async def call_tool(self, name, args):
        self.calls.append((name, args))
        if self.fail:
            raise self.fail
        return f"ok:{name}"


def run(coro):
    return asyncio.run(coro)


class ConnError(unittest.TestCase):
    def test_true(self):
        for m in ("Connection closed", "MCPError: Connection closed", "container ts-fs is not running",
                  "Error response from daemon: container abc is not running", "BrokenPipeError", "Broken pipe"):
            self.assertTrue(conn_error(Exception(m)), m)

    def test_false(self):
        for m in ("Error code: 400 - does not support tools", "No such file", "timed out after 30s"):
            self.assertFalse(conn_error(Exception(m)), m)
        self.assertFalse(conn_error(asyncio.TimeoutError()))


class Heal(unittest.TestCase):
    def _router(self, bad, good_factory):
        r = Router([bad], reopen={bad: good_factory})
        run(r.list_tools())
        return r

    def test_heals_and_retries_once(self):
        bad = FakeSession(fail=Exception("MCPError: Connection closed"))
        good = FakeSession()
        opened = []

        async def factory():
            opened.append(1)
            return good

        r = self._router(bad, factory)
        self.assertEqual(run(r.call_tool("read_file", {"path": "/a"})), "ok:read_file")
        self.assertEqual(len(opened), 1)
        self.assertEqual(r.heals, 1)
        # later calls go straight to the new session, no second reopen
        self.assertEqual(run(r.call_tool("read_file", {"path": "/b"})), "ok:read_file")
        self.assertEqual(len(opened), 1)
        self.assertEqual(len(good.calls), 2)
        self.assertEqual(len(bad.calls), 1)

    def test_bounded_when_heal_keeps_failing(self):
        bad = FakeSession(fail=Exception("Connection closed"))
        opened = []

        async def factory():
            opened.append(1)
            return FakeSession(fail=Exception("Connection closed"))

        r = self._router(bad, factory)
        with self.assertRaises(Exception) as cm:
            run(r.call_tool("read_file", {"path": "/a"}))
        self.assertIn("Connection closed", str(cm.exception))
        self.assertLessEqual(len(opened), 2)

    def test_reopen_itself_failing_raises_original(self):
        bad = FakeSession(fail=Exception("Connection closed"))

        async def factory():
            raise RuntimeError("docker is down")

        r = self._router(bad, factory)
        with self.assertRaises(Exception) as cm:
            run(r.call_tool("read_file", {}))
        self.assertIn("Connection closed", str(cm.exception))

    def test_other_errors_not_healed(self):
        bad = FakeSession(fail=ValueError("No such file"))
        opened = []

        async def factory():
            opened.append(1)
            return FakeSession()

        r = self._router(bad, factory)
        with self.assertRaises(ValueError):
            run(r.call_tool("read_file", {}))
        self.assertEqual(opened, [])

    def test_without_reopen_behaves_as_before(self):
        bad = FakeSession(fail=Exception("Connection closed"))
        r = Router([bad])
        run(r.list_tools())
        with self.assertRaises(Exception):
            run(r.call_tool("read_file", {}))
        self.assertEqual(r.heals, 0)

    def test_other_sessions_keep_their_tools(self):
        a = FakeSession(tools=("read_file",), fail=Exception("Connection closed"))
        b = FakeSession(tools=("search_code",))
        good = FakeSession(tools=("read_file",))

        async def factory():
            return good

        r = Router([a, b], reopen={a: factory})
        run(r.list_tools())
        self.assertEqual(run(r.call_tool("search_code", {})), "ok:search_code")
        self.assertEqual(run(r.call_tool("read_file", {})), "ok:read_file")
        self.assertEqual(run(r.call_tool("search_code", {})), "ok:search_code")
        self.assertEqual(len(b.calls), 2)


class OpenRetry(unittest.TestCase):
    """The gateway can die during the initial open (calls=0), before any call_tool heal can apply."""

    def _patch(self, fails, msg="Connection closed"):
        import contextlib
        from unittest import mock
        from router import mcp_client
        opened = []

        @contextlib.asynccontextmanager
        async def fake(profile, params=None):
            opened.append(profile)
            if len(opened) <= fails:
                raise Exception(msg)
            yield FakeSession()

        return opened, mock.patch.object(mcp_client, "open_profile", fake)

    def _open(self):
        from router.mcp_client import open_role

        async def go():
            async with open_role("analyze") as r:
                return await r.call_tool("read_file", {}) if await r.list_tools() else None
        return run(go())

    def test_retries_open_once_on_conn_error(self):
        opened, p = self._patch(1)
        with p:
            self.assertEqual(self._open(), "ok:read_file")
        self.assertEqual(len(opened), 2)

    def test_open_retry_bounded(self):
        opened, p = self._patch(99)
        with p, self.assertRaises(BaseException):
            self._open()
        self.assertLessEqual(len(opened), 3)

    def test_other_open_errors_not_retried(self):
        opened, p = self._patch(99, msg="No such profile")
        with p, self.assertRaises(BaseException):
            self._open()
        self.assertEqual(len(opened), 1)


class BackendEnsure(unittest.TestCase):
    """A native server backed by a docker container (synaptree + neo4j) must be started by the router when stopped.

    Contract: `mcp_client.ensure_backend(name) -> bool` (async, best-effort, never raises); containers come from
    `config.NATIVE_BACKENDS[name]`, dependency first; docker is reached only via `mcp_client._docker(*args) -> (rc, out)`;
    `inspect` is called with `-f {{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}`;
    wait loop is bounded by `BACKEND_WAIT_S` and sleeps `BACKEND_POLL_S` between polls.
    """

    def _fake(self, states):
        """states: container -> list of inspect outputs (last repeats). `start` makes no other change."""
        calls = []

        async def docker(*args):
            calls.append(args)
            if args[0] == "inspect":
                seq = states[args[-1]]
                return 0, (seq.pop(0) if len(seq) > 1 else seq[0])
            return 0, ""

        return calls, docker

    def _run(self, states, name="synaptree", wait=0.05):
        from unittest import mock
        from router import mcp_client
        calls, docker = self._fake(states)
        with mock.patch.object(mcp_client, "_docker", docker), \
             mock.patch.object(mcp_client, "BACKEND_WAIT_S", wait), \
             mock.patch.object(mcp_client, "BACKEND_POLL_S", 0.01):
            ok = run(mcp_client.ensure_backend(name))
        return ok, calls

    def test_mapping_exists(self):
        from router import config
        self.assertEqual(config.NATIVE_BACKENDS["synaptree"], ["synaptree-neo4j-1", "synaptree-synaptree-1"])

    def test_running_is_noop(self):
        ok, calls = self._run({"synaptree-neo4j-1": ["running|healthy"], "synaptree-synaptree-1": ["running|"]})
        self.assertTrue(ok)
        self.assertEqual([c for c in calls if c[0] == "start"], [])

    def test_stopped_started_dependency_first(self):
        ok, calls = self._run({"synaptree-neo4j-1": ["exited|", "running|healthy"],
                               "synaptree-synaptree-1": ["exited|", "running|"]})
        self.assertTrue(ok)
        starts = [c[-1] for c in calls if c[0] == "start"]
        self.assertEqual(starts, ["synaptree-neo4j-1", "synaptree-synaptree-1"])

    def test_waits_for_health(self):
        ok, calls = self._run({"synaptree-neo4j-1": ["exited|", "running|starting", "running|healthy"],
                               "synaptree-synaptree-1": ["running|"]})
        self.assertTrue(ok)
        self.assertEqual([c[-1] for c in calls if c[0] == "start"], ["synaptree-neo4j-1"])

    def test_restarting_container_waited_not_started(self):
        ok, calls = self._run({"synaptree-neo4j-1": ["running|healthy"],
                               "synaptree-synaptree-1": ["restarting|", "running|"]})
        self.assertTrue(ok)
        self.assertEqual([c for c in calls if c[0] == "start"], [])

    def test_never_healthy_returns_false_bounded(self):
        ok, calls = self._run({"synaptree-neo4j-1": ["running|unhealthy"], "synaptree-synaptree-1": ["running|"]})
        self.assertFalse(ok)

    def test_unknown_native_server_noop(self):
        ok, calls = self._run({}, name="plan")
        self.assertTrue(ok)
        self.assertEqual(calls, [])

    def test_host_node_noop(self):
        import os
        from unittest import mock
        with mock.patch.dict(os.environ, {"SYNAPTREE_HOST_NODE": "1"}):
            ok, calls = self._run({})
        self.assertTrue(ok)
        self.assertEqual(calls, [])

    def test_docker_failure_does_not_raise(self):
        from unittest import mock
        from router import mcp_client

        async def boom(*a):
            raise OSError("docker missing")

        with mock.patch.object(mcp_client, "_docker", boom):
            self.assertFalse(run(mcp_client.ensure_backend("synaptree")))

    def test_open_role_ensures_before_native_open_each_attempt(self):
        import contextlib
        from unittest import mock
        from router import mcp_client
        order = []

        async def ens(name):
            order.append(("ensure", name))
            return True

        @contextlib.asynccontextmanager
        async def fake_native(name):
            order.append(("open", name))
            if order.count(("open", name)) == 1:
                raise Exception("Connection closed")
            yield FakeSession()

        async def go():
            async with mcp_client.open_role(None, ["synaptree"]) as r:
                return await r.list_tools()

        with mock.patch.object(mcp_client, "ensure_backend", ens), mock.patch.object(mcp_client, "open_native", fake_native):
            run(go())
        self.assertEqual(order, [("ensure", "synaptree"), ("open", "synaptree"),
                                 ("ensure", "synaptree"), ("open", "synaptree")])


if __name__ == "__main__":
    unittest.main()
