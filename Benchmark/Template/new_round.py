"""Create Benchmark/rounds/<round-id>/ for a new benchmark round. Refuses to reuse anything.

    python Benchmark/Template/new_round.py <round-id>      e.g. 20261101-new-tools
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main(rid):
    if not re.fullmatch(r"\d{8}-[a-z0-9][a-z0-9-]*", rid):
        sys.exit("round id must look like YYYYMMDD-short-name (lowercase, digits, dashes)")
    d = ROOT / "Benchmark" / "rounds" / rid
    if d.exists():
        sys.exit(f"{d} already exists. Pick a new round id; existing rounds are never reused.")
    for hit in (ROOT / "bench").glob(f"*{rid}*"):
        sys.exit(f"existing result {hit.name} already uses this id")
    for sub in ("raw", "responses", "tables"):
        (d / sub).mkdir(parents=True)
    (d / "README.md").write_text(
        f"# Round {rid}\n\n- Goal:\n- Models:\n- Tools/MCP servers under test:\n- Baseline (if compared):\n"
        "- Hardware / context / quantization:\n- Results: `raw/`, tables in `tables/`\n", encoding="utf-8")
    print("created", d)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
