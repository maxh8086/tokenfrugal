"""Live stress benchmark for the gateway. Results go to bench/<stamp>.json and bench/<stamp>.md.

    python -m scripts.bench                   # everything, N=5
    python -m scripts.bench --n 3 --only roles,concurrency
    python -m scripts.bench --tag before      # label the output files

Sections: roles, context, output, concurrency, resume, plan, resources.
Needs the LLM endpoint, Docker and the models from `python scripts/doctor.py`.
"""
import argparse
import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

os.environ.setdefault("TOKENFRUGAL_TASK_TIMEOUT", "150")  # keep one bad run from stalling the matrix

from gateway import loop, server  # noqa: E402
from gateway.config import OLLAMA_URL, ROOT, SYNAPTREE_PROJECT, load_personas, resolve_role  # noqa: E402

OUT = ROOT / "bench"
SECTIONS = ["roles", "context", "output", "concurrency", "resume", "plan", "resources"]

# One short, checkable task per role: (agent slug, task).
ROLE_TASKS = {
    "builder": ("engineering-backend-architect",
                "Use search_graph to find the symbol named summarize and report its file path."),
    "analyzer": ("finance-analyst", f"Use search_graph to find the symbol named run in project {SYNAPTREE_PROJECT} and say which file defines it."),
    "reviewer": ("testing-code-reviewer", "Read /workspace/%s/gateway/summarize.py and say in two sentences what it does." % SYNAPTREE_PROJECT),
    "debugger": ("engineering-sre", "Read /workspace/%s/gateway/summarize.py and name its public functions." % SYNAPTREE_PROJECT),
    "research": ("support-docs-writer", "Read /workspace/%s/README.md and give a one-sentence description of the project." % SYNAPTREE_PROJECT),
    "data": ("gis-analyst", "List the files in /workspace/%s/gateway and name three." % SYNAPTREE_PROJECT),
    "tracker": ("project-management-project-shepherd", "Report the plan status."),
    "security": ("security-auditor", "Read /workspace/%s/gateway/config.py and list any hard-coded secrets (say none if none)." % SYNAPTREE_PROJECT),
    "designer": ("design-ui-designer", "Say what design tools you have."),
    "browser": ("testing-evidence-collector", "Say what browser tools you have."),
}


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))] if xs else None


def stats(times):
    if not times:
        return {}
    return {"min": round(min(times), 1), "p50": round(pct(times, 50), 1), "p95": round(pct(times, 95), 1),
            "max": round(max(times), 1), "mean": round(statistics.mean(times), 1)}


async def timed(coro):
    t = time.perf_counter()
    try:
        r = await coro
    except Exception as e:  # noqa: BLE001
        r = f"EXC {type(e).__name__}: {e}"
    return time.perf_counter() - t, str(r)


def ok(r):
    return "FAILED" not in r[:60] and not r.startswith(("EXC", "plan task"))


def failure_mode(r):
    i = r.find("FAILED")
    return (r[i:i + 110] if i >= 0 else r[:110]).replace("\n", " ")


async def bench_roles(n):
    res = {}
    cfg = load_personas()
    for role, (agent, task) in ROLE_TASKS.items():
        assert resolve_role(agent, cfg)["role"] == role, f"{agent} is not a {role}"
        runs = []
        for i in range(n):
            dt, r = await timed(server.dispatch_task(agent, task))
            runs.append({"s": round(dt, 1), "ok": ok(r), "out": r[:140]})
            print(f"  roles/{role} #{i + 1} {dt:5.1f}s {'ok' if ok(r) else failure_mode(r)}", flush=True)
        warm = [x["s"] for x in runs[1:] if x["ok"]]
        res[role] = {"cold_s": runs[0]["s"], "warm": stats(warm), "success": f"{sum(x['ok'] for x in runs)}/{n}",
                     "failures": sorted({failure_mode(x["out"]) for x in runs if not x["ok"]}), "runs": runs}
    return res


async def bench_context(n, sizes=(2000, 4000, 8000, 12000, 16000, 24000, 32000)):
    """Pad the prompt with filler (approx 1 token per 4 chars) and ask for a marker hidden in the middle."""
    res = {}
    for toks in sizes:
        filler = "The quick brown fox jumps over the lazy dog. " * (toks * 4 // 46)
        half = len(filler) // 2
        prompt = filler[:half] + " SECRET-WORD is pelican. " + filler[half:] + "\nWhat is SECRET-WORD? Answer with the word only."
        runs = []
        for _ in range(max(1, n // 2)):
            dt, r = await timed(server.dispatch_task("support-docs-writer", prompt))
            runs.append({"s": round(dt, 1), "ok": ok(r), "found": "pelican" in r.lower(), "out": r[:120]})
        res[str(toks)] = {"success": f"{sum(x['ok'] for x in runs)}/{len(runs)}",
                          "recall": f"{sum(x['found'] for x in runs)}/{len(runs)}",
                          "s": stats([x["s"] for x in runs]), "failures": sorted({failure_mode(x["out"]) for x in runs if not x["ok"]})}
        print(f"  context/{toks} {res[str(toks)]}", flush=True)
    return res


def bench_output(n, lengths=(128, 512, 1024, 2048, 4096)):
    """Direct completions per model: tokens/s and whether the length cap is honoured."""
    from openai import OpenAI
    c = OpenAI(base_url=OLLAMA_URL, api_key="x", timeout=180, max_retries=0)
    cfg = load_personas()["models"]
    res = {}
    for name, model in cfg.items():
        res[name] = {}
        for ln in lengths:
            tps, secs, fails = [], [], 0
            for _ in range(max(1, n // 2)):
                t = time.perf_counter()
                try:
                    r = c.chat.completions.create(model=model, max_tokens=ln, temperature=0.1, messages=[
                        {"role": "user", "content": "Write numbered sentences about the sea. Keep going until told to stop."}])
                    dt = time.perf_counter() - t
                    secs.append(dt)
                    tps.append(r.usage.completion_tokens / dt)
                except Exception:  # noqa: BLE001
                    fails += 1
            res[name][str(ln)] = {"tok_per_s": round(statistics.mean(tps), 1) if tps else None,
                                  "s": stats(secs), "fails": fails}
            print(f"  output/{name}/{ln} {res[name][str(ln)]}", flush=True)
    return res


async def bench_concurrency(n, levels=(1, 2, 4, 8)):
    res = {}
    agent, task = ROLE_TASKS["research"]
    for k in levels:
        t = time.perf_counter()
        out = await asyncio.gather(*[timed(server.dispatch_task(agent, task)) for _ in range(k)])
        wall = time.perf_counter() - t
        per = [dt for dt, _ in out]
        res[str(k)] = {"wall_s": round(wall, 1), "per_task": stats(per), "success": f"{sum(ok(r) for _, r in out)}/{k}",
                       "throughput_per_min": round(k / wall * 60, 1),
                       "failures": sorted({failure_mode(r) for _, r in out if not ok(r)})}
        print(f"  concurrency/{k} {res[str(k)]}", flush=True)
    # mixed models: builder + thinker at once forces model swaps in VRAM
    mixed = await asyncio.gather(timed(server.dispatch_task(*ROLE_TASKS["builder"])), timed(server.dispatch_task(*ROLE_TASKS["research"])),
                                 timed(server.dispatch_task(*ROLE_TASKS["builder"])), timed(server.dispatch_task(*ROLE_TASKS["research"])))
    res["mixed_models_4"] = {"s": [round(dt, 1) for dt, _ in mixed], "success": f"{sum(ok(r) for _, r in mixed)}/4"}
    print(f"  concurrency/mixed {res['mixed_models_4']}", flush=True)
    return res


async def bench_resume(n, rounds=5):
    """Force a failure with a tiny task limit, then resume repeatedly and watch conversation growth and time."""
    from gateway import store
    old = loop.TASK_TIMEOUT
    loop.TASK_TIMEOUT = 2.0
    try:
        agent, task = ROLE_TASKS["builder"]
        dt, r = await timed(server.dispatch_task(agent, task))
        tid = r[1:r.find("]")]
        rows = [{"round": 0, "s": round(dt, 1), "ok": ok(r), "msgs": len(store.get(tid)["messages"] or [])}]
        for i in range(1, rounds + 1):
            dt, r = await timed(server.resume_task(tid))
            t = store.get(tid)
            rows.append({"round": i, "s": round(dt, 1), "ok": ok(r), "msgs": len(t["messages"] or []), "attempts": t["attempts"]})
            if ok(r):
                break
        loop.TASK_TIMEOUT = old
        dt, r = await timed(server.resume_task(tid))  # finally let it finish
        rows.append({"round": "final", "s": round(dt, 1), "ok": ok(r), "msgs": len(store.get(tid)["messages"] or [])})
    finally:
        loop.TASK_TIMEOUT = old
    for r in rows:
        print(f"  resume {r}", flush=True)
    return rows


async def bench_plan(n):
    res = {}
    t = time.perf_counter()
    out = await server.plan_add("bench task", None, 0, "bench", "bench")
    res["plan_add"] = {"s": round(time.perf_counter() - t, 1), "out": out[:80]}
    t = time.perf_counter()
    out = await server.plan_overview("bench")
    res["plan_overview"] = {"s": round(time.perf_counter() - t, 1), "out": out[:120]}
    p = subprocess.run([sys.executable, "-m", "scripts.smoke_plan"], cwd=ROOT, capture_output=True, text=True, timeout=300,
                       env={**os.environ, "PYTHONPATH": str(ROOT)})
    res["smoke_plan"] = {"rc": p.returncode, "tail": (p.stdout + p.stderr).strip().splitlines()[-6:]}
    print(f"  plan {res}", flush=True)
    return res


def sh(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"n/a ({e})"


async def bench_resources(n):
    agent, task = ROLE_TASKS["builder"]
    gpu = ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader"]
    res = {"gpu_before": sh(gpu), "docker_before": sh(["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.CPUPerc}} {{.MemUsage}}"])}
    peak = []

    async def sample():
        while True:
            peak.append(sh(["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.CPUPerc}} {{.MemUsage}}"]))
            await asyncio.sleep(1)
    s = asyncio.create_task(sample())
    dt, r = await timed(server.dispatch_task(agent, task))
    s.cancel()
    res.update(gpu_after=sh(gpu), run_s=round(dt, 1), ok=ok(r), docker_samples=peak[-5:],
               ollama_ps=sh(["ollama", "ps"]), leftover_containers=sh(["docker", "ps", "--format", "{{.Names}}"]))
    print(f"  resources {res}", flush=True)
    return res


def markdown(data):
    L = [f"# Benchmark {data['tag']} {data['stamp']}", "", f"n={data['n']}, task timeout {os.environ['TOKENFRUGAL_TASK_TIMEOUT']}s", ""]
    if "roles" in data["results"]:
        L += ["## Roles", "", "| role | cold s | warm p50 | warm p95 | success | failure modes |", "|---|---|---|---|---|---|"]
        for k, v in data["results"]["roles"].items():
            w = v["warm"]
            L.append(f"| {k} | {v['cold_s']} | {w.get('p50', '-')} | {w.get('p95', '-')} | {v['success']} | {'; '.join(v['failures']) or '-'} |")
        L.append("")
    if "context" in data["results"]:
        L += ["## Context ramp (docs role, prompt tokens)", "", "| tokens | success | recall | p50 s | failures |", "|---|---|---|---|---|"]
        for k, v in data["results"]["context"].items():
            L.append(f"| {k} | {v['success']} | {v['recall']} | {v['s'].get('p50', '-')} | {'; '.join(v['failures']) or '-'} |")
        L.append("")
    if "output" in data["results"]:
        L += ["## Output length (direct)", "", "| model | max_tokens | tok/s | p50 s | fails |", "|---|---|---|---|---|"]
        for m, d in data["results"]["output"].items():
            for ln, v in d.items():
                L.append(f"| {m} | {ln} | {v['tok_per_s']} | {v['s'].get('p50', '-')} | {v['fails']} |")
        L.append("")
    if "concurrency" in data["results"]:
        L += ["## Concurrency", "", "| parallel | wall s | per-task p50 | success | per min |", "|---|---|---|---|---|"]
        for k, v in data["results"]["concurrency"].items():
            if "wall_s" in v:
                L.append(f"| {k} | {v['wall_s']} | {v['per_task'].get('p50', '-')} | {v['success']} | {v['throughput_per_min']} |")
        L += ["", f"Mixed builder/thinker x4: {data['results']['concurrency'].get('mixed_models_4')}", ""]
    for key in ("resume", "plan", "resources"):
        if key in data["results"]:
            L += [f"## {key.title()}", "", "```json", json.dumps(data["results"][key], indent=1)[:4000], "```", ""]
    return "\n".join(L)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--only", default=",".join(SECTIONS))
    ap.add_argument("--tag", default="run")
    a = ap.parse_args()
    want = a.only.split(",")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    data = {"tag": a.tag, "stamp": stamp, "n": a.n, "results": {}}
    fns = {"roles": bench_roles, "context": bench_context, "concurrency": bench_concurrency, "resume": bench_resume,
           "plan": bench_plan, "resources": bench_resources}
    OUT.mkdir(exist_ok=True)
    for s in SECTIONS:
        if s not in want:
            continue
        print(f"== {s}", flush=True)
        t = time.perf_counter()
        try:
            data["results"][s] = bench_output(a.n) if s == "output" else await fns[s](a.n)
        except Exception as e:  # noqa: BLE001
            data["results"][s] = {"error": f"{type(e).__name__}: {e}"}
        print(f"== {s} done in {time.perf_counter() - t:.0f}s", flush=True)
        (OUT / f"{stamp}-{a.tag}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    (OUT / f"{stamp}-{a.tag}.md").write_text(markdown(data), encoding="utf-8")
    print("wrote", OUT / f"{stamp}-{a.tag}.md")


if __name__ == "__main__":
    asyncio.run(main())
