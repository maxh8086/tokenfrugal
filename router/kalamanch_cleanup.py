"""Run the KalaManch voice cleanup from the router, in the background.

Set KALAMANCH_DIR to the kalamanch checkout. KALAMANCH_PYTHON optionally names
the interpreter that has kalamanch's dependencies; it defaults to this one.
At most one cleanup starts per day, so a busy router does not hit Voicebox on
every call. Nothing here can fail a dispatch.
"""

import os
import subprocess
import sys
import threading
import time

INTERVAL_S = 86400
_last_started = None
_lock = threading.Lock()


def maybe_run(now=None):
    """Start a cleanup thread if KALAMANCH_DIR is set and a day has passed since the last one."""
    global _last_started
    kdir = os.environ.get("KALAMANCH_DIR")
    if not kdir:
        return False
    now = time.monotonic() if now is None else now
    with _lock:
        if _last_started is not None and now - _last_started < INTERVAL_S:
            return False
        _last_started = now
    threading.Thread(target=_run, args=(kdir,), daemon=True).start()
    return True


def _run(kdir):
    python = os.environ.get("KALAMANCH_PYTHON") or sys.executable
    try:
        result = subprocess.run(
            [python, "-m", "kalamanch.cli", "cleanup"],
            cwd=kdir, capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"kalamanch cleanup could not run: {exc}", file=sys.stderr)
        return
    if result.returncode:
        print(f"kalamanch cleanup failed: {result.stderr.strip()[-300:]}", file=sys.stderr)
