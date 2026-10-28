"""On-demand start/stop of the compose-managed MCP backends a role needs."""
import asyncio
import contextlib
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from .config import COMPOSE_FILE, COMPOSE_PROJECT, DB_PATH, KEEP_ALIVE

PERSISTENT = {"neo4j"}  # started with the router, only stopped by stop_all_sync() on router exit
LEASES = DB_PATH.parent / "leases"  # one file per (service, router pid, task) using a backend
_users: dict[str, int] = {}  # backend -> concurrent tasks using it (in this router process)
_lock = asyncio.Lock()


class ComposeError(Exception):
    pass


async def _compose(*args: str, timeout: int) -> None:
    try:
        await _compose_once(*args, timeout=timeout)
    except ComposeError as first:
        if args[0] != "up" or "timed out" in str(first):
            raise
        # a fast `up` failure is usually a race with a container still stopping from the previous run: retry once
        await asyncio.sleep(5)
        try:
            await _compose_once(*args, timeout=timeout)
        except ComposeError as second:
            raise ComposeError(f"{second} (first attempt: {first})") from None


async def _compose_once(*args: str, timeout: int) -> None:
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
    leases: list[Path] = []
    async with _lock:
        for s in services:
            _users[s] = _users.get(s, 0) + 1
        try:
            leases = lease_acquire(services)
            await _compose("up", "-d", "--wait", *services, timeout=timeout)
        except BaseException:
            await _release(services, leases, False)
            raise
    try:
        yield
    finally:
        async with _lock:
            await _release(services, leases, keep_alive or KEEP_ALIVE)


async def _release(services: list[str], leases: list[Path], keep: bool) -> None:
    for s in services:
        _users[s] = _users.get(s, 1) - 1
        if _users[s] <= 0:
            _users.pop(s, None)
    idle = [s for s in lease_release(leases) if s not in PERSISTENT]
    if idle and not keep:
        with contextlib.suppress(Exception):
            await _compose("stop", *idle, timeout=120)


def lease_acquire(services: list[str]) -> list[Path]:
    """Create one lease file per service, tagged with this router's pid, so other routers see the user."""
    LEASES.mkdir(parents=True, exist_ok=True)
    paths = []
    for s in services:
        p = LEASES / f"{s}.{os.getpid()}.{uuid.uuid4().hex}"
        p.write_text("")
        paths.append(p)
    return paths


def lease_release(paths: list[Path]) -> list[str]:
    """Drop our leases; return the services with no other live user (stale peer leases are pruned)."""
    for p in paths:
        with contextlib.suppress(OSError):
            p.unlink()
    free = []
    for s in dict.fromkeys(p.name.split(".")[0] for p in paths):
        live = False
        for f in LEASES.glob(f"{s}.*") if LEASES.exists() else []:
            pid = f.name.split(".")[1]
            if pid.isdigit() and _alive(int(pid)):
                live = True
            else:
                with contextlib.suppress(OSError):
                    f.unlink()
        if not live:
            free.append(s)
    return free


async def ensure(services: list[str], timeout: int = 300) -> None:
    """Idempotent `up -d --wait` for always-on services (no stop afterwards)."""
    async with _lock:
        await _compose("up", "-d", "--wait", *services, timeout=timeout)


async def recreate(services: list[str], timeout: int = 300) -> None:
    """Force-recreate backends (a no-op for none) so the next connection starts from a clean container."""
    if services:
        async with _lock:
            await _compose("up", "-d", "--wait", "--force-recreate", *services, timeout=timeout)


def stop_all_sync() -> None:
    """Stop every running container of the tokenfrugal project (backends and stdio wrappers). Safe to call twice."""
    docker = shutil.which("docker") or "docker"
    with contextlib.suppress(Exception):
        ids = subprocess.run([docker, "ps", "-q", "--filter", f"label=com.docker.compose.project={COMPOSE_PROJECT}"],
                             capture_output=True, text=True, timeout=30).stdout.split()
        if ids:
            subprocess.run([docker, "stop", *ids], capture_output=True, timeout=120)


# --- last-one-out shutdown: every router process (Claude, Codex, ...) drops a pid file; only the last stops containers
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
    """Drop this process from the registry; stop all containers only if no other live router remains."""
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
