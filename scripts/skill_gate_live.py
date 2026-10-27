"""Live run of the skill gate for leveled coding skills: real benchmark runs, real reviewer call.

For each skill: the offline tests run, then the level's coding case runs n times with the baseline skill text and n
times with the candidate. The candidate text is swapped into router/skills/<skill>/SKILL.md for its runs only; the
original bytes are restored afterwards, even on error. The reviewer is Sonnet 5.5 for L1-L3 and Opus 5.5 for L4-L6.
Results go to Benchmark/results/gate/. Needs Docker, Ollama and ANTHROPIC_API_KEY.

    python -m scripts.skill_gate_live --skills code-l2,code-l4,code-l6 --n 3
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

from router import preflight
from router.config import ROOT
from scripts import skill_gate as g

CASES = {"code-l2": "code_l2_slugify", "code-l4": "code_l4_rename", "code-l6": "code_l6_callers"}
RESULTS = ROOT / "Benchmark" / "results" / "gate"
SUITE_TIMEOUT_S = 3 * 3600
API_URL = "https://api.anthropic.com/v1/messages"


def _records(node):
    """Every run record (a dict with 'status' and 'verified') anywhere in the bench JSON."""
    if isinstance(node, dict):
        if "status" in node and isinstance(node.get("verified"), bool):  # skips the text summary row
            yield node
        for v in node.values():
            yield from _records(v)
    elif isinstance(node, list):
        for v in node:
            yield from _records(v)


def run_variant(skill, label, text, n, stamp):
    """Run one case n times with `text` as the skill. Returns (verified, runs) counting non-infra runs only."""
    # checked before every variant; a drifted or missing skill file is restored to the baseline first
    action = preflight.heal_skill(g.SKILLS / skill / "SKILL.md", BASE[skill])
    if action:
        print(f"preflight {skill} {label}: {action}", flush=True)
    if "heal failed" in action:
        raise RuntimeError(f"preflight refused {skill} {label}: {action}")
    (g.SKILLS / skill / "SKILL.md").write_text(text, encoding="utf-8")
    tag = f"gate-{skill}-{stamp}-{label}"
    out = RESULTS / "raw" / tag
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "BENCH_SUITE": "coding", "BENCH_CASES": CASES[skill], "BENCH_OUT_DIR": str(out)}
    subprocess.run([sys.executable, "-m", "scripts.bench", "--only", "realworld", "--n", str(n), "--tag", tag],
                   cwd=ROOT, env=env, check=False, timeout=SUITE_TIMEOUT_S)
    hits = sorted(out.glob(f"*-{tag}.json"), key=lambda p: p.stat().st_mtime)
    if not hits:
        raise RuntimeError(f"no bench JSON for {tag} in {out}")
    data = json.loads(hits[-1].read_text(encoding="utf-8"))
    runs = [r for r in _records(data) if r["status"] != "infra"]
    return sum(1 for r in runs if r["verified"]), len(runs)


BASE = {}  # skill -> original text (LF), filled before any run


def run_tests():
    # the benchmark's TOKENFRUGAL_MODEL_* overrides must not reach the offline tests, which check the real config
    env = {k: v for k, v in os.environ.items() if not k.startswith("TOKENFRUGAL_MODEL_")}
    p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."], cwd=ROOT,
                       capture_output=True, text=True, timeout=900, env=env)
    tail = (p.stdout + p.stderr).strip().splitlines()
    return p.returncode == 0, "\n".join(tail[-3:])


def review(model, skill, text):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in this process")
    prompt = ("You review one short instruction note (a SKILL.md) for a small local coding model. Approve only if it "
              "is specific, does not change the task, and is safe to use. You cannot edit it. Reply with JSON only: "
              '{"approved": true or false, "reason": "one sentence"}.\n\n---\n' + text)
    body = json.dumps({"model": model, "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(API_URL, data=body, headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                                              "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        blocks = json.loads(r.read())["content"]
        reply = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    verdict = json.loads(reply[reply.index("{"): reply.rindex("}") + 1])
    return bool(verdict["approved"]), str(verdict["reason"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skills", required=True)
    ap.add_argument("--n", type=int, default=g.MIN_N)
    ap.add_argument("--apply", action="store_true", help="write a passing candidate to router/skills (default: report only)")
    a = ap.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    RESULTS.mkdir(parents=True, exist_ok=True)
    for skill in a.skills.split(","):
        g.level_of(skill)
        live = g.SKILLS / skill / "SKILL.md"
        original = live.read_bytes()
        cand_path = sorted((g.CANDIDATES / skill).glob("*.md"), key=lambda p: p.stat().st_mtime)
        candidate = cand_path[-1].read_bytes().decode("utf-8").replace("\r\n", "\n") if cand_path else None
        if candidate is None:
            print(f"{skill}: no candidate in {g.CANDIDATES / skill}; skipped")
            continue
        BASE[skill] = original.decode("utf-8").replace("\r\n", "\n")
        rates = {}

        def run_bench(s, text, level):
            t0 = time.time()
            try:
                bv, bn = run_variant(s, "base", BASE[s], a.n, stamp)
                cv, cn = run_variant(s, "cand", text, a.n, stamp)
            finally:
                live.write_bytes(original)  # always restore the live skill
            n = min(bn, cn)
            rates.update({"baseline_verified": bv, "baseline_runs": bn, "candidate_verified": cv, "candidate_runs": cn,
                          "seconds": round(time.time() - t0)})
            return {"n": n, "candidate": cv / cn if cn else 0.0, "baseline": bv / bn if bn else 0.0}

        verdict = g.gate(skill, candidate, run_tests, run_bench, review, apply=a.apply)
        out = {"skill": skill, "case": CASES[skill], "passed": verdict.passed, "gate": verdict.gate,
               "reason": verdict.reason, "rates": rates, "stamp": stamp}
        (RESULTS / f"{skill}-{stamp}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        print(json.dumps(out))


if __name__ == "__main__":
    main()
