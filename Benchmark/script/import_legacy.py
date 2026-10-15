"""One-off: turn the legacy Benchmark/model-comparison.md table into results/benchmark.csv (the master CSV)."""
import csv, re, sys
from pathlib import Path
B = Path(__file__).resolve().parent.parent
rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in (B / "model-comparison.md").read_text(encoding="utf-8").splitlines() if l.startswith("|")]
head, body = rows[0], rows[2:]
cases = [h.split("<br>")[0] for h in head[5:]]
out = B / "results" / "benchmark.csv"
with out.open("w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["tag", "params", "score", "max", "ran", "mean_s_per_case", "hardware", *cases])
    for r in body:
        s, m = r[2].split("/")
        w.writerow([r[0], r[1], s, m, r[3].split("/")[0], r[4], "RTX 4060 8GB / 16384 ctx", *r[5:]])
print(f"{len(body)} runs, {len(cases)} cases -> {out}")
