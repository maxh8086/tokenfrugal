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

cases = {c[0]: c for c in bench.cases()}
assert "role_browser" in bench.SYNAPTREE_CASES
assert bench.REQUIRED_TOOLS["role_browser"] == "navigate_page"
browser = cases["role_browser"]
assert "http://host.docker.internal:8787/ui/" in browser[3] and "navigate_page" in browser[3]
for reply, expected in [("Synaptree TRACE", True), ("Synaptree", False), ("trace", False)]:
    assert browser[4](reply)[0] == expected
for reply, expected in [("MCP local. " + "Hello! "*5, True), ("MCP local. " + "Hello! "*6, False),
                        ("MCP router " + "a"*1200, False), ("A local router.", False)]:
    assert bench._readme_ok(reply)[0] == expected

async def timed(call):
    return 0.0, await call

with tempfile.TemporaryDirectory() as tmp, patch.object(bench, "SCRATCH", Path(tmp)/"scratch"):
    scratch = bench.SCRATCH
    scratch.mkdir()
    for name in ("calc.py", "stack.py"):
        (scratch/name).write_text("stale", encoding="utf-8")
    cases["role_data"][2]()
    assert all((scratch/n).read_text().strip() == "x = 1" for n in ("calc.py", "stack.py"))
    outside = Path(tmp)/"outside"
    outside.touch()
    def seed():
        assert scratch.is_dir() and not list(scratch.iterdir())
        (scratch/"stray").touch()
        (scratch/"nested").mkdir()
    case = ("role_data", cases["role_data"][1], seed, "fixture", lambda r: (True, "ok"))
    router.server.dispatch_task = AsyncMock(return_value="answer")
    with patch.object(bench, "cases", return_value=[case]), patch.dict(os.environ, {"BENCH_CASES": "role_data"}):
        asyncio.run(bench.run(2, timed, bool, str, lambda s: {}))
    assert outside.exists() and scratch.is_dir()
