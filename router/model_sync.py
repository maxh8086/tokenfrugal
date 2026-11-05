"""Make sure the quantized model files under models/ are present before a media job runs.

ensure_models() reads models/.hf_pulled.json. When every recorded file is present with the recorded size it
returns "". Otherwise it runs scripts/hf_models.py pull inside the tokenfrugal/comfyui:1 image and returns "" on
success or an error string. The Docker SDK is not used; this module only calls the docker CLI.
"""
import json
import os
import subprocess
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TIMEOUT = 4 * 60 * 60  # seconds
IMAGE = "tokenfrugal/comfyui:1"
MARKER = ".hf_pulled.json"
_lock = threading.Lock()  # concurrent first jobs share one pull


def _models_dir() -> Path:
    env = os.environ.get("TF_MODELS_DIR")
    return Path(env) if env else REPO / "models"


def _env_file_value(path: Path, key: str) -> str:
    """KEY=value from a .env file, read by hand. Never printed."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.strip() == key:
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
                v = v[1:-1]
            return v
    return ""


def _marker_ok(models: Path) -> bool:
    try:
        data = json.loads((models / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    repos = data.get("repos") or {}
    if not repos:
        return False
    for info in repos.values():
        for rel, size in (info.get("files") or {}).items():
            try:
                if (models / rel).stat().st_size != int(size):
                    return False
            except (OSError, TypeError, ValueError):
                return False
    return True


def ensure_models() -> str:
    """Return "" when all model files are present, else an error string."""
    models = _models_dir()
    if _marker_ok(models):
        return ""
    with _lock:
        if _marker_ok(models):  # another thread finished the pull while this one waited
            return ""
        env = dict(os.environ)
        if not env.get("HF_TOKEN"):
            env["HF_TOKEN"] = _env_file_value(REPO / ".env", "HUGGINGFACE")
        if not env.get("HF_TOKEN"):
            return "error: HUGGINGFACE missing from .env; model pull skipped"
        argv = ["docker", "run", "--rm", "-e", "HF_TOKEN", "-e", "HF_HUB_OFFLINE=0",
                "-v", f"{REPO / 'scripts'}:/work:ro", "-v", f"{models}:/hfmodels",
                "--entrypoint", "python", IMAGE, "/work/hf_models.py", "pull", "--models-dir", "/hfmodels"]
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT, env=env)
        except subprocess.TimeoutExpired:
            return "error: model pull failed: timed out after 4 hours"
        except OSError as e:
            return f"error: model pull failed: {type(e).__name__}"
        if r.returncode != 0:
            tail = "\n".join(((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-10:])
            return "error: model pull failed: " + tail
        if not _marker_ok(models):
            return "error: model pull finished but the marker does not match the files"
        return ""
