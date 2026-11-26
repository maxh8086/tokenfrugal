"""Starts a local Ollama server when the router's LLM endpoint is local and not answering.

Best-effort and detached: the server outlives the router, like the ComfyUI bridge. Only a localhost/127.0.0.1 endpoint
is started; a remote endpoint is never touched. TOKENFRUGAL_OLLAMA_AUTOSTART=0 disables it.
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse

from .config import OLLAMA_URL

LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
WAIT_S = 30.0


def enabled() -> bool:
    return os.getenv("TOKENFRUGAL_OLLAMA_AUTOSTART", "1").lower() not in ("0", "false", "no", "off")


def is_local(url: str) -> bool:
    return (urlparse(url).hostname or "") in LOCAL_HOSTS


def reachable(url: str = OLLAMA_URL) -> bool:
    try:
        urllib.request.urlopen(url.rstrip("/") + "/models", timeout=2).read(1)
        return True
    except Exception:  # noqa: BLE001
        return False


def binary() -> str | None:
    found = shutil.which("ollama")
    if found:
        return found
    if os.name == "nt":
        cand = os.path.join(os.getenv("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe")
        if os.path.isfile(cand):
            return cand
    return None


def ensure(url: str = OLLAMA_URL) -> bool:
    """True when the endpoint answers (already running or started now)."""
    if not enabled() or not is_local(url) or reachable(url):
        return reachable(url)
    exe = binary()
    if not exe:
        print("tokenfrugal ollama: ollama not found, endpoint stays down", file=sys.stderr)
        return False
    flags = 0
    if os.name == "nt":
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    try:
        subprocess.Popen([exe, "serve"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    except OSError as e:
        print(f"tokenfrugal ollama: could not start ({e})", file=sys.stderr)
        return False
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        if reachable(url):
            return True
        time.sleep(0.5)
    print("tokenfrugal ollama: started but not answering yet", file=sys.stderr)
    return False
