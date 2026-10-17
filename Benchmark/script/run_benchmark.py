"""Benchmark local models on this machine and append the result to Benchmark/results/benchmark.csv.

    python Benchmark/script/run_benchmark.py <builder-model> [thinker-model] [--n 2] [--tag NAME]
    python Benchmark/script/run_benchmark.py --from-json bench/<stamp>-<tag>.json

Step 1 runs scripts.bench (16 real-world cases, output verified), step 2 flattens the JSON into
one CSV row. The CSV is the source of truth; run build_report.py afterwards,
then have a cloud model review the CSV and update Observations in Benchmark.md (see README.md).
"""
import argparse
import csv
import json
import os
import socket
import subprocess
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "scripts"))

import bench_csv  # noqa: E402
import hardware  # noqa: E402
import modelinfo  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("builder", nargs="?")
ap.add_argument("thinker", nargs="?")
ap.add_argument("--n", type=int, default=3)
ap.add_argument("--tag")
ap.add_argument("--csv", default=str(HERE.parent / "results" / "benchmark.csv"))
ap.add_argument("--endpoint", help="OpenAI-compatible base URL (default: TOKENFRUGAL_LLM_URL / local Ollama)")
ap.add_argument("--api-key-env", help="name of the env var holding the endpoint API key (value is never printed)")
ap.add_argument("--from-json", help="skip the run and import an existing bench JSON")
a = ap.parse_args()

# Bump when cases, scoring or router/harness behaviour change; rows with different values are not comparable.
HARNESS_VERSION = "1"
LOCAL = ("localhost", "127.0.0.1", "[::1]", "host.docker.internal")
PROFILES = ("analyze", "browser", "build-data", "build", "debug", "design", "docs", "security")
EXTRA = ["tag", "params", "score", "max", "ran", "mean_s_per_case"]
META = ["date", "endpoint", "temperature", "max_tokens", "builder_model", "thinker_model", "git_sha", "harness_version", "n",
        "context_used_peak_tokens", "tokens_in_per_run", "tokens_out_per_run",
        "compression_level", "model_file_size_gb", "context_window_tokens", "model_max_context_tokens", "gpu_memory_used_gb", "shared_system_memory_gb", "peak_model_ram_gb",
        "valid_cases", "infra_cases", "mean_s_valid", "total_s",
        "os", "cpu", "cores", "ram_gb", "gpu", "vram_gb", "ollama_version", "hardware_id"]


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
    if bad:
        sys.exit(f"preflight failed: {', '.join(bad)}")

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
    preflight(endpoint, env.get("TOKENFRUGAL_LLM_API_KEY") or os.environ.get("TOKENFRUGAL_LLM_API_KEY"), [a.builder, thinker])
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
            sys.exit(f"not appended to CSV. Raw JSON kept in {raw} (tag {tag}); review it, then import with "
                     f"--from-json once the synaptree container is stable.")
        sys.exit(f"bench exited with code {proc.returncode}; not appended to CSV. Raw JSON (if any) kept in {raw} (tag {tag}).")
    hits = sorted(raw.glob(f"*-{tag}.json"), key=lambda p: p.stat().st_mtime)
    if not hits:
        sys.exit(f"bench wrote no result file for tag {tag}")
    src = hits[-1]

data = json.loads(src.read_text(encoding="utf-8"))
out = bench_csv.rows(data)
if not out:
    sys.exit(f"no realworld results in {src}")
row = out[0]
score, mx = row[2].split("/")
ran = row[3].split("/")[0]
hwi = hardware.info()
hw = hwi["id"]
meta = data.get("meta", {})
endpoint = meta.get("endpoint") or a.endpoint or ""
if endpoint and not any(h in endpoint for h in LOCAL):
    hw = "cloud:" + endpoint.split("//")[-1].split("/")[0]  # not this machine's GPU
real = data["results"]["realworld"]
labels = [label for _, label, _ in bench_csv.LAYOUT]
peaks = {label: real.get(cid, {}).get("peak", "") for cid, label, _ in bench_csv.LAYOUT}
done = [real[cid] for cid, _, _ in bench_csv.LAYOUT if cid in real]
temp = "omitted (rejected by model)" if meta.get("temperature_omitted") else meta.get("temperature", "")
stamp = data.get("stamp", "")
date = datetime.strptime(stamp, "%Y%m%d-%H%M%S").isoformat(timespec="seconds") if stamp else ""
def _peak_ram(d):
    m = ((d.get("hardware") or {}).get("ollama_ram_mib") or {}).get("max")
    return round(m / 1024, 1) if m else ""


rec = {"tag": row[0], "params": row[1], "score": score, "max": mx, "ran": ran, "mean_s_per_case": row[4],
       **dict(zip(labels, row[5:])),
       "date": date, "endpoint": endpoint, "temperature": temp, "max_tokens": meta.get("max_tokens", ""),
       "builder_model": meta.get("builder", ""), "thinker_model": meta.get("thinker", ""),
       "git_sha": meta.get("git_sha", ""), "harness_version": HARNESS_VERSION, "n": data.get("n", ""),
       "context_used_peak_tokens": max([c.get("peak", 0) for c in done] or [0]),
       "tokens_in_per_run": sum(c.get("input", 0) for c in done),
       "tokens_out_per_run": sum(c.get("output", 0) for c in done),
       "peak_model_ram_gb": _peak_ram(data),
       "os": hwi["os"], "cpu": hwi["cpu"], "cores": hwi["cores"] or "", "ram_gb": hwi["ram_gb"] or "",
       "gpu": hwi["gpu"], "vram_gb": hwi["vram_gb"] or "", "ollama_version": hwi["ollama"], "hardware_id": hw,
       **{f"context_used_{k}": v for k, v in peaks.items()}}
# valid_cases / infra_cases / mean_s_valid: see bench_csv.status_scores (infra cases excluded from validity and mean)
rec["valid_cases"], rec["infra_cases"], rec["mean_s_valid"] = bench_csv.status_scores(real)
rec["total_s"] = bench_csv.total_seconds(real)  # elapsed time of all repeats, timeouts and infra included
mi = modelinfo.info(meta.get("builder") or row[0], endpoint, rec["context_used_peak_tokens"])
rec.update(mi)
cols = EXTRA + labels + META + [f"context_used_{k}" for k in labels]
dst = Path(a.csv)
old = list(csv.DictReader(dst.open(encoding="utf-8"))) if dst.exists() else []
tmp = dst.with_suffix(".csv.tmp")  # write beside the target, then swap in, so a failed write never truncates the real file
with tmp.open("w", newline="", encoding="utf-8") as f:  # rewrite so legacy rows get the new columns blank
    w = csv.DictWriter(f, fieldnames=cols, restval="")
    w.writeheader()
    w.writerows(old)
    w.writerow(rec)
tmp.replace(dst)
print(f"appended {rec['tag']}: {score}/{mx} verified, {rec['mean_s_per_case']} s/case, peak ctx {rec['context_used_peak_tokens']} tokens on {hw} -> {dst}")
