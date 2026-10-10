"""Run a cascade combo for real: partner model runs only the cases the primary did not fully pass.

    PYTHONPATH=. python -m scripts.cascade_run <primary-solo-json> <partner-ollama-model> <name>

Writes bench/<stamp>-cascade-<name>.json (partner run on the remaining cases only) and prints the
combined score and time (primary on all cases + partner on the remaining ones). Candidates: Benchmark/combos.md.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(primary, partner, name):
    d = json.loads(Path(primary).read_text(encoding="utf-8"))
    rw = d["results"]["realworld"]
    rest = [c for c, v in rw.items() if v["verified"].split("/")[0] != v["verified"].split("/")[1]]
    print(f"primary {d['tag']}: {len(rest)} remaining cases: {','.join(rest)}", flush=True)
    env = dict(os.environ, BENCH_CASES=",".join(rest), TOKENFRUGAL_MODEL_BUILDER=partner,
               TOKENFRUGAL_MODEL_THINKER=partner, PYTHONPATH=str(ROOT), PYTHONIOENCODING="utf-8")
    py = ROOT / ".venv" / "Scripts" / "python.exe"
    subprocess.run([str(py if py.exists() else sys.executable), "-m", "scripts.bench", "--only", "realworld",
                    "--n", str(d["n"]), "--tag", f"cascade-{name}"], env=env, cwd=ROOT, check=True)


if __name__ == "__main__":
    main(*sys.argv[1:4])
