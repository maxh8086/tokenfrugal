"""Replay task rw-012: scripts/bench_model.py runs scripts/bench.py for one model tag (offline, no model)."""
import argparse
import contextlib
import io
import os
import runpy
import shutil
import subprocess
import sys
import tempfile
from unittest import mock

for _name in list(os.environ):
    if _name.startswith("TOKENFRUGAL_"):
        del os.environ[_name]

ROOT = os.getcwd()
sys.path.insert(0, ROOT)
SCRIPT = os.path.join(ROOT, "scripts", "bench_model.py")
TAG = "example-model:q4"
LIST_OUTPUT = f"NAME              ID              SIZE      MODIFIED\n{TAG}  abc123def456    2.1 GB    2 days ago\n"
OUT_NAME = "bench/rw012-check"
CHILD_RC = 7
CALLS = []


def fail(message):
    print("FAIL:", message)
    return 1


def is_bench(parts):
    return any(p.replace("\\", "/").endswith("scripts/bench.py") for p in parts)


def record(args, kwargs):
    cmd = args[0] if args else kwargs.get("args")
    parts = [str(p) for p in cmd] if isinstance(cmd, (list, tuple)) else [str(cmd)]
    rc = CHILD_RC if is_bench(parts) else 0
    CALLS.append((parts, dict(kwargs)))
    return parts, rc


def fake_run(*args, **kwargs):
    parts, rc = record(args, kwargs)
    out = LIST_OUTPUT if "list" in parts else ""
    return subprocess.CompletedProcess(parts, rc, stdout=out, stderr="")


def fake_check_output(*args, **kwargs):
    parts, _ = record(args, kwargs)
    return LIST_OUTPUT if "list" in parts else ""


def fake_call(*args, **kwargs):
    return record(args, kwargs)[1]


def fake_check_call(*args, **kwargs):
    parts, rc = record(args, kwargs)
    if rc:
        raise subprocess.CalledProcessError(rc, parts)
    return 0


class FakePopen:
    def __init__(self, *args, **kwargs):
        self.args, self.returncode = record(args, kwargs)
        self.stdout = io.StringIO(LIST_OUTPUT if "list" in self.args else "")
        self.stderr = io.StringIO("")

    def wait(self, timeout=None):
        return self.returncode

    def poll(self):
        return self.returncode

    def communicate(self, input=None, timeout=None):
        return self.stdout.read(), ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def run_script(argv):
    del CALLS[:]
    saved_argv = sys.argv
    sys.argv = [SCRIPT] + argv
    patches = [
        mock.patch.object(subprocess, "run", fake_run),
        mock.patch.object(subprocess, "call", fake_call),
        mock.patch.object(subprocess, "check_call", fake_check_call),
        mock.patch.object(subprocess, "check_output", fake_check_output),
        mock.patch.object(subprocess, "Popen", FakePopen),
    ]
    code = 0
    try:
        for patch in patches:
            patch.start()
        with contextlib.redirect_stdout(io.StringIO()):
            try:
                runpy.run_path(SCRIPT, run_name="__main__")
            except SystemExit as exc:
                code = 0 if exc.code is None else exc.code
    finally:
        for patch in patches:
            patch.stop()
        sys.argv = saved_argv
    return code


def main():
    helped = subprocess.run([sys.executable, SCRIPT, "--help"], cwd=ROOT, capture_output=True, text=True, timeout=120)
    if helped.returncode != 0:
        return fail("--help exited %d" % helped.returncode)
    bench_dir = os.path.join(ROOT, "bench")
    had_bench = os.path.isdir(bench_dir)
    try:
        code = run_script(["--model", TAG, "--out-dir", OUT_NAME])
        if code != CHILD_RC:
            return fail("exit code %r, expected the child's return code %d" % (code, CHILD_RC))
        bench_calls = [(parts, kw) for parts, kw in CALLS if is_bench(parts)]
        if len(bench_calls) != 1:
            return fail("expected one run of scripts/bench.py, saw %d" % len(bench_calls))
        parts, kw = bench_calls[0]
        env = kw.get("env") or os.environ
        wanted = (("TOKENFRUGAL_MODEL_BUILDER", TAG), ("TOKENFRUGAL_MODEL_THINKER", TAG), ("BENCH_OUT_DIR", OUT_NAME))
        for key, want in wanted:
            if env.get(key) != want:
                return fail("%s is %r, expected %r" % (key, env.get(key), want))
        norm = [p.replace("\\", "/") for p in parts]
        start = next(i for i, p in enumerate(norm) if p.endswith("scripts/bench.py"))
        tail = norm[start + 1:]
        parser = argparse.ArgumentParser(add_help=False)
        for flag in ("--n", "--only", "--tag"):
            parser.add_argument(flag, required=True)
        try:
            options, _ = parser.parse_known_args(tail)
        except SystemExit:
            return fail("missing benchmark arguments in %r" % (tail,))
        if options.n != "2" or options.only != "output,realworld" or not options.tag:
            return fail("unexpected benchmark arguments in %r" % (tail,))
        with tempfile.TemporaryDirectory() as tmp:
            gguf = os.path.join(tmp, "model.gguf")
            with open(gguf, "wb") as handle:
                handle.write(b"GGUF")
            run_script(["--model", TAG, "--out-dir", OUT_NAME, "--gguf", gguf])
        if not any("list" in parts for parts, _ in CALLS):
            return fail("the --gguf run did not check ollama list")
        for parts, _ in CALLS:
            if "create" in parts:
                return fail("ollama create ran although ollama list shows the tag: %r" % (parts,))
    except Exception as exc:
        return fail("raised %r" % (exc,))
    finally:
        shutil.rmtree(os.path.join(ROOT, "bench", "rw012-check"), ignore_errors=True)
        if not had_bench and os.path.isdir(bench_dir) and not os.listdir(bench_dir):
            os.rmdir(bench_dir)
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
