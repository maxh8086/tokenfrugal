"""Thin client for `docker mcp gateway run --profile <p>` (stdio)."""
import asyncio
import contextlib
import os

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from . import docker_mcp, mcp_reap, profile_sync, secrets_store
from .config import MCP_CPUS, MCP_MEMORY, NATIVE_BACKENDS, NATIVE_SERVERS, SYNAPTREE_PROJECT, WORKSPACE


# Arguments small models routinely omit; filled in before the call.
ARG_DEFAULTS = {"navigate_page": {"type": "url"}}

CONN_ERROR_MARKERS = ("connection closed", "is not running", "broken pipe", "brokenpipe")
MAX_HEALS_PER_CALL = 2
OPEN_ATTEMPTS = 3  # initial open of a session: 1 try + 2 retries on connection errors
BACKEND_WAIT_S = 90  # max time to wait for a native server's containers to be running and healthy
BACKEND_POLL_S = 2


def conn_error(exc: BaseException) -> bool:
    """True when the exception means the gateway/container connection died (worth a reopen)."""
    if isinstance(exc, asyncio.TimeoutError):
        return False
    text = str(exc).lower()
    return any(m in text for m in CONN_ERROR_MARKERS)


def _open_conn_error(exc: BaseException) -> bool:
    """conn_error that also looks inside (possibly nested) exception groups raised by async context entry."""
    if isinstance(exc, BaseExceptionGroup):
        return any(_open_conn_error(e) for e in exc.exceptions)
    return conn_error(exc)


async def _docker(*args: str) -> tuple[int, str]:
    """Run the docker binary; returns (returncode, combined output). Raises on timeout or missing binary."""
    proc = await asyncio.create_subprocess_exec(docker_mcp.docker_bin(), *args,
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    return proc.returncode, out.decode(errors="replace").strip()


async def ensure_backend(name: str) -> bool:
    """Start the Docker containers behind a native server and wait until they are running and healthy.

    Best effort: True when the server needs no backend, False on any failure or timeout (never raises).
    Containers are handled in NATIVE_BACKENDS order, each waited on before the next.
    """
    if name not in NATIVE_BACKENDS or os.getenv("SYNAPTREE_HOST_NODE") == "1":
        return True
    try:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + BACKEND_WAIT_S
        for c in NATIVE_BACKENDS[name]:
            while True:
                rc, out = await _docker("inspect", "-f", "{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}", c)
                if rc != 0:
                    return False  # container missing or docker unreachable: nothing to heal
                status, _, health = out.partition("|")
                if status == "running" and health in ("", "healthy"):
                    break
                if loop.time() >= deadline:
                    return False
                if status not in ("running", "restarting"):  # exited, dead, paused, created: start it
                    rc, _ = await _docker("start", c)
                    if rc != 0:
                        return False
                await asyncio.sleep(BACKEND_POLL_S)
        return True
    except Exception:
        return False


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
        for attempt in range(OPEN_ATTEMPTS):
            st = contextlib.AsyncExitStack()  # fresh stack per attempt
            stacks.append(st)
            try:
                return await st.enter_async_context(open_fn(*args)), st
            except Exception as exc:
                with contextlib.suppress(Exception):  # failed attempt: release whatever it half-entered
                    await st.aclose()
                stacks.remove(st)
                if attempt == OPEN_ATTEMPTS - 1 or not _open_conn_error(exc):
                    raise
                await asyncio.sleep(1)

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
            ns, st = await start(_open_native_ensured, n)
            sessions.append(ns)
            nat.add(ns)
            reopen[ns] = reopener(_open_native_ensured, n, stack=st)
        yield Router(sessions, nat, reopen)
    finally:
        for st in reversed(stacks):
            with contextlib.suppress(Exception):  # dead sessions may fail to close
                await st.aclose()


@contextlib.asynccontextmanager
async def _open_native_ensured(name: str):
    """open_native preceded by ensure_backend, so a stopped backing container is started before every attempt."""
    await ensure_backend(name)  # module globals resolved at call time
    async with open_native(name) as s:
        yield s


@contextlib.asynccontextmanager
async def open_native(name: str):
    cfg = NATIVE_SERVERS[name]
    # "docker-secret:NAME" values in the server's env block are read from their secret files
    extra = secrets_store.resolve_env(cfg.get("env") or {})
    params = StdioServerParameters(command=cfg["command"], args=cfg["args"], env={**os.environ, **extra})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            yield s


@contextlib.asynccontextmanager
async def open_profile(profile: str, params: dict | None = None):
    """`docker mcp gateway run --profile`; catalog `params` (config/secrets, docker-secret: refs resolved) are pushed first."""
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
    return [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                              "parameters": _schema(t)}}
            for t in tools if not allow or t.name in allow]


def result_text(res) -> str:
    return "\n".join(getattr(c, "text", "") for c in res.content)
