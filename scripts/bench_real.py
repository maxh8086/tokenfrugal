"""Real-world benchmark cases: each task is verified by running the produced code or inspecting files,
not by trusting the model's "done" report. Used by scripts/bench.py (section `realworld`)."""
import os
import subprocess
import sys

from gateway import server
from gateway.config import ROOT, SYNAPTREE_PROJECT

SCRATCH = ROOT / "bench" / "scratch"
WS = f"/workspace/{SYNAPTREE_PROJECT}/bench/scratch"


def _py(code):
    p = subprocess.run([sys.executable, "-c", code], cwd=SCRATCH, capture_output=True, text=True, timeout=60)
    return p.returncode == 0, (p.stdout + p.stderr)[-160:]


def _seed(name, text):
    (SCRATCH / name).write_text(text, encoding="utf-8")


def _has(*words):
    return lambda a: (any(w in a.lower() for w in words), a[:100].replace("\n", " "))


def _none():
    return None


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
        n = f.read_text(encoding="utf-8").count("def test_")
        return p.returncode == 0 and n >= 3, f"rc={p.returncode} tests={n} {p.stderr[-100:]}"

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
        for n in ("calc.py", "stack.py"):
            if not (SCRATCH / n).exists():
                _seed(n, "x = 1" + chr(10))

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
         _has("gateway/config.py", "gateway\\config.py")),
        ("review_sqli", "testing-code-reviewer", s_review,
         f"Review {WS}/db.py for security problems. Name the vulnerability class.",
         _has("sql injection", "sqli", "injection")),
        ("debug_trace", "engineering-sre", s_debug,
         f"{WS}/bug.py crashes. Read it and name the exception and root cause.",
         _has("zerodivision", "division by zero", "empty")),
        ("summarize_readme", "support-docs-writer", _none,
         f"Read /workspace/{SYNAPTREE_PROJECT}/README.md and summarize what the project does in 3 sentences.",
         _has("mcp", "local")),
        # one verified case per remaining role: analyzer, data, docs, security, designer, browser, tracker, research
        ("role_analyzer", "finance-analyst", _none,
         "Use search_graph to find where resolve_role is defined and give its file path.",
         _has("gateway/config.py", "gateway\\config.py")),
        ("role_data", "gis-analyst", s_files,
         f"List the files in {WS} with list_directory and name them.", _has("calc.py", "stack.py")),
        ("role_docs", "engineering-technical-writer", s_tests,
         f"Read {WS}/stack.py and describe its public methods in two sentences.", _has("push")),
        ("role_security", "security-auditor", s_secret,
         f"Read {WS}/secret.py and list any hard-coded secrets.", _has("api_key", "password", "hard-coded", "hardcoded")),
        ("role_designer", "design-ui-designer", _none,
         "Call high_level_overview and report what it returns, or the exact error.", _has("penpot", "design", "file", "error")),
        ("role_browser", "testing-evidence-collector", _none,
         "Navigate to https://example.com, take a snapshot and report the page heading.", _has("example domain", "documentation examples")),
        ("role_tracker", "project-management-project-shepherd", _none,
         "Call plan_status and report the numbers.", _has("task", "plan", "done", "open", "0")),
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
        runs = []
        for i in range(n):
            setup()
            dt, r = await timed(server.dispatch_task(agent, task))
            good, note = (False, failure_mode(r)) if not ok(r) else check(r)
            runs.append({"s": round(dt, 1), "ok": ok(r), "verified": bool(good), "note": str(note)[:140]})
            print(f"  realworld/{cid} #{i + 1} {dt:5.1f}s ran={ok(r)} verified={bool(good)} {'' if good else note}"[:200],
                  flush=True)
        res[cid] = {"verified": f"{sum(x['verified'] for x in runs)}/{n}", "ran": f"{sum(x['ok'] for x in runs)}/{n}",
                    "s": stats([x["s"] for x in runs]), "notes": sorted({x["note"] for x in runs if not x["verified"]})[:3]}
    return res
