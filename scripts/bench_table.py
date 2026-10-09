"""Build a model-comparison table from bench/*.json runs that cover the full realworld suite.
Usage: python -m scripts.bench_table [glob ...]   (default: bench/*full-*.json bench/*confirm*.json)
Writes Benchmark/model-comparison.md and prints it."""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(patterns):
    rows = {}
    for pat in patterns:
        for f in sorted(glob.glob(str(ROOT / pat))):
            d = json.loads(Path(f).read_text(encoding="utf-8"))
            rw = (d.get("results") or {}).get("realworld") or {}
            if len(rw) >= 16:
                rows[d["tag"]] = (d, rw)  # later files win for the same tag
    return rows


def frac(s):
    a, b = s.split("/")
    return int(a), int(b)


def main():
    pats = sys.argv[1:] or ["bench/*full-*.json", "bench/*confirm*.json", "bench/*-llama*full*.json"]
    rows = load(pats)
    if not rows:
        sys.exit("no full-suite runs found")
    cases = list(next(iter(rows.values()))[1])
    table = []
    for tag, (d, rw) in rows.items():
        ok = sum(frac(c["verified"])[0] for c in rw.values() if c["verified"] != "n/a" and "/" in c["verified"])
        tot = sum(frac(c["verified"])[1] for c in rw.values() if "/" in c["verified"])
        ran = sum(frac(c["ran"])[0] for c in rw.values() if "/" in c["ran"])
        mean = sum(c["s"]["mean"] for c in rw.values() if c.get("s")) / max(1, len(rw))
        table.append((ok / max(tot, 1), tag, ok, tot, ran, mean, rw))
    table.sort(reverse=True)
    out = ["# Model comparison (realworld suite, all cases)", "",
           "| Model / run tag | Verified | Ran | Mean s/case | " + " | ".join(cases) + " |",
           "|---|---|---|---|" + "---|" * len(cases)]
    for _, tag, ok, tot, ran, mean, rw in table:
        out.append(f"| {tag} | {ok}/{tot} | {ran}/{tot} | {mean:.1f} | " + " | ".join(rw[c]["verified"] if c in rw else "-" for c in cases) + " |")
    text = "\n".join(out) + "\n"
    (ROOT / "Benchmark").mkdir(exist_ok=True)
    (ROOT / "Benchmark" / "model-comparison.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
