"""Check TokenFrugal prerequisites on any OS. Installs nothing; prints what is missing and how to fix it."""
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HINTS = {
    "docker": {"Windows": "winget install Docker.DockerDesktop", "Darwin": "brew install --cask docker",
               "Linux": "https://docs.docker.com/engine/install/ (Podman/Colima/Rancher Desktop also work)"},
    "ollama": {"Windows": "winget install Ollama.Ollama", "Darwin": "brew install ollama",
               "Linux": "curl -fsSL https://ollama.com/install.sh | sh"},
    "git": {"Windows": "winget install Git.Git", "Darwin": "brew install git", "Linux": "use your package manager"},
}


# Tag to confirm at the first ComfyUI build. --pull never below, so doctor never downloads it.
GPU_TEST_IMAGE = "nvidia/cuda:12.6.3-base-ubuntu24.04"


def gpu_container_ok() -> bool:
    """True when a container with GPU access runs nvidia-smi. Uses only a local image (--pull never)."""
    try:
        r = subprocess.run(["docker", "run", "--rm", "--pull", "never", "--gpus", "all", GPU_TEST_IMAGE, "nvidia-smi", "-L"],
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


MIN_DRIVER_MAJOR = 525  # CUDA 12.x minimum; warning only (the ComfyUI spike records the real torch and CUDA versions)


def driver_check(report) -> None:
    """Warning: the NVIDIA driver version (needed by the ComfyUI GPU lease). Missing nvidia-smi is also a warning."""
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=15)
        version = r.stdout.strip().splitlines()[0] if r.returncode == 0 and r.stdout.strip() else ""
    except (OSError, subprocess.TimeoutExpired, IndexError):
        version = ""
    if not version:
        report("NVIDIA driver (nvidia-smi)", False,
               "install the NVIDIA driver; the ComfyUI GPU lease needs nvidia-smi", soft=True)
        return
    major = version.split(".")[0]
    ok = major.isdigit() and int(major) >= MIN_DRIVER_MAJOR
    report(f"NVIDIA driver {version} >= {MIN_DRIVER_MAJOR} (CUDA 12)", ok,
           f"update the NVIDIA driver to {MIN_DRIVER_MAJOR} or newer for the ComfyUI image", soft=True)


def wslconfig_check(report) -> None:
    """Warning: the WSL2 memory limit in %USERPROFILE%\\.wslconfig. A low cap kills the container during a model load."""
    if platform.system() != "Windows":
        print("[skip] .wslconfig memory limit (Windows only)")
        return
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from comfy_spike import read_wslconfig_memory_mb
    try:
        limit = read_wslconfig_memory_mb()
    except ValueError as e:
        report("WSL memory limit (.wslconfig [wsl2] memory)", False, f"fix the memory value in .wslconfig: {e}", soft=True)
        return
    if limit is None:
        report("WSL memory limit (.wslconfig [wsl2] memory)", False,
               "set [wsl2] memory=<GB>GB in %USERPROFILE%\\.wslconfig (WSL default is half the RAM); then wsl --shutdown",
               soft=True)
    else:
        report(f"WSL memory limit {limit:.0f} MB (.wslconfig)", True)


def llm_url() -> str:
    if (ROOT / ".env").exists():
        for ln in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if ln.startswith("TOKENFRUGAL_LLM_URL="):
                return ln.split("=", 1)[1].strip()
    return os.getenv("TOKENFRUGAL_LLM_URL", "http://localhost:11434/v1")


def required_models() -> list[tuple[str, str]]:
    """(tag, Modelfile name) for the builder and thinker models named in router/tf-roles.yaml."""
    import yaml
    models = yaml.safe_load((ROOT / "router" / "tf-roles.yaml").read_text(encoding="utf-8"))["models"]
    return [(models["builder"], "builder.Modelfile"), (models["thinker"], "thinker.Modelfile")]


def main() -> int:
    osn, bad = platform.system(), 0

    def report(name, ok, fix="", soft=False):
        nonlocal bad
        label = "ok" if ok else ("warn" if soft else "MISSING")
        print(f"[{label}] {name}" + ("" if ok else f"  ->  {fix}"))
        bad += not ok and not soft

    report("python >= 3.11", sys.version_info >= (3, 11), "install Python 3.11+ (3.10.0 breaks pydantic)")
    report("git", bool(shutil.which("git")), HINTS["git"].get(osn, ""))
    dk = bool(shutil.which("docker"))
    report("docker CLI", dk, HINTS["docker"].get(osn, ""))
    if dk:
        up = subprocess.run(["docker", "info"], capture_output=True).returncode == 0
        report("docker daemon running", up, "start Docker Desktop / the docker service")
        if up:  # warning only: machines without a GPU still pass
            report("docker GPU container (nvidia-smi)", gpu_container_ok(),
                   f"needed only for the ComfyUI GPU lease: install the NVIDIA driver and container toolkit, then docker pull {GPU_TEST_IMAGE}",
                   soft=True)
    else:
        print("[skip] docker GPU container check (docker is not installed)")
    driver_check(report)
    wslconfig_check(report)
    url = llm_url()
    have = None  # installed model ids, None when the endpoint is unreachable
    try:
        urllib.request.urlopen(url.rstrip("/") + "/models", timeout=3)
        report(f"LLM endpoint {url}", True)
        have = {m.get("id") for m in json.load(urllib.request.urlopen(url.rstrip("/") + "/models", timeout=3)).get("data", [])}
        for tag, modelfile in required_models():
            report(f"model {tag}", tag in have, f"ollama pull <base> && ollama create {tag} -f models/{modelfile}")
    except Exception:
        report(f"LLM endpoint {url}", False, "start Ollama (" + HINTS["ollama"].get(osn, "") + ") or set TOKENFRUGAL_LLM_URL in .env")
    if have is not None:  # content-pipeline stage models: report only, never pulled, not counted as failures
        sys.path.insert(0, str(ROOT))
        from router.config import load_tf_roles
        from router.preflight import stage_model_gaps
        for agent, tag in stage_model_gaps(load_tf_roles(), have):
            print(f"[stage] {agent} needs {tag}, not installed  ->  ollama pull {tag} (not pulled automatically)")
    if bad:
        print("\nTell your agent (Claude Code/Codex) or run the hints above yourself. Nothing was installed.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
