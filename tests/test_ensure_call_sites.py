"""Reconnect and claude_import open native servers through open_native_ensured (handoff: self-heal layer 4)."""
import asyncio
import contextlib
import unittest
from types import SimpleNamespace
from unittest import mock

from router import claude_import, mcp_client, reconnect


class FakeSession:
    async def list_tools(self):
        return SimpleNamespace(tools=[SimpleNamespace(name="t1")])


def fake_stack(order):
    @contextlib.asynccontextmanager
    async def fake_native(name):
        order.append(("open", name))
        yield FakeSession()

    async def ensure(name):
        order.append(("ensure", name))
        return True

    return ensure, fake_native


class EnsuredWrapperTests(unittest.TestCase):
    def test_ensure_runs_before_open(self):
        order = []
        ensure, fake_native = fake_stack(order)

        async def go():
            async with mcp_client.open_native_ensured("synaptree") as s:
                return await s.list_tools()

        with mock.patch.object(mcp_client, "ensure_backend", ensure), \
                mock.patch.object(mcp_client, "open_native", fake_native):
            asyncio.run(go())
        self.assertEqual(order, [("ensure", "synaptree"), ("open", "synaptree")])


class ReconnectProbeTests(unittest.TestCase):
    def test_probe_ensures_native_backend_first(self):
        order = []
        ensure, fake_native = fake_stack(order)
        m = {"native": "crawl4ai"}
        with mock.patch.object(mcp_client, "ensure_backend", ensure), \
                mock.patch.object(mcp_client, "open_native", fake_native):
            n = asyncio.run(reconnect._probe(m))
        self.assertEqual(n, 1)
        self.assertEqual(order, [("ensure", "crawl4ai"), ("open", "crawl4ai")])


class ClaudeImportProbeTests(unittest.TestCase):
    def test_probe_tools_ensures_native_backend_first(self):
        order = []
        ensure, fake_native = fake_stack(order)
        with mock.patch.object(claude_import, "load", return_value={"servers": {}}), \
                mock.patch.object(mcp_client, "ensure_backend", ensure), \
                mock.patch.object(mcp_client, "open_native", fake_native):
            names = asyncio.run(claude_import.probe_tools("memory"))
        self.assertEqual(names, ["t1"])
        self.assertEqual(order, [("ensure", "memory"), ("open", "memory")])


if __name__ == "__main__":
    unittest.main()
