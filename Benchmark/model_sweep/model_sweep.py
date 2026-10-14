"""Model sweep: one builder/analyzer task per local model through the gateway.

Usage: python -m scripts.model_sweep [--models a,b] [--roles builder,analyzer] [--out PATH]

The model for a role is pinned with TOKENFRUGAL_MODEL_<TIER>, where TIER is the
role's model tier (builder or thinker) from personas.yaml. Setting it changes every
role on that tier, so each run sets the env var and reloads the config first.
"""
import argparse
import asyncio
import csv
import os
import subprocess
import time
from pathlib import Path

from gateway.config import load_personas, resolve_role
from gateway.loop import leaf, run

CFG = load_personas()
DEFAULT_OUT = Path(r"C:\Users\vaibh\AppData\Local\Temp\claude\C--Users-vaibh-Downloads-Projects-tokenfrugal\1471e18d-f8ff-4197-ab1e-e98cf205d815\scratchpad\model_sweep.csv")
EXCLUDE = ("embed", "qwen2.5vl", "qwen2-5vl")
TIMEOUT = 240
HEADER = ["model", "role", "result", "seconds", "error"]
DEFAULT_TOOLS_OUT = DEFAULT_OUT.with_name("model_sweep_tools.csv")
TOOL_HEADER = ["model", "role", "step", "tool", "arguments", "result", "error"]

# role -> (agency-agents slug, task, answer check)
ROLES = {
    "builder": (
        "engineering-backend-architect",
        "Create file sweep_probe.txt in the workspace containing the word ok.",
        lambda out: "success" in out.lower(),
    ),
    "analyzer": (
        "engineering-software-architect",
        "Use search_graph to find function resolve_role and say which file defines it.",
        lambda out: "gateway/config.py" in out.replace("\\", "/").lower(),
    ),
}


def ollama_models() -> list[str]:
    proc = subprocess.run(["ollama", "list"], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True)
    names = [line.split()[0] for line in proc.stdout.splitlines()[1:] if line.split()]
    return [n for n in names if not any(x in n.lower() for x in EXCLUDE)]


def tool_rows(model: str, role_name: str, msgs: list) -> list:
    """One row per tool call in the run: the step it belongs to, its result, and the error text if any."""
    results = {m.get("tool_call_id"): str(m.get("content", "")) for m in msgs if m.get("role") == "tool"}
    rows, step = [], 0
    for m in msgs:
        if m.get("role") != "assistant" or not m.get("tool_calls"):
            continue
        step += 1
        for c in m["tool_calls"]:
            fn = c["function"]
            args = str(fn.get("arguments", ""))[:200]
            content = results.get(c.get("id"))
            if content is None:
                rows.append([model, role_name, step, fn["name"], args, "error", "no result"])
                continue
            failed = content.startswith("tool error") or content.startswith("LINT:")
            rows.append([model, role_name, step, fn["name"], args,
                         "error" if failed else "ok", content[:200] if failed else ""])
    return rows


async def one(model: str, role_name: str, tier: str) -> tuple[str, float, str, list]:
    agent, task, check = ROLES[role_name]
    os.environ[f"TOKENFRUGAL_MODEL_{tier.upper()}"] = model
    cfg = load_personas()  # re-read so the env override takes effect
    role = resolve_role(agent, cfg)
    t = time.time()
    try:
        out, msgs = await asyncio.wait_for(run(agent, role, task), TIMEOUT)
        ok = check(out)
        return ("PASS" if ok else "FAIL"), time.time() - t, "" if ok else "CheckFailed", tool_rows(model, role_name, msgs)
    except Exception as e:  # noqa: BLE001
        return "FAIL", time.time() - t, type(leaf(e)).__name__, []


async def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sweep local models over builder/analyzer tasks.")
    ap.add_argument("--models", help="comma-separated model tags (default: ollama list, minus embed/qwen2.5vl models)")
    ap.add_argument("--roles", default="builder,analyzer", help="comma-separated roles: builder, analyzer")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="CSV output path (appended to)")
    ap.add_argument("--tools-out", default=str(DEFAULT_TOOLS_OUT), help="per-tool-call CSV path (appended to)")
    args = ap.parse_args(argv)

    roles = [r.strip() for r in args.roles.split(",") if r.strip()]
    unknown = [r for r in roles if r not in ROLES]
    if unknown:
        ap.error(f"unknown role(s): {', '.join(unknown)}; choose from {', '.join(ROLES)}")
    models = [m.strip() for m in args.models.split(",") if m.strip()] if args.models else ollama_models()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tools_out = Path(args.tools_out)
    write_header = not out.exists() or out.stat().st_size == 0
    write_tool_header = not tools_out.exists() or tools_out.stat().st_size == 0
    with out.open("a", newline="", encoding="utf-8") as fh, tools_out.open("a", newline="", encoding="utf-8") as tfh:
        w = csv.writer(fh)
        tw = csv.writer(tfh)
        if write_header:
            w.writerow(HEADER)
            fh.flush()
        if write_tool_header:
            tw.writerow(TOOL_HEADER)
            tfh.flush()
        for model in models:
            for role_name in roles:
                tier = CFG["roles"][resolve_role(ROLES[role_name][0], CFG)["role"]]["model"]
                result, secs, err, rows = await one(model, role_name, tier)
                w.writerow([model, role_name, result, f"{secs:.1f}", err])
                fh.flush()
                tw.writerows(rows)
                tfh.flush()
                print(f"{result} {model} {role_name} {secs:.1f}s {err} tool_calls={len(rows)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
