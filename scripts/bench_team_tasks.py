# Teams left out of the model benchmark (scoreboard, team tasks, report). mediahouse has its own suite.
BENCH_EXCLUDED_TEAMS = {"mediahouse"}

TEAM_TASKS = {
    "designer": [("design-ui-designer", "Say what design tools you have.", "reply_ok"),
                 ("design-ui-designer", "Call high_level_overview and report what it returns, or the exact error.", "designer_tools")],
    "browser": [("testing-evidence-collector", "Use navigate_page to open https://example.com, then say in one sentence what the page is about. Read-only: do not submit forms or change state.", "reply_ok"),
                ("testing-evidence-collector", "Navigate to http://host.docker.internal:8787/ui/ with navigate_page, take a snapshot and report the page title.", "browser_ui_trace")],
    "builder": [("engineering-backend-architect", "Use search_graph to find the symbol named summarize and report its file path.", "reply_ok"),
                ("engineering-backend-architect", "Write /workspace/bench/scratch/slug.py with a function slugify(text) that returns the lowercase words of text joined with hyphens. Make /workspace/bench/scratch/test_slug.py pass.", "sandbox_tests"),
                ("engineering-backend-architect", "Fix the bug in /workspace/bench/scratch/stats.py: mean() divides by len plus one but must divide by len. Make /workspace/bench/scratch/test_stats.py pass without editing the tests.", "sandbox_tests"),
                ("engineering-backend-architect", "Write unittest tests with at least two test methods for the functions in /workspace/bench/scratch/calc.py, in a new file /workspace/bench/scratch/test_calc.py.", "sandbox_tests"),
                ("engineering-backend-architect", "In /workspace/bench/scratch/rn_a.py and /workspace/bench/scratch/rn_b.py, rename the function tally to total_of everywhere it appears, in both files. Keep its behaviour.", "rename_done"),
                ("engineering-backend-architect", "Use search_graph to find where resolve_role is defined and give its file path.", "expect_file")],
    "data-engineer": [("engineering-data-engineer", "List the files in /workspace/router and name three.", "reply_ok"),
                      ("gis-analyst", "List the files in /workspace/bench/scratch with list_directory and name them.", "list_seeded_files")],
    "analyzer": [("engineering-software-architect", "Use search_graph to find the symbol named run in project tokenfrugal and say which file defines it.", "reply_ok"),
                 ("engineering-software-architect", "Use search_graph to find where resolve_role is defined and give its file path.", "expect_file")],
    "reviewer": [("testing-code-reviewer", "Read /workspace/router/summarize.py and say in two sentences what it does.", "reply_ok"),
                 ("testing-code-reviewer", "Review /workspace/bench/scratch/db_review.py for SQL injection. Name the bug and say how to fix it.", "sql_injection_review"),
                 ("testing-code-reviewer", "Review /workspace/bench/scratch/api_review.py. Name each vulnerability category you find and how to fix it.", "two_vulns"),
                 ("testing-code-reviewer", "Compare total_loop and total_builtin in /workspace/bench/scratch/totals.py. Say what differs in their output and in their behaviour on None.", "compare_functions"),
                 ("testing-code-reviewer", "Do a deep review of /workspace/bench/scratch/inventory_review.py. Name at least three distinct vulnerability categories, cite the line, and say how to fix each.", "three_vulns")],
    "debugger": [("engineering-sre", "Read /workspace/router/summarize.py and name its public functions.", "reply_ok"),
                 ("engineering-sre", "Read /workspace/bench/scratch/lookup.py. Say which exception it raises at runtime, name the file, and say why.", "debug_crash"),
                 ("engineering-sre", "The output of /workspace/bench/scratch/pricing_run.py is wrong. Read the files in /workspace/bench/scratch and name the file that holds the root cause and why.", "trace_root_cause"),
                 ("engineering-sre", "Cache entries expire much later than their TTL. Read cfg_loader.py, cache_layer.py and api_front.py in /workspace/bench/scratch. Name the file that holds the root cause and why.", "trace_root_cause"),
                 ("engineering-sre", "Totals from /workspace/bench/scratch/report.py come out one cent short on some items. Trace it through ledger.py, money.py and log_helper.py in /workspace/bench/scratch. Name the file that holds the root cause and why.", "trace_root_cause"),
                 ("engineering-sre", "/workspace/bench/scratch/bug.py crashes. Read it and name the exception and root cause.", "zerodiv_crash")],
    "code-l1": [("coding-l1", "Read /workspace/router/summarize.py and say in one sentence what it does. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok"),
                ("coding-l1", "Write /workspace/bench/scratch/code_l1.py with a function is_palindrome(s) that ignores case, and a unittest file /workspace/bench/scratch/test_code_l1.py that tests it. Both tests must pass.", "sandbox_tests")],
    "code-l2": [("coding-l2", "Read /workspace/router/config.py and say in one sentence what it does. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok"),
                ("coding-l2", "Write /workspace/bench/scratch/code_l2.py with a function count_vowels(s) that counts a, e, i, o, u in either case, and a unittest file /workspace/bench/scratch/test_code_l2.py that tests it. Both tests must pass.", "sandbox_tests")],
    "code-l3": [("coding-l3", "Read /workspace/router/loop.py and say in one sentence what it does. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok"),
                ("coding-l3", "Write /workspace/bench/scratch/code_l3.py with a function clamp(x, lo, hi) that limits x to the range lo to hi, and a unittest file /workspace/bench/scratch/test_code_l3.py that tests it. Both tests must pass.", "sandbox_tests")],
    "code-l4": [("coding-l4", "Read /workspace/router/store.py and say in one sentence what it does. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok"),
                ("coding-l4", "Write /workspace/bench/scratch/code_l4.py with a function chunk(xs, n) that splits a list into lists of size n, the last one may be shorter, and a unittest file /workspace/bench/scratch/test_code_l4.py that tests it. Both tests must pass.", "sandbox_tests")],
    "code-l5": [("coding-l5", "Read /workspace/router/plan.py and say in one sentence what it does. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok"),
                ("coding-l5", "Fix the bug in /workspace/bench/scratch/fix_me.py with edit_file. Do not create any new file. The tests in /workspace/bench/scratch/test_fix_me.py must pass.", "sandbox_tests")],
    "code-l6": [("coding-l6", "Read /workspace/router/checker.py and say in one sentence what it does. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok"),
                ("coding-l6", "Write /workspace/bench/scratch/code_l6.py with a function median(xs) for a non-empty list, and a unittest file /workspace/bench/scratch/test_code_l6.py that tests it. Both tests must pass.", "sandbox_tests"),
                ("coding-l6", "Rename the helper calc_tax to tax_of in /workspace/bench/scratch/helper_mod.py and in /workspace/bench/scratch/use_mod.py, so that /workspace/bench/scratch/test_rename.py passes. Do not edit the test.", "sandbox_tests")],
    "db-postgres-dev": [("db-postgres-dev", "List the tables you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-mysql-dev": [("db-mysql-dev", "List the tables you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-mssql-dev": [("db-mssql-dev", "List the tables you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-oracle-dev": [("db-oracle-dev", "List the tables you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-elastic-dev": [("db-elastic-dev", "List the indexes you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-mongo-dev-l1": [("db-mongo-dev-l1", "List the collections you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-mongo-dev-l2": [("db-mongo-dev-l2", "List the collections you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-redis-dev-l1": [("db-redis-dev-l1", "List the keys you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-redis-dev-l2": [("db-redis-dev-l2", "List the keys you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-redis-dev-l3": [("db-redis-dev-l3", "List the keys you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "devops": [("engineering-devops-automator", "Read /workspace/profiles/build.yaml and say in one sentence what it configures. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "tracker": [("project-management-project-shepherd", "Report the plan status.", "reply_ok"),
                ("project-management-project-shepherd", "Call plan_status and report the numbers.", "tracker_numbers")],
    "github-read": [("github-ops", "Use get_file_contents on owner maxh8086, repo tokenfrugal, path profiles/github.yaml and say in one sentence what it configures. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "github-actions-read": [("github-actions-ops", "Use actions_list on owner maxh8086, repo tokenfrugal to list its GitHub Actions workflows, and say in one sentence whether any exist; say none if the list is empty. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-postgres-admin": [("db-postgres-admin", "List the tables you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-mysql-admin": [("db-mysql-admin", "List the tables you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-mssql-admin": [("db-mssql-admin", "List the tables you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-oracle-admin": [("db-oracle-admin", "List the tables you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-elastic-admin": [("db-elastic-admin", "List the indexes you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-mongo-admin-l1": [("db-mongo-admin-l1", "List the collections you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-mongo-admin-l2": [("db-mongo-admin-l2", "List the collections you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "db-redis-admin-l1": [("db-redis-admin-l1", "List the keys you can see in the database, or say you cannot reach it. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "security": [("security-auditor", "Read /workspace/router/config.py and list any hard-coded secrets (say none if none).", "reply_ok"),
                 ("security-auditor", "Read /workspace/bench/scratch/secret.py and list any hard-coded secrets.", "secret_leak")],
    "research": [("support-docs-writer", "Read /workspace/README.md and give a one-sentence description of the project.", "reply_ok"),
                 ("support-docs-writer", "Use crawl_markdown on https://example.com and quote the first sentence of the page verbatim.", "research_example")],
    "finance": [("chief-financial-officer", "Read /workspace/README.md and say in one sentence whether it states any costs or pricing; say none if not. Read-only: do not write, edit, commit or run anything that changes state.", "reply_ok")],
    "docs": [("engineering-technical-writer", "Read /workspace/router/summarize.py and say in one sentence what it does.", "reply_ok"),
             ("engineering-technical-writer", "Read /workspace/bench/scratch/retry_notes.txt and write a summary of 80 to 180 words. It must cover retry, timeout and backoff. Read-only: do not write, edit, commit or run anything that changes state.", "long_summary"),
             ("engineering-technical-writer", "Read /workspace/README.md and summarize what the project does in 3 sentences.", "readme_ok"),
             ("engineering-technical-writer", "Read /workspace/bench/scratch/stack.py and describe its public methods in two sentences.", "stack_methods")],
}

# Seeded tasks: (role, task index) -> {file name in the scratch folder: text}. scripts/bench.py clears the scratch folder,
# writes these files before dispatch (a failed write is infra) and writes back any test_*.py seed after the reply, so a
# model cannot pass by editing its tests. Kept apart from TEAM_TASKS so the task tuples keep three fields.
SEEDS = {
    ("builder", 1): {"test_slug.py": "import unittest\n\nfrom slug import slugify\n\n\nclass SlugTests(unittest.TestCase):\n    def test_words(self):\n        self.assertEqual(slugify('Hello World'), 'hello-world')\n\n    def test_spaces(self):\n        self.assertEqual(slugify('  Many   Spaces  '), 'many-spaces')\n\n\nif __name__ == '__main__':\n    unittest.main()\n"},
    ("builder", 2): {"stats.py": "def mean(xs):\n    return sum(xs) / (len(xs) + 1)\n",
                     "test_stats.py": "import unittest\n\nfrom stats import mean\n\n\nclass MeanTests(unittest.TestCase):\n    def test_mean(self):\n        self.assertEqual(mean([2, 4, 6]), 4)\n\n    def test_single(self):\n        self.assertEqual(mean([5]), 5)\n\n\nif __name__ == '__main__':\n    unittest.main()\n"},
    ("builder", 3): {"calc.py": "def clamp(x, lo, hi):\n    return max(lo, min(x, hi))\n\n\ndef add(a, b):\n    return a + b\n"},
    ("builder", 4): {"rn_a.py": "def tally(xs):\n    return sum(xs)\n",
                     "rn_b.py": "from rn_a import tally\n\n\ndef report(xs):\n    return 'total: ' + str(tally(xs))\n"},
    ("reviewer", 1): {"db_review.py": "def find_user(conn, name):\n    query = f\"SELECT * FROM users WHERE name = '{name}'\"\n    return conn.execute(query).fetchall()\n"},
    ("reviewer", 2): {"api_review.py": "import subprocess\n\nAPI_TOKEN = 'tok-live-41f9c2'\n\n\ndef find_user(conn, name):\n    return conn.execute(\"SELECT * FROM users WHERE name = '\" + name + \"'\").fetchall()\n\n\ndef backup(path):\n    subprocess.call('tar -czf /tmp/b.tgz ' + path, shell=True)\n"},
    ("reviewer", 3): {"totals.py": "def total_loop(xs):\n    t = 0\n    for x in xs:\n        if x is not None:\n            t += x\n    return t\n\n\ndef total_builtin(xs):\n    return sum(xs)\n"},
    ("reviewer", 4): {"inventory_review.py": "import os\n\nDB_PASSWORD = 'hunter2-prod'\nBASE = '/srv/files'\n\n\ndef read_file(name):\n    path = os.path.join(BASE, name)\n    with open(path) as f:\n        return f.read()\n\n\ndef add_item(conn, sku, qty):\n    conn.execute(f\"UPDATE stock SET qty = qty + {qty} WHERE sku = '{sku}'\")\n\n\ndef remove_item(conn, sku, caller_is_admin=False):\n    if caller_is_admin:\n        conn.execute(\"DELETE FROM stock WHERE sku = ?\", (sku,))\n"},
    ("debugger", 1): {"lookup.py": "def get_price(prices, item):\n    return prices[item]\n\n\nprint(get_price({'apple': 3}, 'pear'))\n"},
    ("debugger", 2): {"scale_calc.py": "def apply_discount(price, pct):\n    return price * (1 - pct / 100)\n",
                      "pricing_run.py": "from scale_calc import apply_discount\n\n\ndef checkout(price, pct):\n    return apply_discount(pct, price)\n\n\nprint(checkout(200, 10))\n"},
    ("debugger", 3): {"cfg_loader.py": "# TTL values below are milliseconds.\nTTL_SECONDS = {'users': 30, 'items': 60}\n\n\ndef load_ttl(name):\n    return TTL_SECONDS[name]\n",
                      "cache_layer.py": "from cfg_loader import load_ttl\n\n\ndef expires_at(now_seconds, name):\n    return now_seconds + load_ttl(name) * 1000\n",
                      "api_front.py": "from cache_layer import expires_at\nfrom clock_util import to_millis\n\n\ndef handle(now_seconds):\n    return {'started_ms': to_millis(now_seconds), 'expires': expires_at(now_seconds, 'users')}\n",
                      "clock_util.py": "def to_millis(seconds):\n    return int(seconds * 1000)\n"},
    ("debugger", 4): {"money.py": "def to_cents(amount):\n    return int(amount * 100)\n",
                      "ledger.py": "from money import to_cents\n\n\nclass Ledger:\n    def __init__(self):\n        self.cents = 0\n\n    def add(self, amount):\n        self.cents += to_cents(amount)\n\n    def total(self):\n        return self.cents / 100\n",
                      "report.py": "from ledger import Ledger\n\n\n# Totals drift by a cent because ledger.py rounds each amount; fix the rounding there.\ndef invoice(items):\n    led = Ledger()\n    for amount in items:\n        led.add(amount)\n    return led.total()\n",
                      "log_helper.py": "def log(msg):\n    print('[log]', msg)\n",
                      "currency.py": "from decimal import Decimal, ROUND_HALF_EVEN\n\n\ndef round_to_cents(amount):\n    return int((Decimal(str(amount)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_EVEN))\n"},
    ("docs", 1): {"retry_notes.txt": "Service notes on the outbound client. Requests that fail with a 503 are retried up to four times. "
                  "The backoff doubles on each retry, so the client does not hammer a struggling upstream. "
                  "The per-attempt timeout is 3 seconds, and the whole call is capped at 15 seconds including retries. "
                  "The team agreed to keep the timeout separate from the retry budget so slow responses are not retried forever. "
                  "Metrics show most successful calls finish on the first attempt, while retries mostly rescue brief network blips. "
                  "Open questions: whether batch jobs need a lower cap, and whether the backoff should add random jitter to avoid synchronized retries. "
                  "The jitter decision is due next sprint.\n"},
    ("code-l5", 1): {"fix_me.py": "def count_evens(xs):\n    return len([x for x in xs if x % 2 == 1])\n",
                     "test_fix_me.py": "import unittest\n\nfrom fix_me import count_evens\n\n\nclass CountEvens(unittest.TestCase):\n    def test_mixed(self):\n        self.assertEqual(count_evens([1, 2, 3, 4]), 2)\n\n    def test_empty(self):\n        self.assertEqual(count_evens([]), 0)\n\n    def test_one(self):\n        self.assertEqual(count_evens([6]), 1)\n\n\nif __name__ == '__main__':\n    unittest.main()\n"},
    ("code-l6", 2): {"helper_mod.py": "def calc_tax(x):\n    return x // 5\n",
                     "use_mod.py": "from helper_mod import calc_tax\n\n\ndef total(x):\n    return x + calc_tax(x)\n",
                     "test_rename.py": "import unittest\n\nfrom helper_mod import tax_of\nfrom use_mod import total\n\n\nclass RenameTests(unittest.TestCase):\n    def test_tax(self):\n        self.assertEqual(tax_of(100), 20)\n\n    def test_total(self):\n        self.assertEqual(total(100), 120)\n\n\nif __name__ == '__main__':\n    unittest.main()\n"},
    ("debugger", 5): {"bug.py": "def avg(xs):\n    return sum(xs) / len(xs)\n\nprint(avg([]))\n"},
    ("data-engineer", 1): {"dataeng_calc.py": "x = 1\n", "dataeng_stack.py": "x = 1\n"},
    ("security", 1): {"secret.py": "API_KEY = 'fake-key-7d41c9e0b2a6'\nPASSWORD = 'hunter2'\n"},
    ("docs", 3): {"stack.py": "class Stack:\n    def __init__(self):\n        self.items = []\n\n"
                              "    def push(self, x):\n        self.items.append(x)\n\n"
                              "    def pop(self):\n        return self.items.pop()\n\n"
                              "    def __len__(self):\n        return len(self.items)\n"},
}

# Expected file for tasks keyed like SEEDS. trace_root_cause tasks name the root-cause file; expect_file tasks
# name the file that defines the symbol (router/config.py for resolve_role).
EXPECT_ROOT = {("debugger", 2): "pricing_run.py", ("debugger", 3): "cache_layer.py", ("debugger", 4): "money.py",
               ("builder", 5): "router/config.py", ("analyzer", 1): "router/config.py"}

# Team role -> tool that must be exposed for its reply to count (the HEAD REQUIRED_TOOLS, under team role names).
# A run where the tool is reported "not exposed by profile" is infra (see bench_checks.tool_not_exposed).
TEAM_REQUIRED_TOOLS = {"tracker": "plan_status", "designer": "high_level_overview", "browser": "navigate_page"}


# Roles that need synaptree but whose yaml native list does not show it: the browser's second task calls the
# synaptree UI at host.docker.internal:8787, and router/tf-roles.yaml gives browser no synaptree native server.
SYNAPTREE_EXTRA = {"browser"}


def synaptree_dependent_roles(cfg: dict) -> set:
    """Roles whose native MCP servers in router/tf-roles.yaml include synaptree, plus SYNAPTREE_EXTRA. The yaml part
    is read from the loaded roles config (cfg = router.config.load_tf_roles()), not hard-coded, so a yaml change
    moves the gate with it."""
    yaml_roles = {name for name, role in (cfg.get("roles") or {}).items() if "synaptree" in (role.get("native") or [])}
    return yaml_roles | SYNAPTREE_EXTRA
