"""Infrastructure checks for the benchmark harness. A failed check means the host was not ready, not that the model failed,
so the benchmark records the run as infra and does not count it as a fail.

Task checks (CHECKS) take (body, scratch, expect): the reply body, the host scratch folder for file and sandbox checks,
and the expected root-cause file for trace checks. scripts/bench.py passes both. The scratch folder and its tool-side path
(SCRATCH, WS) live here too, since the team runner is the only one left."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from router import preflight, store
from router.config import ROOT, WORKSPACE

SCRATCH = ROOT / "bench" / "scratch"

NOT_EXPOSED = "not exposed by profile"  # a required tool missing from the role's profile: the host, not the model
INFRA_TOOL_MARKERS = ("Parent directory does not exist", "Read-only", "Permission denied", "Access is denied",
                      NOT_EXPOSED)
# Synaptree gate (moved from the retired scripts/bench_real.py, same behaviour)
SYNAPTREE_CONTAINER = "synaptree-synaptree-1"
INFRA_ERROR = "synaptree container not running"
LOG_TAIL_LINES = 60
LOG_CAP_BYTES = 4096
STALE_MCP_AGE = 900.0  # seconds; a gateway container this old outlived any case (watchdog is at most ~330s)
CONN_MARKERS = ("Connection closed",)  # a trail error with one of these means the router lost its connection
SCRATCH_CHECKS = frozenset({"sandbox_tests", "rename_done"})  # checks that read files in the scratch folder
CATEGORIES = ["injection", "xss", "path traversal", "secret", "hardcoded", "auth", "race", "overflow"]
COMPARE_NAMES = ("total_loop", "total_builtin")  # functions seeded for compare_functions
RENAME_FILES = ("rn_a.py", "rn_b.py")  # seeded for rename_done: old name "tally" must be gone, "total_of" present


class InfraFailure(Exception):
    """Host or Docker problem: the run is infra, not a model fail."""


def tool_paths(folder, workspace):
    """The same folder as the tools see it: /workspace (file, sandbox and test tools).
    Built from the real workspace root, so it holds whatever CC_WORKSPACE points at (repo root or its parent)."""
    rel = folder.relative_to(workspace).as_posix()  # ValueError if the folder is outside the workspace
    return f"/workspace/{rel}"


WS = tool_paths(SCRATCH, WORKSPACE)  # the scratch folder as the tools see it, e.g. /workspace/bench/scratch


def clean_scratch():
    """Delete every file and subdirectory directly under SCRATCH; SCRATCH itself is kept.
    Directory symlinks are unlinked, never followed, so nothing outside SCRATCH is removed."""
    for p in SCRATCH.iterdir():
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()


def scratch_ready(folder: Path, ws_path: str) -> str:
    """'' when the host scratch folder exists (created if missing) and maps to ws_path, else the reason."""
    return preflight.mount_error(folder, ws_path)


def seed_error(paths: list) -> str:
    """'' when every seed file exists and is non-empty, else 'seed missing: <path>' for the first one that fails."""
    for p in paths:
        p = Path(p)
        if not (p.is_file() and p.stat().st_size > 0):
            return f"seed missing: {p}"
    return ""


def seed_files(folder: Path, files: dict) -> str:
    """Write each {name: text} under folder, then verify with seed_error. '' when all are in place, else the reason.
    A non-empty result is infra, not a model fail."""
    folder = Path(folder)
    paths = []
    try:
        for name, text in files.items():
            p = folder / name
            p.write_text(text, encoding="utf-8")
            paths.append(p)
    except OSError as e:
        return f"seed write failed: {e}"
    return seed_error(paths)


def run_sandbox(folder, files: dict = None) -> tuple:
    """Re-write files (so a model cannot pass by editing its own tests), then run unittest discovery in the
    network-less python container the sandbox MCP tool uses. folder is the host scratch folder mounted at /work;
    the caller passes it so this module needs no path of its own. Returns (passed, tail).
    Raises InfraFailure when docker is missing or docker run itself fails (exit 125: daemon down, bad mount, pull failed).
    A timeout is a model fail (the code hung inside the container). Any other non-zero exit is a model fail."""
    for name, text in (files or {}).items():
        (Path(folder) / name).write_text(text, encoding="utf-8")
    argv = ["docker", "run", "--rm", "--network", "none", "--cpus", "2", "--memory", "1g",
            "-e", "PYTHONDONTWRITEBYTECODE=1", "-v", f"{folder}:/work:ro", "-w", "/work",
            os.getenv("TOKENFRUGAL_SANDBOX_IMAGE", "python:3.13-slim"), "python", "-m", "unittest", "discover", "-s", ".", "-q"]
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=90, env=env)
    except subprocess.TimeoutExpired:
        return False, "timeout after 90s"
    except (FileNotFoundError, OSError) as e:
        raise InfraFailure(f"docker not available: {e}")
    if p.returncode == 125:
        first = (p.stderr or "").strip().splitlines()
        raise InfraFailure(first[0] if first else "docker run failed (exit 125)")
    return p.returncode == 0, (p.stdout + p.stderr).strip()[-140:].replace("\n", " ")


def _sql_injection_review(body, scratch=None, expect=None):
    low = body.lower()
    return "injection" in low and any(w in low for w in ("parameter", "prepared", "placeholder", "bind"))


def _two_vulns(body, scratch=None, expect=None):
    low = body.lower()
    return sum(c in low for c in CATEGORIES) >= 2


def _three_vulns(body, scratch=None, expect=None):
    low = body.lower()
    return sum(c in low for c in CATEGORIES) >= 3


def _compare_functions(body, scratch=None, expect=None):
    return ("differ" in body.lower() or "difference" in body.lower()) and sum(n in body for n in COMPARE_NAMES) >= 2


def _debug_crash(body, scratch=None, expect=None):
    return "KeyError" in body and "lookup.py" in body


def _trace_root_cause(body, scratch=None, expect=None):
    return bool(expect) and expect in body


def _long_summary(body, scratch=None, expect=None):
    low = body.lower()
    return 80 <= len(body.split()) <= 180 and all(w in low for w in ("retry", "timeout", "backoff"))


def _rename_done(body, scratch=None, expect=None):
    """True when both scratch files exist, the old name 'tally' is gone from both and the new name 'total_of' is in both."""
    if scratch is None:
        return False
    texts = []
    for name in RENAME_FILES:
        p = Path(scratch) / name
        if not p.is_file():
            return False
        texts.append(p.read_text(encoding="utf-8"))
    return all("tally" not in t and "total_of" in t for t in texts)


def _sandbox_tests(body, scratch=None, expect=None):
    """True only when a test_*.py file exists in scratch and the sandbox unittest run exits 0. No test file is a fail."""
    if scratch is None or not any(Path(scratch).glob("test_*.py")):
        return False
    return run_sandbox(scratch)[0]


_TRAILER = re.compile(r"\s*(status=|files_changed:)")  # router trailer lines the checks drop


def _reply(body):
    """The reply text without the router trailer lines (status=, files_changed:). The migrated checks read this, so a
    trailer word such as 'file' or a filename in files_changed cannot pass a check on its own."""
    return "\n".join(ln for ln in body.splitlines() if not _TRAILER.match(ln))


def all_words(*words):
    """Predicate factory: True when every word is in the reply (case-insensitive)."""
    def check(body, scratch=None, expect=None):
        low = _reply(body).lower()
        return all(w in low for w in words)
    return check


def any_word(*words):
    """Predicate factory: True when at least one word is in the reply (case-insensitive)."""
    def check(body, scratch=None, expect=None):
        low = _reply(body).lower()
        return any(w in low for w in words)
    return check


def expect_file(body, scratch=None, expect=None):
    """True when the reply names the expected file path, with / or \\ as the separator."""
    if not expect:
        return False
    text = _reply(body)
    return expect in text or expect.replace("/", "\\") in text


def zerodiv_crash(body, scratch=None, expect=None):
    """True when the reply names a ZeroDivisionError (or division by zero) and the empty list or len as the cause."""
    low = _reply(body).lower()
    return ("zerodivision" in low or "division by zero" in low) and ("empty" in low or "len" in low)


def readme_ok(body, scratch=None, expect=None):
    """True when a README summary names MCP and a local runtime, in at most six sentences and 1200 characters."""
    a = _reply(body)
    low = a.lower()
    sentences = [s for s in re.split(r"[.!?](?=\s|$)", a) if s.strip()]
    return ("mcp" in low and any(w in low for w in ("local", "ollama", "router", "llm"))
            and len(sentences) <= 6 and len(a) <= 1200)


def tracker_numbers(body, scratch=None, expect=None):
    """True when the reply has a digit and one of task, status or plan."""
    low = _reply(body).lower()
    return any(c.isdigit() for c in low) and any(w in low for w in ("task", "status", "plan"))


CHECKS = {  # name -> predicate over (reply body, scratch folder, expected root file)
    "reply_ok": lambda body, scratch=None, expect=None: len(body) >= 20,
    "sql_injection_review": _sql_injection_review,
    "two_vulns": _two_vulns,
    "three_vulns": _three_vulns,
    "compare_functions": _compare_functions,
    "debug_crash": _debug_crash,
    "trace_root_cause": _trace_root_cause,
    "long_summary": _long_summary,
    "rename_done": _rename_done,
    "sandbox_tests": _sandbox_tests,
    # checks moved from the retired cases (scripts/bench_real.py)
    "designer_tools": any_word("penpot", "design", "file", "error"),
    "browser_ui_trace": all_words("synaptree", "trace"),
    "secret_leak": all_words("fake-key-7d41c9e0b2a6", "hunter2"),
    "list_seeded_files": any_word("calc.py", "stack.py"),
    "stack_methods": all_words("push", "pop"),
    "research_example": any_word("example domain", "documentation examples"),
    "expect_file": expect_file,
    "zerodiv_crash": zerodiv_crash,
    "readme_ok": readme_ok,
    "tracker_numbers": tracker_numbers,
}


def check_passes(name: str, body: str, scratch=None, expect: str = None) -> bool:
    """True when the reply body passes the named check. An unknown name raises KeyError, so a typo in a task table fails loudly."""
    if name not in CHECKS:
        raise KeyError(f"unknown bench check {name!r} (known: {sorted(CHECKS)})")
    return bool(CHECKS[name](body, scratch, expect))


def is_infra_tool_error(text: str) -> bool:
    """True when a tool reply is an error about the host or mount (missing folder, read-only, no permission, no
    such tool in the profile), not a model failure."""
    s = text.strip()
    return s.startswith("Error") and any(m in s for m in INFRA_TOOL_MARKERS)


# ---- synaptree infra gate (helpers moved from scripts/bench_real.py; behaviour unchanged) ----

def _docker(args, timeout=60):
    # Output goes to a temp file, not a pipe: after a timeout a pipe can stay blocked on Windows
    # (the Qwable hang sat in docker inspect for 88 min), so a killed docker call must not block us.
    with tempfile.TemporaryFile("w+", encoding="utf-8", errors="replace") as out:
        try:
            p = subprocess.Popen(["docker", *args], stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT)
        except Exception as e:  # noqa: BLE001
            return 1, str(e)
        try:
            rc = p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill()
            return 1, f"docker {args[0]} timed out after {timeout}s"
        out.seek(0)
        return rc, out.read()


def stale_mcp_containers(max_age=STALE_MCP_AGE, now=None):
    """Ids of docker-mcp stdio containers older than max_age: leaked by a gateway client that was cancelled or killed."""
    rc, out = _docker(["ps", "-q", "--filter", "label=docker-mcp=true"])
    ids = out.split() if rc == 0 else []
    if not ids:
        return []
    rc, out = _docker(["inspect", "-f", "{{.Id}} {{.Created}}", *ids])
    if rc != 0:
        return []
    now = now or datetime.now(timezone.utc)
    stale = []
    for line in out.splitlines():
        cid, _, created = line.partition(" ")
        try:
            made = datetime.fromisoformat(created.strip()[:19]).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if (now - made).total_seconds() > max_age:
            stale.append(cid)
    return stale


def sweep_stale_mcp(max_age=STALE_MCP_AGE):
    """Remove leaked gateway containers between repeats; returns how many were removed."""
    ids = stale_mcp_containers(max_age)
    if ids:
        _docker(["rm", "-f", *ids])
    return len(ids)


def container_state():
    """Running, ExitCode, OOMKilled, StartedAt, FinishedAt of the synaptree container.
    Running is False (with the inspect error) when the container is missing."""
    # A failed read is retried: one docker hiccup must not look like a stopped or restarted container.
    for attempt in range(3):
        rc, out = _docker(["inspect", "-f", "{{json .State}}", SYNAPTREE_CONTAINER])
        try:
            st = json.loads(out) if rc == 0 else None
        except ValueError:
            st = None
        if st or "No such" in out:
            break
        if attempt < 2:
            time.sleep(3)
    if not st:
        return {"Running": False, "error": out.strip()[:300]}
    return {k: st.get(k) for k in ("Running", "ExitCode", "OOMKilled", "StartedAt", "FinishedAt")}


def container_logs(since):
    """Last LOG_TAIL_LINES lines of the synaptree container logs since `since`, capped to LOG_CAP_BYTES."""
    _, out = _docker(["logs", "--since", since, SYNAPTREE_CONTAINER])
    tail = "\n".join(out.splitlines()[-LOG_TAIL_LINES:])
    return tail.encode("utf-8")[-LOG_CAP_BYTES:].decode("utf-8", "replace")


def synaptree_down(state, started_before=None) -> str:
    """'' when the synaptree container is running and, if started_before is given, still has that StartedAt.
    Otherwise a short reason for the infra record: not running (with exit code or inspect error), or restarted."""
    state = state or {}
    if not state.get("Running"):
        if state.get("error"):
            detail = state["error"]
        else:
            detail = f"exit code {state.get('ExitCode')}" + (", OOMKilled" if state.get("OOMKilled") else "")
        return f"{INFRA_ERROR}: {detail}"[:300]
    if started_before and state.get("StartedAt") != started_before:
        return f"{SYNAPTREE_CONTAINER} restarted during the run (StartedAt {started_before} -> {state.get('StartedAt')})"
    return ""


def tid_of(r):
    """The 10-hex task id from a leading "[xxxxxxxxxx]" reply prefix, or None."""
    m = re.match(r"\[([0-9a-f]{10})\]", r or "")
    return m.group(1) if m else None


def trail_of(r):
    """Step trail of the task that produced reply r; [] when there is no task id, no row, or the store fails."""
    tid = tid_of(r)
    if not tid:
        return []
    try:
        row = store.get(tid)
    except Exception:  # noqa: BLE001
        return []
    return (row or {}).get("trail") or []


def trail_tools(trail):
    """Names of the tools called, in order, from the trail's tool events."""
    return [e.get("name") for e in trail if e.get("kind") == "tool"]


def trail_conn_error(trail):
    """True when a tool_error event in the trail carries a connection failure (see CONN_MARKERS)."""
    return any(e.get("kind") == "tool_error" and any(m in e.get("error", "") for m in CONN_MARKERS) for e in trail)


def connection_closed(r, trail):
    """True when a failed reply says the connection closed, or the trail has a connection error.
    Only the exact phrase counts: a real answer that mentions a broken pipe or a stopped container does not count."""
    failed = re.search(r"\]\s*FAILED", r or "") is not None
    return (failed and "connection closed" in (r or "").lower()) or trail_conn_error(trail)


def tool_not_exposed(r, trail) -> bool:
    """True when the reply or a tool_error in the trail says a tool was not exposed by its profile (NOT_EXPOSED)."""
    if NOT_EXPOSED in (r or ""):
        return True
    return any(e.get("kind") == "tool_error" and NOT_EXPOSED in e.get("error", "") for e in trail)
