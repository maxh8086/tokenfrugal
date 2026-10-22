"""Ranking logic shared by build_report.py and update_recommendations.py: loads benchmark.csv and picks models per role."""

import csv
import html
import json
import math
import re
import urllib.request
from pathlib import Path

import yaml

B = Path(__file__).resolve().parent.parent          # Benchmark/
AGENTS = B.parent / "router" / "tf-roles.yaml"

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


# The per-test detail files are the source of truth: one row per (run, model, case), with `superseded=yes`
# on older rows. benchmark.csv is only a summary and is not read here. Each run becomes one wide row.
# Excluded from the report: diagnostic runs (probe, browser-longlived) and the cloud Haiku baseline,
# which stays out of the ranking. Runs where every case hit an infra failure have no valid score.
EXCLUDE_TAGS = {"probe-qwen-tracker-browser", "browser-longlived", "haiku-baseline"}


def _live(name):
    """Rows of a detail file that were not superseded by a newer run."""
    return [r for r in _load(name) if not (r.get("superseded") or "").strip()]


def _detail_runs():
    """One wide row per run, from builder.csv (builder cases) and thinker.csv (thinker cases), joined on run_id."""
    runs = {}
    for fname, role in (("builder.csv", "builder"), ("thinker.csv", "thinker")):
        for r in _live(fname):
            g = runs.setdefault(r["run_id"], {"date": r["date"], "git": "", "cases": {}, "s": [], "out": 0.0,
                                               "infra": 0.0, "valid": 0, "ran": 0, "builder_model": "", "thinker_model": ""})
            g[f"{role}_model"] = r["model"]
            g["git"] = g["git"] or r.get("git_sha", "")
            g["cases"][r["case"]] = r["verified"].lstrip("'")
            if r.get("s_p50"):
                g["s"].append(float(r["s_p50"]))
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
        row = {"model": g["builder_model"] or g["thinker_model"], "date": g["date"], "params": "", "git_sha": g["git"],
               "harness_version": "", "shared_system_memory_gb": "", "total_s": "", "run_id": run_id,
               "builder_model": g["builder_model"] or g["thinker_model"], "thinker_model": g["thinker_model"],
               "score": str(a), "max": str(n), "ran": str(g["ran"]), "valid_cases": str(g["valid"]),
               "mean_s_per_case": f"{sum(g['s']) / len(g['s']):.2f}" if g["s"] else "",
               "tokens_out_per_run": f"{g['out']:g}", "infra_cases": f"{g['infra']:g}"}
        for c in CASES:
            row[c] = g["cases"].get(c, "")
        out.append(row)
    return out


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
    return f"{a}/{n}" if n else "·"


def tps(r):
    """Tokens per second, the primary speed metric: tokens_out_per_run / (mean_s_per_case x max).
    None when the row lacks the inputs (legacy rows), so it shows blank rather than zero."""
    s, m, t = num(r, "mean_s_per_case"), num(r, "max"), num(r, "tokens_out_per_run")
    return round(t / (s * m), 1) if s and m and t else None


def spc(r):
    """Seconds per case, the primary speed metric: mean wall seconds for one case (lower = faster). None when absent."""
    return num(r, "mean_s_per_case") or None


def speed_score(s, fast, slow):
    """0-1 speed term from seconds per case on a log scale: the fastest in the pool scores 1, the slowest 0."""
    if not s or not fast or not slow:
        return 0
    if slow <= fast:
        return 1
    return max(0, min(1, math.log(slow / s) / math.log(slow / fast)))


rows.sort(key=lambda r: (spc(r) or 1e9, -pct(r)))
for r in rows:
    r["pct"] = round(pct(r))
    r["spc"] = spc(r)
    r["tps"] = tps(r)
    r["day"] = (r.get("date") or "")[:10]
    r["source"], r["pull"] = origin(r["builder_model"])
    r["builder_score"], r["thinker_score"] = sub_md(r, BUILDER_CASES), sub_md(r, THINKER_CASES)
    r["params_b"] = params_b(r["params"], r["builder_model"])


# Composite score, the same formula as the post pick in ui/server.js:
# 0.6 x pass rate + 0.4 x ln(slowest s/case / s/case) / ln(slowest s/case / fastest s/case).
# Only local runs on the full check count take part; fastest and slowest are taken among those runs.
# Cloud and partial runs get no composite (None) so they never shift the reference.
_local = [r for r in rows if not r["builder_model"].startswith("claude-") and (r["spc"] or 0) > 0]
_full = max((num(r, "max") for r in _local), default=0)
_cands = [r for r in _local if num(r, "max") == _full]
_fast = min((r["spc"] for r in _cands), default=0)
_slow = max((r["spc"] for r in _cands), default=0)
_max_tps = max((r["tps"] for r in _cands if r["tps"]), default=1)  # kept for callers that still import it
for r in rows:
    r["composite"] = None
    if r in _cands:
        r["composite"] = round(0.6 * r["pct"] / 100 + 0.4 * speed_score(r["spc"], _fast, _slow), 3)
    elif r["builder_model"].startswith("claude-") and r["spc"] and _fast:
        # cloud reference: same formula against the local range (speed clamped to 0-1); shown, never ranked
        r["composite"] = round(0.6 * r["pct"] / 100 + 0.4 * speed_score(r["spc"], _fast, _slow), 3)


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
    "s per case = mean wall seconds for one case (primary speed metric, lower = faster). It measures how long you wait for an answer, so wordy models get no credit for verbosity.",
    "t/s = tokens generated per second, shown for information only; it no longer affects rank.",
    "Rank = 100 x (0.6 x pass rate + 0.4 x speed), speed = ln(slowest s per case / s per case) / ln(slowest / fastest) over full local runs (the post pick score). Blank = partial run. The cloud baseline gets the same score against the local range (speed clamped to 0-1), shown for comparison and never ranked.",
    "Run time = wall clock for the whole run.",
    "Valid cases = cases that finished without infrastructure failure (invalid cases are excluded from speed, not from score).",
    "Date = when the run happened; newer = made with newer code.",
]
RANK_LEGEND_MD = "\n".join(f"- {l}" for l in RANK_LEGEND)


def md_table():
    o = ["| # | Model | Date | Params | Score | Pass rate % | Builder | Thinker | s per case | t/s | Rank | Run time | Valid cases |",
         "|--:|---|---|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|"]
    for i, r in enumerate(rows, 1):
        m = f"`{r['builder_model']}`" + (" ⚠infra" if num(r, "infra_cases") > 0 else "")
        comp = "" if r["composite"] is None else f"{r['composite'] * 100:.1f}"
        o.append(f"| {i} | {m} | {r['day']} | {r['params']} | {r['score']}/{r['max']} "
                 f"| {r['pct']} | {r['builder_score']} | {r['thinker_score']} "
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


def role_score(m, fast, slow):
    """Role recommendation score 0-1: 0.6 x pass rate on the role's own cases + 0.4 x speed, speed from the model's
    mean seconds per case on a log scale between the fastest and slowest model in the role."""
    s = sum(m["s"]) / len(m["s"]) if m["s"] else 0
    return 0.6 * m["a"] / m["n"] + 0.4 * speed_score(s, fast, slow)


def _sort_role(agg):
    """Rank by role score alone (0.6 x pass rate + 0.4 x speed), then more evidence. Status is a label, not a sort key.
    Each role is ranked on its own cases only."""
    means = [sum(m["s"]) / len(m["s"]) for m in agg.values() if m["s"]]
    fast, slow = min(means, default=0), max(means, default=0)
    for m in agg.values():
        m["score"] = round(role_score(m, fast, slow), 3)
    return sorted(agg.items(), key=lambda kv: (-kv[1]["score"], -kv[1]["n"]))


def cloud_reference(cases):
    """Cloud (claude-*) reference for one role, from cloud.csv: pass rate on the cases it actually ran, scaled to the
    role's size. The cloud model is the ceiling, shown beside the local ranking and never part of it. None if absent."""
    best = None
    for r in _load("cloud.csv"):
        a, n = subtotal(r, cases)
        if n and (best is None or a / n > best[1]["a"] / best[1]["n"]):
            best = (r["builder_model"], {"a": a, "n": n})
    return best


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
        if r["s_p50"]:
            m["secs"].append(float(r["s_p50"]))
    for m in out.values():
        secs = sorted(m.pop("secs"))
        m["a"] = sum(v for v, _ in m["cases"].values())
        m["n"] = sum(n for _, n in m["cases"].values())
        m["s"] = secs[len(secs) // 2] if secs else 0.0
    return out


def _hard_mark(a, n):
    """Colour mark plus verified count for one hard case, e.g. '🟨 2/3'."""
    a, n = int(a), int(n)
    mark = "🟩" if n and a == n else "🟨" if a > 0 else "🟥"
    return f"{mark} {a}/{n}"


def hard_md(results=None):
    """Markdown table of the hard suite, best first."""
    res = hard_results() if results is None else results
    if not res:
        return "_No hard-suite runs yet._"
    short = [c.replace("hard_", "") for c in HARD_CASES]
    lines = ["| Model | Hard score | " + " | ".join(short) + " | median s/case |", "|---|---|" + "---|" * len(short) + "---|"]
    for m, r in sorted(res.items(), key=lambda kv: (-kv[1]["a"] / max(kv[1]["n"], 1), kv[1]["s"] or 1e9)):
        cells = [_hard_mark(*r["cases"][c]) if c in r["cases"] else "·" for c in HARD_CASES]
        lines.append(f"| `{m}` | {r['a']}/{r['n']} | " + " | ".join(cells) + f" | {r['s']:.0f} |")
    return "\n".join(lines)
