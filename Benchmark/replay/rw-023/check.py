"""Offline replay acceptance check. Run from the task worktree."""
import os
import sys
from pathlib import Path

for key in list(os.environ):
    if key.startswith("TOKENFRUGAL_"):
        del os.environ[key]
sys.dont_write_bytecode = True
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

import importlib
import tempfile
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

router = ModuleType("router")
router.__path__ = []
router.loop = Mock()
router.server = Mock()
router.store = Mock()
config = ModuleType("router.config")
config.ROOT = ROOT
config.SYNAPTREE_PROJECT = "fixture"
sys.modules.update({"router": router, "router.config": config, "router.store": router.store,
                    "router.loop": router.loop, "router.server": router.server})
with patch("subprocess.run", side_effect=AssertionError), patch("urllib.request.urlopen", side_effect=AssertionError), patch("socket.socket.connect", side_effect=AssertionError):
    bench = importlib.import_module("scripts.bench_real")

import asyncio
from unittest.mock import AsyncMock

async def timed(call):
    return 0.1, await call

def run_case(cid, trail):
    tid = "123456abcd"
    router.loop.DONE = {}
    router.store.get.return_value = {"trail": trail}
    router.server.dispatch_task = AsyncMock(return_value=f"[{tid}] plan done")
    with tempfile.TemporaryDirectory() as tmp, patch.object(bench, "SCRATCH", Path(tmp)/"scratch"), patch.dict(os.environ, {"BENCH_CASES": cid}), patch.object(bench, "container_state", return_value={"Running": True, "StartedAt": "same"}), patch.object(bench, "container_logs", return_value=""):
        result = asyncio.run(bench.run(1, timed, lambda r: True, str, lambda s: {}))
        return result[cid]["runs"][0]

tid = "123456abcd"
reply = f"[{tid}] answer"
tool = {"ev": "tool", "name": "read_file", "args": "{}"}
closed = {"ev": "tool_error", "name": "read_file", "error": "transport: Connection closed"}
events = [tool, closed]
assert bench.tid_of(reply) == tid and bench.tid_of("[xyz] answer") is None
assert bench.strip_tid(reply) == "answer"
router.store.get.return_value = {"trail": events}
assert bench.trail_of(reply) == events
router.store.get.assert_called_with(tid)
router.store.get.return_value = None
assert bench.trail_of(reply) == [] and bench.trail_of("answer") == []
with patch.object(router.store, "get", side_effect=RuntimeError):
    assert bench.trail_of(reply) == []
assert bench.trail_tools(events) == ["read_file"]
assert bench.trail_conn_error(events)
assert not bench.trail_conn_error([dict(closed, error="missing"), dict(tool, args="Connection closed")])
assert run_case("role_analyzer", events)["status"] == "infra"
assert run_case("role_analyzer", [tool])["status"] == "valid"
rec = run_case("role_tracker", [tool])
assert rec["trail_tools"] == ["read_file"] and not rec["verified"]
assert rec["note"] == "tool plan_status not called"
assert run_case("role_tracker", [])["verified"]
assert run_case("role_tracker", [dict(tool, name="plan_status")])["verified"]
