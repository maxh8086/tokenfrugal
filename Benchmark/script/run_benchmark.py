"""Benchmark local models on this machine and append the result to Benchmark/results/benchmark.csv.

    python Benchmark/script/run_benchmark.py <builder-model> [thinker-model] [--n 2] [--tag NAME]
    python Benchmark/script/run_benchmark.py --from-json bench/<stamp>-<tag>.json

Step 1 runs scripts.bench (16 real-world cases, output verified), step 2 flattens the JSON into
one CSV row with a hardware id. The CSV is the source of truth; run build_report.py afterwards,
then have a cloud model review the CSV and update Observations in Benchmark.md (see README.md).
"""
import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts"))

import bench_csv  # noqa: E402
import hardware  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("builder", nargs="?")
ap.add_argument("thinker", nargs="?")
ap.add_argument("--n", type=int, default=2)
ap.add_argument("--tag")
ap.add_argument("--csv", default=str(HERE.parent / "results" / "benchmark.csv"))
ap.add_argument("--from-json", help="skip the run and import an existing bench JSON")
a = ap.parse_args()

if a.from_json:
    src = Path(a.from_json)
else:
    if not a.builder:
        ap.error("builder model is required unless --from-json is given")
    thinker = a.thinker or a.builder
    tag = a.tag or "full-" + f"{a.builder}+{thinker}".replace(":", "-").replace("/", "-")[:60]
    raw = HERE.parent / "results" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONIOENCODING": "utf-8", "BENCH_OUT_DIR": str(raw),
           "TOKENFRUGAL_MODEL_BUILDER": a.builder, "TOKENFRUGAL_MODEL_THINKER": thinker}
    subprocess.run([sys.executable, "-m", "scripts.bench", "--only", "realworld", "--n", str(a.n), "--tag", tag],
                   cwd=ROOT, env=env, check=True)
    src = max(raw.glob("*.json"), key=lambda p: p.stat().st_mtime)

data = json.loads(src.read_text(encoding="utf-8"))
out = bench_csv.rows(data)
if not out:
    sys.exit(f"no realworld results in {src}")
row = out[0]
score, mx = row[2].split("/")
ran = row[3].split("/")[0]
hw = hardware.info()["id"]
rec = [row[0], row[1], score, mx, ran, row[4], hw, *row[5:]]
dst = Path(a.csv)
new = not dst.exists()
with dst.open("a", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    if new:
        w.writerow(["tag", "params", "score", "max", "ran", "mean_s_per_case", "hardware",
                    *[label for _, label, _ in bench_csv.LAYOUT]])
    w.writerow(rec)
print(f"appended {rec[0]}: {score}/{mx} verified, {rec[5]} s/case on {hw} -> {dst}")
