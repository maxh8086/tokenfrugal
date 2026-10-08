"""Check TokenFrugal prerequisites on any OS. Installs nothing; prints what is missing and how to fix it."""
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


def llm_url() -> str:
    if (ROOT / ".env").exists():
        for ln in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if ln.startswith("TOKENFRUGAL_LLM_URL="):
                return ln.split("=", 1)[1].strip()
    return os.getenv("TOKENFRUGAL_LLM_URL", "http://localhost:11434/v1")


def main() -> int:
    osn, bad = platform.system(), 0

    def report(name, ok, fix=""):
        nonlocal bad
        print(f"[{'ok' if ok else 'MISSING'}] {name}" + ("" if ok else f"  ->  {fix}"))
        bad += not ok

    report("python >= 3.11", sys.version_info >= (3, 11), "install Python 3.11+ (3.10.0 breaks pydantic)")
    report("git", bool(shutil.which("git")), HINTS["git"].get(osn, ""))
    dk = bool(shutil.which("docker"))
    report("docker CLI", dk, HINTS["docker"].get(osn, ""))
    if dk:
        up = subprocess.run(["docker", "info"], capture_output=True).returncode == 0
        report("docker daemon running", up, "start Docker Desktop / the docker service")
    url = llm_url()
    try:
        urllib.request.urlopen(url.rstrip("/") + "/models", timeout=3)
        report(f"LLM endpoint {url}", True)
    except Exception:
        report(f"LLM endpoint {url}", False, "start Ollama (" + HINTS["ollama"].get(osn, "") + ") or set TOKENFRUGAL_LLM_URL in .env")
    if bad:
        print("\nTell your agent (Claude Code/Codex) or run the hints above yourself. Nothing was installed.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
