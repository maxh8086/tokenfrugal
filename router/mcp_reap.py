"""Keep MCP containers inside their session: remove gateway stdio containers a closed gateway left behind.

Backends (databases, neo4j, ...) live in the `tokenfrugal` compose project and are never touched here. The per-call stdio
containers the Docker MCP gateway starts (label docker-mcp=true) are not compose-managed, so they are snapshotted
before a gateway opens and the new ones are removed once the last open gateway in this process has closed.
"""
import subprocess
import threading

LABEL = "label=docker-mcp=true"
_lock = threading.Lock()
_active = 0
_before: set[str] = set()
_seen: set[str] = set()


def _docker(args: list[str], docker: str = "docker") -> tuple[int, str]:
    try:
        p = subprocess.run([docker, *args], capture_output=True, text=True, timeout=30)
        return p.returncode, p.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def mcp_container_ids(docker: str = "docker") -> set[str]:
    rc, out = _docker(["ps", "-aq", "--filter", LABEL], docker)
    return set(out.split()) if rc == 0 else set()


def enter(docker: str = "docker") -> None:
    """Called when a gateway opens; the first one records which containers already exist."""
    global _active, _before
    with _lock:
        if _active == 0:
            _before = mcp_container_ids(docker)
        _active += 1


def sweep(docker: str = "docker") -> int:
    """Called after each tool call: remove containers new since enter() that were already seen by an earlier sweep.

    The gateway starts one stdio container per call and keeps it until it closes, so a long run piles them up.
    A container seen once is idle by the next call boundary (calls are sequential), so it is safe to remove.
    """
    global _seen
    with _lock:
        if not _active:
            return 0
        cur = mcp_container_ids(docker) - _before
        stale = sorted(cur & _seen)
        _seen = cur - set(stale)
    if stale:
        _docker(["rm", "-f", *stale], docker)
    return len(stale)


def leave(docker: str = "docker") -> int:
    """Called when a gateway closes; the last one removes containers that appeared since enter(). Returns the count."""
    global _active
    with _lock:
        _active = max(0, _active - 1)
        if _active:
            return 0
        new = sorted(mcp_container_ids(docker) - _before)
    if new:
        _docker(["rm", "-f", *new], docker)
    return len(new)
