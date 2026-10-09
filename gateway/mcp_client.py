"""Thin client for `docker mcp gateway run --profile <p>` (stdio)."""
import contextlib
import os
import shutil

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .config import MCP_CPUS, MCP_MEMORY, NATIVE_SERVERS, SYNAPTREE_PROJECT, WORKSPACE


# Arguments small models routinely omit; filled in before the call.
ARG_DEFAULTS = {"navigate_page": {"type": "url"}}


class Router:
    """One session facade over a Docker profile plus optional native MCP servers."""

    def __init__(self, sessions: list, native: set | None = None):
        self._sessions, self._owner, self._native = sessions, {}, native or set()
        self._needs_project = set()

    async def list_tools(self):
        tools = []
        for s in self._sessions:
            for t in (await s.list_tools()).tools:
                if t.name not in self._owner:
                    self._owner[t.name] = s
                    if s in self._native and "project" in ((getattr(t, "inputSchema", None) or getattr(t, "input_schema", None) or {}).get("properties") or {}):
                        self._needs_project.add(t.name)
                    tools.append(t)
        return type("Tools", (), {"tools": tools})()

    async def call_tool(self, name, args):
        if name in self._needs_project:
            args = {"project": SYNAPTREE_PROJECT, **args}
        args = {**ARG_DEFAULTS.get(name, {}), **args}
        return await self._owner[name].call_tool(name, args)


@contextlib.asynccontextmanager
async def open_role(profile: str | None, native: list[str] | None = None):
    async with contextlib.AsyncExitStack() as stack:
        sessions = [await stack.enter_async_context(open_profile(profile))] if profile else []
        nat = set()
        for n in native or []:
            ns = await stack.enter_async_context(open_native(n))
            sessions.append(ns)
            nat.add(ns)
        yield Router(sessions, nat)


@contextlib.asynccontextmanager
async def open_native(name: str):
    cfg = NATIVE_SERVERS[name]
    params = StdioServerParameters(command=cfg["command"], args=cfg["args"], env=dict(os.environ))
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            yield s


@contextlib.asynccontextmanager
async def open_profile(profile: str):
    params = StdioServerParameters(command=shutil.which("docker") or "docker",
                                   args=["mcp", "gateway", "run", "--profile", profile,
                                         "--cpus", MCP_CPUS, "--memory", MCP_MEMORY],
                                   env={**os.environ,
                                        "MCP_GATEWAY_DOCKER_BIND_ALLOWED_PATHS": WORKSPACE,
                                        "MCP_GATEWAY_DOCKER_BIND_ALLOW_WRITABLE_PATHS": WORKSPACE})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            yield s


def _schema(t) -> dict:
    sc = dict(getattr(t, "inputSchema", None) or getattr(t, "input_schema", None) or {"type": "object", "properties": {}})
    props = {k: v for k, v in (sc.get("properties") or {}).items() if k != "project"}
    return {**sc, "properties": props, "required": [r for r in sc.get("required", []) if r != "project"]}


def to_openai_tools(tools, allow: list[str]) -> list[dict]:
    """Convert MCP tools to OpenAI function specs, filtered to the role allowlist (empty = all)."""
    return [{"type": "function", "function": {"name": t.name, "description": (t.description or "")[:300],
                                              "parameters": _schema(t)}}
            for t in tools if not allow or t.name in allow]


def result_text(res) -> str:
    return "\n".join(getattr(c, "text", "") for c in res.content)
