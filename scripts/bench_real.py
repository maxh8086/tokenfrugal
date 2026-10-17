"""Real-world benchmark cases: each task is verified by running the produced code or inspecting files,
not by trusting the model's "done" report. Used by scripts/bench.py (section `realworld`)."""
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from router import loop, server, store
from router.config import ROOT, SYNAPTREE_PROJECT

SCRATCH = ROOT / "bench" / "scratch"
WS = f"/workspace/{SYNAPTREE_PROJECT}/bench/scratch"

# Per-repeat status and infrastructure gate.
#   infra   the synaptree container (native MCP server of the builder/reviewer/debugger/analyzer roles) was not
#           running before the repeat, or was down or restarted around a failed repeat. Not dispatched when down.
#   timeout TimeoutError / APITimeoutError / the per-case watchdog (CASE_TIMEOUT).
#   valid   everything else: the repeat ran (verified or not), or failed with a model/loop error such as
#           LoopError or CheckFailed, while the infrastructure was healthy.
#   partial a case whose repeats mix timeouts with other non-infra outcomes (infra repeats are ignored).
# A case is infra only when every repeat is infra; the infra repeats never count in valid_cases or mean_s_valid.
SYNAPTREE_CONTAINER = "synaptree-synaptree-1"
SYNAPTREE_CASES = {"write_function", "fix_bug", "write_tests", "rename_across_files",
                   "find_symbol", "review_sqli", "debug_trace", "role_analyzer",  # cases 1-7 and 9
                   "role_browser"}  # also the browser case, which needs the synaptree UI container
CASE_TIMEOUT = float(os.getenv("BENCH_CASE_TIMEOUT", "600"))  # seconds; per-repeat watchdog, a hit is scored as a failure (status timeout)
LOG_TAIL_LINES = 60
LOG_CAP_BYTES = 4096
INFRA_ERROR = "synaptree container not running"
TIMEOUT_MARKERS = ("TimeoutError", "APITimeoutError", "timed out", "watchdog")
CONN_MARKERS = ("Connection closed",)
# tool a case must have called (per the step trail) before its reply can count as verified; None = no requirement
REQUIRED_TOOLS = {"role_tracker": "plan_status", "role_designer": "high_level_overview", "role_browser": "navigate_page"}


def _py(code):
    p = subprocess.run([sys.executable, "-c", code], cwd=SCRATCH, capture_output=True, text=True, timeout=60)
    return p.returncode == 0, (p.stdout + p.stderr)[-160:]


def _seed(name, text):
    (SCRATCH / name).write_text(text, encoding="utf-8")


def _clean_scratch():
    """Delete every file and subdirectory directly under SCRATCH; SCRATCH itself is kept.
    Directory symlinks are unlinked, never followed, so nothing outside SCRATCH is removed."""
    for p in SCRATCH.iterdir():
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()


def _has(*words):
    return lambda a: (any(w in a.lower() for w in words), a[:100].replace("\n", " "))


def strip_tid(r):
    return re.sub(r"^\[[0-9a-f]{10}\]\s*", "", r)


def tid_of(r):
    """The 10-hex task id from a leading "[xxxxxxxxxx]" reply prefix, or None."""
    m = re.match(r"\[([0-9a-f]{10})\]", r)
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


def _all_has(*words):
    return lambda a: (all(w in a.lower() for w in words), a[:100].replace("\n", " "))


def _tracker_ok(a):
    low = a.lower()
    return (any(c.isdigit() for c in low) and any(w in low for w in ("task", "status", "plan")),
            a[:100].replace("\n", " "))


def _debug_ok(a):
    low = a.lower()
    return (("zerodivision" in low or "division by zero" in low) and ("empty" in low or "len" in low),
            a[:100].replace("\n", " "))


def _readme_ok(a):
    low = a.lower()
    sentences = [s for s in re.split(r"[.!?](?=\s|$)", a) if s.strip()]
    good = ("mcp" in low and any(w in low for w in ("local", "ollama", "router", "llm"))
            and len(sentences) <= 6 and len(a) <= 1200)
    return (good, a[:100].replace("\n", " "))


def _none():
    return None


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _docker(args):
    try:
        p = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60)
        return p.returncode, p.stdout + p.stderr
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def container_state():
    """Running, ExitCode, OOMKilled, StartedAt, FinishedAt of the synaptree container.
    Running is False (with the inspect error) when the container is missing."""
    rc, out = _docker(["inspect", "-f", "{{json .State}}", SYNAPTREE_CONTAINER])
    try:
        st = json.loads(out) if rc == 0 else None
    except ValueError:
        st = None
    if not st:
        return {"Running": False, "error": out.strip()[:300]}
    return {k: st.get(k) for k in ("Running", "ExitCode", "OOMKilled", "StartedAt", "FinishedAt")}


def container_logs(since):
    """Last LOG_TAIL_LINES lines of the synaptree container logs since `since`, capped to LOG_CAP_BYTES."""
    _, out = _docker(["logs", "--since", since, SYNAPTREE_CONTAINER])
    tail = "\n".join(out.splitlines()[-LOG_TAIL_LINES:])
    return tail.encode("utf-8")[-LOG_CAP_BYTES:].decode("utf-8", "replace")


def classify(ran, error, uses_synaptree, container_bad):
    """Status of one repeat (rules in the module comment above)."""
    if uses_synaptree and container_bad:
        return "infra"
    if not ran and "unknown agent" in error:
        return "infra"  # router rejected the slug: harness/config fault, not the model
    if not ran and any(m in error for m in TIMEOUT_MARKERS):
        return "timeout"
    return "valid"


def case_status(statuses):
    """Status of a case from its repeats: infra repeats are dropped; all infra -> infra; all valid -> valid;
    all timeout -> timeout; any other mix of non-infra outcomes -> partial."""
    live = [s for s in statuses if s != "infra"]
    if not live:
        return "infra"
    if all(s == "valid" for s in live):
        return "valid"
    if all(s == "timeout" for s in live):
        return "timeout"
    return "partial"


def cases():
    def s_write():
        (SCRATCH / "slug.py").unlink(missing_ok=True)

    def c_write(_):
        return _py("from slug import slugify as s\nassert s('Hello, World!')=='hello-world'\n"
                   "assert s('  a  b ')=='a-b'\nassert s('')==''")

    def s_fix():
        _seed("calc.py", "def add(a, b):\n    return a - b\n\n\ndef mul(a, b):\n    return a * b\n")

    def c_fix(_):
        return _py("from calc import add, mul\nassert add(2,3)==5 and mul(2,3)==6")

    def s_tests():
        _seed("stack.py", "class Stack:\n    def __init__(self):\n        self.items = []\n\n"
              "    def push(self, x):\n        self.items.append(x)\n\n"
              "    def pop(self):\n        return self.items.pop()\n\n"
              "    def __len__(self):\n        return len(self.items)\n")
        (SCRATCH / "test_stack.py").unlink(missing_ok=True)

    def c_tests(_):
        f = SCRATCH / "test_stack.py"
        if not f.exists():
            return False, "no test file written"
        p = subprocess.run([sys.executable, "-m", "unittest", "test_stack", "-q"], cwd=SCRATCH,
                           capture_output=True, text=True, timeout=60)
        text = f.read_text(encoding="utf-8")
        n = len(re.findall(r"^\s*def test_", text, re.M))
        present = "import stack" in text or "from stack import" in text
        return p.returncode == 0 and n >= 3 and present, f"rc={p.returncode} tests={n} {p.stderr[-100:]}"

    def s_rename():
        _seed("a_mod.py", "def old_name(x):\n    return x + 1\n")
        _seed("b_mod.py", "from a_mod import old_name\n\nprint(old_name(1))\n")

    def c_rename(_):
        a = (SCRATCH / "a_mod.py").read_text(encoding="utf-8")
        b = (SCRATCH / "b_mod.py").read_text(encoding="utf-8")
        good = "old_name" not in a + b and "new_name" in a and "new_name" in b and _py("import b_mod")[0]
        return good, (a + b)[:80].replace("\n", " ")

    def s_review():
        _seed("db.py", "def get_user(conn, name):\n    return conn.execute(\"SELECT * FROM users WHERE name = '\" + name + \"'\").fetchall()\n")

    def s_debug():
        _seed("bug.py", "def avg(xs):\n    return sum(xs) / len(xs)\n\nprint(avg([]))\n")

    def s_secret():
        _seed("secret.py", "API_KEY = 'AKIAFAKEFAKEFAKE1234'" + chr(10) + "PASSWORD = 'hunter2'" + chr(10))

    def s_files():
        _seed("calc.py", "x = 1" + chr(10))
        _seed("stack.py", "x = 1" + chr(10))

    return [
        ("write_function", "engineering-backend-architect", s_write,
         f"Create {WS}/slug.py with slugify(s): lowercase, strip, collapse runs of non-alphanumerics into a single '-', "
         "no leading or trailing '-'. Use write_file.", c_write),
        ("fix_bug", "engineering-backend-architect", s_fix,
         f"{WS}/calc.py has a bug: add() subtracts. Fix it in place with edit_file.", c_fix),
        ("write_tests", "engineering-backend-architect", s_tests,
         f"Read {WS}/stack.py and write {WS}/test_stack.py: unittest tests for push, pop and len (at least 3 tests). Use write_file.", c_tests),
        ("rename_across_files", "engineering-backend-architect", s_rename,
         f"Rename old_name to new_name in {WS}/a_mod.py and {WS}/b_mod.py (definition, import and call).", c_rename),
        ("find_symbol", "engineering-backend-architect", _none,
         "Use search_graph to find where resolve_role is defined and give its file path.",
         _has("router/config.py", "router\\config.py")),
        ("review_sqli", "testing-code-reviewer", s_review,
         f"Review {WS}/db.py for security problems. Name the vulnerability class.",
         _has("sql injection", "sqli", "injection")),
        ("debug_trace", "engineering-sre", s_debug,
         f"{WS}/bug.py crashes. Read it and name the exception and root cause.",
         _debug_ok),
        ("summarize_readme", "engineering-technical-writer", _none,
         f"Read /workspace/{SYNAPTREE_PROJECT}/README.md and summarize what the project does in 3 sentences.",
         _readme_ok),
        # one verified case per remaining role: analyzer, data, docs, security, designer, browser, tracker, research
        ("role_analyzer", "engineering-software-architect", _none,
         "Use search_graph to find where resolve_role is defined and give its file path.",
         _has("router/config.py", "router\\config.py")),
        ("role_data", "gis-analyst", s_files,
         f"List the files in {WS} with list_directory and name them.", _has("calc.py", "stack.py")),
        ("role_docs", "engineering-technical-writer", s_tests,
         f"Read {WS}/stack.py and describe its public methods in two sentences.", _all_has("push", "pop")),
        ("role_security", "security-auditor", s_secret,
         f"Read {WS}/secret.py and list any hard-coded secrets.", _all_has("akiafakefakefake1234", "hunter2")),
        ("role_designer", "design-ui-designer", _none,
         "Call high_level_overview and report what it returns, or the exact error.", _has("penpot", "design", "file", "error")),  # tool call enforced by REQUIRED_TOOLS
        ("role_browser", "testing-evidence-collector", _none,
         "Navigate to http://host.docker.internal:8787/ui/ with navigate_page, take a snapshot and report the page title.",
         _all_has("synaptree", "trace")),
        ("role_tracker", "project-management-project-shepherd", _none,
         "Call plan_status and report the numbers.", _tracker_ok),
        ("role_research", "support-docs-writer", _none,
         "Use crawl_markdown on https://example.com and report the page heading.", _has("example domain", "documentation examples")),
    ]


async def run(n, timed, ok, failure_mode, stats):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    res = {}
    pick = [c for c in os.getenv("BENCH_CASES", "").split(",") if c]  # e.g. BENCH_CASES=write_tests,role_browser
    for cid, agent, setup, task, check in cases():
        if pick and cid not in pick:
            continue
        uses = cid in SYNAPTREE_CASES
        runs = []
        for i in range(n):
            _clean_scratch()  # no leftovers from the previous repeat or case; the seed below runs after this
            start = _now()
            pre = container_state() if uses else None
            if pre is not None and not pre.get("Running"):
                # infra gate: the case is not dispatched at all while the synaptree container is down
                runs.append({"run": i + 1, "start": start, "end": _now(), "s": 0.0, "ok": False, "verified": False,
                             "status": "infra", "dispatched": False, "error": INFRA_ERROR, "note": INFRA_ERROR,
                             "peak": 0, "input": 0, "output": 0,
                             "container_state": pre, "container_logs": container_logs(start)})
                print(f"  realworld/{cid} #{i + 1} infra: {INFRA_ERROR}", flush=True)
                continue
            setup()
            dt, r = await timed(asyncio.wait_for(server.dispatch_task(agent, task), CASE_TIMEOUT))
            end = _now()
            ran = ok(r)
            if not ran:
                good, note = False, failure_mode(r)
            else:
                try:
                    good, note = check(strip_tid(r))
                except Exception as e:  # noqa: BLE001 - a check that raises fails this repeat only, not the whole section
                    good, note = False, f"check raised {type(e).__name__}: {e}"
            if ran and not good:
                # diagnostic: show what the shared scratch folder held at verify time (missing or overwritten files)
                listing = sorted(p.name for p in SCRATCH.iterdir()) if SCRATCH.exists() else ["<no scratch dir>"]
                note = f"{note} | scratch={listing}"
            trail = trail_of(r)
            tools = trail_tools(trail)
            req = REQUIRED_TOOLS.get(cid)
            if good and req and trail and req not in tools:  # reply passed the check but the required tool was never called
                good, note = False, f"tool {req} not called"
            state = None
            container_bad = uses and trail_conn_error(trail)  # a connection error in the trail is infra even when the reply is an answer
            if not ran or container_bad:  # capture the container after a failed repeat; a synaptree case is infra if it went down or restarted
                state = container_state()
                container_bad = container_bad or (uses and (not state.get("Running") or state.get("StartedAt") != pre.get("StartedAt")))
            status = classify(ran, r, uses, container_bad)
            m = re.match(r"\[([^\]]+)\]", r)
            u = loop.DONE.get(m.group(1), {}) if m else {}
            rec = {"run": i + 1, "start": start, "end": end, "s": round(dt, 1), "ok": ran, "verified": bool(good),
                   "status": status, "dispatched": True, "error": r, "note": str(note)[:140],
                   "peak": u.get("peak", 0), "input": u.get("input", 0), "output": u.get("output", 0),
                   "trail_tools": tools}
            if state is not None:
                rec["container_state"] = state
                rec["container_logs"] = container_logs(start)
            runs.append(rec)
            print(f"  realworld/{cid} #{i + 1} {dt:5.1f}s {status} ran={ran} verified={bool(good)} {'' if good else note}"[:200],
                  flush=True)
        live = [x for x in runs if x["status"] != "infra"]
        nl = len(live)
        live_s = [x["s"] for x in live]
        res[cid] = {"verified": f"{sum(x['verified'] for x in live)}/{nl}", "ran": f"{sum(x['ok'] for x in live)}/{nl}",
                    "status": case_status([x["status"] for x in runs]),
                    "infra_runs": sum(x["status"] == "infra" for x in runs),
                    "s": stats(live_s) or None, "peak": max(x["peak"] for x in runs),
                    "input": round(sum(x["input"] for x in live) / max(nl, 1)),
                    "output": round(sum(x["output"] for x in live) / max(nl, 1)),
                    "notes": sorted({x["note"] for x in runs if not x["verified"]})[:3], "runs": runs}
    return res
