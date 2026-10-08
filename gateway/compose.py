"""On-demand start/stop of the compose-managed MCP backends a role needs."""
import asyncio
import contextlib
import os
import shutil
import subprocess

from .config import COMPOSE_FILE, COMPOSE_PROJECT, DB_PATH, KEEP_ALIVE

PERSISTENT = {"neo4j"}  # started with the gateway, only stopped by stop_all_sync() on gateway exit
_users: dict[str, int] = {}  # backend -> concurrent tasks using it (in this gateway process)
_lock = asyncio.Lock()


class ComposeError(Exception):
    pass


async def _compose(*args: str, timeout: int) -> None:
    p = await asyncio.create_subprocess_exec(
        shutil.which("docker") or "docker", "compose", "-p", COMPOSE_PROJECT, "-f", str(COMPOSE_FILE), *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=dict(os.environ))
    try:
        out, _ = await asyncio.wait_for(p.communicate(), timeout)
    except asyncio.TimeoutError:
        p.kill()
        raise ComposeError(f"compose {args[0]} timed out after {timeout}s") from None
    if p.returncode:
        tail = out.decode(errors="replace").strip().splitlines()[-3:]
        raise ComposeError(f"compose {args[0]} failed: {' | '.join(tail)}")


@contextlib.asynccontextmanager
async def backends(services: list[str], keep_alive: bool = False, timeout: int = 300):
    """Start `services` (waiting for healthchecks) and stop them afterwards unless keep-alive is set."""
    if not services:
        yield
        return
    async with _lock:
        for s in services:
            _users[s] = _users.get(s, 0) + 1
        try:
            await _compose("up", "-d", "--wait", *services, timeout=timeout)
        except BaseException:
            await _release(services, False)
            raise
    try:
        yield
    finally:
        async with _lock:
            await _release(services, keep_alive or KEEP_ALIVE)


async def _release(services: list[str], keep: bool) -> None:
    idle = []
    for s in services:
        _users[s] = _users.get(s, 1) - 1
        if _users[s] <= 0:
            _users.pop(s, None)
            idle.append(s)
    idle = [s for s in idle if s not in PERSISTENT]
    if idle and not keep:
        with contextlib.suppress(Exception):
            await _compose("stop", *idle, timeout=120)


async def ensure(services: list[str], timeout: int = 300) -> None:
    """Idempotent `up -d --wait` for always-on services (no stop afterwards)."""
    async with _lock:
        await _compose("up", "-d", "--wait", *services, timeout=timeout)


def stop_all_sync() -> None:
    """Stop every running container of the ts-mcp project (backends and stdio wrappers). Safe to call twice."""
    docker = shutil.which("docker") or "docker"
    with contextlib.suppress(Exception):
        ids = subprocess.run([docker, "ps", "-q", "--filter", f"label=com.docker.compose.project={COMPOSE_PROJECT}"],
                             capture_output=True, text=True, timeout=30).stdout.split()
        if ids:
            subprocess.run([docker, "stop", *ids], capture_output=True, timeout=120)


# --- last-one-out shutdown: every gateway process (Claude, Codex, ...) drops a pid file; only the last stops containers
REGISTRY = DB_PATH.parent / "gateways"


def _alive(pid: int) -> bool:
    if os.name == "nt":  # os.kill(pid, 0) would terminate the process on Windows
        import ctypes
        h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(h, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(h)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def register() -> None:
    REGISTRY.mkdir(parents=True, exist_ok=True)
    (REGISTRY / str(os.getpid())).write_text("")


def release() -> bool:
    """Drop this process from the registry; stop all containers only if no other live gateway remains."""
    with contextlib.suppress(OSError):
        (REGISTRY / str(os.getpid())).unlink()
    others = 0
    for f in REGISTRY.glob("*") if REGISTRY.exists() else []:
        if f.name.isdigit() and _alive(int(f.name)):
            others += 1
        else:
            with contextlib.suppress(OSError):
                f.unlink()
    if others:
        return False
    stop_all_sync()
    return True
