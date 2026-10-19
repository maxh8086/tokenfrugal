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


if __name__ == "__main__":
    unittest.main()
