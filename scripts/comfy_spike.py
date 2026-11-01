"""ComfyUI feasibility spike (design docs/designs/comfyui-gpu-lease.md, Piece 2b) and the run helpers that
scripts/comfy_quality.py (Piece 5) reuses.

Runs the LTX 0.9.8 distilled workflow once through the ComfyUI HTTP API at a fixed seed and appends one row to
Benchmark/results/comfy_baseline.csv. It needs the GPU. It refuses to run (exit 2) unless:
  * no Ollama model is loaded,
  * nvidia-smi lists no compute process,
  * the GPU lease (router/gpu_lease.py) is held by `comfyui`.

Usage:
  python scripts/comfy_spike.py --dry-run          # validates the workflow, prints the plan, contacts nothing
  python scripts/comfy_spike.py                    # real run (needs the GPU, the container and the lease)

Pure functions (parsing, injection, CSV rows, guards, timings) take plain values so tests can cover them offline.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import statistics
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORKFLOW_DIR = ROOT / "docker" / "comfyui" / "workflows"
RESULTS = ROOT / "Benchmark" / "results"
BASELINE_CSV = RESULTS / "comfy_baseline.csv"
REFERENCE_DIR = RESULTS / "comfy_reference"

COLUMNS = ["workflow_hash", "seed", "settings", "wall_s", "load_s", "sampler_s_per_step", "peak_vram_mb",
           "peak_ram_mb", "spill", "output_path", "sha256", "psnr", "ssim"]

DEFAULT_WORKFLOW = "ltx098"
DEFAULT_SEED = 42
DEFAULT_PROMPT = "A person in a dark blazer looks at the camera and slowly nods."
DEFAULT_CONTAINER = "tokenfrugal-gpu-comfyui-1"  # compose project tokenfrugal-gpu, service comfyui (docker-compose.gpu.yml)
DEFAULT_COMFY_URL = "http://127.0.0.1:8188"
DEFAULT_OLLAMA_NATIVE = "http://127.0.0.1:11434"
SAMPLE_S = 1.0  # sampling period for nvidia-smi, typeperf and docker stats
IDLE_S = 2.0  # samples taken before the job, to get the idle values
POLL_S = 1.0  # /history polling period
JOB_TIMEOUT_S = 3600
SPILL_THRESHOLD_BYTES = 0.5 * 1024 ** 3  # design: more than 0.5 GB above idle counts as spill
SHARED_USAGE_COUNTER = r"\GPU Adapter Memory(*)\Shared Usage"
LOADER_CLASSES = ("CheckpointLoaderSimple", "CLIPLoader")
SAMPLER_CLASS = "SamplerCustomAdvanced"
STEPS_CLASS = "ManualSigmas"

_UNITS_MB = {"": 1.0 / (1024 * 1024), "B": 1.0 / (1024 * 1024), "KB": 1.0 / 1024, "KIB": 1.0 / 1024,
             "MB": 1.0, "MIB": 1.0, "GB": 1024.0, "GIB": 1024.0, "TB": 1024.0 ** 2, "TIB": 1024.0 ** 2}


class WorkflowError(ValueError):
    pass


class GuardRefused(RuntimeError):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


# ---------------------------------------------------------------- pure parsing

def parse_nvidia_smi_used_mb(text):
    """`nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits` -> the largest used value in MB."""
    values = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            values.append(float(line.split(",")[0].strip()))
        except ValueError:
            continue
    if not values:
        raise ValueError(f"no memory.used value in nvidia-smi output: {text!r}")
    return max(values)


def parse_compute_apps(text):
    """`nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv,noheader,nounits` -> list of dicts.
    Windows often prints 'N/A' for the processes of a WDDM driver; those rows are kept with pid None."""
    apps = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or "no running" in line.lower():
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        pid = int(parts[0]) if parts[0].isdigit() else None
        used = parts[2] if len(parts) > 2 else ""
        apps.append({"pid": pid, "name": parts[1], "used_mb": float(used) if re.fullmatch(r"[\d.]+", used) else None})
    return apps


def parse_typeperf_line(line):
    """One data line of `typeperf "<counter>" -si 1` -> the summed value in bytes, or None for header and footer lines.
    Lines look like: "04/12/2026 10:00:01.123","1234567","0"  (one column per adapter instance)."""
    line = (line or "").strip()
    if not line or line.startswith("(PDH") or not line.startswith('"'):
        return None
    try:
        cells = next(csv.reader([line]))
    except (csv.Error, StopIteration):
        return None
    total, seen = 0.0, False
    for cell in cells[1:]:
        cell = cell.strip()
        if re.fullmatch(r"-?[\d.]+(e[-+]?\d+)?", cell, re.IGNORECASE):
            total += float(cell)
            seen = True
    return total if seen else None


def parse_typeperf(text):
    """All data values from a whole typeperf capture (bytes, one per sample)."""
    return [v for v in (parse_typeperf_line(line) for line in (text or "").splitlines()) if v is not None]


def parse_size_mb(text):
    """'8GB', '8G', '8192MB', '512 MB', '1TB' -> MB (float). A bare number is bytes."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([KMGT]?I?B?)\s*", (text or "").strip(), re.IGNORECASE)
    if not m:
        raise ValueError(f"unrecognised size {text!r}")
    unit = m.group(2).upper()
    if unit in ("", "B"):
        factor = _UNITS_MB[""]
    elif unit in ("K", "KB", "KIB"):
        factor = _UNITS_MB["KB"]
    elif unit in ("M", "MB", "MIB"):
        factor = _UNITS_MB["MB"]
    elif unit in ("G", "GB", "GIB"):
        factor = _UNITS_MB["GB"]
    elif unit in ("T", "TB", "TIB"):
        factor = _UNITS_MB["TB"]
    else:
        raise ValueError(f"unrecognised unit in {text!r}")
    return float(m.group(1)) * factor


def parse_wslconfig_memory_mb(text):
    """The [wsl2] memory value of a .wslconfig file in MB, or None when the key is absent (WSL then uses its default)."""
    section = None
    for raw in (text or "").splitlines():
        line = re.split(r"[#;]", raw, maxsplit=1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip().lower()
            continue
        if section == "wsl2" and "=" in line:
            key, value = line.split("=", 1)
            if key.strip().lower() == "memory":
                return parse_size_mb(value.strip())
    return None


def read_wslconfig_memory_mb(path=None):
    """Reads %USERPROFILE%\\.wslconfig (or the given path). None when the file or the key is missing."""
    if path is None:
        home = os.environ.get("USERPROFILE") or str(Path.home())
        path = Path(home) / ".wslconfig"
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return parse_wslconfig_memory_mb(text)


def parse_mem_usage_mb(text):
    """`docker stats --format '{{.MemUsage}}'` -> used memory in MB, from '1.234GiB / 15.6GiB'."""
    used = (text or "").split("/")[0].strip()
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([A-Za-z]*)", used)
    if not m:
        raise ValueError(f"unrecognised docker memory usage {text!r}")
    unit = m.group(2).upper() or "B"
    if unit not in _UNITS_MB:
        raise ValueError(f"unrecognised unit in {text!r}")
    return float(m.group(1)) * _UNITS_MB[unit]


def torch_cuda_from_version(torch_version):
    """'2.8.0+cu128' -> '12.8'. Without a local +cuNNN tag the build is CPU or unknown: None."""
    m = re.search(r"\+cu(\d{2,})", torch_version or "")
    if not m:
        return None
    digits = m.group(1)  # 'cu128' -> '128' -> '12.8'; 'cu121' -> '12.1'
    return f"{digits[:-1]}.{digits[-1]}"


def parse_system_stats(data):
    """ComfyUI /system_stats -> torch, CUDA and ComfyUI versions (CUDA is read from the torch build tag)."""
    system = (data or {}).get("system") or {}
    torch_version = str(system.get("pytorch_version") or "")
    return {"comfyui": str(system.get("comfyui_version") or ""), "torch": torch_version,
            "cuda": torch_cuda_from_version(torch_version) or ""}


def parse_ollama_ps(data):
    """Ollama /api/ps -> names of the loaded models (empty list when nothing is loaded)."""
    models = (data or {}).get("models") or []
    return [m.get("name") or m.get("model") or "?" for m in models if isinstance(m, dict)]


def workflow_hash(raw_bytes):
    return hashlib.sha256(raw_bytes).hexdigest()


def load_workflow(path):
    """Parses a ComfyUI API-format workflow and checks the seed and prompt nodes exist. Raises WorkflowError."""
    try:
        wf = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise WorkflowError(f"cannot read workflow {path}: {e}") from e
    if not isinstance(wf, dict) or not wf:
        raise WorkflowError(f"{path} is not a ComfyUI API workflow (expected an object of nodes)")
    for node_id, node in wf.items():
        if not isinstance(node, dict) or "class_type" not in node or not isinstance(node.get("inputs"), dict):
            raise WorkflowError(f"node {node_id} has no class_type/inputs")
    for title in ("seed", "prompt"):
        found = find_by_title(wf, title)
        if len(found) != 1:
            raise WorkflowError(f"expected exactly one node titled {title!r}, found {len(found)}")
    return wf


def find_by_title(wf, title):
    return [node_id for node_id, node in wf.items()
            if isinstance(node, dict) and (node.get("_meta") or {}).get("title") == title]


def node_ids(wf, class_types):
    return [node_id for node_id, node in wf.items() if node.get("class_type") in class_types]


def inject(wf, seed, prompt):
    """Copy of the workflow with the seed and prompt set on the nodes titled 'seed' and 'prompt'."""
    out = json.loads(json.dumps(wf))
    (seed_id,) = find_by_title(out, "seed")
    inputs = out[seed_id]["inputs"]
    seed_key = "noise_seed" if "noise_seed" in inputs else "seed"
    if seed_key not in inputs:
        raise WorkflowError(f"seed node {seed_id} has neither noise_seed nor seed")
    inputs[seed_key] = int(seed)
    (prompt_id,) = find_by_title(out, "prompt")
    if "text" not in out[prompt_id]["inputs"]:
        raise WorkflowError(f"prompt node {prompt_id} has no text input")
    out[prompt_id]["inputs"]["text"] = prompt
    return out


def workflow_steps(wf):
    """Sampler steps: the number of sigmas in the ManualSigmas node minus one (the final 0.0 is not a step)."""
    for node_id in node_ids(wf, (STEPS_CLASS,)):
        sigmas = [s for s in str(wf[node_id]["inputs"].get("sigmas", "")).split(",") if s.strip()]
        if len(sigmas) >= 2:
            return len(sigmas) - 1
    for node in wf.values():
        if isinstance(node, dict) and "steps" in (node.get("inputs") or {}):
            return int(node["inputs"]["steps"])
    return None


def timings_from_history(entry, loader_ids, sampler_id):
    """(load_s, sampler_total_s) from a /history entry's status messages (timestamps in ms).
    load_s: execution_start to the last loader node finishing. sampler_total_s: the sampler node's executing to executed.
    Either is None when the message is missing."""
    messages = ((entry or {}).get("status") or {}).get("messages") or []
    t_start, executing, executed = None, {}, {}
    for kind, data in messages:
        if not isinstance(data, dict):
            continue
        ts = data.get("timestamp")
        if kind == "execution_start" and ts is not None:
            t_start = ts
        elif kind == "executing" and ts is not None and data.get("node") is not None:
            executing.setdefault(str(data["node"]), ts)
        elif kind == "executed" and ts is not None and data.get("node") is not None:
            executed[str(data["node"])] = ts
    load_s = None
    loaders = [executed[str(n)] for n in loader_ids if str(n) in executed]
    if t_start is not None and loaders:
        load_s = (max(loaders) - t_start) / 1000.0
    sampler_total = None
    if str(sampler_id) in executing and str(sampler_id) in executed:
        sampler_total = (executed[str(sampler_id)] - executing[str(sampler_id)]) / 1000.0
    return load_s, sampler_total


def find_output_files(entry):
    """Saved files of a history entry: dicts with filename, subfolder, type. Key names are unverified (see ltx098.NOTES.md)."""
    files = []
    for out in ((entry or {}).get("outputs") or {}).values():
        if not isinstance(out, dict):
            continue
        for key in ("images", "gifs", "videos"):
            for item in out.get(key) or []:
                if isinstance(item, dict) and item.get("filename"):
                    files.append({"filename": item["filename"], "subfolder": item.get("subfolder", ""),
                                  "type": item.get("type", "output")})
    return files


def idle_value(values):
    """Idle level of a sampled counter: the median of the idle window (None when there are no samples)."""
    return statistics.median(values) if values else None


def spill_check(idle_bytes, job_values, threshold_bytes=SPILL_THRESHOLD_BYTES):
    """(spill, excess_bytes). Spill is True when the peak during the job is more than the threshold above idle."""
    if idle_bytes is None or not job_values:
        return False, None
    excess = max(job_values) - idle_bytes
    return excess > threshold_bytes, excess


def settings_string(pairs):
    """key=value pairs joined by ';', in the order given."""
    return ";".join(f"{k}={v}" for k, v in pairs)


def sampler_s_per_step(sampler_total_s, steps):
    if sampler_total_s is None or not steps:
        return None
    return sampler_total_s / steps


def guard_problems(ollama_models, compute_apps, lease, lease_error=None):
    """Reasons the GPU must not be used now. Empty list means the run may start."""
    problems = []
    if ollama_models:
        problems.append("Ollama still has models loaded (" + ", ".join(ollama_models) + "); unload them first")
    if compute_apps:
        names = ", ".join(str(a.get("name")) for a in compute_apps)
        problems.append(f"other GPU compute processes are visible ({names}); stop them first")
    if lease_error is not None:
        problems.append(f"the GPU lease file is unreadable ({lease_error})")
    elif lease is None:
        problems.append("no GPU lease is held; the lease must be held by comfyui (start the ComfyUI tab)")
    elif lease.holder != "comfyui":
        problems.append(f"the GPU lease is held by {lease.holder}, not comfyui")
    return problems


def make_row(**values):
    """A CSV row dict with every column present; missing values are empty strings; floats are rounded."""
    unknown = set(values) - set(COLUMNS)
    if unknown:
        raise ValueError(f"unknown CSV columns: {sorted(unknown)}")
    row = {c: "" for c in COLUMNS}
    for key, value in values.items():
        if isinstance(value, float):
            value = round(value, 3)
        elif isinstance(value, bool):
            value = "true" if value else "false"
        row[key] = "" if value is None else value
    return row


def append_row(path, row, columns=COLUMNS):
    """Appends one row, writing the header when the file is new. Refuses a file whose header differs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        with path.open(newline="", encoding="utf-8") as f:
            header = next(csv.reader(f), [])
        if header != list(columns):
            raise ValueError(f"{path} has a different header; refusing to append")
        new_file = False
    else:
        new_file = True
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(columns), extrasaction="raise")
        if new_file:
            writer.writeheader()
        writer.writerow({c: row.get(c, "") for c in columns})


# ---------------------------------------------------------------- sampling

class Sampler:
    """Calls read_fn every `interval` seconds on a daemon thread and keeps every non-None value."""

    def __init__(self, read_fn, interval=SAMPLE_S):
        self.values = []
        self.errors = 0
        self._read = read_fn
        self._interval = interval
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="comfy-spike-sampler", daemon=True)

    def _run(self):
        while not self._stop.is_set():
            try:
                value = self._read()
                if value is not None:
                    self.values.append(value)
            except Exception:  # noqa: BLE001 - a failed sample must not stop the run
                self.errors += 1
            self._stop.wait(self._interval)

    def start(self):
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)
        return self


class TypeperfSampler:
    """Streams `typeperf` (Windows) and keeps the summed shared GPU memory in bytes per sample."""

    def __init__(self):
        self.values = []
        self._proc = None
        self._thread = None

    def start(self):
        self._proc = subprocess.Popen(["typeperf", SHARED_USAGE_COUNTER, "-si", str(int(SAMPLE_S))],
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                      errors="replace")
        self._thread = threading.Thread(target=self._read, name="comfy-spike-typeperf", daemon=True)
        self._thread.start()
        return self

    def _read(self):
        for line in self._proc.stdout:
            value = parse_typeperf_line(line)
            if value is not None:
                self.values.append(value)

    def stop(self):
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        return self


def _run_cmd(args, timeout=15):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def read_vram_mb():
    out = _run_cmd(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"])
    if out.returncode != 0:
        raise RuntimeError((out.stderr or "nvidia-smi failed").strip())
    return parse_nvidia_smi_used_mb(out.stdout)


def read_compute_apps():
    out = _run_cmd(["nvidia-smi", "--query-compute-apps=pid,process_name,used_memory", "--format=csv,noheader,nounits"])
    if out.returncode != 0:
        raise RuntimeError((out.stderr or "nvidia-smi failed").strip())
    return parse_compute_apps(out.stdout)


def read_container_ram_mb(container):
    out = _run_cmd(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container])
    if out.returncode != 0:
        raise RuntimeError((out.stderr or "docker stats failed").strip())
    return parse_mem_usage_mb(out.stdout)


def read_driver_version():
    out = _run_cmd(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"])
    return out.stdout.strip().splitlines()[0] if out.returncode == 0 and out.stdout.strip() else ""


# ---------------------------------------------------------------- HTTP (ComfyUI and Ollama)

def http_json(url, method="GET", body=None, timeout=10):
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # local endpoints only
    with opener.open(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw.strip() else {}


def http_bytes(url, timeout=120):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=timeout) as r:
        return r.read()


def submit_prompt(base, wf, client_id):
    data = http_json(base + "/prompt", "POST", {"prompt": wf, "client_id": client_id}, timeout=30)
    if data.get("node_errors"):
        raise RuntimeError(f"ComfyUI rejected the workflow: {json.dumps(data['node_errors'])[:800]}")
    return data["prompt_id"]


def wait_history(base, prompt_id, timeout=JOB_TIMEOUT_S, poll=POLL_S):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        entry = (http_json(f"{base}/history/{prompt_id}", timeout=15) or {}).get(prompt_id)
        if entry:
            status = (entry.get("status") or {}).get("status_str")
            if status == "error":
                raise RuntimeError("ComfyUI reported an error for this job; see the ComfyUI log")
            return entry
        time.sleep(poll)
    raise TimeoutError(f"no /history entry for {prompt_id} after {timeout} s")


def download_output(base, file_info, dest):
    query = urllib.parse.urlencode({"filename": file_info["filename"], "subfolder": file_info["subfolder"],
                                    "type": file_info["type"]})
    data = http_bytes(f"{base}/view?{query}")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def guard_state(comfy_url, ollama_native, lease_module=None):
    """Reads the three guard inputs and returns the list of problems (empty when the GPU is free for us)."""
    if lease_module is None:
        from router import gpu_lease as lease_module
    try:
        models = lease_module.loaded_models(ollama_native)
    except Exception as e:  # noqa: BLE001
        models = [f"unknown ({e})"]
    try:
        apps = read_compute_apps()
        apps_error = None
    except Exception as e:  # noqa: BLE001
        apps, apps_error = [], e
    lease, lease_error = None, None
    try:
        lease = lease_module.read()
    except Exception as e:  # noqa: BLE001 - LeaseUnreadable and I/O errors both refuse
        lease_error = str(e) or type(e).__name__
    problems = guard_problems(models, apps, lease, lease_error)
    if apps_error is not None:
        problems.append(f"nvidia-smi could not list compute processes ({apps_error})")
    return problems


def require_free_gpu(comfy_url, ollama_native, lease_module=None):
    problems = guard_state(comfy_url, ollama_native, lease_module)
    if problems:
        raise GuardRefused(problems)


# ---------------------------------------------------------------- one run

def run_once(*, workflow_path, seed, prompt, settings, out_dir, comfy_url, container, ollama_native,
             tag="spike", lease_module=None, patch=None):
    """Runs the workflow once and returns a CSV row dict (psnr and ssim left empty). Raises GuardRefused before
    anything is submitted. The clip is saved under out_dir. `patch` (dict -> dict) changes the workflow for a
    quality variant; the hash then covers the patched workflow."""
    raw = Path(workflow_path).read_bytes()
    base_wf = load_workflow(workflow_path)
    if patch is not None:
        base_wf = patch(json.loads(json.dumps(base_wf)))
        raw = json.dumps(base_wf, sort_keys=True).encode("utf-8")
    wf = inject(base_wf, seed, prompt)
    steps = workflow_steps(wf)
    loaders = node_ids(wf, LOADER_CLASSES)
    sampler = (node_ids(wf, (SAMPLER_CLASS,)) or [None])[0]
    require_free_gpu(comfy_url, ollama_native, lease_module)
    stats = parse_system_stats(http_json(comfy_url + "/system_stats"))

    vram = Sampler(read_vram_mb).start()
    apps = Sampler(read_compute_apps).start()
    ram = Sampler(lambda: read_container_ram_mb(container)).start() if container else None
    spill = TypeperfSampler().start() if sys.platform == "win32" else None
    try:
        time.sleep(IDLE_S)
        idle_bytes = idle_value(spill.values) if spill else None
        i_vram, i_apps = len(vram.values), len(apps.values)
        i_ram = len(ram.values) if ram else 0
        i_spill = len(spill.values) if spill else 0
        t0 = time.monotonic()
        prompt_id = submit_prompt(comfy_url, wf, str(uuid.uuid4()))
        entry = wait_history(comfy_url, prompt_id)
        wall_s = time.monotonic() - t0
    finally:
        vram.stop()
        apps.stop()
        if ram:
            ram.stop()
        if spill:
            spill.stop()

    load_s, sampler_total = timings_from_history(entry, loaders, sampler)
    peak_vram = max(vram.values[i_vram:], default=None)
    peak_ram = max(ram.values[i_ram:], default=None) if ram else None
    spill_flag, _excess = spill_check(idle_bytes, spill.values[i_spill:] if spill else [])
    nvsmi_procs = any(apps.values[i_apps:])

    files = find_output_files(entry)
    if not files:
        raise RuntimeError("the job finished but /history lists no saved file (check the output key, ltx098.NOTES.md)")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    ext = Path(files[0]["filename"]).suffix or ".mp4"
    dest = Path(out_dir) / f"{tag}_seed{seed}_{stamp}{ext}"
    download_output(comfy_url, files[0], dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()

    pairs = [("prompt_sha", hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]),
             ("steps", steps), ("torch", stats["torch"]), ("cuda", stats["cuda"]),
             ("comfyui", stats["comfyui"]), ("nvsmi_procs", "yes" if nvsmi_procs else "no"),
             ("wslconfig_mb", read_wslconfig_memory_mb() or "default"), ("driver", read_driver_version())]
    return make_row(workflow_hash=workflow_hash(raw), seed=seed, settings=settings + ";" + settings_string(pairs),
                    wall_s=wall_s, load_s=load_s, sampler_s_per_step=sampler_s_per_step(sampler_total, steps),
                    peak_vram_mb=peak_vram, peak_ram_mb=peak_ram, spill=spill_flag,
                    output_path=str(dest), sha256=digest)


# ---------------------------------------------------------------- CLI

def build_parser():
    p = argparse.ArgumentParser(description="ComfyUI LTX 0.9.8 feasibility spike (one run, one CSV row).")
    p.add_argument("--dry-run", action="store_true", help="validate the workflow and print the plan; contact nothing")
    p.add_argument("--workflow", default=DEFAULT_WORKFLOW, help="workflow name in docker/comfyui/workflows (default ltx098)")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    p.add_argument("--comfy-url", default=os.getenv("COMFY_URL", DEFAULT_COMFY_URL))
    p.add_argument("--ollama-url", default=os.getenv("TF_OLLAMA_NATIVE_URL", DEFAULT_OLLAMA_NATIVE))
    p.add_argument("--container", default=DEFAULT_CONTAINER, help="container name for docker stats ('' to skip)")
    p.add_argument("--out-dir", default=str(REFERENCE_DIR))
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    wf_path = WORKFLOW_DIR / f"{args.workflow}.json"
    try:
        wf = load_workflow(wf_path)
        inject(wf, args.seed, args.prompt)
    except WorkflowError as e:
        print(f"Workflow error: {e}")
        return 2
    steps = workflow_steps(wf)
    if args.dry_run:
        print("DRY RUN: nothing is contacted, nothing is written.")
        print(f"  workflow      {wf_path} (hash {workflow_hash(wf_path.read_bytes())[:16]}..., {len(wf)} nodes)")
        print(f"  seed node     {find_by_title(wf, 'seed')} -> seed {args.seed}")
        print(f"  prompt node   {find_by_title(wf, 'prompt')} -> {args.prompt[:60]!r}")
        print(f"  sampler steps {steps}")
        print(f"  ComfyUI       {args.comfy_url}  (POST /prompt, GET /history, GET /system_stats, GET /view)")
        print(f"  Ollama        {args.ollama_url}  (/api/ps)")
        print(f"  container     {args.container or '(none: RAM not sampled)'}")
        print(f"  clips to      {args.out_dir}")
        print(f"  CSV           {BASELINE_CSV}")
        print("  guards        no Ollama model loaded; no nvidia-smi compute process; lease held by comfyui")
        return 0
    try:
        row = run_once(workflow_path=wf_path, seed=args.seed, prompt=args.prompt,
                       settings="spike=baseline", out_dir=args.out_dir, comfy_url=args.comfy_url,
                       container=args.container, ollama_native=args.ollama_url)
    except GuardRefused as e:
        print("Refusing to run; the GPU is not free for ComfyUI:")
        for problem in e.problems:
            print(f"  - {problem}")
        return 2
    except (OSError, RuntimeError, TimeoutError, ValueError) as e:
        print(f"Run failed: {e}")
        return 1
    append_row(BASELINE_CSV, row)
    print(f"Wrote one row to {BASELINE_CSV}")
    print(f"  clip {row['output_path']}")
    print(f"  wall {row['wall_s']} s, load {row['load_s']} s, peak VRAM {row['peak_vram_mb']} MB, spill {row['spill']}")
    print("Next: check the clip by eye against generate_ltx.py output, then confirm the lease is released after the debounce.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
