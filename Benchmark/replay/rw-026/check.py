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

default = "write_function fix_bug write_tests rename_across_files find_symbol review_sqli debug_trace summarize_readme role_analyzer role_data role_docs role_security role_designer role_browser role_tracker role_research".split()
hard = set("hard_multifile_bug hard_two_vulns hard_ambiguous_trace hard_long_summary hard_compare_functions".split())
agents = {"testing-code-reviewer", "engineering-sre", "engineering-technical-writer"}
os.environ.pop("BENCH_SUITE", None)
assert [c[0] for c in bench.cases()] == default
hard_cases = bench.hard_cases()
assert len(hard_cases) == 5 and {c[0] for c in hard_cases} == hard
with tempfile.TemporaryDirectory() as tmp, patch.object(bench, "SCRATCH", Path(tmp)):
    for cid, agent, setup, prompt, check in hard_cases:
        bench._clean_scratch()
        setup()
        assert agent in agents and any(p.is_file() for p in Path(tmp).rglob("*"))
        assert not check("")[0]

async def timed(call):
    return 0.0, await call

with tempfile.TemporaryDirectory() as tmp, patch.object(bench, "SCRATCH", Path(tmp)), patch.object(bench, "container_state", return_value={"Running": True}), patch.object(bench, "container_logs", return_value=""):
    router.server.dispatch_task = AsyncMock(return_value="offline")
    for suite in (None, "unknown", "hard"):
        with patch.dict(os.environ, {"BENCH_CASES": ""}):
            if suite is not None:
                os.environ["BENCH_SUITE"] = suite
            result = asyncio.run(bench.run(1, timed, lambda r: False, str, lambda s: {}))
            if suite == "hard":
                assert set(result) == hard
            else:
                assert list(result) == default
