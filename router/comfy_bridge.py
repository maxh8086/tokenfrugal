"""Detached ComfyUI event bridge for the GPU lease (docs/designs/comfyui-gpu-lease.md, piece 3).

One process per ComfyUI session. It holds the GPU lease through router/gpu_lease.py, listens to ComfyUI's websocket
events, writes router/leases/comfy_status.json for the ComfyUI tab, and keeps per-workflow timings in
router/leases/comfy_history.json. It releases the lease after the ComfyUI queue has been empty for
QUEUE_DEBOUNCE_S, and it exits after a release, after a Stop request that found an empty queue, or when the container
is gone. Closing a browser tab does not affect it.

ComfyTracker is pure: it takes parsed event dicts and a clock, so tests replay recorded events without ComfyUI.
run() owns the websocket, the HTTP calls and the files. It imports `websockets` only when it runs.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import uuid
from pathlib import Path

from . import gpu_lease

ROOT_DIR = Path(__file__).resolve().parent.parent
COMPOSE_FILE = ROOT_DIR / "docker-compose.gpu.yml"
STATUS_FILE = "comfy_status.json"
HISTORY_FILE = "comfy_history.json"
STOP_FILE = "comfy_stop.request"
ALPHA = 0.3  # EMA weight for the seconds-per-sampler-step estimate
HISTORY_PER_KEY = 20
SEED_KEYS = frozenset({"seed", "noise_seed"})
PROMPT_KEYS = frozenset({"text", "prompt", "text_g", "text_l"})
POLL_S = 1.0
RELEASE_RETRY_S = 30
CONNECT_RETRY_S = 2
CONNECT_FAILS_GONE = 6  # about 12 s of failed connects: the container is gone
STOP_TIMEOUT_S = 120
DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
TERMINAL = {"execution_success": "success", "execution_error": "error", "execution_interrupted": "interrupted"}


def workflow_key(workflow: dict) -> str:
    """SHA-256 of an API-format workflow with seed and prompt text removed, so reruns of one workflow share history."""
    stripped = {}
    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        inputs = node.get("inputs") or {}
        kept = {k: v for k, v in inputs.items() if k not in SEED_KEYS and k not in PROMPT_KEYS}
        stripped[node_id] = {"class_type": node.get("class_type"), "inputs": kept}
    blob = json.dumps(stripped, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ComfyTracker:
    """State over ComfyUI websocket messages. `clock` returns seconds (monotonic in the runner)."""

    def __init__(self, clock=time.monotonic, history=None):
        self.clock = clock
        self.history = history if history is not None else {}
        self.queue_remaining = 0
        self.finished_result = None
        self.finished_key = None
        self.finished_stats = None
        self._empty_since = clock()
        self._reset()

    def _reset(self):
        self.prompt_id = None
        self.key = None
        self.started = None
        self.first_progress = None
        self.load_s = None
        self.value = 0
        self.max = 0
        self.step_s = None
        self.sampler_done = None
        self.post_s = None
        self._last_step_t = None
        self._last_value = None

    def set_workflow(self, workflow):
        """Called by the runner with the API-format workflow of the running prompt (from GET /queue)."""
        self.key = workflow_key(workflow) if workflow else None

    def handle(self, msg):
        kind, data = msg.get("type"), msg.get("data") or {}
        now = self.clock()
        if kind == "status":
            info = (data.get("status") or {}).get("exec_info") or {}
            self.queue_remaining = int(info.get("queue_remaining") or 0)
        elif kind == "execution_start":
            self._reset()
            self.prompt_id = data.get("prompt_id")
            self.started = now
        elif kind == "executing" and self.prompt_id and data.get("prompt_id", self.prompt_id) == self.prompt_id:
            if data.get("node") is None and self.sampler_done is not None and self.post_s is None:
                self.post_s = now - self.sampler_done  # sampler finished, then decode and save
        elif kind == "progress" and self.prompt_id:
            value, top = int(data.get("value") or 0), int(data.get("max") or 0)
            if self.first_progress is None:
                self.first_progress = now
                self.load_s = now - self.started
            elif self._last_step_t is not None and value > self._last_value:
                per_step = (now - self._last_step_t) / (value - self._last_value)
                self.step_s = per_step if self.step_s is None else ALPHA * per_step + (1 - ALPHA) * self.step_s
            self._last_step_t, self._last_value = now, value
            self.value, self.max = value, top
            if top and value >= top and self.sampler_done is None:
                self.sampler_done = now
        elif kind in TERMINAL and self.prompt_id:
            self.finished_result = TERMINAL[kind]
            self.finished_key = self.key
            self.finished_stats = {"load_s": self.load_s, "step_s": self.step_s, "post_s": self.post_s,
                                   "total_s": now - self.started}
            self._reset()
        self._update_empty(now)

    def tick(self):
        self._update_empty(self.clock())

    def record(self):
        """Store the finished run's timings. Only a successful run counts; failed and interrupted runs are dropped."""
        if self.finished_result != "success" or not self.finished_key or not self.finished_stats:
            return None
        runs = self.history.setdefault(self.finished_key, [])
        runs.append(dict(self.finished_stats))
        del runs[:-HISTORY_PER_KEY]
        return runs[-1]

    def typical_post_s(self):
        if not self.key:
            return None
        posts = [r["post_s"] for r in self.history.get(self.key, []) if r.get("post_s") is not None]
        return statistics.median(posts) if posts else None

    def eta_s(self, now=None):
        """Remaining sampler steps times the step EMA, plus the median post-sampling time from history.
        None until the first two sampler steps; without history the post-sampling part counts as zero."""
        now = self.clock() if now is None else now
        if self.prompt_id is None or self.step_s is None:
            return None
        post = self.typical_post_s() or 0.0
        if self.sampler_done is not None:
            return max(post - (now - self.sampler_done), 0.0)
        return (self.max - self.value) * self.step_s + post

    def state_name(self):
        if self.prompt_id is None:
            return "queued" if self.queue_remaining > 0 else "idle"
        if self.first_progress is None:
            return "loading"
        return "finishing" if self.sampler_done is not None else "running"

    def _update_empty(self, now):
        busy = self.prompt_id is not None or self.queue_remaining > 0
        if busy:
            self._empty_since = None
        elif self._empty_since is None:
            self._empty_since = now

    def empty_for(self, now=None):
        now = self.clock() if now is None else now
        return 0.0 if self._empty_since is None else now - self._empty_since

    def should_release(self, now=None):
        return self._empty_since is not None and self.empty_for(now) >= gpu_lease.QUEUE_DEBOUNCE_S

    def snapshot(self, now=None):
        now = self.clock() if now is None else now
        eta = self.eta_s(now)
        return {
            "state": self.state_name(),
            "prompt_id": self.prompt_id,
            "elapsed_s": round(now - self.started, 1) if self.started is not None else None,
            "step": self.value if self.first_progress is not None else None,
            "max_steps": self.max or None,
            "eta_s": round(eta, 1) if eta is not None else None,
            "eta_partial": self.typical_post_s() is None,
            "load_s": round(self.load_s, 1) if self.load_s is not None else None,
            "queue_remaining": self.queue_remaining,
            "empty_for_s": round(self.empty_for(now), 1),
            "debounce_s": gpu_lease.QUEUE_DEBOUNCE_S,
            "last_result": self.finished_result,
        }


# ---- files, HTTP and process helpers (no ComfyUI needed to import this module) ----

def _lease_root() -> Path:
    return Path(gpu_lease.lease_dir())


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime(gpu_lease.TIME_FMT)


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _http_json(url: str, method: str = "GET", body=None, timeout: float = gpu_lease.QUEUE_TIMEOUT_S):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"null")


def _queue(comfy_url: str):
    """(running, pending) from GET /queue, or None when ComfyUI does not answer."""
    try:
        data = _http_json(comfy_url.rstrip("/") + "/queue")
    except (OSError, ValueError):
        return None
    return data.get("queue_running") or [], data.get("queue_pending") or []


def _prompt_workflow(comfy_url: str, prompt_id: str):
    """API-format workflow of a queued prompt. Queue entries are [number, prompt_id, prompt, extra, outputs]."""
    found = _queue(comfy_url) or ([], [])
    for entry in found[0] + found[1]:
        if len(entry) > 2 and entry[1] == prompt_id and isinstance(entry[2], dict):
            return entry[2]
    return None


def _ws_url(comfy_url: str, client_id: str) -> str:
    base = comfy_url.rstrip("/")
    scheme, rest = base.split("://", 1)
    return f"{'wss' if scheme == 'https' else 'ws'}://{rest}/ws?clientId={client_id}"


def _stop_container() -> None:
    try:
        subprocess.run(["docker", "compose", "-p", "tokenfrugal-gpu", "-f", str(COMPOSE_FILE), "stop"],
                       capture_output=True, timeout=STOP_TIMEOUT_S, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def spawn_detached(args=()) -> subprocess.Popen:
    """Start this module detached from the caller: no console on Windows, its own session elsewhere."""
    flags = (CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS) if os.name == "nt" else 0
    return subprocess.Popen([sys.executable, "-m", "router.comfy_bridge", *args], cwd=str(ROOT_DIR),
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            creationflags=flags, close_fds=True, start_new_session=os.name != "nt")


def run(comfy_url: str, container_id: str | None = None, task: str = "ComfyUI session") -> int:
    """Hold the lease for one ComfyUI session. Returns the process exit code."""
    from websockets.exceptions import ConnectionClosed  # noqa: PLC0415 - only the bridge process needs websockets
    from websockets.sync.client import connect  # noqa: PLC0415

    root = _lease_root()
    status_p, history_p, stop_p = root / STATUS_FILE, root / HISTORY_FILE, root / STOP_FILE
    stop_p.unlink(missing_ok=True)  # a stale stop request from an earlier session must not stop this one

    def publish(tracker, **extra):
        snap = tracker.snapshot()
        snap.update(extra, pid=os.getpid(), holder="comfyui", updated_at=_now_iso())
        try:
            _write_json(status_p, snap)
        except OSError:
            pass  # the tab reads a stale file; the next publish retries

    try:
        lease = gpu_lease.acquire("comfyui", task, container_id=container_id, comfy_url=comfy_url)
    except gpu_lease.GpuError as e:
        _write_json(status_p, {"state": "error", "error": str(e), "pid": os.getpid(), "updated_at": _now_iso()})
        return 1

    lost = threading.Event()
    beat = gpu_lease.start_heartbeat(lease, on_lost=lambda e: lost.set())
    tracker = ComfyTracker(history=_load_json(history_p))
    client_id, ws, fails, release_retry_at = uuid.uuid4().hex, None, 0, 0.0
    outcome = "exited"
    try:
        while True:
            now = time.monotonic()
            if lost.is_set():
                outcome = "lease_lost"  # someone force-released or replaced it: do not touch the lease
                break
            if stop_p.exists():
                queue = _queue(comfy_url)
                stop_p.unlink(missing_ok=True)
                if queue is None or queue[0] or queue[1]:
                    publish(tracker, stop="refused")
                else:
                    if gpu_lease.release(lease, comfy_url):
                        _stop_container()
                        outcome = "stopped"
                        break
                    publish(tracker, warning="VRAM still low after /free; lease kept")
            if tracker.should_release() and now >= release_retry_at:
                if gpu_lease.release(lease, comfy_url):
                    outcome = "released"
                    break
                release_retry_at = now + RELEASE_RETRY_S
                publish(tracker, warning="VRAM still low after /free; lease kept")
            if ws is None:
                try:
                    # legacy=True keeps the connection open across the loop (no context manager); the
                    # websockets 17 DeprecationWarning is only raised when legacy is not given.
                    ws = connect(_ws_url(comfy_url, client_id), open_timeout=5, legacy=True)
                    fails = 0
                except Exception:  # noqa: BLE001 - any connect failure counts toward "container gone"
                    fails += 1
                    if fails >= CONNECT_FAILS_GONE:
                        gpu_lease.release(lease)  # the container is gone: nothing is left to free
                        outcome = "container_gone"
                        break
                    publish(tracker, warning="ComfyUI is not answering")
                    time.sleep(CONNECT_RETRY_S)
                    continue
            try:
                raw = ws.recv(timeout=POLL_S)
            except TimeoutError:
                tracker.tick()
                publish(tracker)
                continue
            except ConnectionClosed:
                ws = None
                continue
            if isinstance(raw, bytes):
                continue  # preview images are not used
            msg = json.loads(raw)
            kind = msg.get("type")
            tracker.handle(msg)
            if kind == "execution_start" and tracker.prompt_id:
                tracker.set_workflow(_prompt_workflow(comfy_url, tracker.prompt_id))
            elif kind == "execution_success":
                tracker.record()
                _write_json(history_p, tracker.history)
            publish(tracker)
    finally:
        beat.set()
        if ws is not None:
            try:
                ws.close()
            except Exception:  # noqa: BLE001
                pass
        publish(tracker, outcome=outcome)
    return 0 if outcome in ("released", "stopped", "container_gone") else 2


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m router.comfy_bridge", description=__doc__.splitlines()[0])
    ap.add_argument("--comfy-url", default=os.getenv("COMFY_URL", "http://127.0.0.1:8188"))
    ap.add_argument("--container-id", default=None)
    ap.add_argument("--task", default="ComfyUI session")
    args = ap.parse_args(argv)
    return run(args.comfy_url, args.container_id, args.task)


if __name__ == "__main__":
    sys.exit(main())
