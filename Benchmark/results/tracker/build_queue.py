import csv, re, sys
S = sys.argv[1]
def san(m):
    return re.sub(r"[^a-z0-9]+", "-", m.lower()).strip("-")
done = set()
with open("Benchmark/results/benchmark.csv", encoding="utf-8-sig", newline="") as f:
    for row in csv.reader(f):
        if row and row[0].startswith("full-"):
            done.add(san(row[0][len("full-"):].split("+")[0]))
def read(p):
    return [l.strip().replace("\r", "") for l in open(p, encoding="utf-8") if l.strip()]
eligible = []
for n in range(1, 10):
    eligible += read(f"{S}/q-batch-{n:02d}.lst")
eligible = [m for m in eligible if m != "ts-gemma3-4b-65536:latest" or True]
excluded = read(f"{S}/excluded_remaining.txt")
seen, out, skipped = set(), [], []
for m in eligible + excluded:
    key = san(m)
    if key in done or key in seen:
        skipped.append(m)
        continue
    seen.add(key)
    out.append(m)
print("to run:", len(out), "skipped:", len(skipped))
for m in skipped:
    print("  skip", m)
open("Benchmark/results/tracker/queue.lst", "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
