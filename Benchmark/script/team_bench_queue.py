"""Run the per-team role benchmark for every 40-run model that is installed in Ollama, one model at a time.

    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe Benchmark/script/team_bench_queue.py [--n 3] [--dry-run]

For each builder tag in results/benchmark.csv: run scripts.bench --only roles --team <all five teams> with the
model as builder and thinker, then append its roles to results/team_results.csv (team_results.py skips rows it
already wrote). Afterwards the report is rebuilt. Tags not installed in Ollama, and cloud tags, are skipped and listed.
"""
import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.bench_model import _sanitize  # noqa: E402

TEAMS = "frontend,backend-sql-dba,backend-nosql-dba,dev-sql,dev-nosql,infra,orchestrator,dev-coding,dev-analyst,security,research"
PY = sys.executable


def installed():
    out = subprocess.run(["ollama", "list"], capture_output=True, text=True, encoding="utf-8").stdout
    return {line.split()[0] for line in out.splitlines()[1:] if line.strip()}


def run_tags():
    with (ROOT / "Benchmark" / "results" / "benchmark.csv").open(encoding="utf-8", newline="") as f:
        tags = [r["builder_model"] for r in csv.DictReader(f) if r["builder_model"]]
    seen = []
    for t in tags:
        if t not in seen and not t.startswith("claude-"):
            seen.append(t)
    return seen


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    have = installed()
    todo = [t for t in run_tags() if t in have]
    skipped = [t for t in run_tags() if t not in have]
    print(f"{len(todo)} to run; skipped (not installed): {skipped}", flush=True)
    if a.dry_run:
        return
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8", BENCH_OUT_DIR="bench",
               TOKENFRUGAL_TF_ROLES_MODELS="0")
    for i, tag in enumerate(todo, 1):
        safe = _sanitize(tag) + "-team"
        print(f"=== [{i}/{len(todo)}] {tag}", flush=True)
        e = dict(env, TOKENFRUGAL_MODEL_BUILDER=tag, TOKENFRUGAL_MODEL_THINKER=tag)
        before = set((ROOT / "bench").glob("*.json"))
        subprocess.run([PY, "-m", "scripts.bench", "--n", str(a.n), "--only", "roles", "--team", TEAMS, "--tag", safe],
                       cwd=str(ROOT), env=e)
        new = sorted(set((ROOT / "bench").glob(f"*-{safe}.json")) - before)
        if not new:
            print(f"!!! no json written for {tag}", flush=True)
            continue
        subprocess.run([PY, "Benchmark/script/team_results.py", "--model", tag] + [str(p) for p in new],
                       cwd=str(ROOT), env=env)
    subprocess.run([PY, "Benchmark/script/build_report.py", "--no-clean", "--update", "no"], cwd=str(ROOT), env=env)
    print("ALL_DONE", flush=True)


if __name__ == "__main__":
    main()
