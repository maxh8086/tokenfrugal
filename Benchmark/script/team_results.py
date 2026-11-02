"""Write per-team role results from bench JSON files to Benchmark/results/team_results.csv.

Input: bench/<stamp>-<tag>.json files written by `scripts.bench --only roles --team <name>`.
One row per team, role and run. Rows already in the CSV (same json file and role) are skipped, so the script
can be run again after each team finishes.

A failure whose reply says the compose backend did not start is marked infra: it is a harness fault,
not a model result, and it is left out of the pass rate.

Usage (from the repo root):
    PYTHONPATH=. .venv/Scripts/python.exe Benchmark/script/team_results.py --model "maternion/spark-x2.5:4b-q8_0" bench/*-spark-team-*.json

The JSON files do not record the model, so it is passed in with --model.
"""
import csv
import re
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from router.config import load_tf_roles  # noqa: E402
from scripts.bench import ok  # noqa: E402
from store import thinking_of  # noqa: E402

OUT = ROOT / "Benchmark" / "results" / "team_results.csv"
COLS = ["team", "role", "model", "tag", "thinking", "json", "runs", "passes", "infra", "pass_pct", "mean_s_warm", "failure", "date"]


def run_date(json_name):
    """YYYY-MM-DD from the bench file stamp (YYYYMMDD-HHMMSS-...), or blank."""
    m = re.match(r"(\d{4})(\d{2})(\d{2})-", json_name)
    return f"{m[1]}-{m[2]}-{m[3]}" if m else ""
INFRA = ("ComposeError", "compose up failed")


def team_of_role(cfg):
    """Active role -> team name. A role in no team is an error, so the CSV never gets a blank team."""
    out = {}
    for team, spec in cfg["teams"].items():
        for role in spec["roles"]:
            if role in cfg["roles"]:
                out[role] = team
    return out


def rows_from(path, teams, model):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    tag = d.get("tag", "")
    think = thinking_of(d.get("meta", {}), model)
    rows = []
    for role, v in d.get("results", {}).get("roles", {}).items():
        if role not in teams:
            continue  # not an active role: never reported
        if "error" in v:
            rows.append({"team": teams[role], "role": role, "model": model, "tag": tag, "json": Path(path).name,
                         "runs": 0, "passes": 0, "infra": 0, "pass_pct": "", "mean_s_warm": "",
                         "failure": v["error"][:120]})
            continue
        runs = v.get("runs", [])
        for r in runs:  # a run passes only if scripts.bench.ok also accepts the reply (harness and tool-auth errors fail)
            r["ok"] = r["ok"] and ok(r["out"])
        infra = [r for r in runs if not r["ok"] and any(m in r["out"] for m in INFRA)]
        valid = len(runs) - len(infra)
        passes = sum(1 for r in runs if r["ok"])
        warm = v.get("warm") or {}
        fails = sorted({r["out"][:120] for r in runs if not r["ok"] and r not in infra})
        rows.append({"team": teams[role], "role": role, "model": model, "tag": tag, "json": Path(path).name,
                     "runs": len(runs), "passes": passes, "infra": len(infra),
                     "pass_pct": round(100 * passes / valid) if valid else "",
                     "mean_s_warm": warm.get("mean", ""),
                     "failure": ("infra: compose backend did not start" if infra and not fails
                                 else (fails[0] if fails else ""))})
    for r in rows:
        r["thinking"] = think
    return rows


def main(model, paths):
    cfg = load_tf_roles()
    teams = team_of_role(cfg)
    seen = set()
    if OUT.exists():
        with OUT.open(encoding="utf-8", newline="") as f:
            seen = {(r["json"], r["role"]) for r in csv.DictReader(f)}
    new = []
    for p in paths:
        for r in rows_from(p, teams, model):
            if (r["json"], r["role"]) not in seen:
                new.append(r)
    if not new:
        print("nothing new to write")
        return
    write_header = not OUT.exists() or OUT.stat().st_size == 0
    with OUT.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS, lineterminator="\r\n")
        if write_header:
            w.writeheader()
        w.writerows({**r, "date": run_date(r["json"])} for r in new)
    print(f"wrote {len(new)} rows to {OUT}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) < 3 or args[0] != "--model":
        sys.exit("usage: team_results.py --model TAG bench/*.json")
    main(args[1], args[2:])
