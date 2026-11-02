"""Starts the Node dashboard (ui/server.js) with the router and opens it in the browser.

Optional and best-effort: no node, a busy port or a headless box never breaks the router.
TOKENFRUGAL_UI=0 disables it, `port` in router/ui.yaml (or UI_PORT) sets the port, TOKENFRUGAL_UI_OPEN=0 skips the browser pop-up.
"""
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser

import yaml

from . import comfy_bridge, gpu_lease
from .config import ROOT
from .events import UI_TEXT

_proc: subprocess.Popen | None = None


def port() -> int:
    """UI_PORT env wins over `port:` in router/ui.yaml; default 7777."""
    if os.getenv("UI_PORT"):
        return int(os.environ["UI_PORT"])
    try:
        return int(yaml.safe_load(UI_TEXT.read_text(encoding="utf-8")).get("port", 7777))
    except (OSError, ValueError, AttributeError, yaml.YAMLError):
        return 7777


def enabled() -> bool:
    return os.getenv("TOKENFRUGAL_UI", "1").lower() not in ("0", "false", "no", "off")


def listening(p: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", p)) == 0


def start() -> str | None:
    """Returns the dashboard URL, or None when it is disabled or unavailable."""
    global _proc
    if not enabled():
        return None
    p = port()
    url = f"http://127.0.0.1:{p}"
    opened = listening(p)  # another router already serves it: reuse, and do not pop a second tab
    if not opened:
        node, script = shutil.which("node"), ROOT / "ui" / "server.js"
        if not node or not script.exists():
            print("tokenfrugal ui: node or ui/server.js not found, dashboard disabled", file=sys.stderr)
            return None
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            _proc = subprocess.Popen([node, str(script)], cwd=str(ROOT), stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
        except OSError as e:
            print(f"tokenfrugal ui: could not start ({e})", file=sys.stderr)
            return None
        for _ in range(25):
            if listening(p) or _proc.poll() is not None:
                break
            time.sleep(0.1)
        if not listening(p):
            _proc = None
            return None
        if os.getenv("TOKENFRUGAL_UI_OPEN", "1").lower() not in ("0", "false", "no", "off"):
            try:
                webbrowser.open(url)
            except Exception:  # noqa: BLE001
                pass
    return url


def _lease_held() -> bool:
    """True while the GPU lease is held. An unreadable lease counts as held, so nothing is killed by mistake."""
    try:
        return gpu_lease.read() is not None
    except Exception:  # noqa: BLE001
        return True


def start_bridge(comfy_url: str | None = None, container_id: str | None = None):
    """Spawn the detached ComfyUI event bridge, which acquires the GPU lease. Called for a ComfyUI session only, never
    at router start. The dashboard's Start route spawns the same module. Returns the Popen, or None on failure."""
    args = []
    if comfy_url:
        args += ["--comfy-url", comfy_url]
    if container_id:
        args += ["--container-id", container_id]
    try:
        return comfy_bridge.spawn_detached(args)
    except OSError as e:
        print(f"tokenfrugal ui: could not start the ComfyUI bridge ({e})", file=sys.stderr)
        return None


def stop() -> None:
    """Stop the dashboard at router exit, unless a GPU lease is held: then it stays up so the ComfyUI tab can still
    show the session and stop it. The bridge itself is detached and is never terminated here."""
    global _proc
    if _proc and _proc.poll() is None and not _lease_held():
        _proc.terminate()
    _proc = None
