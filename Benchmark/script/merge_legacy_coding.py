"""One-time backfill: legacy L1-L6 coding runs (results/coding/ and results/coding-t15/) into coder.csv.

The legacy runs were made before the policy context settings (c1, c2, t15), so they are not comparable with
current runs. They are written as history: superseded=yes. The summary row (benchmark.csv) only reads live rows,
so it does not change. Nothing is written with publish_detail(), because that would mark the newer live rows
superseded.

Re-running is safe: a run_id already in coder.csv is skipped.
Usage: python Benchmark/script/merge_legacy_coding.py [--apply]   (default is a dry run)
"""
import argparse
import glob
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import store  # noqa: E402


def legacy_rows():
    """Coding rows from every legacy run JSON, all marked superseded."""
    t = store.TESTS["coding"]
    rows = []
    for folder in ("coding", "coding-t15"):
        for path in sorted(glob.glob(str(RESULTS / folder / "*.json"))):
            for r in store.suite_detail(path, t["role"], t["suite"], t["cases"]):
                r["superseded"] = "yes"
                rows.append(r)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    target = RESULTS / store.TESTS["coding"]["file"]
    existing = store._read(target, store.ROLE_COLS)
    have = {r["run_id"] for r in existing}
    new = legacy_rows()
    runs = {}
    for r in new:
        runs.setdefault((r["run_id"], r["model"], r["source_file"]), []).append(r)
    todo = {k: v for k, v in runs.items() if k[0] not in have}
    for (run_id, model, src), rows in sorted(todo.items()):
        print(f"{run_id}  {model[:45]:45}  {len(rows):2} rows  {src}")
    print(f"legacy runs: {len(runs)}, new to coder.csv: {len(todo)}, already present: {len(runs) - len(todo)}")
    if not a.apply:
        print("dry run: nothing written (use --apply)")
        return
    rows = [r for v in todo.values() for r in v]
    if not rows:
        return
    backup = store._backup(target)
    store._write(target, store.ROLE_COLS, existing + rows)
    print(f"coder.csv: {len(rows)} rows appended, backup: {backup}")


if __name__ == "__main__":
    main()
