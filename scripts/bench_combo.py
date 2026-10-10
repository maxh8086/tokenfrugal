"""Rank builder+thinker combinations from the INDIVIDUAL (single-model) full-suite runs.

Method: every model ran all 16 realworld cases alone (bench/*full-*.json, 2 runs per case).
Cases served by the builder role (CASE_ROLE=builder|data) are scored with the builder model,
the rest with the thinker model. A combo's expected score = best builder-case score of model A
+ thinker-case score of model B; time = mean seconds per case in each group.
Output: Benchmark/combos.md (candidates to test next with scripts/combo_runs.sh) .
Edit MAX_PARAMS / MIN_RATE / TOP below and re-run:
    PYTHONIOENCODING=utf-8 PYTHONPATH=. python -m scripts.bench_combo
"""
import json
from pathlib import Path

from scripts.bench_table import load, PARAMS, CASE_ROLE, ROOT

MAX_PARAMS = 8      # billions loaded at once must fit the GPU (RTX 4060 8 GB)
TOP = 8
SOLO_TAGS = lambda t: t.startswith("full-ts-") and "builder" not in t or t == "full-llama3-2-3b-16k"
BUILDER = {c for c, r in CASE_ROLE.items() if r in ("builder", "data")}


def score(rw, cases):
    ok = tot = 0
    secs = []
    for c in cases:
        v = rw[c]
        a, b = (int(x) for x in v["verified"].split("/"))
        ok += a
        tot += b
        secs.append(v["s"]["mean"] or 0)
    return ok, tot, sum(secs) / len(secs)


def main():
    rows = load(["bench/*full-*.json"])
    models = {}
    for tag, (d, rw) in rows.items():
        if not SOLO_TAGS(tag) or PARAMS.get(tag, ("", 99))[1] > MAX_PARAMS:
            continue
        b = [c for c in rw if c in BUILDER]
        t = [c for c in rw if c not in BUILDER]
        models[tag] = (score(rw, b), score(rw, t), rw)
    out = ["# Combination ranking from solo runs", "",
           f"Models up to {MAX_PARAMS}B. Builder cases: {len(BUILDER)} x2 runs, thinker cases: {16-len(BUILDER)} x2 runs.", "",
           "## Individual model scores", "",
           "| Model | Builder cases | s/case | Thinker cases | s/case |", "|---|---|---|---|---|"]
    name = lambda t: t.replace("full-ts-", "").replace("-16384", "")
    for t, (b, th, _) in sorted(models.items(), key=lambda x: -(x[1][0][0] + x[1][1][0])):
        out.append(f"| {name(t)} | {b[0]}/{b[1]} | {b[2]:.1f} | {th[0]}/{th[1]} | {th[2]:.1f} |")
    # Cascade rule: primary model P runs everything. Cases it does not fully pass (not 2/2) go to the
    # partner Q only. Combo score = P's passes + Q's passes on those cases. Combo time = P's time on all
    # cases + Q's time on the remaining ones. A combo "wins" if score >= best solo score and time < the
    # time of that best solo model (ties on score: the faster solo).
    def full(rw, c):
        return rw[c]["verified"].split("/")[0] == rw[c]["verified"].split("/")[1]
    n = lambda rw, c: int(rw[c]["verified"].split("/")[0])
    sec = lambda rw, c: rw[c]["s"]["mean"] or 0
    solo = {t: (sum(n(m[2], c) for c in m[2]), sum(sec(m[2], c) for c in m[2])) for t, m in models.items()}
    best = max(solo, key=lambda t: (solo[t][0], -solo[t][1]))
    fast = min((t for t in solo if solo[t][0] >= 0.75 * solo[best][0]), key=lambda t: solo[t][1])
    out += ["", "## Baselines (solo)", "",
            f"- Highest score: **{name(best)}** {solo[best][0]}/32 in {solo[best][1]:.0f} s",
            f"- Fastest with at least 75% of that score: **{name(fast)}** {solo[fast][0]}/32 in {solo[fast][1]:.0f} s"]
    combos = []
    for pt, pm in models.items():
        prw = pm[2]
        rest = [c for c in prw if not full(prw, c)]
        for qt, qm in models.items():
            if qt == pt:
                continue
            qrw = qm[2]
            score_ = sum(n(prw, c) for c in prw if c not in rest) + sum(max(n(prw, c), n(qrw, c)) for c in rest)
            t_ = sum(sec(prw, c) for c in prw) + sum(sec(qrw, c) for c in rest)
            combos.append((score_, -t_, pt, qt, rest, solo[pt][0]))
    combos.sort(reverse=True)
    out += ["", "## Cascade candidates (simulated from solo runs)", "",
            "| Primary | Passes alone | Remaining cases | Partner | Expected score | Est. time s | Beats best solo? | Beats fastest? |",
            "|---|---|---|---|---|---|---|---|"]
    tot = 32
    for s_, nt, pt, qt, rest, alone in combos[:TOP * 2]:
        out.append(f"| {name(pt)} | {alone}/32 | {len(rest)} | {name(qt)} | {s_}/{tot} | {-nt:.0f} | "
                   f"{'yes' if s_ >= solo[best][0] and -nt < solo[best][1] else 'no'} | "
                   f"{'yes' if s_ >= solo[fast][0] and -nt < solo[fast][1] else 'no'} |")
    out += ["", "## Measured combination runs (real 16-case runs, 2 runs per case)", "",
            "| Run | Builder cases | Thinker cases | Total | Total s (sum of case means) |", "|---|---|---|---|---|"]
    for tag, (d, rw) in sorted(load(["bench/*pair-*.json"]).items()):
        b = score(rw, [c for c in rw if c in BUILDER])
        t = score(rw, [c for c in rw if c not in BUILDER])
        out.append(f"| {tag.replace('pair-', '')} | {b[0]}/{b[1]} | {t[0]}/{t[1]} | {b[0]+t[0]}/{b[1]+t[1]} | {sum(v['s']['mean'] or 0 for v in rw.values()):.0f} |")
    # Measured cascades: primary solo run (all cases) + partner run on the primary's non-2/2 cases only.
    # Add a line to PRIMARY when you run scripts/cascade_run.py with a new <name>.
    PRIMARY = {"qwen25c-then-gemma4": "full-ts-qwen25c-7b-16384", "llama32-then-gemma4": "full-llama3-2-3b-16k",
               "gemma4-then-llama32": "full-ts-gemma4-e4b-16384", "defaults-then-gemma4": "full-defaults-yarn3b-llama32"}
    allruns = load(["bench/*full-*.json"])
    out += ["", "## Measured cascades (primary on all cases, partner only on the cases the primary did not fully pass)", "",
            f"Baselines: highest score {name(best)} {solo[best][0]}/32 in {solo[best][1]:.0f} s; "
            f"fastest >=75% {name(fast)} {solo[fast][0]}/32 in {solo[fast][1]:.0f} s.", "",
            "| Primary | Partner | Primary alone | Cases re-run | Combo score | Combo time s | Beats best solo? | Beats fastest? |",
            "|---|---|---|---|---|---|---|---|"]
    for f in sorted(Path(ROOT / "bench").glob("*cascade-*.json")):
        cd = json.loads(f.read_text(encoding="utf-8"))
        nm = cd["tag"].replace("cascade-", "")
        pk = next((k for k in allruns if k == PRIMARY.get(nm)), None)
        if not pk:
            continue
        prw, crw = allruns[pk][1], cd["results"]["realworld"]
        alone = sum(n(prw, c) for c in prw)
        s_ = sum(n(prw, c) for c in prw if c not in crw) + sum(max(n(prw, c), n(crw, c)) for c in crw)
        t_ = sum(sec(prw, c) for c in prw) + sum(sec(crw, c) for c in crw)
        out.append(f"| {name(pk)} | {nm.split('-then-')[1]} | {alone}/32 | {len(crw)} | {s_}/32 | {t_:.0f} | "
                   f"{'yes' if s_ >= solo[best][0] and t_ < solo[best][1] else 'no'} | "
                   f"{'yes' if s_ >= solo[fast][0] and t_ < solo[fast][1] else 'no'} |")
    (ROOT / "Benchmark" / "combos.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    print("\n".join(out))


if __name__ == "__main__":
    main()
