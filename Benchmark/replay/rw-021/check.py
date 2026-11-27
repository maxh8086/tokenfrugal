"""Run the preflight and live branch with fake services and a private raw result."""
import contextlib
import io
import os
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path.cwd()))
for key in list(os.environ):
    if key.startswith("TOKENFRUGAL_"):
        del os.environ[key]

source = Path.cwd() / "Benchmark/script/run_benchmark.py"
container = "synaptree-synaptree-1"
inspect_cmd = ["docker", "inspect", "-f", "{{.State.Running}} {{.State.StartedAt}}", container]
old, new = "2020-01-01T00:00:00Z", "2020-02-02T00:00:00Z"
def scenario(root, *, running=True, reachable=True, after=None, inspect_error=False):
    script = root / "Benchmark/script/run_benchmark.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(source, script)
    csv = root / "result.csv"
    started = False
    raw = None
    guard_offset = 0

    def fake_run(cmd, **kwargs):
        nonlocal started, raw, guard_offset
        cmd = list(map(str, cmd))
        if cmd == inspect_cmd:
            if inspect_error:
                return subprocess.CompletedProcess(cmd, 1, "", "inspect failed")
            state = after if started and after else (running, old)
            output = f"{str(state[0]).lower()} {state[1]}\n"
        elif cmd[:4] == ["docker", "mcp", "profile", "ls"]:
            output = "analyze browser build-data build debug design docs security"
        elif cmd == ["docker", "info"] or cmd[:4] == ["docker", "mcp", "profile", "show"]:
            output = ""
        elif cmd[:3] == [sys.executable, "-m", "scripts.bench"]:
            started = True
            guard_offset = console.tell()
            raw = Path(kwargs["env"]["BENCH_OUT_DIR"]) / "123-probe.json"
            raw.write_text(raw_text, encoding="utf-8")
            output = ""
        else:
            raise AssertionError(cmd)
        return subprocess.CompletedProcess(cmd, 0, output, "")

    def connect(address, *args, **kwargs):
        if address == ("127.0.0.1", 17687) and not reachable:
            raise OSError("offline")
        return Mock()

    guarded = after is not None and (not after[0] or after[1] != old)
    # An early JSON read raises immediately if the guard runs too late.
    raw_text = "unreviewed raw output" if guarded else "{}"
    profile = ModuleType("router.profile_sync")
    profile.ensure_profiles = Mock()
    modules = dict(hardware=ModuleType("hardware"), modelinfo=ModuleType("modelinfo"),
                   bench_csv=SimpleNamespace(rows=Mock(return_value=[])))
    modules["router.profile_sync"] = profile
    console = io.StringIO()
    argv = [str(script), "sample", "--tag", "probe", "--csv", str(csv)]
    with patch.dict(sys.modules, modules), patch.object(sys, "argv", argv), patch.object(sys, "path", sys.path[:]), \
         patch("subprocess.run", side_effect=fake_run), patch("socket.create_connection", side_effect=connect), \
         patch("urllib.request.urlopen", return_value=io.BytesIO(b'{"data":[]}')), \
         contextlib.redirect_stdout(console), contextlib.redirect_stderr(console):
        try:
            spec = importlib.util.spec_from_file_location("__main__", script)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except SystemExit as exc:
            assert exc.code not in (None, 0)
            message = console.getvalue() + "\n" + str(exc)
        else:
            raise AssertionError("expected preflight, guard or empty result to stop the run")

    for rc, output, expected in [(0, "true " + old, (True, old)), (0, "false " + old, (False, old)),
                                 (1, "inspect failed", (False, ""))]:
        with patch.object(module, "run_cmd", return_value=(rc, output)):
            assert module.synaptree_state() == expected

    for label, passed in [(f"synaptree container {container} running", running),
                          ("synaptree neo4j 127.0.0.1:17687", reachable)]:
        assert any(label in line and ("PASS" if passed else "FAIL") in line
                   for line in message.splitlines()), message
    if running:
        assert old in message
    assert started == (running and reachable)
    if started:
        assert raw.read_text(encoding="utf-8") == raw_text
        if guarded:
            assert not csv.exists()
            modules["bench_csv"].rows.assert_not_called()
            warning = message[guard_offset:].lower()
            assert all(word in warning for word in
                       [old.lower(), after[1].lower(), "builder", "reviewer", "debugger", "analyzer", "--from-json"]), warning
        else:
            modules["bench_csv"].rows.assert_called_once()


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    scenario(root / "container", running=False)
    scenario(root / "inspect-error", running=False, inspect_error=True)
    scenario(root / "database", reachable=False)
    scenario(root / "restart", after=(True, new))
    scenario(root / "stopped", after=(False, old))
    scenario(root / "stable")
