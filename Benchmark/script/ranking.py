"""Ranking logic shared by build_report.py and update_recommendations.py: loads benchmark.csv and picks models per role."""

import csv
import html
import json
import math
import re
from pathlib import Path

import yaml

B = Path(__file__).resolve().parent.parent          # Benchmark/
AGENTS = B.parent / "router" / "agents.yaml"

# The 16 real case columns. Anything else in the CSV (meta, context_used_* columns) is not a case.
BUILDER_CASES = ["write_function", "fix_bug", "write_tests", "rename_across_files"]
THINKER_CASES = ["find_symbol", "review_sqli", "debug_trace", "summarize_readme", "code_graph_search",
                 "list_project_files", "read_docs_file", "security_file_read", "design_overview",
                 "browser_navigate_snapshot", "plan_status", "web_crawl"]
CASES = BUILDER_CASES + THINKER_CASES
assert len(CASES) == 16

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


# benchmark.csv is the source of truth (one row per raw run log in results/raw/).
# Excluded from the report: diagnostic runs (probe, browser-longlived) and the cloud Haiku baseline,
# which stays out of the ranking. Runs where every case hit an infra failure have no valid score.
EXCLUDE_TAGS = {"probe-qwen-tracker-browser", "browser-longlived", "haiku-baseline"}
rows = [r for r in _load("benchmark.csv") if r.get("tag") not in EXCLUDE_TAGS]
rows = [r for r in rows if (r.get("ran") or "0") not in ("", "0") and (r.get("valid_cases") or "0") not in ("", "0")]
missing = [c for c in CASES if c not in rows[0]]
if missing:
    raise SystemExit(f"benchmark CSVs are missing case columns: {missing}")


def num(r, k):
    try:
        return float(r[k])
    except (ValueError, TypeError, KeyError):
        return 0.0


def pct(r):
    return 100 * num(r, "score") / max(num(r, "max"), 1)


def params_b(p):
    m = re.match(r"\s*([\d.]+)B", p or "")
    return float(m.group(1)) if m else None


def case_frac(r, c):
    try:
        a, n = r[c].split("/")
        return int(a) / int(n)
    except Exception:
        return None


LOCAL_BUILDS = {   # tag -> (base model to pull, Modelfile that derives the tag)
    "qwen2.5-coder-yarn:3b": ("qwen2.5-coder:3b", "models/builder.Modelfile"),
    "llama3.2:3b-16k": ("llama3.2:3b", "models/thinker.Modelfile"),
}


def origin(name):
    """(source, exact command to get this model) from the model tag the run used."""
    if name.startswith("claude-"):
        return "Anthropic API", "not pullable (cloud baseline)"
    if name in LOCAL_BUILDS:
        base, mf = LOCAL_BUILDS[name]
        return "Ollama library + local Modelfile", f"ollama pull {base} && ollama create {name} -f {mf}"
    if name.startswith("hf.co/"):
        org_repo = name[len("hf.co/"):].split(":")[0]
        return f"Hugging Face: {org_repo}", f"ollama pull {name}"
    return "Ollama library", f"ollama pull {name}"


def subtotal(r, cases):
    """(passed, total) summed over the given case columns."""
    a = n = 0
    for c in cases:
        try:
            x, y = r[c].split("/")
            a, n = a + int(x), n + int(y)
        except Exception:
            pass
    return a, n


def sub_md(r, cases):
    a, n = subtotal(r, cases)
    return f"{a}/{n}" if n else "·"


def tps(r):
    """Tokens per second, the primary speed metric: tokens_out_per_run / (mean_s_per_case x max).
    None when the row lacks the inputs (legacy rows), so it shows blank rather than zero."""
    s, m, t = num(r, "mean_s_per_case"), num(r, "max"), num(r, "tokens_out_per_run")
    return round(t / (s * m), 1) if s and m and t else None


rows.sort(key=lambda r: (-(tps(r) or 0), -pct(r)))
for r in rows:
    r["pct"] = round(pct(r))
    r["tps"] = tps(r)
    r["day"] = (r.get("date") or "")[:10]
    r["source"], r["pull"] = origin(r["builder_model"])
    r["builder_score"], r["thinker_score"] = sub_md(r, BUILDER_CASES), sub_md(r, THINKER_CASES)
    r["params_b"] = params_b(r["params"])


# Composite score, the same formula as the post pick in ui/server.js: 0.6 x pass rate + 0.4 x ln(t/s) / ln(highest t/s).
# Only local runs on the full check count take part; the speed reference is the highest t/s among those runs.
# Cloud and partial runs get no composite (None) so they never shift the reference.
_local = [r for r in rows if not r["builder_model"].startswith("claude-") and (r["tps"] or 0) > 0]
_full = max((num(r, "max") for r in _local), default=0)
_cands = [r for r in _local if num(r, "max") == _full]
_max_tps = max((r["tps"] for r in _cands), default=1)
for r in rows:
    r["composite"] = None
    if r in _cands and _max_tps > 1:
        r["composite"] = round(0.6 * r["pct"] / 100 + 0.4 * math.log(r["tps"]) / math.log(_max_tps), 3)


def mmss(v):
    """total_s seconds as m:ss; '' when blank (legacy rows written before total_s existed)."""
    try:
        t = int(float(v))
    except (ValueError, TypeError):
        return ""
    return f"{t // 60}:{t % 60:02d}"


RANK_LEGEND = [
    f"Score = verified checks passed out of total checks across {len(CASES)} cases.",
    "Pass rate % = Score / max.",
    "Builder / Thinker = the same score split by role cases.",
    "t/s = tokens generated per second (primary speed metric) = tokens out / (s per case x cases).",
    "Rank = 100 x (0.6 x pass rate + 0.4 x ln(t/s) / ln(highest t/s)), over full local runs (the post pick score). Blank = partial run or cloud baseline.",
    "s per case = mean seconds per case (secondary speed metric).",
    "Run time = wall clock for the whole run.",
    "Valid cases = cases that finished without infrastructure failure (invalid cases are excluded from speed, not from score).",
    "Date = when the run happened; newer = made with newer code.",
]
RANK_LEGEND_MD = "\n".join(f"- {l}" for l in RANK_LEGEND)


def md_table():
    o = ["| # | Model | Date | Params | Score | Pass rate % | Builder | Thinker | t/s | Rank | s per case | Run time | Valid cases |",
         "|--:|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for i, r in enumerate(rows, 1):
        m = f"`{r['builder_model']}`" + (" ⚠infra" if num(r, "infra_cases") > 0 else "")
        comp = "" if r["composite"] is None else f"{r['composite'] * 100:.1f}"
        o.append(f"| {i} | {m} | {r['day']} | {r['params']} | {r['score']}/{r['max']} "
                 f"| {r['pct']} | {r['builder_score']} | {r['thinker_score']} "
                 f"| {'' if r['tps'] is None else r['tps']} | {comp} | {r['mean_s_per_case']} | {mmss(r.get('total_s'))} | {r.get('valid_cases') or ''} |")
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
    return sorted(agg.items(), key=lambda kv: (-kv[1]["a"] / kv[1]["n"], -kv[1]["n"],
                                                -sum(kv[1].get("t", [0])) / max(len(kv[1].get("t", [])), 1)))


def _role_agg(cases):
    """Per-model totals for one role's cases across ALL of the model's runs, so each model is compared
    against its own history. Newest run date and the newest run's shared memory are kept for display."""
    agg = {}
    for r in rows:
        a, n = subtotal(r, cases)
        name = r["builder_model"]
        if not n or name.startswith("claude-"):
            continue
        d = (r.get("date") or "")[:10]
        m = agg.setdefault(name, {"a": 0, "n": 0, "runs": 0, "full": 0, "infra": 0, "shared": 0,
                                  "s": [], "t": [], "d": "", "g": set(), "h": set(), "pull": r["pull"]})
        m["a"] += a
        m["n"] += n
        m["runs"] += 1
        m["full"] += a == n
        m["infra"] += num(r, "infra_cases") > 0
        m["shared"] = max(m["shared"], num(r, "shared_system_memory_gb"))
        m["g"].add((r.get("git_sha") or "")[:7])
        m["h"].add(r.get("harness_version") or "")
        if d >= m["d"]:
            m["d"], m["pull"] = d, r["pull"]
        if num(r, "mean_s_per_case"):
            m["s"].append(num(r, "mean_s_per_case"))
        if r["tps"] is not None:
            m["t"].append(r["tps"])
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
