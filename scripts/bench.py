"""Live stress benchmark for the router. Results go to bench/<stamp>.json and bench/<stamp>.md.

    python -m scripts.bench                   # everything, N=5
    python -m scripts.bench --n 3 --only roles,concurrency
    python -m scripts.bench --tag before      # label the output files

Sections: roles, context, output, concurrency, resume, plan, resources.
Needs the LLM endpoint, Docker and the models from `python scripts/doctor.py`.
"""
import argparse
import asyncio
import faulthandler
import json
import os
import re
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

TASK_TIMEOUT_DEFAULT = "150"
_ENV_AT_START = dict(os.environ)  # snapshot before the default below, so the run records whether the timeout was set
os.environ.setdefault("TOKENFRUGAL_TASK_TIMEOUT", TASK_TIMEOUT_DEFAULT)  # keep one bad run from stalling the matrix

from router import loop, server  # noqa: E402
from scripts import bench_checks, bench_csv, bench_env  # noqa: E402
from scripts.bench_team_tasks import BENCH_EXCLUDED_TEAMS, EXPECT_ROOT, SEEDS, TEAM_REQUIRED_TOOLS, TEAM_TASKS, synaptree_dependent_roles  # noqa: E402
from router.config import LLM_API_KEY, LLM_TEMPERATURE, OLLAMA_URL, ROOT, SYNAPTREE_PROJECT, THINK_LEVEL, load_tf_roles, resolve_role  # noqa: E402

OUT = ROOT / os.getenv("BENCH_OUT_DIR", "bench")  # new rounds set this so old results are never touched
SECTION_MARGIN = 600  # seconds
CASE_TIMEOUT = float(os.getenv("BENCH_CASE_TIMEOUT", "600"))  # per-dispatch limit of the roles section (see bench_roles)


def parse_only(ap, raw):
    """Split the --only value into section names. Any name not in SECTIONS is a usage error (exit 2, names the bad ones)."""
    names = [x.strip() for x in raw.split(",")]
    unknown = [x for x in names if x not in SECTIONS]
    if unknown:
        ap.error(f"unknown --only section(s): {', '.join(unknown)}; valid sections: {', '.join(SECTIONS)}")
    return names


def section_timeout(n):
    """Hang safety net only, not a per-task limit (a task timeout is a scored failure in bench_roles).
    BENCH_SECTION_TIMEOUT wins when set; otherwise every team task at its full CASE_TIMEOUT for n repeats,
    plus SECTION_MARGIN."""
    env = os.getenv("BENCH_SECTION_TIMEOUT")
    if env:
        return float(env)
    return sum(len(tasks) for tasks in TEAM_TASKS.values()) * n * CASE_TIMEOUT + SECTION_MARGIN


SECTIONS = ["roles", "context", "output", "concurrency", "resume", "plan", "resources"]

# Short, checkable tasks per role: role -> [(agent slug, task, check name)], grouped by team in scripts/bench_team_tasks.py
ROLE_TASKS = TEAM_TASKS


def first_task(role):
    """The (agent, prompt) pair of a role's first task. Callers that unpack two values use this, so a role can hold
    several tasks in ROLE_TASKS without breaking them; the check name is dropped here."""
    agent, prompt, _check = ROLE_TASKS[role][0]
    return agent, prompt


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


# Harness errors come back as ordinary text, so they must not count as passes (a run with a bad mount reported "ok").
HARNESS_ERRORS = ("is not in the workspace", "fix the mount", "container is not running")
# Tool-auth failures (e.g. the filesystem MCP answering 401) come back as a model reply that says it could not read
# the file. Matched case-insensitively, since the model may capitalise them differently.
AUTH_ERRORS = ("tool authorization error", "401 unauthorized")


def ok(r):
    if any(m in r for m in HARNESS_ERRORS) or any(m in r.lower() for m in AUTH_ERRORS):
        return False
    return "FAILED" not in r[:60] and not r.startswith(("EXC", "plan task"))


def failure_mode(r):
    i = r.find("FAILED")
    return (r[i:i + 110] if i >= 0 else r[:110]).replace("\n", " ")


async def role_call(agent, task, role_timeout):
    # Only the harness wait_for limit becomes a role timeout. A TimeoutError inside the model reply stays as text,
    # so its real class (request_timeout) is kept instead of being relabelled with the role limit.
    try:
        return await asyncio.wait_for(server.dispatch_task(agent, task, task_type="benchmark"), role_timeout)
    except asyncio.TimeoutError:
        return f"FAILED TimeoutError after {role_timeout:g}s"


async def bench_roles(n, only=None):
    res = {}
    role_timeout = float(os.getenv("BENCH_CASE_TIMEOUT", "600"))  # a hung dispatch is a scored failure, not a stall
    cfg = load_tf_roles()
    synaptree = synaptree_dependent_roles(cfg)  # roles whose native servers include synaptree (from the yaml)
    missing = set(cfg["roles"]) - set(ROLE_TASKS)
    # assert not missing, f"bench does not cover roles: {sorted(missing)}"
    if missing:  # report uncovered roles instead of aborting the whole section
        print(f"  roles: no bench task for {sorted(missing)}, skipped", flush=True)
    # BENCH_ROLES=code-l2,code-l4 runs only those roles (comma-separated); unset keeps the default selection
    env_roles = [x.strip() for x in os.getenv("BENCH_ROLES", "").split(",") if x.strip()]
    if env_roles:
        unknown = [r for r in env_roles if r not in ROLE_TASKS]
        if unknown:
            raise ValueError(f"BENCH_ROLES names no bench task: {unknown}")
        only = env_roles
    chosen = ROLE_TASKS if not only else {r: ROLE_TASKS[r] for r in only}
    for role, tasks in chosen.items():
        runs = []  # every task of the role, n repeats each; a run keeps the check name it was scored with
        uses_synaptree = role in synaptree  # the roles runner's synaptree infra gate, for roles that need the container
        for idx, (agent, task, check_name) in enumerate(tasks):
            assert resolve_role(agent, cfg)["role"] == role, f"{agent} is not a {role}"
            seeds = SEEDS.get((role, idx), {})  # seeded files for this task (see bench_team_tasks.SEEDS)
            expect = EXPECT_ROOT.get((role, idx))  # expected root-cause file for trace tasks
            needs_scratch = bool(seeds) or check_name in bench_checks.SCRATCH_CHECKS
            for i in range(n):
                # Synaptree gate, checked before every dispatch (the HEAD runner did this per repeat): sweep leaked
                # gateway containers, then do not dispatch while the synaptree container is down. Infra, nothing is sent.
                started = None
                if uses_synaptree:
                    bench_checks.sweep_stale_mcp()
                    pre_state = bench_checks.container_state()
                    down = bench_checks.synaptree_down(pre_state)
                    if down:
                        runs.append({"s": 0.0, "ok": False, "infra": True, "out": down[:400], "check": check_name})
                        print(f"  roles/{role} #{len(runs)} infra: {down}", flush=True)
                        continue
                    started = pre_state.get("StartedAt")  # compared after the dispatch: a restart during the run is infra
                # Host scratch folder check before every dispatch: a missing or unmapped folder is infra, nothing is sent.
                pre = bench_checks.scratch_ready(bench_checks.SCRATCH, bench_checks.WS)
                if not pre and needs_scratch:  # clean folder, then this task's seeds; a seed that cannot be written is infra
                    bench_checks.clean_scratch()
                    pre = bench_checks.seed_files(bench_checks.SCRATCH, seeds)
                if pre:
                    runs.append({"s": 0.0, "ok": False, "infra": True, "out": pre[:400], "check": check_name})
                    print(f"  roles/{role} #{len(runs)} infra: {pre}", flush=True)
                    continue
                dt, r = await timed(role_call(agent, task, role_timeout))
                # a reply shorter than 20 chars (after dropping the leading "[tid] ") is a failure, not a success
                body = re.sub(r"^\[[^\]]*\]\s*", "", r).strip()
                # put the seeded test files back, so a model cannot pass by editing its tests; a failed write is infra
                reseed = bench_checks.seed_files(bench_checks.SCRATCH, {k: v for k, v in seeds.items() if k.startswith("test_")})
                # a tool reply saying the host folder or mount is missing is infra, not a model failure
                infra = bench_checks.is_infra_tool_error(body) or bool(reseed)
                try:
                    role_ok = ok(r) and len(body) >= 20 and not infra and bench_checks.check_passes(
                        check_name, body, bench_checks.SCRATCH, expect)
                except bench_checks.InfraFailure as e:  # docker or host failure during the check: infra, not a model fail
                    reason = str(e)[:400]
                    runs.append({"s": round(dt, 1), "ok": False, "infra": True, "out": reason, "check": check_name})
                    print(f"  roles/{role} #{len(runs)} infra: {reason}", flush=True)
                    continue
                # Post-dispatch infra checks. A tool that was not exposed by the profile is infra, not a fail. A failed
                # (or connection-broken) synaptree run is infra only when the container is down or was restarted.
                # Ordinary model fails with a healthy container keep their score.
                trail = bench_checks.trail_of(r) if (uses_synaptree or role in TEAM_REQUIRED_TOOLS) else []
                reason = ""
                if role in TEAM_REQUIRED_TOOLS and bench_checks.tool_not_exposed(r, trail):
                    reason = f"tool {TEAM_REQUIRED_TOOLS[role]} not exposed by profile"
                elif uses_synaptree and (not role_ok or bench_checks.connection_closed(r, trail)):
                    reason = bench_checks.synaptree_down(bench_checks.container_state(), started)
                if reason:
                    infra, role_ok = True, False
                    r = f"{reason} | {r[:200]}"
                if ok(r) and not role_ok and not infra:
                    r = (f"FAILED reply too short ({len(body)} chars)" if len(body) < 20
                         else f"FAILED check {check_name} ({len(body)} chars)")
                runs.append({"s": round(dt, 1), "ok": role_ok, "infra": infra, "out": r[:400], "check": check_name})  # keep the full compose/infra error
                status = "ok" if role_ok else ("infra" if infra else failure_mode(r))
                print(f"  roles/{role} #{len(runs)} {dt:5.1f}s {status}", flush=True)
        live = [x for x in runs if not x.get("infra")]  # infra runs are not fails: left out of success and failures
        warm = [x["s"] for x in live[1:] if x["ok"]]
        res[role] = {"cold_s": live[0]["s"] if live else None, "warm": stats(warm),
                     "success": f"{sum(x['ok'] for x in live)}/{len(live)}" if live else "infra",
                     "failures": sorted({failure_mode(x["out"]) for x in live if not x["ok"]}),
                     "infra": sorted({x["out"] for x in runs if x.get("infra")}), "runs": runs}
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
            dt, r = await timed(server.dispatch_task("support-docs-writer", prompt, task_type="benchmark"))
            runs.append({"s": round(dt, 1), "ok": ok(r), "found": "pelican" in r.lower(), "out": r[:120]})
        res[str(toks)] = {"success": f"{sum(x['ok'] for x in runs)}/{len(runs)}",
                          "recall": f"{sum(x['found'] for x in runs)}/{len(runs)}",
                          "s": stats([x["s"] for x in runs]), "failures": sorted({failure_mode(x["out"]) for x in runs if not x["ok"]})}
        print(f"  context/{toks} {res[str(toks)]}", flush=True)
    return res


def bench_output(n, lengths=(128, 512, 1024, 2048, 4096)):
    """Direct completions per model: tokens/s and whether the length cap is honoured."""
    from openai import OpenAI
    c = OpenAI(base_url=OLLAMA_URL, api_key=LLM_API_KEY, timeout=180, max_retries=0)
    cfg = load_tf_roles()["models"]
    res = {}
    for name, model in cfg.items():
        res[name] = {}
        for ln in lengths:
            tps, secs, fails = [], [], 0
            for _ in range(max(1, n // 2)):
                t = time.perf_counter()
                try:
                    r = c.chat.completions.create(model=model, max_tokens=ln, temperature=LLM_TEMPERATURE, messages=[
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
    agent, task = first_task("research")
    for k in levels:
        t = time.perf_counter()
        out = await asyncio.gather(*[timed(server.dispatch_task(agent, task, task_type="benchmark")) for _ in range(k)])
        wall = time.perf_counter() - t
        per = [dt for dt, _ in out]
        res[str(k)] = {"wall_s": round(wall, 1), "per_task": stats(per), "success": f"{sum(ok(r) for _, r in out)}/{k}",
                       "throughput_per_min": round(k / wall * 60, 1),
                       "failures": sorted({failure_mode(r) for _, r in out if not ok(r)})}
        print(f"  concurrency/{k} {res[str(k)]}", flush=True)
    # mixed models: builder + thinker at once forces model swaps in VRAM
    mixed = await asyncio.gather(timed(server.dispatch_task(*first_task("builder"), task_type="benchmark")), timed(server.dispatch_task(*first_task("research"), task_type="benchmark")),
                                 timed(server.dispatch_task(*first_task("builder"), task_type="benchmark")), timed(server.dispatch_task(*first_task("research"), task_type="benchmark")))
    res["mixed_models_4"] = {"s": [round(dt, 1) for dt, _ in mixed], "success": f"{sum(ok(r) for _, r in mixed)}/4"}
    print(f"  concurrency/mixed {res['mixed_models_4']}", flush=True)
    return res


async def bench_resume(n, rounds=5):
    """Force a failure with a tiny task limit, then resume repeatedly and watch conversation growth and time."""
    from router import store
    old = loop.TASK_TIMEOUT
    loop.TASK_TIMEOUT = 2.0
    try:
        agent, task = first_task("builder")
        dt, r = await timed(server.dispatch_task(agent, task, task_type="benchmark"))
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
    agent, task = first_task("builder")
    gpu = ["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu", "--format=csv,noheader"]
    res = {"gpu_before": sh(gpu), "docker_before": sh(["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.CPUPerc}} {{.MemUsage}}"])}
    peak = []

    async def sample():
        while True:
            peak.append(sh(["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.CPUPerc}} {{.MemUsage}}"]))
            await asyncio.sleep(1)
    s = asyncio.create_task(sample())
    dt, r = await timed(server.dispatch_task(agent, task, task_type="benchmark"))
    s.cancel()
    res.update(gpu_after=sh(gpu), run_s=round(dt, 1), ok=ok(r), docker_samples=peak[-5:],
               ollama_ps=sh(["ollama", "ps"]), leftover_containers=sh(["docker", "ps", "--format", "{{.Names}}"]))
    print(f"  resources {res}", flush=True)
    return res


def markdown(data):
    timeout = data["task_timeout"]
    L = [f"# Benchmark {data['tag']} {data['stamp']}", "", f"n={data['n']}, task timeout {timeout['task_timeout_s']:g}s ({timeout['source']})", ""]
    for k, v in data["results"].items():  # errored sections are reported, not rendered as tables
        if isinstance(v, dict) and "error" in v:
            L += [f"## {k.title()}", "", f"Section failed: {v['error']}", ""]
    ok = lambda k: k in data["results"] and "error" not in data["results"][k]  # noqa: E731
    if ok("roles"):
        L += ["## Roles", "", "| role | cold s | warm p50 | warm p95 | success | failure modes |", "|---|---|---|---|---|---|"]
        for k, v in data["results"]["roles"].items():
            w = v["warm"]
            L.append(f"| {k} | {v['cold_s']} | {w.get('p50', '-')} | {w.get('p95', '-')} | {v['success']} | {'; '.join(v['failures']) or '-'} |")
        L.append("")
    if ok("context"):
        L += ["## Context ramp (docs role, prompt tokens)", "", "| tokens | success | recall | p50 s | failures |", "|---|---|---|---|---|"]
        for k, v in data["results"]["context"].items():
            L.append(f"| {k} | {v['success']} | {v['recall']} | {v['s'].get('p50', '-')} | {'; '.join(v['failures']) or '-'} |")
        L.append("")
    if ok("output"):
        L += ["## Output length (direct)", "", "| model | max_tokens | tok/s | p50 s | fails |", "|---|---|---|---|---|"]
        for m, d in data["results"]["output"].items():
            for ln, v in d.items():
                L.append(f"| {m} | {ln} | {v['tok_per_s']} | {v['s'].get('p50', '-')} | {v['fails']} |")
        L.append("")
    if ok("concurrency"):
        L += ["## Concurrency", "", "| parallel | wall s | per-task p50 | success | per min |", "|---|---|---|---|---|"]
        for k, v in data["results"]["concurrency"].items():
            if "wall_s" in v:
                L.append(f"| {k} | {v['wall_s']} | {v['per_task'].get('p50', '-')} | {v['success']} | {v['throughput_per_min']} |")
        L += ["", f"Mixed builder/thinker x4: {data['results']['concurrency'].get('mixed_models_4')}", ""]
    for key in ("resume", "plan", "resources"):
        if ok(key):
            L += [f"## {key.title()}", "", "```json", json.dumps(data["results"][key], indent=1)[:4000], "```", ""]
    L += bench_env.markdown_section(data["env"], timeout, data["hardware"])
    return "\n".join(L)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--only", default=",".join(SECTIONS))
    ap.add_argument("--tag", default="run")
    ap.add_argument("--team", default="", help="comma-separated teams; runs every active role in each team (roles section)")
    a = ap.parse_args()
    want = parse_only(ap, a.only)
    cfg = load_tf_roles()
    role_only = []  # empty = every active role in ROLE_TASKS
    for t in [x.strip() for x in a.team.split(",") if x.strip()]:
        if t not in cfg["teams"]:
            ap.error(f"unknown team: {t}")
        if t in BENCH_EXCLUDED_TEAMS:  # has its own suite; skipped here
            print(f"skip team {t}: not part of the model benchmark", flush=True)
            continue
        role_only += [r for r in cfg["teams"][t]["roles"] if r in cfg["roles"] and r in ROLE_TASKS and r not in role_only]
    if a.team.strip() and not role_only:  # every requested team was excluded: never fall back to all roles
        ap.error("no benchmark team left to run after excluding " + ", ".join(sorted(BENCH_EXCLUDED_TEAMS)))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    data = {"tag": a.tag, "stamp": stamp, "n": a.n, "results": {},
            "env": bench_env.capture_env(), "task_timeout": bench_env.task_timeout(_ENV_AT_START, TASK_TIMEOUT_DEFAULT)}
    # Parameter counts come from Ollama before any case runs, one model at a time, so a missing model shows up now.
    for role in ("builder", "thinker"):
        model = os.getenv(f"TOKENFRUGAL_MODEL_{role.upper()}", "")
        size = bench_csv.ollama_params(model, OLLAMA_URL)
        data.setdefault("model_params", {})[role] = size
        print(f"params {role} {model or '(default)'}: {size or 'not reported by endpoint'}", flush=True)
    sampler = bench_env.HardwareSampler(interval=2.0)
    sampler.start()
    async def _roles(n):
        return await bench_roles(n, role_only or None)

    fns = {"roles": _roles, "context": bench_context, "concurrency": bench_concurrency, "resume": bench_resume,
           "plan": bench_plan, "resources": bench_resources}
    OUT.mkdir(exist_ok=True)
    for s in SECTIONS:
        if s not in want:
            continue
        print(f"== {s}", flush=True)
        t = time.perf_counter()
        try:
            # Hang safety net: a section that exceeds section_timeout(n) is recorded as failed and the run moves on.
            # bench_output is blocking, so it runs in a thread; a timed-out thread is left to finish on its own.
            limit = section_timeout(a.n)
            run = asyncio.to_thread(bench_output, a.n) if s == "output" else fns[s](a.n)
            data["results"][s] = await asyncio.wait_for(run, limit)
        except asyncio.TimeoutError:
            data["results"][s] = {"error": f"no result after {limit:g}s (section watchdog)"}
        except Exception as e:  # noqa: BLE001
            data["results"][s] = {"error": f"{type(e).__name__}: {e}"}
        print(f"== {s} done in {time.perf_counter() - t:.0f}s", flush=True)
        print(f"tail: {s} summarising hardware", flush=True)
        data["hardware"] = sampler.summary()
        data["hardware_samples"] = sampler.samples
        print(f"tail: {s} writing section json", flush=True)
        (OUT / f"{stamp}-{a.tag}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
        print(f"tail: {s} json written", flush=True)
    print("tail: stopping hardware sampler", flush=True)
    sampler.stop()
    print("tail: sampler stopped", flush=True)
    data["meta"] = {"endpoint": OLLAMA_URL, "temperature": LLM_TEMPERATURE,"temperature_omitted": sorted(loop._NO_TEMP),
                    "thinking": THINK_LEVEL, "thinking_refused": sorted(loop._NO_THINK),
                    "max_tokens": 2048, "builder": os.getenv("TOKENFRUGAL_MODEL_BUILDER", ""),
                    "thinker": os.getenv("TOKENFRUGAL_MODEL_THINKER", ""),
                    "git_sha": sh(["git", "rev-parse", "--short", "HEAD"]).strip()}
    print("tail: meta done", flush=True)
    data["hardware"] = sampler.summary()
    data["hardware_samples"] = sampler.samples
    (OUT / f"{stamp}-{a.tag}.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    print("tail: final json written", flush=True)
    (OUT / f"{stamp}-{a.tag}.md").write_text(markdown(data), encoding="utf-8")
    print("tail: md written", flush=True)
    print("wrote", OUT / f"{stamp}-{a.tag}.md", flush=True)


if __name__ == "__main__":
    for s in (sys.stdout, sys.stderr):  # piped Windows consoles default to cp1252 and die on model output like U+2011
        s.reconfigure(encoding="utf-8", errors="replace")
    # Dump every thread's stack to the log every 15 min, so a hang shows where it is stuck.
    faulthandler.dump_traceback_later(900, repeat=True)
    # asyncio.run() waits for leftover tasks and executor threads at shutdown. On Windows a stuck subprocess or
    # worker blocks that wait forever after the results are on disk, so exit directly once main() has returned.
    loop_ = asyncio.new_event_loop()
    asyncio.set_event_loop(loop_)
    loop_.run_until_complete(main())
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)
    faulthandler.cancel_dump_traceback_later()
