"""Thin client for `docker mcp gateway run --profile <p>` (stdio)."""
import asyncio
import contextlib
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from . import docker_mcp, mcp_reap, profile_sync, secrets_store
from .config import MCP_CPUS, MCP_MEMORY, NATIVE_SERVERS, SYNAPTREE_PROJECT, WORKSPACE


# Arguments small models routinely omit; filled in before the call.
ARG_DEFAULTS = {"navigate_page": {"type": "url"}}

CONN_ERROR_MARKERS = ("connection closed", "is not running", "broken pipe", "brokenpipe")
MAX_HEALS_PER_CALL = 2


def conn_error(exc: BaseException) -> bool:
    """True when the exception means the gateway/container connection died (worth a reopen)."""
    if isinstance(exc, asyncio.TimeoutError):
        return False
    text = str(exc).lower()
    return any(m in text for m in CONN_ERROR_MARKERS)


class Router:
    """One session facade over a Docker profile plus optional native MCP servers.

    `reopen` maps a session to an async factory returning a fresh, initialised replacement;
    used to self-heal when the connection dies mid-run.
    """

    def __init__(self, sessions: list, native: set | None = None, reopen: dict | None = None):
        self._sessions, self._owner, self._native = sessions, {}, native or set()
        self._needs_project = set()
        self._reopen = dict(reopen or {})
        self.heals = 0

    def _swap(self, old, new):
        self._sessions = [new if s is old else s for s in self._sessions]
        for name, s in self._owner.items():
            if s is old:
                self._owner[name] = new
        if old in self._native:
            self._native.discard(old)
            self._native.add(new)
        self._reopen[new] = self._reopen.pop(old)

    async def list_tools(self):
        tools = []
        for s in self._sessions:
            for t in (await s.list_tools()).tools:
                if t.name not in self._owner:
                    self._owner[t.name] = s
                    if s in self._native and "project" in ((getattr(t, "input_schema", None) or getattr(t, "inputSchema", None) or {}).get("properties") or {}):
                        self._needs_project.add(t.name)
                    tools.append(t)
        return type("Tools", (), {"tools": tools})()

    async def call_tool(self, name, args):
        if name in self._needs_project:
            args = {"project": SYNAPTREE_PROJECT, **args}
        args = {**ARG_DEFAULTS.get(name, {}), **args}
        heals = 0
        while True:
            s = self._owner[name]
            try:
                return await s.call_tool(name, args)
            except Exception as exc:
                factory = self._reopen.get(s)
                if heals >= MAX_HEALS_PER_CALL or factory is None or not conn_error(exc):
                    raise
                try:
                    new = await factory()
                except Exception:
                    raise exc  # reopen itself failed: report the original connection error
                heals += 1
                self.heals += 1
                self._swap(s, new)


@contextlib.asynccontextmanager
async def open_role(profile: str | list[str] | None, native: list[str] | None = None, params: dict | None = None):
    stacks: list[contextlib.AsyncExitStack] = []  # every stack ever opened, closed on exit

    async def start(open_fn, *args):
        st = contextlib.AsyncExitStack()
        stacks.append(st)
        return await st.enter_async_context(open_fn(*args)), st

    def reopener(open_fn, *args, stack):
        cur = {"stack": stack}

        async def reopen():
            with contextlib.suppress(Exception):  # the dead connection's stack
                await cur["stack"].aclose()
            sess, cur["stack"] = await start(open_fn, *args)
            return sess

        return reopen

    profiles = [profile] if isinstance(profile, str) else list(profile or [])
    sessions, nat, reopen = [], set(), {}
    try:
        for p in profiles:
            pr = (params or {}).get(p)
            sess, st = await start(open_profile, p, pr)
            sessions.append(sess)
            reopen[sess] = reopener(open_profile, p, pr, stack=st)
        for n in native or []:
            ns, st = await start(open_native, n)
            sessions.append(ns)
            nat.add(ns)
            reopen[ns] = reopener(open_native, n, stack=st)
        yield Router(sessions, nat, reopen)
    finally:
        for st in reversed(stacks):
            with contextlib.suppress(Exception):  # dead sessions may fail to close
                await st.aclose()


@contextlib.asynccontextmanager
async def open_native(name: str):
    cfg = NATIVE_SERVERS[name]
    # "keyring:NAME" values in the server's env block are read from the OS secret store, never from a file
    extra = secrets_store.resolve_env(cfg.get("env") or {})
    params = StdioServerParameters(command=cfg["command"], args=cfg["args"], env={**os.environ, **extra})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            yield s


@contextlib.asynccontextmanager
async def open_profile(profile: str, params: dict | None = None):
    """`docker mcp gateway run --profile`; catalog `params` (config/secrets, keyring: refs resolved) are pushed first."""
    docker = docker_mcp.docker_bin()
    await asyncio.to_thread(profile_sync.ensure_profiles, WORKSPACE)  # no-op unless the workspace changed
    if params:
        await asyncio.to_thread(docker_mcp.apply_params, profile, params)
    sp = StdioServerParameters(command=docker,
                                   args=docker_mcp.gateway_argv(profile, MCP_CPUS, MCP_MEMORY, docker)[1:],
                                   env={**os.environ,
                                        "MCP_GATEWAY_DOCKER_BIND_ALLOWED_PATHS": WORKSPACE,
                                        "MCP_GATEWAY_DOCKER_BIND_ALLOW_WRITABLE_PATHS": WORKSPACE})
    await asyncio.to_thread(mcp_reap.enter, docker)
    try:
        async with stdio_client(sp) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                yield s
    finally:
        await asyncio.to_thread(mcp_reap.leave, docker)  # gateway stdio containers stay inside this session


def _schema(t) -> dict:
    sc = dict(getattr(t, "input_schema", None) or getattr(t, "inputSchema", None) or {"type": "object", "properties": {}})
    props = {k: v for k, v in (sc.get("properties") or {}).items() if k != "project"}
    return {**sc, "properties": props, "required": [r for r in sc.get("required", []) if r != "project"]}


def to_openai_tools(tools, allow: list[str]) -> list[dict]:
    """Convert MCP tools to OpenAI function specs, filtered to the role allowlist (empty = all)."""
    return [{"type": "function", "function": {"name": t.name, "description": (t.description or "")[:300],
                                              "parameters": _schema(t)}}
            for t in tools if not allow or t.name in allow]


def result_text(res) -> str:
    return "\n".join(getattr(c, "text", "") for c in res.content)
