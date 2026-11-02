"""GPU lease: one exclusive record of who holds the GPU (a ComfyUI session or a kalamanch script).

Stdlib only; imports neither router.config nor router.compose, so kalamanch can use it with its own requirements.
Only this module reads or writes the lease file (gpu.json) and its lock (gpu.lock) in the leases folder.
Design: docs/designs/comfyui-gpu-lease.md.
"""
import contextlib
import dataclasses
import datetime as dt
import json
import os
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from .proc_alive import _alive

# timing table (design "The lease record")
HEARTBEAT_S = 5
TTL_S = 30
LOCK_WAIT_S = 2
LOCK_STALE_S = 10
UNLOAD_WAIT_S = 60
UNLOAD_POLL_S = 1
REFUSAL_WINDOW_S = 30
QUEUE_DEBOUNCE_S = 180  # used by the ComfyUI bridge, kept here with the other timings
FREE_WAIT_S = 5
QUEUE_TIMEOUT_S = 2
NVIDIA_SMI_TIMEOUT_S = 10
DOCKER_TIMEOUT_S = 10
OLLAMA_HTTP_TIMEOUT_S = 5
MIN_FREE_VRAM_MB = 6 * 1024  # placeholder until measured in the spike
DEFAULT_ETA_S = 180  # retry hint when no ETA is known

HOLDERS = ("comfyui", "kalamanch")
LEASE_FILE = "gpu.json"
LOCK_FILE = "gpu.lock"
LOCAL_HOSTS = ("localhost", "127.0.0.1", "[::1]", "host.docker.internal")
TIME_FMT = "%Y-%m-%dT%H:%M:%SZ"


class GpuError(Exception):
    """Base of the lease errors. Each one means the caller must not start its GPU work."""


class GpuBusy(GpuError):
    def __init__(self, holder="", task="", running_s=0, eta_s=None, text=""):
        self.holder, self.task, self.running_s = holder, task, int(running_s)
        self.retry_s = self.running_s + (DEFAULT_ETA_S if eta_s is None else int(eta_s))
        super().__init__(text or f"the GPU is in use by {holder}" + (f" ({task})" if task else "")
                         + f" for {self.running_s} s")

    @property
    def hint(self):
        return f"The GPU is in use by {self.holder}; retry in about {self.retry_s} s; do not call resume_task."


class UnloadTimeout(GpuError):
    def __init__(self, models, waited_s=0):
        self.models, self.waited_s = list(models), waited_s
        super().__init__(f"Ollama is busy with a task: {', '.join(self.models)} still loaded")


class LowVram(GpuError):
    def __init__(self, free_mb, detail=""):
        self.free_mb = free_mb
        super().__init__(f"free VRAM {free_mb} MB is below {MIN_FREE_VRAM_MB} MB" if free_mb is not None
                         else f"could not read free VRAM: {detail}")


class LeaseLost(GpuError):
    pass


class LeaseUnreadable(ValueError):
    pass


@dataclasses.dataclass
class Lease:
    version: int
    holder: str
    state: str
    task: str
    job_id: str | None
    pid: int
    container_id: str | None
    started_at: str
    heartbeat_at: str
    ttl_s: int
    generation: int


def _now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def _iso(t):
    return t.strftime(TIME_FMT)


def _parse(s):
    return dt.datetime.strptime(s, TIME_FMT).replace(tzinfo=dt.timezone.utc)


def _since(ts, now):
    return (now - _parse(ts)).total_seconds()


_sleep = time.sleep
_run = subprocess.run
_urlopen = urllib.request.urlopen


def lease_dir():
    """The shared leases folder: the same place as router/compose.py LEASES (GATEWAY_DB relocates it).
    GPU_LEASE_DIR overrides it, for tests."""
    override = os.getenv("GPU_LEASE_DIR")
    if override:
        return Path(override)
    db = Path(os.getenv("GATEWAY_DB", str(Path(__file__).parent / "tasks.db")))
    return db.parent / "leases"


def _path(name):
    return lease_dir() / name


def read():
    """The lease record, or None when there is no file (free). Raises LeaseUnreadable for a damaged file."""
    try:
        data = json.loads(_path(LEASE_FILE).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        raise LeaseUnreadable(str(e)) from e
    try:
        return Lease(**{f.name: data[f.name] for f in dataclasses.fields(Lease)})
    except (KeyError, TypeError) as e:
        raise LeaseUnreadable(str(e)) from e


def _save(lease):
    path = _path(LEASE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="gpu.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dataclasses.asdict(lease), f)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


def _delete():
    with contextlib.suppress(FileNotFoundError):
        _path(LEASE_FILE).unlink()


def _lock_age(path):
    try:
        return time.time() - path.stat().st_mtime
    except OSError:
        return 0


@contextlib.contextmanager
def _locked():
    """Exclusive lock file. A lock older than LOCK_STALE_S is removed once; otherwise wait LOCK_WAIT_S, then refuse."""
    path = _path(LOCK_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + LOCK_WAIT_S
    cleared = False
    while True:
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            break
        except (FileExistsError, PermissionError):  # Windows reports a lock being unlinked by a peer as PermissionError
            if not cleared and _lock_age(path) > LOCK_STALE_S:
                cleared = True
                with contextlib.suppress(OSError):
                    path.unlink()
                continue
            if time.monotonic() >= deadline:
                raise GpuBusy(holder="unknown", text="lease file is locked")
            _sleep(0.05)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            path.unlink()


def _expired(lease, now):
    return _since(lease.heartbeat_at, now) > lease.ttl_s


def _busy(lease, now):
    return GpuBusy(lease.holder, lease.task, max(0, _since(lease.started_at, now)))


def comfy_running(comfy_url=None):
    """True when ComfyUI reports a running job. None when the call fails or times out (the caller lets the task through)."""
    url = (comfy_url or os.getenv("COMFY_URL", "http://127.0.0.1:8188")).rstrip("/") + "/queue"
    try:
        with _urlopen(url, timeout=QUEUE_TIMEOUT_S) as r:
            return bool(json.loads(r.read()).get("queue_running"))
    except (OSError, ValueError, AttributeError):
        return None


def _container_stopped(cid):
    try:
        out = _run(["docker", "inspect", "-f", "{{.State.Running}}", cid], capture_output=True, text=True,
                   timeout=DOCKER_TIMEOUT_S)
    except Exception:  # noqa: BLE001 - docker unavailable: cannot prove the container stopped
        return False
    if out.returncode != 0:
        return "No such" in (out.stderr or "")
    return out.stdout.strip() == "false"


def _may_take_over(lease, comfy_url):
    """An expired lease is taken over only when its holder is dead and ComfyUI has no running job."""
    if lease.holder == "kalamanch":
        if _alive(lease.pid):
            return False
    elif not (lease.container_id and _container_stopped(lease.container_id)):
        return False
    return not comfy_running(comfy_url)


def check_for_ollama(comfy_url=None):
    """Read-only router check. Raises GpuBusy while a lease is held, or expired but inside its refusal window,
    or unreadable inside its window, or while ComfyUI runs a job after the window. Never writes the file."""
    now = _now()
    try:
        lease = read()
    except LeaseUnreadable:
        try:
            age = now.timestamp() - _path(LEASE_FILE).stat().st_mtime
        except OSError:
            return
        if age < REFUSAL_WINDOW_S or comfy_running(comfy_url):
            raise GpuBusy(holder="unknown", text="the GPU lease file is unreadable; retry shortly")
        return
    if lease is None:
        return
    if not _expired(lease, now):
        raise _busy(lease, now)
    if _since(lease.heartbeat_at, now) < lease.ttl_s + REFUSAL_WINDOW_S or comfy_running(comfy_url):
        raise _busy(lease, now)


def guard_ollama(url, comfy_url=None):
    """Called before each Ollama request. Only a local endpoint is checked."""
    if any(h in (url or "") for h in LOCAL_HOSTS):
        check_for_ollama(comfy_url)


def _json(url, method="GET", body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with _urlopen(req, timeout=OLLAMA_HTTP_TIMEOUT_S) as r:
        raw = r.read()
    return json.loads(raw) if raw.strip() else {}


def _native_url(url=None):
    """Native Ollama base URL (no /v1, because /v1 cannot unload models)."""
    base = (url or os.getenv("TF_OLLAMA_NATIVE_URL", "http://127.0.0.1:11434")).rstrip("/")
    return base[:-3] if base.endswith("/v1") else base


def loaded_models(native):
    """Names of the models Ollama holds in memory. An unreachable Ollama holds no GPU memory for us, so it reads as empty."""
    try:
        models = _json(native + "/api/ps").get("models") or []
    except (OSError, ValueError, AttributeError):
        return []
    return [m.get("name") or m.get("model") or "?" for m in models if isinstance(m, dict)]


def unload_ollama(native, beat=None):
    for name in loaded_models(native):
        with contextlib.suppress(OSError, ValueError):
            _json(native + "/api/generate", "POST", {"model": name, "keep_alive": 0})
    deadline = time.monotonic() + UNLOAD_WAIT_S
    while True:
        left = loaded_models(native)
        if not left:
            return
        if time.monotonic() >= deadline:
            raise UnloadTimeout(left, UNLOAD_WAIT_S)
        if beat:
            beat()
        _sleep(UNLOAD_POLL_S)


def free_vram_mb():
    out = _run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
               capture_output=True, text=True, timeout=NVIDIA_SMI_TIMEOUT_S)
    if out.returncode != 0:
        raise RuntimeError((out.stderr or "nvidia-smi failed").strip())
    return int(out.stdout.split()[0])


def _check_vram():
    try:
        free = free_vram_mb()
    except Exception as e:  # noqa: BLE001 - any failure of the probe counts as a failed check
        raise LowVram(None, str(e) or type(e).__name__) from e
    if free < MIN_FREE_VRAM_MB:
        raise LowVram(free)


def _rollback(lease):
    with contextlib.suppress(GpuError, OSError):
        with _locked():
            try:
                cur = read()
            except LeaseUnreadable:
                return
            if cur is not None and cur.generation == lease.generation:
                _delete()


def acquire(holder, task, job_id=None, container_id=None, ollama_url=None, comfy_url=None):
    """Take the GPU: write `pending`, unload Ollama, check free VRAM, then write `held`. Raises GpuBusy, UnloadTimeout
    or LowVram; a failure deletes the pending lease."""
    if holder not in HOLDERS:
        raise ValueError(f"unknown holder {holder!r}")
    native = _native_url(ollama_url)
    with _locked():
        now = _now()
        unreadable = False
        try:
            cur = read()
        except LeaseUnreadable:
            unreadable = True
            cur = None
            check_for_ollama(comfy_url)  # same refusal window and queue check as the router
        if cur is not None and not _expired(cur, now):
            raise _busy(cur, now)
        if cur is not None and not _may_take_over(cur, comfy_url):
            raise _busy(cur, now)
        # rises on every acquire, also after a release deleted the file, so an old holder's generation never matches again
        generation = max((cur.generation if cur else 0) + 1, int(time.time() * 1000))
        lease = Lease(version=1, holder=holder, state="pending", task=task, job_id=job_id, pid=os.getpid(),
                      container_id=container_id, started_at=_iso(now), heartbeat_at=_iso(now), ttl_s=TTL_S,
                      generation=generation)
        _save(lease)
    try:
        unload_ollama(native, beat=lambda: heartbeat(lease))
        _check_vram()
        left = loaded_models(native)
        if left:
            raise UnloadTimeout(left)
        with _locked():
            cur = read()
            if cur is None or cur.generation != lease.generation:
                raise LeaseLost("the lease was replaced during acquire")
            cur.state = "held"
            cur.heartbeat_at = _iso(_now())
            _save(cur)
            return cur
    except BaseException:
        _rollback(lease)
        raise


def heartbeat(lease):
    """Refresh heartbeat_at. Raises LeaseLost when the file's generation differs (or the file is gone)."""
    with _locked():
        try:
            cur = read()
        except LeaseUnreadable as e:
            raise LeaseLost(f"lease file unreadable: {e}") from e
        if cur is None or cur.generation != lease.generation:
            raise LeaseLost(f"lease generation {lease.generation} is no longer current")
        cur.heartbeat_at = _iso(_now())
        _save(cur)
    lease.heartbeat_at = cur.heartbeat_at


def start_heartbeat(lease, on_lost=None):
    """Daemon thread that beats every HEARTBEAT_S. Set the returned Event to stop it. On LeaseLost, calls on_lost once."""
    stop = threading.Event()

    def beat():
        while not stop.wait(HEARTBEAT_S):
            try:
                heartbeat(lease)
            except LeaseLost as e:
                if on_lost:
                    on_lost(e)
                return
            except (GpuError, OSError):
                continue  # lock busy or a disk hiccup: the next beat retries

    threading.Thread(target=beat, name="gpu-lease-heartbeat", daemon=True).start()
    return stop


def _free_comfy(comfy_url):
    """ComfyUI release step: free models and memory, wait, then check VRAM again. False keeps the lease."""
    try:
        _json(comfy_url.rstrip("/") + "/free", "POST", {"unload_models": True, "free_memory": True})
        _sleep(FREE_WAIT_S)
        _check_vram()
        return True
    except (GpuError, OSError, ValueError):
        return False


def release(lease, comfy_url=None):
    """Delete the lease if it is still ours. For comfyui with comfy_url, first free ComfyUI and re-check VRAM;
    returns False and keeps the lease when that check fails. Raises LeaseLost when the generation differs."""
    if lease.holder == "comfyui" and comfy_url and not _free_comfy(comfy_url):
        return False
    with _locked():
        try:
            cur = read()
        except LeaseUnreadable as e:
            raise LeaseLost(f"lease file unreadable: {e}") from e
        if cur is None:
            return True
        if cur.generation != lease.generation:
            raise LeaseLost(f"lease generation {lease.generation} is no longer current")
        _delete()
    return True


def force_release():
    """Delete the lease whatever its state and return the old record. The container or a running job keep going,
    so the GPU may still be in use."""
    with _locked():
        try:
            cur = read()
        except LeaseUnreadable:
            cur = None
        _delete()
    return cur
