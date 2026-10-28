"""Two-layer result store.

  results/benchmark.csv   one summary row per model: its latest run. Built from the test files, never typed by hand.
  results/builder.csv     builder realworld cases
  results/coder.csv       builder coding cases
  results/thinker.csv     thinker realworld cases
  results/hard_test.csv   thinker hard cases

Column order and the test list are in results/LAYOUT.md. A new test is added to TESTS below.

A run writes its detail rows to the test files. Older rows for the same model, role and suite stay there,
marked superseded=yes. The summary row for the model is then recomputed from the latest non-superseded rows.
Every write is preceded by a backup in results/backups/.
"""
import csv
import json
import shutil
import statistics
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import csvstore  # noqa: E402
import ranking as R  # noqa: E402

CODING_CASES = ["code_l1_clamp", "code_l2_slugify", "code_l3_tax", "code_l4_rename", "code_l5_median",
                "code_l6_callers"]
HARD_CASES = ["hard_multifile_bug", "hard_two_vulns", "hard_ambiguous_trace", "hard_long_summary",
              "hard_compare_functions"]
RUNS_PER_CASE = 3

# One entry per test, in summary column order. role = which model ran it; suite = the suite key in the raw JSON.
TESTS = {
    "builder": {"file": "builder.csv", "role": "builder", "suite": "realworld", "cases": R.BUILDER_CASES,
                "score": "builder_score", "when": "datetime_builder"},
    "thinker": {"file": "thinker.csv", "role": "thinker", "suite": "realworld", "cases": R.THINKER_CASES,
                "score": "thinker_score", "when": "datetime_thinker"},
    "hard": {"file": "hard_test.csv", "role": "thinker", "suite": "hard", "cases": HARD_CASES,
             "score": "thinker_hard_score", "when": "datetime_hard"},
    "coding": {"file": "coder.csv", "role": "builder", "suite": "coding", "cases": CODING_CASES,
               "score": "coding_score", "when": "datetime_coding"},
}

# Per-case columns, same for every test file.
CASE_COLS = ["run_id", "date", "model", "role", "suite", "case", "verified", "ran", "status", "s_p50", "s_min",
             "s_max", "peak", "input", "output", "timeout_s", "source_file", "git_sha", "superseded"]
# Run-level values that stay with the test files (not in the summary).
RUN_COLS = ["score", "max", "mean_s_per_case", "failure_kind", "n", "max_tokens", "tokens_in_per_run",
            "tokens_out_per_run", "model_file_size_gb", "context_window_tokens", "model_max_context_tokens",
            "infra_cases", "mean_s_valid", "total_s", "os", "cpu", "cores", "gpu", "ollama_version", "hardware_id"]
ROLE_COLS = CASE_COLS + RUN_COLS

# Summary columns, in the order of results/LAYOUT.md.
HEAD_COLS = ["model", "params", "endpoint", "temperature", "harness_version", "loop_version", "compression_level"]
RANK_COLS = ["rank", "total_score", "valid_cases", "median_s", "max", "ran"]
TEST_COLS = [c for t in TESTS.values() for c in (t["when"], t["score"])]
TAIL_COLS = ["mean_s_per_case", "context_used_peak_tokens", "gpu_memory_capacity", "gpu_memory_used_gb",
             "system_ram_gb", "shared_system_memory_capacity_gb", "shared_system_memory_used_gb", "peak_model_ram_gb"]
ROLES = list(dict.fromkeys(t["role"] for t in TESTS.values()))  # roles, in TESTS order
MODEL_COLS = [f"{role}_model" for role in ROLES]  # which model ran each role
PIPELINE = ["raw_json"] + MODEL_COLS
SUMMARY_COLS = HEAD_COLS + RANK_COLS + TEST_COLS + TAIL_COLS + PIPELINE + ["note", "team"]  # note: free text, e.g. discontinued models


def team_of(row):
    """Team a summary row belongs to: a builder score is development, a thinker-only score is research."""
    if str(row.get("builder_score") or "").strip():
        return "development"
    if str(row.get("thinker_score") or "").strip():
        return "research"
    return ""
FRACTION_COLS = ["total_score"] + [t["score"] for t in TESTS.values()]

# Thinker cases whose raw JSON key is a role_* name
ROLE_KEY = {"code_graph_search": "role_analyzer", "list_project_files": "role_data", "read_docs_file": "role_docs",
            "security_file_read": "role_security", "design_overview": "role_designer",
            "browser_navigate_snapshot": "role_browser", "plan_status": "role_tracker", "web_crawl": "role_research"}


def test_of(row):
    """The test a detail row belongs to, from its role and suite."""
    for name, t in TESTS.items():
        if (t["role"], t["suite"]) == (row["role"], row["suite"]):
            return name
    raise KeyError(f"no test for role={row['role']} suite={row['suite']}")


def route(rows):
    """Group detail rows by the file they belong in. Returns {file_name: rows}."""
    out = {}
    for r in rows:
        out.setdefault(TESTS[test_of(r)]["file"], []).append(r)
    return out


def _case_result(results, case):
    return results.get(case, results.get(ROLE_KEY.get(case, case)))


def _fraction(v):
    a, b = str(v).lstrip("'").split("/")
    return int(a), int(b)


def suite_detail(json_path, role, suite, cases, run_id=None, model=None, run_cols=None):
    """Case rows for one suite from one raw/suite JSON. Cases missing from the file are skipped, not invented.
    run_id and model override the file's own stamp and meta, so tests run in one invocation share one run id.
    Suite files keep their cases under results[<suite>] or, as the existing runner writes them, under results[realworld]."""
    json_path = Path(json_path)
    d = json.loads(json_path.read_text(encoding="utf-8"))
    meta = d.get("meta", {})
    stamp = run_id or d["stamp"]
    model = model or meta.get(role, "")
    if not model:
        raise ValueError(f"{json_path.name}: no {role} model given or in meta")
    date = datetime.strptime(stamp, "%Y%m%d-%H%M%S").isoformat(timespec="seconds")
    results = d["results"].get(suite) or d["results"].get("realworld", {})
    rows = []
    for case in cases:
        c = _case_result(results, case)
        if not isinstance(c, dict):
            continue
        s = c.get("s") or {}
        rows.append({
            "run_id": stamp, "date": date, "model": model, "role": role, "suite": suite, "case": case,
            "verified": c.get("verified", ""), "ran": c.get("ran", ""), "status": c.get("status", ""),
            "s_p50": s.get("p50", ""), "s_min": s.get("min", ""), "s_max": s.get("max", ""),
            "peak": c.get("peak", ""), "input": c.get("input", ""), "output": c.get("output", ""),
            "timeout_s": c.get("timeout_s", ""), "source_file": json_path.name,
            "git_sha": meta.get("git_sha", ""), "superseded": "",
            **(run_cols or {}),
        })
    return rows


def load_details(results_dir):
    """Every detail row from all test files in results_dir, superseded rows included."""
    rows = []
    for name in dict.fromkeys(t["file"] for t in TESTS.values()):
        rows += _read(Path(results_dir) / name, ROLE_COLS)
    return rows


def _backup(path):
    if path.exists() and path.stat().st_size:
        bdir = path.parent / "backups"
        bdir.mkdir(exist_ok=True)
        backup = bdir / f"{path.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.csv"
        shutil.copy2(path, backup)
        return backup
    return None


def _read(path, cols):
    return csvstore.read_rows(path, cols) if Path(path).exists() and Path(path).stat().st_size else []


def _write(path, cols, rows):
    tmp = path.with_suffix(".csv.tmp")  # beside the target, then swap in: a failed write never truncates it
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, restval="", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})
    tmp.replace(path)


def publish_detail(role_path, rows):
    """Write one run's rows into a test file. Re-publishing the same run replaces its rows. Older runs of the
    same model, role and suite are kept and marked superseded=yes. Returns (backup, superseded_count)."""
    role_path = Path(role_path)
    if not rows:
        return None, 0
    old = _read(role_path, ROLE_COLS)
    key = {(r["model"], r["role"], r["suite"]) for r in rows}
    new_run = rows[0]["run_id"]
    kept, marked = [], 0
    for r in old:
        same = (r["model"], r["role"], r["suite"]) in key
        if same and r["run_id"] == new_run:
            continue
        if same and r["superseded"] != "yes":
            r["superseded"] = "yes"
            marked += 1
        kept.append(r)
    backup = _backup(role_path)
    _write(role_path, ROLE_COLS, kept + rows)
    return backup, marked


def model_key(row):
    """The model a summary row belongs to: its first non-blank role model. `model` holds the run tag, not the model."""
    return next((row[c] for c in MODEL_COLS if row.get(c)), "")


def summarize(models, rows):
    """Summary values for one set of role models from their live rows, latest run only. `models` maps each role
    to its model name, e.g. {"builder": "...", "thinker": "..."}. Takes detail rows from all test files. Blank
    fields when a test is incomplete. Returns a dict with the computed summary columns."""
    out ={c: "" for c in TEST_COLS + ["total_score", "median_s", "mean_s_per_case"]}
    live = [r for r in rows if r["superseded"] != "yes" and r["model"] == models[r["role"]]]
    attempts = max((int(r["n"]) for r in live if str(r.get("n", "")).isdigit()), default=RUNS_PER_CASE)
    out["max"] = str(sum(len(t["cases"]) for t in TESTS.values()) * attempts)  # 27 cases x n attempts
    if not live:
        return out
    by_test = {}
    for r in live:
        by_test.setdefault(test_of(r), []).append(r)
    for name, trows in by_test.items():  # each test keeps its own latest run, so a role-only run keeps the other roles
        run = max(r["run_id"] for r in trows)
        by_test[name] = [r for r in trows if r["run_id"] == run]

    complete = True
    total_a = total_n = 0
    p50 = {}
    for name, t in TESTS.items():
        trows = by_test.get(name, [])
        if {r["case"] for r in trows} != set(t["cases"]):
            complete = False
            continue
        a = sum(_fraction(r["verified"])[0] for r in trows)
        n = sum(_fraction(r["verified"])[1] for r in trows)
        out[t["score"]] = f"{a}/{n}"
        out[t["when"]] = trows[0]["date"]
        total_a, total_n = total_a + a, total_n + n
        for r in trows:
            if r["s_p50"] not in ("", None):
                p50[(name, r["case"])] = float(r["s_p50"])
    if complete:
        out["total_score"] = f"{total_a}/{total_n}"
        vals = list(p50.values())
        out["median_s"] = str(round(statistics.median(vals), 1))
        out["mean_s_per_case"] = str(round(statistics.mean(vals), 1))
    return out


def rank_rows(rows):
    """Assign rank among complete local runs: total pass count (desc), then median_s (asc). A complete run has the
    full check count, the largest denominator in the file. Partial totals, cloud rows and blanks stay unranked.
    A run is one run: rows whose role datetimes differ mix roles from different runs and are not ranked, because the
    explorer ranks only a single run_id covering every suite. The explorer (ranking.py) uses the same rule."""
    full = max((_fraction(r["total_score"])[1] for r in rows if r.get("total_score")), default=0)
    ranked = []
    for r in rows:
        r["rank"] = ""
        cloud = r.get("builder_model", "").startswith("claude-")  # cloud reference rows never enter the local ranking
        stamps = {r.get(k, "") for k in ("datetime_builder", "datetime_thinker", "datetime_hard")} - {""}
        one_run = len(stamps) <= 1
        if r.get("total_score") and r.get("median_s") and not cloud and one_run and _fraction(r["total_score"])[1] == full:
            ranked.append((-_fraction(r["total_score"])[0], float(r["median_s"]), r))
    for i, (_, _, r) in enumerate(sorted(ranked, key=lambda x: (x[0], x[1])), start=1):
        r["rank"] = str(i)
    return rows


def upsert_summary(bench_path, rec_summary, config):
    """Replace the model's summary row (latest run) and re-rank all rows. Returns (backup, displaced_rows).
    Displaced rows are not kept here: their detail is in the test files, and the summary is rebuilt from them.
    rec_summary holds the values from summarize(); config holds the run's config and pipeline values."""
    bench_path = Path(bench_path)
    old = _read(bench_path, SUMMARY_COLS)
    me = model_key(config)
    displaced = [r for r in old if model_key(r) == me]
    kept = [r for r in old if model_key(r) != me]
    row = {c: "" for c in SUMMARY_COLS}
    row.update({c: config.get(c, "") for c in SUMMARY_COLS})
    row.update(rec_summary)
    row["model"] = config["model"]
    rows = [dict(r, team=team_of(r)) for r in rank_rows(kept + [row])]
    backup = _backup(bench_path)
    _write(bench_path, SUMMARY_COLS,
           [{k: csvstore.excel_safe(v) if k in FRACTION_COLS else v for k, v in r.items()} for r in rows])
    return backup, displaced
