"""Cloud baseline: run the 16-case real-world suite on claude-haiku-4-5 through the Messages API with local stand-in tools.
Never ranked. Cases that need a service the stand-ins lack (design, browser, tracker) are written as status `n/a`.
Usage: python -m scripts.haiku_run [--case ID] [--n 3] [--out Benchmark/results/cloud_runs.csv]
The key comes from ANTHROPIC_API_KEY, else the Windows User env var; it is never printed."""
import argparse
import csv
import json
import os
import re
import subprocess
import time
import urllib.request
from pathlib import Path

from scripts import bench_real as b

MODEL = "claude-haiku-4-5"
URL = "https://api.anthropic.com/v1/messages"
MAX_STEPS = 8
NOT_AVAILABLE = {"role_designer", "role_browser", "role_tracker"}
FIELDS = ["model", "case", "run", "verified", "status", "seconds", "tokens_in", "tokens_out", "note"]
ROOT = b.ROOT
LOCAL = str(b.SCRATCH).replace("\\", "/")


def api_key():
    k = os.getenv("ANTHROPIC_API_KEY")
    if not k and os.name == "nt":
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "[Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')"],
                             capture_output=True, text=True).stdout
        k = out.strip()
    if not k:
        raise SystemExit("ANTHROPIC_API_KEY not set (env or Windows User variable)")
    return k


def localize(task):
    return task.replace(b.WS, LOCAL).replace(f"/workspace/{b.SYNAPTREE_PROJECT}", str(ROOT).replace("\\", "/"))


def _path(p):
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def run_tool(name, a):
    try:
        if name == "read_file":
            return _path(a["path"]).read_text(encoding="utf-8")[:20000]
        if name == "write_file":
            p = _path(a["path"])
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(a["content"], encoding="utf-8")
            return "ok"
        if name == "edit_file":
            p = _path(a["path"])
            t = p.read_text(encoding="utf-8")
            if a["old"] not in t:
                return "error: old text not found"
            p.write_text(t.replace(a["old"], a["new"], 1), encoding="utf-8")
            return "ok"
        if name == "list_directory":
            return "\n".join(sorted(x.name for x in _path(a["path"]).iterdir()))
        if name == "search_graph":  # stand-in: grep for a def/class line
            pat = re.compile(rf"^\s*(def|class)\s+{re.escape(a['name'])}\b")
            hits = [f"{f.relative_to(ROOT)}:{i}" for f in ROOT.rglob("*.py") if ".venv" not in f.parts
                    for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1)
                    if pat.match(line)]
            return "\n".join(hits[:20]) or "no match"
        if name == "crawl_markdown":
            return urllib.request.urlopen(a["url"], timeout=20).read().decode("utf-8", "ignore")[:6000]
    except Exception as e:
        return f"error: {e}"
    return f"error: unknown tool {name}"


def _tool(tool, desc, *props):
    return {"name": tool, "description": desc, "input_schema": {
        "type": "object", "properties": {k: {"type": "string"} for k in props}, "required": list(props)}}


TOOLS = [_tool("read_file", "Read a text file.", "path"),
         _tool("write_file", "Write a file.", "path", "content"),
         _tool("edit_file", "Replace the first occurrence of old with new.", "path", "old", "new"),
         _tool("list_directory", "List a directory.", "path"),
         _tool("search_graph", "Find where a function or class is defined.", "name"),
         _tool("crawl_markdown", "Fetch a URL as text.", "url")]


def http_call(key, payload):
    req = urllib.request.Request(URL, json.dumps(payload).encode(), {
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))


def run_case(task, call, tools=run_tool):
    """call(payload) -> API response dict. Returns (answer_text, tokens_in, tokens_out, steps)."""
    msgs, tin, tout, text = [{"role": "user", "content": task}], 0, 0, ""
    for step in range(MAX_STEPS):
        r = call({"model": MODEL, "max_tokens": 2048, "tools": TOOLS, "messages": msgs})
        tin += r["usage"]["input_tokens"]
        tout += r["usage"]["output_tokens"]
        msgs.append({"role": "assistant", "content": r["content"]})
        text = "".join(c.get("text", "") for c in r["content"] if c["type"] == "text")
        uses = [c for c in r["content"] if c["type"] == "tool_use"]
        if not uses:
            return text, tin, tout, step + 1
        msgs.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": u["id"], "content": tools(u["name"], u["input"])} for u in uses]})
    return text, tin, tout, MAX_STEPS


def one(case, call):
    cid, _agent, setup, task, check = case
    if cid in NOT_AVAILABLE:
        return dict(case=cid, verified="", status="n/a", seconds=0, tokens_in=0, tokens_out=0,
                    note="needs a service with no cloud stand-in")
    b.SCRATCH.mkdir(parents=True, exist_ok=True)
    b._clean_scratch()  # no leftovers from the previous repeat or case, same as the bench loop
    setup()
    t0 = time.time()
    try:
        ans, tin, tout, _ = run_case(localize(task), call)
        ok, note = check(ans)
        status = "ok" if ok else "fail"
    except Exception as e:
        ok, note, tin, tout, status = False, str(e)[:120], 0, 0, "error"
    return dict(case=cid, verified=int(bool(ok)), status=status, seconds=round(time.time() - t0, 1),
                tokens_in=tin, tokens_out=tout, note=str(note)[:120].replace("\n", " "))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--case")
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--out", default=str(ROOT / "Benchmark" / "results" / "cloud_runs.csv"))
    a = ap.parse_args(argv)
    key = api_key()

    def call(payload):
        return http_call(key, payload)

    cases = [c for c in b.active_cases() if not a.case or c[0] == a.case]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    new = not out.exists()
    with out.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        for c in cases:
            for i in range(1, (1 if c[0] in NOT_AVAILABLE else a.n) + 1):
                row = dict(model=MODEL, run=i, **one(c, call))
                w.writerow(row)
                f.flush()
                print(c[0], i, row["status"], row["verified"], row["note"][:60])


if __name__ == "__main__":
    main()
