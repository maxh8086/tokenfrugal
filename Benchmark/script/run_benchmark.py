"""Benchmark local models on this machine and append the result to Benchmark/results/benchmark.csv.

    python Benchmark/script/run_benchmark.py <builder-model> [thinker-model] [--n 2] [--tag NAME]
    python Benchmark/script/run_benchmark.py --from-json bench/<stamp>-<tag>.json [--hard-json F] [--coding-json F]

Step 1 runs scripts.bench (16 real-world cases, output verified), step 2 runs the hard thinker suite
(5 cases) and, with --coding, the L1-L6 coding suite, all before anything is written. Step 3 writes each test's rows to its own
detail file (builder.csv, coder.csv, thinker.csv, hard_test.csv) and then rebuilds the model's summary row in
benchmark.csv. Layout and rules: Benchmark/results/LAYOUT.md; the registry is store.TESTS.
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts"))

import bench_csv  # noqa: E402
import csvstore  # noqa: E402
import hardware  # noqa: E402
import modelinfo  # noqa: E402
import store  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("builder", nargs="?")
ap.add_argument("thinker", nargs="?")
ap.add_argument("--n", type=int, default=3)
ap.add_argument("--tag")
ap.add_argument("--csv", default=str(HERE.parent / "results" / "benchmark.csv"))
ap.add_argument("--endpoint", help="OpenAI-compatible base URL (default: TOKENFRUGAL_LLM_URL / local Ollama)")
ap.add_argument("--api-key-env", help="name of the env var holding the endpoint API key (value is never printed)")
ap.add_argument("--no-hard", action="store_true", help="skip the hard thinker suite that normally follows the 48-case run")
ap.add_argument("--coding", action="store_true", help="after the run, also run the L1-L6 coding suite (sandbox run_tests; needs Docker)")
ap.add_argument("--from-json", help="skip the run and import an existing bench JSON")
ap.add_argument("--hard-json", help="import this suite JSON instead of running the suite (needs --from-json)")
ap.add_argument("--coding-json", help="import this suite JSON instead of running the suite (needs --from-json)")
a = ap.parse_args()
if (a.hard_json or a.coding_json) and not a.from_json:
    ap.error("--hard-json and --coding-json need --from-json")

# Bump when cases, scoring or router/harness behaviour change; rows with different values are not comparable.
HARNESS_VERSION = "1"
# Router tool-loop generation. Rows written before this column existed are read as "1" (csvstore.COLUMN_DEFAULTS).
LOOP_VERSION = "2"
LOCAL = ("localhost", "127.0.0.1", "[::1]", "host.docker.internal")
PROFILES = ("analyze", "browser", "build-data", "build", "debug", "design", "docs", "security")
SUITE_DIR = HERE.parent / "results" / "raw" / "suites"  # suite JSONs written by run_suite(); a subfolder, so raw/*.json globs are unaffected


def run_suite(suite, out_dir, tag, env, n):
    """Run one suite (hard or coding) through scripts.bench. Returns the JSON it wrote in this run, or None (WARNING printed)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    proc = subprocess.run([sys.executable, "-m", "scripts.bench", "--only", "realworld", "--n", str(n), "--tag", tag],
                          cwd=ROOT, env={**env, "BENCH_SUITE": suite, "BENCH_OUT_DIR": str(out_dir)}, check=False)
    if proc.returncode != 0:
        print(f"WARNING: {suite} suite exited {proc.returncode}; its {suite}_* columns are left blank")
        return None
    hits = sorted((p for p in out_dir.glob(f"*-{tag}.json") if p.stat().st_mtime >= started - 1), key=lambda p: p.stat().st_mtime)
    if not hits:
        print(f"WARNING: {suite} suite wrote no JSON for tag {tag} in {out_dir}; its {suite}_* columns are left blank")
        return None
    return hits[-1]


def run_cmd(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout + r.stderr
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def synaptree_state():
    """(running, StartedAt) of the synaptree MCP container; (False, "") when it is missing."""
    rc, out = run_cmd(["docker", "inspect", "-f", "{{.State.Running}} {{.State.StartedAt}}", "synaptree-synaptree-1"])
    if rc != 0:
        return False, ""
    running, _, started = out.strip().partition(" ")
    return running == "true", started


def run_verdict(before, after, returncode):
    """None when the run may be appended to the CSV, else the reason it must not be."""
    if not after[0] or after[1] != before[1]:
        return "synaptree container changed during the run"
    if returncode != 0:
        return f"bench exited with code {returncode}"
    return None


def mount_ok(shown: str, workspace: str) -> bool:
    """True when every `docker mcp profile show` mount line points at `workspace` (slash/case-insensitive)."""
    norm = lambda t: t.replace("\\", "/").lower().rstrip("/")  # noqa: E731
    want = norm(workspace) + ":/workspace"
    return want in norm(shown).replace(" ", "")


FAILURE_KINDS = ("no-tools", "no-tool-call", "timeout", "infra", "wrong-answer", "other")  # ties resolve in this order
TIMEOUT_MARKERS = ("TimeoutError", "APITimeoutError", "timed out", "watchdog")  # same markers as scripts/bench_real.py


def tool_support(endpoint, key, model):
    """("ok" | "no-tools" | "error", text) from one chat request with a dummy tool, sent like the bench sends its own.
    Only an HTTP 400 whose body says the model does not support tools yields "no-tools". Any other failure is
    "error": reported, but it does not skip the model's runs."""
    from openai import OpenAI
    client = OpenAI(base_url=endpoint, api_key=key or "x", timeout=60, max_retries=0)
    tool = {"type": "function", "function": {"name": "noop", "description": "Does nothing.",
                                             "parameters": {"type": "object", "properties": {}}}}
    try:
        client.chat.completions.create(model=model, messages=[{"role": "user", "content": "Reply with ok."}],
                                       tools=[tool], max_tokens=8)
        return "ok", ""
    except Exception as e:  # noqa: BLE001
        text = f"{type(e).__name__}: {str(e)[:300]}"
        if getattr(e, "status_code", None) == 400 and "does not support tools" in str(e).lower():
            return "no-tools", text
        return "error", text


def run_failure_kind(run):
    """Kind of one failed run (None when it passed). Reads the run dicts scripts/bench_real.py writes."""
    if run.get("verified"):
        return None
    error = str(run.get("error") or "")
    text = f"{error} {run.get('note') or ''}".lower()
    if run.get("status") == "no-tools":
        return "no-tools"
    if run.get("status") == "infra" or error.startswith("infra:") or "ollama 500" in text:
        return "infra"
    if run.get("status") == "timeout" or any(m.lower() in text for m in TIMEOUT_MARKERS):
        return "timeout"
    if run.get("ok"):
        return "wrong-answer"  # reached a final answer, but the output did not verify
    if "tool call" in text:
        return "no-tool-call"
    return "other"


def failure_kind(cases):
    """One value per row: the most common kind among failed runs (ties follow FAILURE_KINDS), "ok" when none failed."""
    counts = dict.fromkeys(FAILURE_KINDS, 0)
    for c in cases.values():
        if not isinstance(c, dict):  # skips a section-level {"error": ...} entry
            continue
        for r in c.get("runs", []):
            k = run_failure_kind(r)
            if k:
                counts[k] += 1
    if not any(counts.values()):
        return "ok"
    return max(FAILURE_KINDS, key=lambda k: counts[k])


def write_no_tools_raw(raw, tag, n, builder, thinker, endpoint, errors):
    """Synthetic raw result for a model without tool support: every realworld case is status "no-tools"
    (not a quality failure, it never ran). Same shape as scripts.bench output, so bench_csv and the CSV row work unchanged."""
    from router.config import LLM_TEMPERATURE
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    err = " | ".join(f"{m}: {t}" for m, t in errors.items())
    cases = {}
    for cid, _, _ in bench_csv.LAYOUT:
        runs = [{"run": i + 1, "start": "", "end": "", "s": 0.0, "ok": False, "verified": False, "status": "no-tools",
                 "dispatched": False, "error": err, "note": err, "peak": 0, "input": 0, "output": 0, "timeout_s": None}
                for i in range(n)]
        cases[cid] = {"verified": f"0/{n}", "ran": f"0/{n}", "status": "no-tools", "infra_runs": 0, "s": None,
                      "peak": 0, "input": 0, "output": 0, "timeout_s": None, "notes": err, "runs": runs}
    data = {"stamp": stamp, "tag": tag, "n": n,
            "meta": {"endpoint": endpoint, "temperature": LLM_TEMPERATURE, "max_tokens": 2048,
                     "builder": builder, "thinker": thinker, "git_sha": ""},
            "results": {"realworld": cases}}
    path = raw / f"{stamp}-{tag}.json"
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return path


def preflight(endpoint, key, models):
    """Every check prints PASS/FAIL with the fix; one FAIL stops the run before any model call."""
    bad = []

    def check(name, good, fix=""):
        print(f"  {'PASS' if good else 'FAIL'}  {name}" + ("" if good else f"  -> {fix}"))
        if not good:
            bad.append(name)

    print("preflight")
    from router.config import LLM_TEMPERATURE
    check(f"LOCAL_LLM_TEMPERATURE = {LLM_TEMPERATURE} (benchmarks need 0.0)", LLM_TEMPERATURE == 0.0,
          "set LOCAL_LLM_TEMPERATURE=0.0 in .env (or unset it) and rerun")
    rc, _ = run_cmd(["docker", "info"])
    check("docker daemon", rc == 0, "start Docker Desktop")
    rc, out = run_cmd(["docker", "mcp", "profile", "ls"])
    have = {p for p in PROFILES if p in out}
    check(f"docker mcp profiles ({len(have)}/{len(PROFILES)})", rc == 0 and have == set(PROFILES),
          "python scripts/install_profiles.py")
    # bench cases address files as /workspace/<project>/..., so the profiles must mount the parent folder
    from router.profile_sync import ensure_profiles
    ws = ROOT.parent.as_posix()
    ensure_profiles(ws)
    shown = {p: run_cmd(["docker", "mcp", "profile", "show", p])[1] for p in PROFILES}
    wrong = [p for p, t in shown.items() if ":/workspace" in t.replace("\\", "/") and not mount_ok(t, ws)]
    check(f"profile mounts -> {ws}:/workspace", not wrong, f"python scripts/install_profiles.py --workspace {ws} (bad: {', '.join(wrong)})")
    try:
        socket.create_connection(("127.0.0.1", 7697), 3).close()
        up = True
    except OSError:
        up = False
    check("neo4j plan store 127.0.0.1:7697", up, "scripts/mcp_up.ps1")
    s_up, s_started = synaptree_state()
    check("synaptree container synaptree-synaptree-1 running" + (f" (started {s_started})" if s_up else ""), s_up,
          "docker start synaptree-synaptree-1 (or start the synaptree plugin)")
    try:
        socket.create_connection(("127.0.0.1", 17687), 3).close()
        s_neo = True
    except OSError:
        s_neo = False
    check("synaptree neo4j 127.0.0.1:17687", s_neo, "start the synaptree compose project (its Neo4j)")
    ids = []
    try:
        rq = urllib.request.Request(endpoint.rstrip("/") + "/models", headers={"Authorization": f"Bearer {key or 'x'}", "x-api-key": key or "x",
                                                           "anthropic-version": "2023-06-01"})
        ids = [m["id"] for m in json.load(urllib.request.urlopen(rq, timeout=20)).get("data", [])]
        check(f"llm endpoint {endpoint}", True)
    except Exception as e:  # noqa: BLE001
        check(f"llm endpoint {endpoint}", False, f"{type(e).__name__}: {str(e)[:80]}; check the URL and key env")
    if ids:
        for m in dict.fromkeys(models):
            check(f"model {m}", m in ids, "pull or enable it on the endpoint")
            print(f"        params: {bench_csv.ollama_params(m, endpoint) or 'not reported'}")
    if bad:
        sys.exit(f"preflight failed: {', '.join(bad)}")

no_tools = {}  # model -> error text, for models the endpoint refuses tools to; their runs are skipped
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
           "CC_WORKSPACE": ROOT.parent.as_posix(), "TOKENFRUGAL_MODEL_BUILDER": a.builder, "TOKENFRUGAL_MODEL_THINKER": thinker}
    if a.endpoint:
        env["TOKENFRUGAL_LLM_URL"] = a.endpoint
    if a.api_key_env:
        key = os.environ.get(a.api_key_env)
        if not key:
            sys.exit(f"{a.api_key_env} is not set in your shell")
        env["TOKENFRUGAL_LLM_API_KEY"] = key
    endpoint = a.endpoint or os.environ.get("TOKENFRUGAL_LLM_URL") or "http://localhost:11434/v1"
    key = env.get("TOKENFRUGAL_LLM_API_KEY") or os.environ.get("TOKENFRUGAL_LLM_API_KEY")
    preflight(endpoint, key, [a.builder, thinker])
    print("tool support")
    for m in dict.fromkeys([a.builder, thinker]):
        state, text = tool_support(endpoint, key, m)
        if state == "no-tools":
            no_tools[m] = text
        label = {"ok": "PASS", "no-tools": "NO-TOOLS", "error": "WARN"}[state]
        print(f"  {label}  {m}" + ("" if state == "ok" else f"  -> {text}"))
    if no_tools:
        src = write_no_tools_raw(raw, tag, a.n, a.builder, thinker, endpoint, no_tools)
        print(f"skipping the runs (no tool support); recorded as no-tools in {src}")
    else:
        before = synaptree_state()
        proc = subprocess.run([sys.executable, "-m", "scripts.bench", "--only", "realworld", "--n", str(a.n), "--tag", tag],
                              cwd=ROOT, env=env, check=False)
        after = synaptree_state()
        verdict = run_verdict(before, after, proc.returncode)
        if verdict:
            if not after[0] or after[1] != before[1]:
                print(f"WARNING: synaptree container changed during the run (StartedAt {before[1] or 'n/a'} -> "
                      f"{after[1] or 'n/a'}, running={after[0]}). synaptree-role cases (builder, reviewer, debugger, "
                      "analyzer: cases 1-7 and 9) are unreliable.")
                sys.exit(f"nothing written to the CSV. Raw JSON kept in {raw} (tag {tag}); review it, then import with "
                         f"--from-json once the synaptree container is stable.")
            sys.exit(f"bench exited with code {proc.returncode}; nothing written to the CSV. Raw JSON (if any) kept in {raw} (tag {tag}).")
        hits = sorted(raw.glob(f"*-{tag}.json"), key=lambda p: p.stat().st_mtime)
        if not hits:
            sys.exit(f"bench wrote no result file for tag {tag}")
        src = hits[-1]

# Suites run before anything is written, so all four tests are written and summarised together.
hard_src = coding_src = None
if not a.from_json:
    hard_tag = ("hard-" + thinker.replace(":", "-").replace("/", "-"))[:50]
    code_tag = ("coding-" + a.builder.replace(":", "-").replace("/", "-"))[:50]
    if not a.no_hard and not no_tools:
        hard_src = run_suite("hard", SUITE_DIR, hard_tag, env, a.n)
    if a.coding and not no_tools:
        coding_src = run_suite("coding", SUITE_DIR, code_tag, env, a.n)
else:
    hard_src = Path(a.hard_json) if a.hard_json else None
    coding_src = Path(a.coding_json) if a.coding_json else None

data = json.loads(src.read_text(encoding="utf-8"))
out = bench_csv.rows(data)
if not out:
    sys.exit(f"no realworld results in {src}")
row = out[0]
if not row[1]:  # older raw JSON without model_params: ask Ollama now
    row[1] = bench_csv.ollama_params(data.get("meta", {}).get("builder", ""), data.get("meta", {}).get("endpoint") or a.endpoint or "")
score, mx = row[2].split("/")
ran = row[3].split("/")[0]
hwi = hardware.info()
hw = hwi["id"]
meta = data.get("meta", {})
endpoint = meta.get("endpoint") or a.endpoint or ""
if endpoint and not any(h in endpoint for h in LOCAL):
    hw = "cloud:" + endpoint.split("//")[-1].split("/")[0]  # not this machine's GPU
real = data["results"]["realworld"]
done = [real[cid] for cid, _, _ in bench_csv.LAYOUT if cid in real]
temp = "omitted (rejected by model)" if meta.get("temperature_omitted") else meta.get("temperature", "")
stamp = data.get("stamp", "")
date = datetime.strptime(stamp, "%Y%m%d-%H%M%S").isoformat(timespec="seconds") if stamp else ""
def _peak_ram(d):
    m = ((d.get("hardware") or {}).get("ollama_ram_mib") or {}).get("max")
    return round(m / 1024, 1) if m else ""


rec = {"model": row[0], "params": row[1], "score": score, "max": mx, "ran": ran, "mean_s_per_case": row[4],
       "date": date, "endpoint": endpoint, "temperature": temp, "max_tokens": meta.get("max_tokens", ""),
       "builder_model": meta.get("builder", ""), "thinker_model": meta.get("thinker", ""),
       "git_sha": meta.get("git_sha", ""), "harness_version": HARNESS_VERSION, "loop_version": LOOP_VERSION,
       "failure_kind": failure_kind(real), "n": data.get("n", ""),
       "context_used_peak_tokens": max([c.get("peak", 0) for c in done] or [0]),
       "tokens_in_per_run": sum(c.get("input", 0) for c in done),
       "tokens_out_per_run": sum(c.get("output", 0) for c in done),
       "peak_model_ram_gb": _peak_ram(data),
       "os": hwi["os"], "cpu": hwi["cpu"], "cores": hwi["cores"] or "", "ram_gb": hwi["ram_gb"] or "",
       "gpu": hwi["gpu"], "vram_gb": hwi["vram_gb"] or "", "ollama_version": hwi["ollama"], "hardware_id": hw}
# valid_cases / infra_cases / mean_s_valid: see bench_csv.status_scores (infra cases excluded from validity and mean)
rec["valid_cases"], rec["infra_cases"], rec["mean_s_valid"] = bench_csv.status_scores(real)
rec["valid_cases"] -= sum(c.get("status") == "no-tools" for c in real.values())  # never ran: not a valid case
rec["total_s"] = bench_csv.total_seconds(real)  # elapsed time of all repeats, timeouts and infra included
mi = modelinfo.info(meta.get("builder") or row[0], endpoint, rec["context_used_peak_tokens"])
rec.update(mi)
rec["raw_json"] = src.name

# Every test in store.TESTS gets its rows from the file that ran its suite. All rows share the realworld stamp as
# run_id, so summarize() sees one run. A missing suite file gives no rows: that test's score stays blank.
dst = Path(a.csv)
results_dir = dst.parent
sources = {"realworld": src, "hard": hard_src, "coding": coding_src}
run_cols = {k: rec[k] for k in store.RUN_COLS if k in rec and k not in ("score", "max", "mean_s_per_case")}
new_rows = []
for name, t in store.TESTS.items():
    jp = sources.get(t["suite"])
    if jp is None:
        print(f"{name}: suite {t['suite']} not run; no rows written")
        continue
    model = rec["builder_model"] if t["role"] == "builder" else rec["thinker_model"]
    new_rows += store.suite_detail(jp, t["role"], t["suite"], t["cases"], run_id=stamp, model=model, run_cols=run_cols)
try:
    for file_name, rows in store.route(new_rows).items():
        backup, marked = store.publish_detail(results_dir / file_name, rows)
        print(f"{file_name}: {len(rows)} rows written, {marked} older run(s) marked superseded"
              + (f", backup: {backup}" if backup else ""))
    summary = store.summarize({"builder": rec["builder_model"], "thinker": rec["thinker_model"]},
                              store.load_details(results_dir))
    config = {
        "model": rec["model"], "params": rec["params"], "endpoint": endpoint, "temperature": temp,
        "harness_version": HARNESS_VERSION, "loop_version": LOOP_VERSION, "compression_level": mi.get("compression_level", ""),
        "valid_cases": rec["valid_cases"], "ran": ran,
        "context_used_peak_tokens": rec["context_used_peak_tokens"],
        "gpu_memory_capacity": hwi["vram_gb"] or "", "gpu_memory_used_gb": mi.get("gpu_memory_used_gb", ""),
        "system_ram_gb": hwi["ram_gb"] or "", "shared_system_memory_capacity_gb": mi.get("shared_system_memory_gb", ""),
        "shared_system_memory_used_gb": mi.get("shared_system_memory_gb", ""),  # same source, per user decision
        "peak_model_ram_gb": rec["peak_model_ram_gb"],
        "raw_json": src.name, "builder_model": rec["builder_model"], "thinker_model": rec["thinker_model"],
    }
    backup, _ = store.upsert_summary(dst, summary, config)
except csvstore.CsvSchemaError as e:
    sys.exit(f"CSV NOT WRITTEN (summary unchanged; detail rows may be in {results_dir}; run kept in {src}): {e}")
csvstore.log_run(results_dir / "runs.jsonl", rec)
if backup:
    print(f"backup: {backup}")
print(f"summary {rec['model']}: total {summary['total_score'] or 'blank'}, median {summary['median_s'] or 'blank'} s, "
      f"{summary['mean_s_per_case'] or 'blank'} s/case, peak ctx {rec['context_used_peak_tokens']} tokens on {hw} -> {dst}")
for name, t in store.TESTS.items():
    print(f"{name}: {summary[t['score']] or 'blank'} ({sources.get(t['suite']) or 'not run'})")
