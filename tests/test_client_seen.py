import asyncio
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import mcp.types as mcp_types

from gateway import events, server


class ClientSeenTests(unittest.TestCase):
    def test_initialize_emits_client_name(self):
        # Same reconstruction FastMCP does for on_initialize (see fastmcp low_level._run_initialize_mw)
        msg = mcp_types.InitializeRequest.model_validate(
            {"method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                                                "clientInfo": {"name": "claude-code", "version": "1"}}},
            by_name=False)
        ctx = types.SimpleNamespace(message=msg)

        async def nxt(_):
            return "ok"

        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "events.jsonl"
            with mock.patch.object(events, "EVENTS_PATH", path):
                self.assertEqual(asyncio.run(server._ClientSeen().on_initialize(ctx, nxt)), "ok")
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([r["name"] for r in rows if r["kind"] == "client"], ["claude-code"])


if __name__ == "__main__":
    unittest.main()
