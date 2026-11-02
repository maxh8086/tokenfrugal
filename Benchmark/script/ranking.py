"""Team scoreboard shared by build_report.py: ranks local models by their team-role results in results/team_results.csv.

The suites builder, thinker, hard and coding are retired. Their CSVs stay in results/ as archives and are not read here.
SCOREBOARD_VERSION labels every ranking output. Rankings compare only within one version; the old 81-check numbers are
archived and never added to the team totals.
"""

import csv
import json
import re
import statistics
import urllib.request
from pathlib import Path

import yaml

B = Path(__file__).resolve().parent.parent          # Benchmark/
AGENTS = B.parent / "router" / "tf-roles.yaml"

import sys  # noqa: E402
sys.path.insert(0, str(B.parent))
from scripts.bench_team_tasks import BENCH_EXCLUDED_TEAMS  # noqa: E402

SCOREBOARD_VERSION = "team-v1"
TEAM_FILE = "team_results.csv"


def _load(name):
    _path = B / "results" / name
    if not _path.exists():
        return []
    return list(csv.DictReader(_path.open(encoding="utf-8")))


def _params_by_model():
    """Model -> params text from the summary CSV (benchmark.csv); the newest non-blank value wins. Used only to
    label the params column; no score is read from it."""
    out = {}
    for r in _load("benchmark.csv"):
        m = (r.get("builder_model") or r.get("model") or "").strip()
        p = (r.get("params") or "").strip()
        if m and p:
            out[m] = p
    return out


_PARAMS = _params_by_model()


def team_rows():
    """One dict per (model, team, role) row of team_results.csv. valid = runs minus infra repeats; passes and checks
    count valid repeats only, so an infra repeat is in neither the passes nor the checks. s = mean warm seconds per
    case for the role (None when blank)."""
    out = []
    for r in _load(TEAM_FILE):
        if r["team"] in BENCH_EXCLUDED_TEAMS:  # not part of the model benchmark
            continue
        runs, infra = int(r["runs"] or 0), int(r["infra"] or 0)
        out.append({"model": r["model"], "team": r["team"], "role": r["role"], "runs": runs, "infra": infra,
                    "valid": max(runs - infra, 0), "passes": int(r["passes"] or 0),
                    "s": float(r["mean_s_warm"]) if (r.get("mean_s_warm") or "").strip() else None,
                    "date": (r.get("date") or "")[:10]})
    return out


TEAM_ROWS = team_rows()
# The team roles the scoreboard covers: every (team, role) pair in team_results.csv. A model is ranked only when it
# has a run with at least one valid check for each of them.
ROLE_KEYS = sorted({(t["team"], t["role"]) for t in TEAM_ROWS})
ROLE_LABELS = [f"{team}/{role}" for team, role in ROLE_KEYS]   # column keys the explorer page reads
TEAMS = sorted({team for team, _ in ROLE_KEYS})


CTX_SUFFIX = re.compile(r"-(8192|16384|32768|40960|49152|65536)$")
TRIAL = Path(__file__).resolve().parents[2] / "models" / "trial"


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


def params_b(p, model=""):
    """Billions of parameters from the params column; if blank, from a size tag in the model name (4b, e4b, 1.2b)."""
    m = re.match(r"\s*([\d.]+)B", p or "")
    if m:
        return float(m.group(1))
    if model.startswith("claude-"):
        return None
    m = re.search(r"(?:^|[^a-z\d.])e?(\d+(?:\.\d+)?)b(?![a-z])", model, re.I)
    return float(m.group(1)) if m else None


def spc(r):
    """Seconds per case, the tie-break speed metric: median of the role timings (lower = faster). None when absent."""
    return r.get("median_s") or None


def num(r, k):
    try:
        return float(r[k])
    except (ValueError, TypeError, KeyError):
        return 0.0


def _scoreboard():
    """One row per model that has any team-role row. Score = passes over valid checks summed across the team roles.
    A model is ranked only when every team role ran (at least one valid check). Rank: pass rate (most first), then
    median seconds per case (fastest first). Unranked models keep their row with rank None."""
    by_model = {}
    for t in TEAM_ROWS:
        by_model.setdefault(t["model"], {})[(t["team"], t["role"])] = t
    out = []
    for model, got in by_model.items():
        a = n = infra = ran = 0
        secs, cells, teams, dates = [], {}, {}, []
        for key, label in zip(ROLE_KEYS, ROLE_LABELS):
            t = got.get(key)
            if t is None:
                cells[label] = "⬜ NA"
                continue
            infra += t["infra"]
            dates.append(t["date"])
            if t["valid"] <= 0:
                cells[label] = "⬜ infra"
                continue
            ran += 1
            a += t["passes"]
            n += t["valid"]
            cells[label] = f"{t['passes']}/{t['valid']}"
            ta, tn = teams.get(key[0], (0, 0))
            teams[key[0]] = (ta + t["passes"], tn + t["valid"])
            if t["s"] is not None:
                secs.append(t["s"])
        params = _PARAMS.get(model, "")
        source, pull = origin(model)
        row = {"builder_model": model, "day": max(dates, default=""), "params": params,
               "params_b": params_b(params, model), "source": source, "pull": pull,
               "a": a, "n": n, "score": str(a), "max": str(n),
               "pct": round(100 * a / n) if n else None,
               "median_s": statistics.median(secs) if secs else None,
               "mean_s_per_case": f"{statistics.median(secs):.2f}" if secs else "",
               "tps": None, "total_s": "", "valid_cases": str(ran), "infra_cases": str(infra),
               "ran": str(ran), "team": "", "git_sha": "", "harness_version": "", "shared_system_memory_gb": "",
               "teams": {tm: f"{x}/{y}" for tm, (x, y) in teams.items()}, "version": SCOREBOARD_VERSION,
               "ranked": ran == len(ROLE_KEYS), "rank": None}
        row.update(cells)  # one "a/b" cell per team role, keyed "team/role"
        out.append(row)
    ranked = sorted((r for r in out if r["ranked"]),
                    key=lambda r: (-(r["a"] / r["n"]), r["median_s"] if r["median_s"] is not None else 1e9,
                                   r["builder_model"]))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i
    return out


rows = _scoreboard()


def mmss(v):
    """total_s seconds as m:ss; '' when blank."""
    try:
        t = int(float(v))
    except (ValueError, TypeError):
        return ""
    return f"{t // 60}:{t % 60:02d}"


RANK_LEGEND = [
    f"Scoreboard version {SCOREBOARD_VERSION}. Rankings compare only within one version. The older builder, thinker, hard and coding suites are retired: their scores are archived and not added to team totals.",
    "Score = passes over valid checks, summed across the team roles in results/team_results.csv. Infra repeats are left out of both the passes and the checks.",
    "Pass rate % = Score / max, where max is the valid checks.",
    "Each team-role cell is passes/valid checks for that role over its runs. A role that only had infra repeats shows ⬜ infra.",
    "s per case = median of the roles' mean warm seconds per case (lower = faster). It is the tie-break after pass rate.",
    "Rank = position among models that ran every team role, by pass rate (most first), then s per case (fastest first). A model missing any role, or with no valid check in one, is not ranked.",
    "Date = the newest run date among the model's team roles.",
]
RANK_LEGEND_MD = "\n".join(f"- {l}" for l in RANK_LEGEND)


def md_table():
    o = ["| # | Model | Date | Params | Score | Pass rate % | s per case | Rank | Valid cases |",
         "|--:|---|---|---|--:|--:|--:|--:|--:|"]
    for i, r in enumerate(rows, 1):
        m = f"`{r['builder_model']}`" + (" ⚠infra" if num(r, "infra_cases") > 0 else "")
        comp = "" if r["rank"] is None else str(r["rank"])
        o.append(f"| {i} | {m} | {r['day']} | {r['params']} | {frac_cell(r['score'] + '/' + r['max'])} "
                 f"| {r['pct'] if r['pct'] is not None else ''} | {r['mean_s_per_case']} | {comp} | {r['valid_cases']} |")
    return "\n".join(o)


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


def pass_entry(name, a, n, runs, cells, s, day="", think=""):
    """One model's row for pass_block: a/n passes, runs per case, one cell per column ('a/b' or a marker), median s/case, latest run date, thinking level."""
    p = _PARAMS.get(name, "")
    return {"name": name, "a": a, "n": n, "runs": runs, "cells": cells, "s": s, "day": day, "params": p, "pb": params_b(p, name),
            "shared": None, "tps": None, "think": think}


def pass_block(key, entries, labels):
    """Register one pass table (a team) and return its placeholder. Entries must be in rank order."""
    PASS_DATA[key] = {"labels": labels, "rows": [
        {"model": e["name"], "params": e["params"], "pb": e["pb"], "rank": i, "a": e["a"], "n": e["n"],
         "pct": round(100 * e["a"] / e["n"]) if e["n"] else None, "s": round(e["s"], 1) if e["s"] else None,
         "runs": e["runs"], "cells": e["cells"], "day": e["day"], "shared": e["shared"], "tps": e["tps"], "think": e["think"]}
        for i, e in enumerate(entries, 1)]}
    return f'<div id="{key}-bar"></div>\n<div id="{key}" class="tbox"></div>'
