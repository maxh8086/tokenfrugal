"""Real-world benchmark cases: each task is verified by running the produced code or inspecting files,
not by trusting the model's "done" report. Used by scripts/bench.py (section `realworld`)."""
import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

from router import loop, preflight, server, store
from router.config import ROOT, SYNAPTREE_PROJECT, WORKSPACE, resolve_role

SCRATCH = ROOT / "bench" / "scratch"


def tool_paths(folder, workspace):
    """The same folder as the tools see it: /workspace (file, sandbox and test tools) and /src (ast-grep).
    Built from the real workspace root, so it holds whatever CC_WORKSPACE points at (repo root or its parent)."""
    rel = folder.relative_to(workspace).as_posix()  # ValueError if the folder is outside the workspace
    return f"/workspace/{rel}", f"/src/{rel}"


WS, AST_DIR = tool_paths(SCRATCH, WORKSPACE)
_repo_rel = ROOT.relative_to(WORKSPACE).as_posix()  # "." when the workspace is the repo root
README = f"/workspace/{_repo_rel}/README.md" if _repo_rel != "." else "/workspace/README.md"

# Per-repeat status and infrastructure gate.
#   infra   the synaptree container (native MCP server of the builder/reviewer/debugger/analyzer roles) was not
#           running before the repeat, or was down or restarted around a failed repeat. Not dispatched when down.
#           Also infra: a failed repeat with NotFoundError (HTTP 404, model missing), ComposeError or preflight.
#   timeout TimeoutError / APITimeoutError / LoopError timeouts / the per-case watchdog (CASE_TIMEOUT).
#   valid   everything else: the repeat ran (verified or not), or failed with a model/loop error such as
#           LoopError or CheckFailed, while the infrastructure was healthy.
#   partial a case whose repeats mix timeouts with other non-infra outcomes (infra repeats are ignored).
# A case is infra only when every repeat is infra; the infra repeats never count in valid_cases or mean_s_valid.
SYNAPTREE_CONTAINER = "synaptree-synaptree-1"
SYNAPTREE_CASES = {"write_function", "fix_bug", "write_tests", "rename_across_files",
                   "find_symbol", "review_sqli", "debug_trace", "role_analyzer",  # cases 1-7 and 9
                   "role_browser", "code_l6_callers_graph"}  # also the browser case, which needs the synaptree UI container
CASE_TIMEOUT = float(os.getenv("BENCH_CASE_TIMEOUT", "600"))  # seconds; per-repeat watchdog, a hit is scored as a failure (status timeout)
LOG_TAIL_LINES = 60
LOG_CAP_BYTES = 4096
INFRA_ERROR = "synaptree container not running"
TIMEOUT_MARKERS = ("TimeoutError", "APITimeoutError", "timed out", "watchdog")
INFRA_MARKERS = ("NotFoundError", "Error code: 404", "ComposeError", "preflight")  # missing model, compose/container start, preflight
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


STALE_MCP_AGE = 900.0  # seconds; a gateway container this old outlived any case (watchdog is at most ~330s)


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


def classify(ran, error, uses_synaptree, container_bad, tool_missing=False):
    """Status of one repeat (rules in the module comment above)."""
    if uses_synaptree and container_bad:
        return "infra"
    if not ran and any(m in error for m in INFRA_MARKERS):
        return "infra"  # missing model (HTTP 404), failed preflight or container start: the endpoint or harness, not the model
    if not ran and "unknown agent" in error:
        return "infra"  # router rejected the slug: harness/config fault, not the model
    if not ran and any(m in error for m in TIMEOUT_MARKERS):
        return "timeout"  # a LoopError or APITimeoutError timeout is the model's, even when it never called the required tool
    if tool_missing and "LoopError" not in error:  # the required tool was never offered: the server failed to start, not the model
        return "infra"
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

    def s_stack():
        _seed("stack.py", "class Stack:\n    def __init__(self):\n        self.items = []\n\n"
              "    def push(self, x):\n        self.items.append(x)\n\n"
              "    def pop(self):\n        return self.items.pop()\n\n"
              "    def __len__(self):\n        return len(self.items)\n")

    def s_tests():
        s_stack()
        (SCRATCH / "test_stack.py").unlink(missing_ok=True)

    def c_tests(_):
        f = SCRATCH / "test_stack.py"
        if not f.exists():
            return False, "test_stack.py not written (no write_file call produced it)"
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
        _seed("secret.py", "API_KEY = 'fake-key-7d41c9e0b2a6'" + chr(10) + "PASSWORD = 'hunter2'" + chr(10))

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
         f"Read {README} and summarize what the project does in 3 sentences.",
         _readme_ok),
        # one verified case per remaining role: analyzer, data, docs, security, designer, browser, tracker, research
        ("role_analyzer", "engineering-software-architect", _none,
         "Use search_graph to find where resolve_role is defined and give its file path.",
         _has("router/config.py", "router\\config.py")),
        ("role_data", "gis-analyst", s_files,
         f"List the files in {WS} with list_directory and name them.", _has("calc.py", "stack.py")),
        ("role_docs", "engineering-technical-writer", s_stack,
         f"Read {WS}/stack.py and describe its public methods in two sentences.", _all_has("push", "pop")),
        ("role_security", "security-auditor", s_secret,
         f"Read {WS}/secret.py and list any hard-coded secrets.", _all_has("fake-key-7d41c9e0b2a6", "hunter2")),
        ("role_designer", "design-ui-designer", _none,
         "Call high_level_overview and report what it returns, or the exact error.", _has("penpot", "design", "file", "error")),  # tool call enforced by REQUIRED_TOOLS
        ("role_browser", "testing-evidence-collector", _none,
         "Navigate to http://host.docker.internal:8787/ui/ with navigate_page, take a snapshot and report the page title.",
         _all_has("synaptree", "trace")),
        ("role_tracker", "project-management-project-shepherd", _none,
         "Call plan_status and report the numbers.", _tracker_ok),
        ("role_research", "support-docs-writer", _none,
         "Use crawl_markdown on https://example.com and quote the first sentence of the page verbatim.", _has("example domain", "documentation examples")),
    ]


def _groups(*groups):
    """Tolerant answer check: every group needs at least one of its words in the reply (case-insensitive)."""
    def check(a):
        low = a.lower()
        return (all(any(w in low for w in g) for g in groups), a[:100].replace("\n", " "))
    return check


def hard_cases():
    """Opt-in harder THINKER suite (BENCH_SUITE=hard): multi-step analysis questions whose answer text is checked
    with tolerant word groups. Seed files live in SCRATCH. Same tuple shape as cases(); none need the synaptree container."""
    def s_multifile():
        _seed("money.py", "def to_cents(amount):\n    return int(amount * 100)\n")
        _seed("ledger.py", "from money import to_cents\n\n\nclass Ledger:\n    def __init__(self):\n"
              "        self.cents = 0\n\n    def add(self, amount):\n        self.cents += to_cents(amount)\n\n"
              "    def total(self):\n        return self.cents / 100\n")
        _seed("report.py", "from ledger import Ledger\n\n\ndef invoice(items):\n    led = Ledger()\n"
              "    for x in items:\n        led.add(x)\n    return f'{led.total():.2f}'\n")

    def c_multifile(a):
        return _groups(("to_cents", "money.py"), ("round", "float", "truncat", "floor"))(a)

    def s_vulns():
        _seed("api.py", "import subprocess\n\n\ndef find_user(conn, name):\n"
              "    return conn.execute(\"SELECT * FROM users WHERE name = '\" + name + \"'\").fetchall()\n\n\n"
              "def backup(path):\n    subprocess.call('tar -czf /tmp/b.tgz ' + path, shell=True)\n")

    def c_vulns(a):
        return _groups(("sql", "sqli"), ("command", "shell", "os command"))(a)

    def s_trace():
        _seed("trace_cfg.py", "CONFIG = {'retries': '3'}\n\n\ndef load_retries(cfg):\n"
              "    return cfg['retries'] + 1\n\n\ndef run(cfg):\n    n = load_retries(cfg)\n    return n * 2\n\n\n"
              "print(run(CONFIG))\n")

    def c_trace(a):
        return _groups(("typeerror", "type error"), ("string", "str", "text"))(a)

    def s_summary():
        filler = " Routine maintenance notes were recorded for the week and nothing else changed."
        _seed("notes.txt", "Weekly engineering notes.\n" + "\n".join(
            f"Item {i}: routine check {i} passed.{filler}" for i in range(1, 9)) + "\n"
            "Key decisions: the cache now runs on Redis. The request timeout went from 5 seconds to 12 seconds. "
            "Retries use exponential backoff with jitter. The legacy admin page was removed.\n")

    def c_summary(a):
        body = re.sub(r"(?m)(?:(?<=\s)|^)\d+[.)](?=\s)|^\s*[-*]\s+", "", a)  # list markers are not sentence ends
        sentences = [s for s in re.split(r"[.!?](?=\s|$)", body) if s.strip()]
        ok, note = _groups(("redis",), ("12", "twelve"), ("backoff", "back-off", "back off"), ("admin",))(a)
        return (ok and len(sentences) <= 5 and len(a) <= 900, note)

    def s_compare():
        _seed("dedupe.py", "def dedupe_a(xs):\n    out = []\n    for x in xs:\n        if x not in out:\n"
              "            out.append(x)\n    return out\n\n\ndef dedupe_b(xs):\n    return list(set(xs))\n")

    def c_compare(a):
        return _groups(("order", "preserv"), ("set", "unordered", "hash"),
                       ("quadratic", "n^2", "n²", "o(n^2)", "slower"))(a)

    return [
        ("hard_multifile_bug", "engineering-sre", s_multifile,
         f"{WS}/ledger.py, {WS}/money.py and {WS}/report.py: invoice(['19.99', ...]) gives totals that are a cent low. "
         "Trace the calls across the three files, name the root cause and the file it is in, and say how to fix it.",
         c_multifile),
        ("hard_two_vulns", "testing-code-reviewer", s_vulns,
         f"Review {WS}/api.py for security problems. Name every distinct vulnerability class in it, with the line that has it.",
         c_vulns),
        ("hard_ambiguous_trace", "engineering-sre", s_trace,
         f"Running {WS}/trace_cfg.py crashes. Read it, name the exception type, and give the real root cause, "
         "not just the line that raised it.", c_trace),
        ("hard_long_summary", "engineering-technical-writer", s_summary,
         f"Read {WS}/notes.txt and summarize the key decisions in at most 5 sentences. Keep the specific values.",
         c_summary),
        ("hard_compare_functions", "testing-code-reviewer", s_compare,
         f"In {WS}/dedupe.py compare dedupe_a and dedupe_b: say what differs in output and in complexity.",
         c_compare),
    ]


def _sandbox_tests(files):
    """Re-write the given test files (so a model cannot pass by editing them), then run unittest discovery in the
    same network-less python container the sandbox MCP tool uses. Returns (passed, tail)."""
    for name, text in files.items():
        _seed(name, text)
    argv = ["docker", "run", "--rm", "--network", "none", "--cpus", "2", "--memory", "1g",
            "-e", "PYTHONDONTWRITEBYTECODE=1", "-v", f"{SCRATCH}:/work:ro", "-w", "/work",
            os.getenv("TOKENFRUGAL_SANDBOX_IMAGE", "python:3.13-slim"), "python", "-m", "unittest", "discover", "-s", ".", "-q"]
    env = {**os.environ, "MSYS_NO_PATHCONV": "1"}
    p = subprocess.run(argv, capture_output=True, text=True, timeout=90, env=env)
    return p.returncode == 0, (p.stdout + p.stderr).strip()[-140:].replace("\n", " ")


def coding_cases():
    """Opt-in CODING suite (BENCH_SUITE=coding): levels L1-L6, each dispatched to its own role (coding-l1..l6, own
    Docker MCP profile and at most 6 tools). Each case seeds a project with failing unittests; the model must fix the
    code, and the check re-writes the tests and runs them in the sandbox container."""
    def case(cid, agent, files, tests, task):
        def seed():
            for n, t in {**files, **tests}.items():
                _seed(n, t)

        def check(_a):
            return _sandbox_tests(tests)
        return (cid, agent, seed, task + f" Folder: {WS}. Do not edit the test files; run the tests with run_tests "
                f"(folder {WS}) until they pass.", check)

    return [
        case("code_l1_clamp", "coding-l1",
             {"util.py": "def clamp(x, lo, hi):\n    if x < lo:\n        return hi\n    if x > hi:\n        return lo\n    return x\n"},
             {"test_util.py": "import unittest\nfrom util import clamp\n\n\nclass T(unittest.TestCase):\n"
              "    def test_low(self):\n        self.assertEqual(clamp(-5, 0, 10), 0)\n"
              "    def test_high(self):\n        self.assertEqual(clamp(50, 0, 10), 10)\n"
              "    def test_mid(self):\n        self.assertEqual(clamp(5, 0, 10), 5)\n"},
             "Fix the bug in clamp() in util.py."),
        case("code_l2_slugify", "coding-l2",
             {"text.py": "def slugify(s):\n    raise NotImplementedError\n"},
             {"test_text.py": "import unittest\nfrom text import slugify\n\n\nclass T(unittest.TestCase):\n"
              "    def test_basic(self):\n        self.assertEqual(slugify('Hello World'), 'hello-world')\n"
              "    def test_punct(self):\n        self.assertEqual(slugify('  A, b & c! '), 'a-b-c')\n"
              "    def test_empty(self):\n        self.assertEqual(slugify('***'), '')\n"},
             "Implement slugify(s) in text.py: lowercase, runs of non-alphanumerics become one '-', no leading or trailing '-'."),
        case("code_l3_tax", "coding-l3",
             {"pricing.py": "def line_total(price, qty):\n    return price * qty\n",
              "cart.py": "from pricing import line_total\n\n\ndef cart_total(items):\n"
                         "    return sum(line_total(p, q) for p, q in items)\n"},
             {"test_cart.py": "import unittest\nfrom cart import cart_total\nfrom pricing import line_total\n\n\n"
              "class T(unittest.TestCase):\n"
              "    def test_line_default(self):\n        self.assertEqual(line_total(10, 2), 20)\n"
              "    def test_line_tax(self):\n        self.assertAlmostEqual(line_total(10, 2, tax=0.1), 22.0)\n"
              "    def test_cart_tax(self):\n        self.assertAlmostEqual(cart_total([(10, 2), (5, 1)], tax=0.2), 30.0)\n"
              "    def test_cart_default(self):\n        self.assertEqual(cart_total([(10, 2), (5, 1)]), 25)\n"},
             "Add an optional tax rate (default 0) to line_total in pricing.py and cart_total in cart.py, passing it through."),
        case("code_l4_rename", "coding-l4",
             {"calc.py": "def calc_avg(xs):\n    return sum(xs) / len(xs)\n",
              "report.py": "from calc import calc_avg\n\n\ndef summary(xs):\n    return f'avg={calc_avg(xs):.1f}'\n",
              "cli.py": "import calc\n\n\ndef run(xs):\n    return calc.calc_avg(xs)\n"},
             {"test_rename.py": "import unittest\nimport calc, cli, report\n\n\nclass T(unittest.TestCase):\n"
              "    def test_new_name(self):\n        self.assertEqual(calc.mean([1, 2, 3]), 2)\n"
              "    def test_old_gone(self):\n        self.assertFalse(hasattr(calc, 'calc_avg'))\n"
              "    def test_cli(self):\n        self.assertEqual(cli.run([2, 4]), 3)\n"
              "    def test_report(self):\n        self.assertEqual(report.summary([2, 4]), 'avg=3.0')\n"},
             "Rename calc_avg to mean everywhere (definition and every caller in all files). "
             f"The ast-grep tool sees this same folder as {AST_DIR} (pass that as its dir)."),
        case("code_l5_median", "coding-l5",
             {"stats.py": "def median(xs):\n    xs = sorted(xs)\n    return xs[len(xs) // 2]\n\n\n"
                          "def spread(xs):\n    return max(xs) - min(xs)\n"},
             {"test_stats.py": "import unittest\nfrom stats import median, spread\n\n\nclass T(unittest.TestCase):\n"
              "    def test_odd(self):\n        self.assertEqual(median([3, 1, 2]), 2)\n"
              "    def test_even(self):\n        self.assertEqual(median([4, 1, 3, 2]), 2.5)\n"
              "    def test_one(self):\n        self.assertEqual(median([7]), 7)\n"
              "    def test_spread(self):\n        self.assertEqual(spread([1, 9, 4]), 8)\n"},
             "The tests in test_stats.py fail. Run them, read the failure, find the cause and fix the code."),
        case("code_l6_callers", "coding-l6",
             {"store.py": "def save(key, value):\n    return {key: value}\n",
              "a.py": "from store import save\n\n\ndef put_a(v):\n    return save('a', v)\n",
              "b.py": "from store import save\n\n\ndef put_b(v):\n    return save('b', v)\n"},
             {"test_store.py": "import unittest\nimport a, b\nfrom store import save\n\n\nclass T(unittest.TestCase):\n"
              "    def test_save_ns(self):\n        self.assertEqual(save('k', 1, ns='x'), {'x:k': 1})\n"
              "    def test_a(self):\n        self.assertEqual(a.put_a(1), {'a:a': 1})\n"
              "    def test_b(self):\n        self.assertEqual(b.put_b(2), {'b:b': 2})\n"},
             "Add a required namespace argument ns to save() in store.py (key becomes 'ns:key'), "
             "then update every caller (read the files in the folder to find them) to pass ns='a' in a.py and ns='b' in b.py."),
        case("code_l6_callers_graph", "coding-l6",
             {"store.py": "def save(key, value):\n    return {key: value}\n",
              "a.py": "from store import save\n\n\ndef put_a(v):\n    return save('a', v)\n",
              "b.py": "from store import save\n\n\ndef put_b(v):\n    return save('b', v)\n"},
             {"test_store.py": "import unittest\nimport a, b\nfrom store import save\n\n\nclass T(unittest.TestCase):\n"
              "    def test_save_ns(self):\n        self.assertEqual(save('k', 1, ns='x'), {'x:k': 1})\n"
              "    def test_a(self):\n        self.assertEqual(a.put_a(1), {'a:a': 1})\n"
              "    def test_b(self):\n        self.assertEqual(b.put_b(2), {'b:b': 2})\n"},
             "Add a required namespace argument ns to save() in store.py (key becomes 'ns:key'), "
             "then update every caller (find them with the code graph) to pass ns='a' in a.py and ns='b' in b.py."),
    ]


def active_cases():
    """The case list this run uses: hard_cases() for BENCH_SUITE=hard, coding_cases() for coding, else cases()."""
    suite = os.getenv("BENCH_SUITE", "").strip().lower()
    return hard_cases() if suite == "hard" else coding_cases() if suite == "coding" else cases()


WATCHDOG_GRACE = 30.0  # the router's own task timeout fires first so a timeout is classified by the router


def case_limits(agent):
    """(role timeout_s or None, watchdog seconds): a role's frozen timeout_s replaces BENCH_CASE_TIMEOUT."""
    t = resolve_role(agent, server.CFG).get("timeout_s")
    return (float(t), float(t) + WATCHDOG_GRACE) if t else (None, CASE_TIMEOUT)


def path_preflight():
    """Stop before any case if the sandbox would not resolve the scratch folder to the host folder the cases seed."""
    err = preflight.mount_error(SCRATCH, WS)
    if err:
        raise RuntimeError(err)


async def run(n, timed, ok, failure_mode, stats):
    res = {}
    pick = [c for c in os.getenv("BENCH_CASES", "").split(",") if c]  # e.g. BENCH_CASES=write_tests,role_browser
    for cid, agent, setup, task, check in active_cases():
        if pick and cid not in pick:
            continue
        uses = cid in SYNAPTREE_CASES
        runs = []
        for i in range(n):
            sweep_stale_mcp()  # a cancelled or killed gateway leaves its stdio containers running
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
            # checked before every repeat, not once per run: a wrong mount or a bad task fails here, before any model time
            err = preflight.mount_error(SCRATCH, WS) or preflight.task_error(agent, task, server.CFG, WORKSPACE)
            if err:
                raise RuntimeError(f"preflight refused {cid} repeat {i + 1}: {err}")
            setup()
            role_t, watchdog = case_limits(agent)
            dt, r = await timed(asyncio.wait_for(server.dispatch_task(agent, task), watchdog))
            if not ok(r) and "step_timeout" in r:  # the router's rule: a timed-out task gets one resume_task before scoring
                tid = r[1:r.find("]")]
                dt2, r = await timed(asyncio.wait_for(server.resume_task(tid), watchdog))
                dt += dt2
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
            tool_missing = bool(req) and not tools  # no tool call at all where one was required: the server offered none
            status = classify(ran, r, uses, container_bad, tool_missing)
            m = re.match(r"\[([^\]]+)\]", r)
            u = loop.DONE.get(m.group(1), {}) if m else {}
            rec = {"run": i + 1, "start": start, "end": end, "s": round(dt, 1), "ok": ran, "verified": bool(good),
                   "status": status, "dispatched": True, "error": r, "note": str(note)[:140],
                   "peak": u.get("peak", 0), "input": u.get("input", 0), "output": u.get("output", 0),
                   "trail_tools": tools, "timeout_s": role_t if role_t else CASE_TIMEOUT}
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
                    "timeout_s": case_limits(agent)[0] or CASE_TIMEOUT,
                    "notes": sorted({x["note"] for x in runs if not x["verified"]})[:3], "runs": runs}
    return res
