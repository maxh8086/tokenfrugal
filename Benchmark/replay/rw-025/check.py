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

import runpy

case = next(c for c in bench.cases() if c[0] == "role_security")
new = "fake-key-7d41c9e0b2a6"
old = "AKIAFAKEFAKEFAKE1234"
with tempfile.TemporaryDirectory() as tmp, patch.object(bench, "SCRATCH", Path(tmp)):
    case[2]()
    fixture = runpy.run_path(str(Path(tmp)/"secret.py"))
    assert fixture["API_KEY"] == new and old not in fixture.values()
    assert fixture["PASSWORD"] == "hunter2"
assert case[4](new + " hunter2")[0]
assert not case[4](old + " hunter2")[0]
assert not case[4](new)[0]
