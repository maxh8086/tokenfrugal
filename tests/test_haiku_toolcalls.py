"""Haiku tool-call verification: can Haiku call every router tool and every allowlisted role tool?

Offline part (always runs): the router exposes exactly the expected tools and each has a valid schema.
Live part: needs ANTHROPIC_API_KEY (Haiku via the Messages API; model from HAIKU_MODEL, default claude-haiku-5-5).
  Router tools: Haiku is offered all router tools and must pick the right one with schema-valid args.
  Role tools (--roles / HAIKU_TEST_ROLES=1, needs Docker): each role's profile is opened through the Docker MCP
  gateway; every allowlisted tool must be listed and Haiku must call it correctly when offered the role's tools.

Run as a script:  .venv/Scripts/python.exe tests/test_haiku_toolcalls.py [--roles] [--tool NAME]
Exit 0 = all PASS, 1 = any FAIL, 2 = live prerequisites missing (nothing was verified).
"""
import asyncio
import json
import os
import shutil
import sys
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import jsonschema  # noqa: E402  (installed with mcp)

HAIKU_MODEL = os.getenv("HAIKU_MODEL", "claude-haiku-5-5")
API_URL = "https://api.anthropic.com/v1/messages"

# tool -> (prompt that needs this tool, argument check). Haiku only *calls* the tools here (call correctness);
# nothing is dispatched, so no local model or Neo4j is needed.
ROUTER_CASES = {
    "dispatch_task": ("Have the local agent engineering-code-reviewer check README.md for typos.",
                      lambda a: a.get("agent") == "engineering-code-reviewer" and bool(a.get("task"))),
    "ask_followup": ("Ask task abc123 this follow-up: which file did you change?",
                     lambda a: a.get("task_id") == "abc123" and bool(a.get("question"))),
    "get_detail": ("Fetch the full stored output of task abc123.", lambda a: a.get("task_id") == "abc123"),
    "resume_task": ("Task abc123 failed; retry it from its saved conversation.", lambda a: a.get("task_id") == "abc123"),
    "list_roles": ("Show which roles, models and tool allowlists exist.", lambda a: True),
    "plan_add": ("Add a plan task titled 'write unit tests' that depends on task 3.",
                 lambda a: "tests" in str(a.get("title", "")).lower() and 3 in (a.get("depends") or [])),
    "plan_overview": ("Show the current plan state.", lambda a: True),
    "plan_revert": ("Undo the latest status change of plan task 7.", lambda a: a.get("task_id") == 7),
    "plan_update_from": ("Plan task 5 changed approach; re-open it and its dependants.", lambda a: a.get("task_id") == 5),
}


def _post(body: dict) -> dict:
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(), method="POST", headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01",
        "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def haiku_pick(prompt: str, tools: list) -> tuple:
    """One Haiku turn with tool_choice=any. Returns (tool name, input), or ('', {}) when Haiku wrote text instead."""
    res = _post({"model": HAIKU_MODEL, "max_tokens": 512, "tools": tools, "tool_choice": {"type": "any"},
                 "messages": [{"role": "user", "content": prompt}]})
    for b in res.get("content", []):
        if b.get("type") == "tool_use":
            return b["name"], b.get("input") or {}
    return "", {}


def anthropic_tool(name: str, desc: str, schema: dict) -> dict:
    return {"name": name, "description": (desc or name)[:1000],
            "input_schema": schema or {"type": "object", "properties": {}}}


def cli_haiku_pick(prompt: str, tools: list) -> tuple:
    """Haiku through `claude -p` and the repo .mcp.json (real router, no API key).

    No --allowedTools is passed, so the call is attempted and denied by permissions: the tool_use event proves
    Haiku chose and shaped the call, and nothing is dispatched. Returns (router tool name, input) or ('', {}).
    """
    import subprocess
    cmd = [shutil.which("claude") or "claude", "-p", prompt, "--model", os.getenv("HAIKU_CLI_MODEL", "haiku"),
           "--output-format", "stream-json", "--verbose", "--mcp-config", str(ROOT / ".mcp.json"),
           "--strict-mcp-config", "--no-session-persistence", "--permission-mode", "default"]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=str(ROOT), encoding="utf-8").stdout
    for line in out.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if ev.get("type") == "result" and ev.get("is_error"):
            raise RuntimeError("claude CLI error: %s" % str(ev.get("result"))[:120])
        for b in (ev.get("message") or {}).get("content") or []:
            if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name", "").startswith("mcp__tokenfrugal__"):
                return b["name"].split("__", 2)[2], b.get("input") or {}
    return "", {}


def use_cli() -> bool:
    return not os.getenv("ANTHROPIC_API_KEY") and bool(shutil.which("claude")) and (ROOT / ".mcp.json").exists()


def live_blocker() -> str:
    """Empty string when Haiku is reachable (API key or the claude CLI), else a clear reason."""
    if not os.getenv("ANTHROPIC_API_KEY") and not use_cli():
        return "no ANTHROPIC_API_KEY and no claude CLI with .mcp.json: cannot reach Haiku, so no tool call was verified"
    return ""


def docker_blocker() -> str:
    return "" if shutil.which("docker") else "docker not on PATH: Docker MCP gateway tools cannot be listed"


async def router_tool_defs() -> list:
    from fastmcp import Client
    from router import server
    async with Client(server.mcp) as c:
        return await c.list_tools()


def check_router_tools(only: str = "") -> list:
    """Rows of (tool, PASS|FAIL, detail) for the router tools called by Haiku."""
    tools = asyncio.run(router_tool_defs())
    spec = [anthropic_tool(t.name, t.description, t.inputSchema) for t in tools]
    schemas = {t.name: t.inputSchema for t in tools}
    rows = []
    for name, (prompt, ok) in ROUTER_CASES.items():
        if only and name != only:
            continue
        try:
            got, args = (cli_haiku_pick if use_cli() else haiku_pick)(prompt, spec)
            if got != name:
                rows.append((name, "FAIL", "Haiku called %r" % (got or "no tool (wrote text)")))
                continue
            jsonschema.validate(args, schemas[name])
            rows.append((name, "PASS" if ok(args) else "FAIL", "args=" + json.dumps(args)[:100]))
        except Exception as e:  # noqa: BLE001
            rows.append((name, "FAIL", "%s: %s" % (type(e).__name__, str(e)[:120])))
    return rows


async def _role_rows(only: str) -> list:
    from router.config import load_personas
    from router.mcp_client import _schema, open_role
    cfg = load_personas()
    rows = []
    for rname, r in cfg["roles"].items():
        allow = list(r.get("tools") or [])
        if not allow or (only and only not in allow):
            continue
        try:
            async with open_role(r.get("profile"), r.get("native"), r.get("params")) as sess:
                listed = {t.name: t for t in (await sess.list_tools()).tools}
        except Exception as e:  # noqa: BLE001
            rows += [("%s/%s" % (rname, t), "FAIL", "role did not open: %s: %s" % (type(e).__name__, str(e)[:80]))
                     for t in allow]
            continue
        spec = [anthropic_tool(n, listed[n].description, _schema(listed[n])) for n in allow if n in listed]
        for t in allow:
            if only and t != only:
                continue
            label = "%s/%s" % (rname, t)
            if t not in listed:
                rows.append((label, "FAIL", "allowlisted but not exposed by the gateway"))
                continue
            try:
                got, args = haiku_pick("Call the tool %s once with minimal plausible arguments. "
                                       "Do not answer in text." % t, spec)
                if got != t:
                    rows.append((label, "FAIL", "Haiku called %r" % (got or "no tool")))
                    continue
                jsonschema.validate(args, _schema(listed[t]))
                rows.append((label, "PASS", "args=" + json.dumps(args)[:80]))
            except Exception as e:  # noqa: BLE001
                rows.append((label, "FAIL", "%s: %s" % (type(e).__name__, str(e)[:100])))
    return rows


def check_role_tools(only: str = "") -> list:
    return asyncio.run(_role_rows(only))


def print_table(rows) -> int:
    w = max([len(r[0]) for r in rows] + [4])
    print("%-*s  RESULT  DETAIL" % (w, "TOOL"))
    for n, s, d in rows:
        print("%-*s  %-6s  %s" % (w, n, s, d))
    bad = sum(s == "FAIL" for _, s, _ in rows)
    print("\n%d pass, %d fail (model %s)" % (len(rows) - bad, bad, HAIKU_MODEL))
    return 1 if bad else 0


class RouterToolSurfaceTests(unittest.TestCase):
    def test_router_exposes_expected_tools_with_schemas(self):
        tools = asyncio.run(router_tool_defs())
        self.assertEqual({t.name for t in tools}, set(ROUTER_CASES))
        for t in tools:
            jsonschema.Draft202012Validator.check_schema(t.inputSchema)


class HaikuLiveTests(unittest.TestCase):
    def setUp(self):
        why = live_blocker()
        if why:
            self.skipTest(why)

    def test_haiku_calls_every_router_tool(self):
        rows = check_router_tools()
        print_table(rows)
        self.assertEqual([r for r in rows if r[1] == "FAIL"], [])

    def test_haiku_calls_every_role_tool(self):
        if os.getenv("HAIKU_TEST_ROLES") != "1":
            self.skipTest("set HAIKU_TEST_ROLES=1 to open every Docker MCP profile (slow)")
        why = docker_blocker()
        if why:
            self.skipTest(why)
        rows = check_role_tools()
        print_table(rows)
        self.assertEqual([r for r in rows if r[1] == "FAIL"], [])


def main(argv: list) -> int:
    why = live_blocker()
    if why:
        print("SKIPPED (exit 2): " + why)
        return 2
    only = argv[argv.index("--tool") + 1] if "--tool" in argv else ""
    rows = check_router_tools(only)
    if "--roles" in argv:
        why = docker_blocker()
        if why:
            print("SKIPPED role tools: " + why)
            return 2
        rows += check_role_tools(only)
    return print_table(rows)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
