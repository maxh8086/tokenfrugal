"""Ranking logic shared by build_report.py and update_recommendations.py: loads benchmark.csv and picks models per role."""

import csv
import html
import json
import math
import re
import statistics
import urllib.request
from pathlib import Path

import yaml

B = Path(__file__).resolve().parent.parent          # Benchmark/
AGENTS = B.parent / "router" / "tf-roles.yaml"

# The 16 real case columns. Anything else in the CSV (meta, context_used_* columns) is not a case.
BUILDER_CASES = ["write_function", "fix_bug", "write_tests", "rename_across_files"]
THINKER_CASES = ["find_symbol", "review_sqli", "debug_trace", "summarize_readme", "role_analyzer", "role_data",
                 "role_docs", "role_security", "role_designer", "role_browser", "role_tracker", "role_research"]
CASES = BUILDER_CASES + THINKER_CASES
assert len(CASES) == 16
RUNS_PER_CASE = 3  # a model is ranked for a role only when each of that role's cases ran this many times

# Cases that need a specific MCP tool. A 0 score here is marked with a warning sign.
REQUIRED_TOOL_CASES = {
    "plan_status": "plan_status",                       # role_tracker
    "design_overview": "high_level_overview",           # role_designer
    "browser_navigate_snapshot": "navigate_page",       # role_browser
}

def _load(name):
    _path = B / "results" / name
    if not _path.exists():
        return []
    return list(csv.DictReader(_path.open(encoding="utf-8")))


# The per-test detail files are the source of truth: one row per (run, model, case), with `superseded=yes`
# on older rows. benchmark.csv is only a summary and is not read here. Each run becomes one wide row.
# Excluded from the report: diagnostic runs (probe, browser-longlived) and the cloud Haiku baseline,
# which stays out of the ranking. Runs where every case hit an infra failure have no valid score.
EXCLUDE_TAGS = {"probe-qwen-tracker-browser", "browser-longlived", "haiku-baseline"}


def _live(name):
    """Rows of a detail file that were not superseded by a newer run."""
    return [r for r in _load(name) if not (r.get("superseded") or "").strip()]


def _params_by_model():
    """Model -> params text from the summary CSVs (benchmark.csv, then cloud.csv); the newest non-blank value wins.
    The detail files have no params column, so this is where a run's params come from."""
    out = {}
    for name in ("benchmark.csv", "cloud.csv"):
        for r in _load(name):
            m = (r.get("builder_model") or r.get("model") or "").strip()
            p = (r.get("params") or "").strip()
            if m and p:
                out[m] = p
    return out


def _detail_runs():
    """One wide row per run, joined on run_id from all four detail files: realworld (builder.csv, thinker.csv), hard
    (hard_test.csv) and coding (coder.csv). Together they are the checks benchmark.csv adds up, so a complete run has FULL checks."""
    runs = {}
    for fname in ("builder.csv", "thinker.csv", "hard_test.csv", "coder.csv"):
        for r in _live(fname):
            g = runs.setdefault(r["run_id"], {"date": r["date"], "git": "", "cases": {}, "case_s": {}, "out": 0.0,
                                               "infra": 0.0, "valid": 0, "ran": 0, "builder_model": "", "thinker_model": ""})
            g[f"{r['role']}_model"] = r["model"]
            g["git"] = g["git"] or r.get("git_sha", "")
            g["cases"][r["case"]] = r["verified"].lstrip("'")
            if r.get("s_p50"):
                g["case_s"][r["case"]] = float(r["s_p50"])
            g["out"] += float(r.get("output") or 0)
            g["infra"] += float(r.get("infra_cases") or 0)
            g["valid"] += r.get("status") == "valid"
            g["ran"] += (r.get("ran") or "0").split("/")[0] not in ("", "0")  # cases with at least one attempt ran
    out = []
    for run_id, g in runs.items():
        if g["builder_model"] in EXCLUDE_TAGS or g["thinker_model"] in EXCLUDE_TAGS:
            continue
        a = sum(int(v.split("/")[0]) for v in g["cases"].values() if "/" in v)
        n = sum(int(v.split("/")[1]) for v in g["cases"].values() if "/" in v)
        row = {"model": g["builder_model"] or g["thinker_model"], "date": g["date"],
               "params": _PARAMS.get(g["builder_model"] or g["thinker_model"], ""), "git_sha": g["git"],
               "harness_version": "", "shared_system_memory_gb": "", "total_s": "", "run_id": run_id,
               "builder_model": g["builder_model"] or g["thinker_model"], "thinker_model": g["thinker_model"],
               "score": str(a), "max": str(n), "ran": str(g["ran"]), "valid_cases": str(g["valid"]),
               "mean_s_per_case": f"{statistics.mean(g['case_s'].values()):.2f}" if g["case_s"] else "",
               "median_s": statistics.median(g["case_s"].values()) if g["case_s"] else None,
               "tokens_out_per_run": f"{g['out']:g}", "infra_cases": f"{g['infra']:g}"}
        for c in CASES:
            row[c] = g["cases"].get(c, "")
        row["case_s"] = g["case_s"]
        out.append(row)
    return out


_PARAMS = _params_by_model()


def _team_scores():
    """Model -> {team: "passes/valid"} summed over that team's roles in results/team_results.csv. Valid = runs minus infra.
    A team with no role run for a model is absent, so the report shows NA for it."""
    tot = {}
    for r in _load("team_results.csv"):
        valid = int(r["runs"] or 0) - int(r["infra"] or 0)
        if valid <= 0 or not r["runs"] or r["runs"] == "0":
            continue
        t = tot.setdefault(r["model"], {}).setdefault(r["team"], [0, 0])
        t[0] += int(r["passes"] or 0)
        t[1] += valid
    return {m: {t: f"{a}/{n}" for t, (a, n) in teams.items()} for m, teams in tot.items()}


_TEAM_SCORES = _team_scores()
rows = [r for r in _detail_runs() + _load("cloud.csv")]  # cloud rows are shown, never ranked (_local)
rows = [r for r in rows if (r.get("ran") or "0") not in ("", "0") and (r.get("valid_cases") or "0") not in ("", "0") or r["builder_model"].startswith("claude-")]


def num(r, k):
    try:
        return float(r[k])
    except (ValueError, TypeError, KeyError):
        return 0.0


def pct(r):
    return 100 * num(r, "score") / max(num(r, "max"), 1)


def params_b(p, model=""):
    """Billions of parameters from the params column; if blank, from a size tag in the model name (4b, e4b, 1.2b)."""
    m = re.match(r"\s*([\d.]+)B", p or "")
    if m:
        return float(m.group(1))
    if model.startswith("claude-"):
        return None
    m = re.search(r"(?:^|[^a-z\d.])e?(\d+(?:\.\d+)?)b(?![a-z])", model, re.I)
    return float(m.group(1)) if m else None


def case_frac(r, c):
    try:
        a, n = r[c].lstrip("'").split("/")  # benchmark.csv stores n/m with a leading apostrophe for Excel
        return int(a) / int(n)
    except Exception:
        return None


TRIAL = Path(__file__).resolve().parents[2] / "models" / "trial"
LOCAL_BUILDS = {   # tag -> (base model to pull, Modelfile that derives the tag)
    "qwen2.5-coder-yarn:3b": ("qwen2.5-coder:3b", "models/builder.Modelfile"),
    "llama3.2:3b-16k": ("llama3.2:3b", "models/thinker.Modelfile"),
}


CTX_SUFFIX = re.compile(r"-(8192|16384|32768|40960|49152|65536)$")


def _ollama_show(name):
    """Ollama's own record of a local model (/api/show), or None when Ollama is not reachable."""
    req = urllib.request.Request("http://localhost:11434/api/show", data=json.dumps({"model": name}).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.load(resp)
    except (OSError, ValueError):
        return None


def ollama_up():
    """True when Ollama answers on localhost:11434; the origin column for ts- builds reads from it."""
    try:
        urllib.request.urlopen("http://localhost:11434/api/version", timeout=5).close()
        return True
    except OSError:
        return False


def _upstream(show):
    """Original publisher repo from the GGUF metadata, e.g. 'Qwen/Qwen2.5-1.5B'; '' when the file does not record one."""
    info = (show or {}).get("model_info", {})
    url = info.get("general.base_model.0.repo_url") or ""
    return url.replace("https://huggingface.co/", "") if url else ""


def _norm(stem):
    """Model stem without the context-size suffix or the GGUF marker, so ts-x-65536 matches ts-x-16384 and ts-x-gguf-16384."""
    return CTX_SUFFIX.sub("", stem.lower()).replace("-gguf", "")


def _from_base(base):
    """(source, pull command) for a base model tag that the wrapper was built from."""
    if base.startswith("hf.co/"):
        return f"Hugging Face: {base[len('hf.co/'):].split(':')[0]}", f"ollama pull {base}"
    return "Ollama library", f"ollama pull {base}"


def origin(name):
    """(source, exact command to get this model) from the model tag the run used. Blank pull = source not recorded."""
    if name.startswith("claude-"):
        return "Anthropic API", "not pullable (cloud baseline)"
    if name in LOCAL_BUILDS:
        base, mf = LOCAL_BUILDS[name]
        return "Ollama library (run as local 16k wrapper)", f"ollama pull {base}"
    if name.startswith("ts-"):
        want = _norm(name.split(":")[0])
        for mf in sorted(TRIAL.glob("*.Modelfile")):
            if _norm(mf.stem) in (want, want[3:]):
                m = re.search(r"^FROM\s+(\S+)", mf.read_text(encoding="utf-8"), re.M)
                if m:
                    src, pull = _from_base(m.group(1))
                    return f"{src} (run as local 16k wrapper)", pull
        show = _ollama_show(name)
        parent = ((show or {}).get("details") or {}).get("parent_model") or ""
        if parent:  # the base tag Ollama recorded when this wrapper was created
            src, pull = _from_base(parent)
            up = _upstream(show)
            return f"{src} (run as local 16k wrapper{'; upstream ' + up if up else ''})", pull
        return "Local build (source not recorded)", ""
    if name.startswith("hf.co/"):
        org_repo = name[len("hf.co/"):].split(":")[0]
        return f"Hugging Face: {org_repo}", f"ollama pull {name}"
    return "Ollama library", f"ollama pull {name}"


def subtotal(r, cases):
    """(passed, total) summed over the given case columns."""
    a = n = 0
    for c in cases:
        try:
            x, y = r[c].lstrip("'").split("/")
            a, n = a + int(x), n + int(y)
        except Exception:
            pass
    return a, n


def sub_md(r, cases):
    a, n = subtotal(r, cases)
    return f"{a}/{n}" if n else "⬜ NA"


def tps(r):
    """Tokens per second, the primary speed metric: tokens_out_per_run / (mean_s_per_case x max).
    None when the row lacks the inputs (legacy rows), so it shows blank rather than zero."""
    s, m, t = num(r, "mean_s_per_case"), num(r, "max"), num(r, "tokens_out_per_run")
    return round(t / (s * m), 1) if s and m and t else None


def spc(r):
    """Seconds per case, the primary speed metric: mean wall seconds for one case (lower = faster). None when absent."""
    return num(r, "mean_s_per_case") or None





rows.sort(key=lambda r: (spc(r) or 1e9, -pct(r)))
for r in rows:
    r["pct"] = round(pct(r))
    r["spc"] = spc(r)
    r["tps"] = tps(r)
    r["day"] = (r.get("date") or "")[:10]
    r["source"], r["pull"] = origin(r["builder_model"])
    r["builder_score"], r["thinker_score"] = sub_md(r, BUILDER_CASES), sub_md(r, THINKER_CASES)
    r["params_b"] = params_b(r["params"], r["builder_model"])
    r["shared_system_memory_gb"] = r.get("shared_system_memory_used_gb") or ""  # the column the page reads as "Shared memory GB"


# Shared memory GB and t/s per builder tag, for the pass tables (team and Hard) that have no benchmark row of their own.
_MODEL_STATS = {}
for r in rows:
    _MODEL_STATS.setdefault(r["builder_model"], {"shared": num(r, "shared_system_memory_gb") if r["shared_system_memory_gb"] else None, "tps": r["tps"]})


# Complete local runs: the full check count, as benchmark.csv scores them.
_local = [r for r in rows if not r["builder_model"].startswith("claude-") and (r["spc"] or 0) > 0]
_full = max((num(r, "max") for r in _local), default=0)
_cands = [r for r in _local if num(r, "max") == _full]
_max_tps = max((r["tps"] for r in _cands if r["tps"]), default=1)  # kept for callers that still import it
# Rank: each model's newest complete run, by total passes (most first), then median seconds per case (fastest first).
# Same order as rank_rows() in store.py. benchmark.csv keeps one summary row per model, so the explorer ranks the
# same runs. Older and partial runs get no rank (None).
_newest = {}
for r in _cands:
    if r["builder_model"] not in _newest or r["run_id"] > _newest[r["builder_model"]]["run_id"]:
        _newest[r["builder_model"]] = r
_ranked = sorted(_newest.values(), key=lambda r: (-num(r, "score"), num(r, "median_s") or 1e9))
for r in rows:
    r["rank"] = None
for i, r in enumerate(_ranked, 1):
    r["rank"] = i


def mmss(v):
    """total_s seconds as m:ss; '' when blank (legacy rows written before total_s existed)."""
    try:
        t = int(float(v))
    except (ValueError, TypeError):
        return ""
    return f"{t // 60}:{t % 60:02d}"


RANK_LEGEND = [
    "Score = verified checks passed out of total checks across the builder, thinker, hard and coding suites.",
    "Pass rate % = Score / max.",
    "Builder / Thinker = the same score split by role cases.",
    "s per case = mean wall seconds for one case (primary speed metric, lower = faster). It measures how long you wait for an answer, so wordy models get no credit for verbosity.",
    "t/s = tokens generated per second, shown for information only; it no longer affects rank.",
    "Rank = position among each model's newest complete run, by total passes (most first), then median seconds per case (fastest first). The same runs benchmark.csv ranks. Cloud and partial runs are not ranked.",
    "Run time = wall clock for the whole run.",
    "Valid cases = cases whose status is valid on the page: a case with infrastructure failure or no tools called is not valid and is excluded from speed, not from score. Counted per case over the builder, thinker, hard and coding files.",
    "Ran = cases with at least one attempt that reached the model. A case that never ran is not counted. Counted per case over the same four files, so it is out of the same total as valid cases.",
    "Date = when the run happened; newer = made with newer code.",
]
RANK_LEGEND_MD = "\n".join(f"- {l}" for l in RANK_LEGEND)


def md_table():
    o = ["| # | Model | Date | Params | Score | Pass rate % | Builder | Thinker | s per case | t/s | Rank | Run time | Valid cases |",
         "|--:|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for i, r in enumerate(rows, 1):
        m = f"`{r['builder_model']}`" + (" ⚠infra" if num(r, "infra_cases") > 0 else "")
        comp = "" if r["rank"] is None else str(r["rank"])
        score = frac_cell(f"{r['score']}/{r['max']}")
        o.append(f"| {i} | {m} | {r['day']} | {r['params']} | {score} "
                 f"| {r['pct']} | {frac_cell(r['builder_score'])} | {frac_cell(r['thinker_score'])} "
                 f"| {r['mean_s_per_case']} | {'' if r['tps'] is None else r['tps']} | {comp} | {mmss(r.get('total_s'))} | {r.get('valid_cases') or ''} |")
    return "\n".join(o)


DOT = {"green": "🟢", "amber": "🟡", "red": "🔴"}
DOT_LEGEND = [
    "🟢 Preferred: every case of the role passes in every run, no infra flag, nothing spilled to system RAM.",
    "🟡 Usable: passes at least 75% of the role's checks overall, or passes everything but had an infra flag or system-RAM spill.",
    "🔴 Not recommended: below 75% of the role's checks.",
]
RANK_DOT_LEGEND_MD = "\n".join(f"- {l}" for l in DOT_LEGEND)


def _status(m):
    clean = m["infra"] == 0 and m["shared"] == 0
    if m["full"] == m["runs"] and clean:
        return "green"
    if m["a"] / m["n"] >= 0.75:
        return "amber"
    return "red"


def _sort_role(agg):
    """Rank by pass rate on the role's own cases (most first), then median seconds per case (fastest first), then more
    evidence. Status is a label, not a sort key. Each role is ranked on its own cases only."""
    for m in agg.values():
        m["score"] = round(m["a"] / m["n"], 3)
    return sorted(agg.items(), key=lambda kv: (-kv[1]["score"], kv[1]["s"][0] if kv[1]["s"] else 1e9, -kv[1]["n"]))


def cloud_reference(cases):
    """Cloud (claude-*) reference for one role, from cloud.csv: pass rate on the cases it actually ran, scaled to the
    role's size. The cloud model is the ceiling, shown beside the local ranking and never part of it. None if absent."""
    best = None
    for r in _load("cloud.csv"):
        a, n = subtotal(r, cases)
        if n and (best is None or a / n > best[1]["a"] / best[1]["n"]):
            best = (r["builder_model"], {"a": a, "n": n})
    return best


def _role_run(r, cases):
    """(passed, total) for one role's cases in this run, or None unless every case ran RUNS_PER_CASE times (n=3)."""
    a = 0
    for c in cases:
        try:
            x, y = (int(v) for v in r[c].lstrip("'").split("/"))
        except (KeyError, ValueError, AttributeError):
            return None  # case missing or not scored
        if y != RUNS_PER_CASE:
            return None
        a += x
    return a, RUNS_PER_CASE * len(cases)


def _role_latest(cases):
    """Each local model's newest run that covers this role's cases: {model: row}. Other roles' runs are ignored."""
    latest = {}
    for r in rows:
        name = r["builder_model"]
        if name.startswith("claude-") or not any(r.get(c) for c in cases):
            continue
        if name not in latest or r.get("run_id", "") > latest[name].get("run_id", ""):
            latest[name] = r
    return latest


def role_unranked(cases):
    """Models whose newest run for this role is not n=3 on every case. They are left out of the role's ranking."""
    return sorted(name for name, r in _role_latest(cases).items() if _role_run(r, cases) is None)


def _role_agg(cases):
    """Per-model totals for one role, from each model's newest run of that role only. A run counts only when every
    case of the role ran n=3 times, so a model with a partial or n!=3 run for the role is not ranked for it."""
    agg = {}
    for name, r in _role_latest(cases).items():
        got = _role_run(r, cases)
        if got is None:
            continue
        a, n = got
        m = {"a": a, "n": n, "runs": 1, "full": a == n, "infra": num(r, "infra_cases") > 0,
             "shared": num(r, "shared_system_memory_gb"), "s": [], "t": [], "d": (r.get("date") or "")[:10],
             "g": {(r.get("git_sha") or "")[:7]}, "h": {r.get("harness_version") or ""}, "pull": r["pull"], "row": r}
        case_s = [r["case_s"][c] for c in cases if c in r.get("case_s", {})]
        if case_s:
            m["s"].append(statistics.median(case_s))
        if r["tps"] is not None:
            m["t"].append(r["tps"])
        agg[name] = m
    return agg


BEST_AVAILABLE_COUNT = 3


def role_pick(cases):
    """(preferred list, faster, best available) for one role. Preferred = green models in rank order; faster = the
    quickest preferred model with the same pass rate as the top one, when it is not the top one.
    When no model is green, best available = the top-ranked models (amber before red) instead."""
    ranked = _sort_role(_role_agg(cases))
    greens = [(n, m) for n, m in ranked if _status(m) == "green"]
    if not greens:
        return [], None, [n for n, _ in ranked[:BEST_AVAILABLE_COUNT]]
    top_name, top = greens[0]
    top_pct = top["a"] / top["n"]
    same = [(n, m) for n, m in greens if m["a"] / m["n"] == top_pct and m["t"]]
    fast_name = max(same, key=lambda kv: sum(kv[1]["t"]) / len(kv[1]["t"]), default=(None, None))[0]
    return [n for n, _ in greens], (fast_name if fast_name != top_name else None), []


# Hard thinker suite: separate from the 48-case standard. Detail rows live in results/hard_test.csv (store.py).
HARD_CASES = ["hard_multifile_bug", "hard_two_vulns", "hard_ambiguous_trace", "hard_long_summary", "hard_compare_functions"]
HARD_FILE = B / "results" / "hard_test.csv"


def hard_results(path=None):
    """{thinker model: {"cases": {case: (verified, n)}, "a": verified total, "n": runs total, "s": median s/case}}.
    Per model and case the newest non-superseded row counts (run_id is a timestamp, so string order is time order)."""
    newest = {}                                 # (model, case) -> row
    try:
        with open(path or HARD_FILE, encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r["superseded"] == "yes" or r["case"] not in HARD_CASES:
                    continue
                key = (r["model"], r["case"])
                if key not in newest or r["run_id"] > newest[key]["run_id"]:
                    newest[key] = r
    except OSError:
        return {}
    out = {}
    for (model, case), r in newest.items():
        try:
            v, n = (int(x) for x in r["verified"].lstrip("'").split("/"))
        except ValueError:
            continue
        m = out.setdefault(model, {"cases": {}, "secs": []})
        m["cases"][case] = (v, n)
        m["day"] = max(m.get("day", ""), r["date"][:10])
        if r["s_p50"]:
            m["secs"].append(float(r["s_p50"]))
    for m in out.values():
        secs = sorted(m.pop("secs"))
        m["a"] = sum(v for v, _ in m["cases"].values())
        m["n"] = sum(n for _, n in m["cases"].values())
        m["s"] = secs[len(secs) // 2] if secs else 0.0
    return out


_HARD = hard_results()  # hard_test.csv, newest non-superseded row per model and case
for r in rows:  # hard and team scores need hard_results(), so they are attached here, after its definition
    h = _HARD.get(r["builder_model"])
    r["hard"] = f"{h['a']}/{h['n']}" if h else ""
    r["teams"] = _TEAM_SCORES.get(r["builder_model"], {})


def score_cell(a, n):
    """Colour mark plus run score, e.g. '🟧 2/3'. Used by every table so a score reads the same everywhere."""
    a, n = int(a), int(n)
    mark = "🟩" if n and a == n else "🟧" if a > 0 else "🟥"
    return f"{mark} {a}/{n}"


def frac_cell(s):
    """score_cell for an 'a/b' string (the form the CSVs store). Blank or unparsable gives '⬜ NA' (not run)."""
    m = re.fullmatch(r"'?(\d+)/(\d+)", str(s or "").strip())
    return score_cell(m.group(1), m.group(2)) if m else "⬜ NA"


PASS_DATA = {}  # page key -> {labels, rows}; the page script draws each one with the same table code as the ranking


def pass_entry(name, a, n, runs, cells, s, day=""):
    """One model's row for pass_block: a/n passes, runs per case, one cell per column ('a/b' or a marker), median s/case, latest run date."""
    p = _PARAMS.get(name, "")
    st = _MODEL_STATS.get(name, {})
    return {"name": name, "a": a, "n": n, "runs": runs, "cells": cells, "s": s, "day": day, "params": p, "pb": params_b(p, name),
            "shared": st.get("shared"), "tps": st.get("tps")}


def pass_block(key, entries, labels):
    """Register one pass table (a team or the Hard suite) and return its placeholder. Entries must be in rank order."""
    PASS_DATA[key] = {"labels": labels, "rows": [
        {"model": e["name"], "params": e["params"], "pb": e["pb"], "rank": i, "a": e["a"], "n": e["n"],
         "pct": round(100 * e["a"] / e["n"]) if e["n"] else None, "s": round(e["s"], 1) if e["s"] else None,
         "runs": e["runs"], "cells": e["cells"], "day": e["day"], "shared": e["shared"], "tps": e["tps"]}
        for i, e in enumerate(entries, 1)]}
    return f'<div id="{key}-bar"></div>\n<div id="{key}" class="tbox"></div>'


def hard_md(results=None):
    """The Hard suite as a pass_block, best first."""
    res = hard_results() if results is None else results
    if not res:
        return "_No hard-suite runs yet._"
    entries = []
    for m, r in sorted(res.items(), key=lambda kv: (-kv[1]["a"] / max(kv[1]["n"], 1), kv[1]["s"] or 1e9)):
        cells = [f"{r['cases'][c][0]}/{r['cases'][c][1]}" if c in r["cases"] else "⬜ NA" for c in HARD_CASES]
        runs = max((n for _, n in r["cases"].values()), default="")
        entries.append(pass_entry(m, r["a"], r["n"], runs, cells, r["s"] or None, r.get("day", "")))
    return pass_block("hd", entries, [c.replace("hard_", "") for c in HARD_CASES])
