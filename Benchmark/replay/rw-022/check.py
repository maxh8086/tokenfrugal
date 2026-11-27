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

assert bench.strip_tid("[012345abcd]  reply") == "reply"
for raw in (" [012345abcd] ok", "[012345ABCd] ok", "[123] ok"):
    assert bench.strip_tid(raw) == raw
cases = {c[0]: c[-1] for c in bench.cases()}
sample = "FIRST\nsecond" + "x"*100
assert bench._all_has("first", "second")(sample) == (True, sample[:100].replace("\n", " "))
assert not bench._all_has("third", "first")(sample)[0]
for msg, expected in [("AKIAFAKEFAKEFAKE1234 hunter2", True), ("hunter2", False), ("api_key password", False)]:
    assert cases["role_security"](msg)[0] == expected
for msg, expected in [("ZeroDivisionError on empty", True), ("division by zero: len", True), ("empty", False), ("zerodivision", False)]:
    assert bench._debug_ok(msg) == (expected, msg)
    assert cases["debug_trace"](msg)[0] == expected

with tempfile.TemporaryDirectory() as tmp, patch.object(bench, "SCRATCH", Path(tmp)), patch("subprocess.run") as run:
    for imp, count, rc, expected in [("import stack",3,0,True), ("from stack import Stack",3,0,True), ("",3,0,False), ("import stack",2,0,False), ("import stack",3,1,False)]:
        body = "".join(f"    def test_{i}(self): pass\n" for i in range(count))
        (Path(tmp)/"test_stack.py").write_text(imp+"\nclass Tests:\n"+body+"# def test_extra", encoding="utf-8")
        run.return_value = SimpleNamespace(returncode=rc, stderr="")
        assert cases["write_tests"]("") == (expected, f"rc={rc} tests={count} ")
