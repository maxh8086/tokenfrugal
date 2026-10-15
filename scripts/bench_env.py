"""Environment and hardware capture for scripts/bench.py.

No router imports here, so tests can load these helpers without starting the router.
"""
import os
import re
import subprocess
import threading
import time

try:
    import psutil
except ImportError:  # psutil is optional: CPU and RAM columns are then recorded as None
    psutil = None

OLLAMA_ENV_KEYS = ("OLLAMA_MAX_LOADED_MODELS", "OLLAMA_NUM_PARALLEL", "OLLAMA_KEEP_ALIVE",
                   "OLLAMA_FLASH_ATTENTION", "OLLAMA_KV_CACHE_TYPE")
NVIDIA_QUERY = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
                "--format=csv,noheader,nounits"]
GPU_FIELDS = ("gpu_util_pct", "vram_used_mib", "vram_total_mib", "gpu_temp_c", "gpu_power_w")
HW_LABELS = (("cpu_pct", "CPU %"), ("ram_pct", "RAM %"), ("gpu_util_pct", "GPU util %"),
             ("vram_used_mib", "VRAM used MiB"), ("gpu_temp_c", "GPU temp C"), ("gpu_power_w", "GPU power W"))
PROCESSOR_RE = re.compile(r"(\d+)%(?:/(\d+)%)?\s+(CPU/GPU|GPU|CPU)")


def capture_env(environ=None):
    """The five OLLAMA_* server settings; a missing variable is recorded as 'unset'."""
    environ = os.environ if environ is None else environ
    return {k: environ.get(k, "unset") for k in OLLAMA_ENV_KEYS}


def task_timeout(environ, default):
    """Effective TOKENFRUGAL_TASK_TIMEOUT and whether it came from the environment or the bench default."""
    raw = environ.get("TOKENFRUGAL_TASK_TIMEOUT")
    if raw:
        return {"task_timeout_s": float(raw), "source": "env"}
    return {"task_timeout_s": float(default), "source": "bench default"}


def _num(text):
    try:
        return float(text.strip())
    except ValueError:  # "[N/A]" or "[Not Supported]"
        return None


def parse_nvidia(text):
    """First GPU line of `nvidia-smi --query-gpu=... --format=csv,noheader,nounits`."""
    lines = text.strip().splitlines()
    parts = lines[0].split(",") if lines else []
    if len(parts) != len(GPU_FIELDS):
        return {k: None for k in GPU_FIELDS}
    return {k: _num(v) for k, v in zip(GPU_FIELDS, parts)}


def parse_ollama_ps(text):
    """One row per loaded model from `ollama ps`: the PROCESSOR text and the share of the model on CPU."""
    rows = []
    for line in text.splitlines()[1:]:  # first line is the header
        m = PROCESSOR_RE.search(line)
        if not m or not line.split():
            continue
        first, second, kind = m.groups()
        if kind == "CPU/GPU":
            cpu = float(first)  # "48%/52% CPU/GPU": the first figure is the CPU share
        elif kind == "CPU":
            cpu = 100.0
        else:
            cpu = 0.0
        rows.append({"model": line.split()[0], "processor": m.group(0), "cpu_share_pct": cpu})
    return rows


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=10).stdout or ""
    except Exception:  # noqa: BLE001  (tool missing or hung: the sample records None)
        return ""


def _spread(xs):
    if not xs:
        return None
    return {"min": round(min(xs), 1), "avg": round(sum(xs) / len(xs), 1), "max": round(max(xs), 1)}


class HardwareSampler:
    """Samples GPU, CPU, RAM and the Ollama PROCESSOR split on a background thread."""

    def __init__(self, interval=2.0, run=_run):
        self.interval = interval
        self.samples = []
        self._run = run
        self._stop = threading.Event()
        self._thread = None

    def sample_once(self):
        s = {"t": round(time.time(), 1)}
        s.update(parse_nvidia(self._run(NVIDIA_QUERY)))
        if psutil is not None:
            s["cpu_pct"] = psutil.cpu_percent(None)
            s["ram_pct"] = psutil.virtual_memory().percent
        else:
            s["cpu_pct"] = s["ram_pct"] = None
        s["ollama"] = parse_ollama_ps(self._run(["ollama", "ps"]))
        self.samples.append(s)
        return s

    def _loop(self):
        while not self._stop.is_set():
            self.sample_once()
            self._stop.wait(self.interval)

    def start(self):
        if psutil is not None:
            psutil.cpu_percent(None)  # the first call always reports 0, so prime it
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=15)

    def summary(self):
        out = {"samples": len(self.samples), "psutil": psutil is not None}
        for key in ("cpu_pct", "ram_pct", "gpu_util_pct", "vram_used_mib", "gpu_temp_c", "gpu_power_w"):
            out[key] = _spread([s[key] for s in self.samples if s.get(key) is not None])
        totals = [s["vram_total_mib"] for s in self.samples if s.get("vram_total_mib") is not None]
        out["vram_total_mib"] = totals[-1] if totals else None
        split, shares = {}, []
        for s in self.samples:
            for row in s["ollama"]:
                split[row["processor"]] = split.get(row["processor"], 0) + 1
                shares.append(row["cpu_share_pct"])
        out["processor_split"] = split  # raw PROCESSOR text -> number of samples that showed it
        out["max_cpu_share_pct"] = max(shares) if shares else None
        return out


def markdown_section(env, timeout, hw):
    """Lines for the Environment and hardware section of the MD report."""
    L = ["## Environment and hardware", "", "| variable | value |", "|---|---|"]
    L += [f"| {k} | {v} |" for k, v in env.items()]
    L += ["", f"Task timeout: {timeout['task_timeout_s']:g}s (source: {timeout['source']})", ""]
    L += ["| metric | min | avg | max |", "|---|---|---|---|"]
    for key, label in HW_LABELS:
        s = hw.get(key)
        L.append(f"| {label} | {s['min']} | {s['avg']} | {s['max']} |" if s else f"| {label} | - | - | - |")
    split = ", ".join(f"{k} (x{v})" for k, v in hw.get("processor_split", {}).items()) or "-"
    L += ["", f"Ollama PROCESSOR split (samples): {split}", "",
          f"Hardware samples: {hw.get('samples', 0)}, psutil: {hw.get('psutil')}", ""]
    return L
