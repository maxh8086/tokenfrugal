"""Fill blank `params` cells in a results CSV from Ollama (/api/show). Blank-only: existing values are never changed.

Usage: python Benchmark/script/backfill_params.py [--csv Benchmark/results/benchmark.csv] [--endpoint URL] [--dry-run]
Models Ollama cannot resolve stay blank (nothing is guessed). Backs up to results/backups/ and swaps atomically.
"""
import argparse
import csv
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts import bench_csv  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(ROOT / "Benchmark/results/benchmark.csv"))
    ap.add_argument("--endpoint", default="http://localhost:11434")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    dst = Path(a.csv)
    with dst.open(encoding="utf-8", newline="") as f:
        rd = csv.reader(f)
        head = next(rd)
        rows = list(rd)
    if "params" not in head or "builder_model" not in head:
        sys.exit("csv has no params/builder_model column")
    ip, im = head.index("params"), head.index("builder_model")
    cache, filled, missing = {}, 0, []
    for r in rows:
        if len(r) != len(head):
            sys.exit(f"row width {len(r)} != header {len(head)}; refusing to rewrite")
        if r[ip].strip() or not r[im].strip():
            continue
        m = r[im]
        if m not in cache:
            cache[m] = bench_csv.ollama_params(m, a.endpoint)
        if cache[m]:
            r[ip] = cache[m]
            filled += 1
        elif m not in missing:
            missing.append(m)
    print(f"filled {filled} cells; unresolved: {missing or 'none'}")
    if a.dry_run or not filled:
        return
    bdir = dst.parent / "backups"
    bdir.mkdir(exist_ok=True)
    shutil.copy2(dst, bdir / f"{dst.stem}-{datetime.now():%Y%m%d-%H%M%S-%f}.csv")
    tmp = dst.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(head)
        w.writerows(rows)
    tmp.replace(dst)
    print(f"wrote {dst}")


if __name__ == "__main__":
    main()
