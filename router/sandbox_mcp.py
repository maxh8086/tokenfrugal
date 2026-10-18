"""Sandboxed test runner (stdio). Lets a builder run the tests it just wrote and read the failure, then fix it."""
import os
import re
import subprocess
from pathlib import Path

from fastmcp import FastMCP

mcp = FastMCP("sandbox")

IMAGE = os.getenv("TOKENFRUGAL_SANDBOX_IMAGE", "python:3.13-slim")
TIMEOUT = int(os.getenv("TOKENFRUGAL_SANDBOX_TIMEOUT", "60"))
MAX_LINES = 40
_SAFE = re.compile(r"^[\w./-]+$")


def _workspace() -> Path:
    return Path(os.environ.get("CC_WORKSPACE") or os.getcwd()).resolve()


def _resolve(path: str) -> Path:
    """Map a /workspace/... or relative path to a host folder inside the workspace; refuse anything outside."""
    ws = _workspace()
    p = path.strip().replace("\\", "/")
    p = p[len("/workspace"):] if p.startswith("/workspace") else p
    host = (ws / p.lstrip("/")).resolve()
    if host != ws and ws not in host.parents:
        raise ValueError("path is outside the workspace")
    if not host.is_dir():
        raise ValueError("folder not found")
    return host


def _tail(text: str) -> str:
    lines = text.strip().splitlines()
    return "\n".join(lines[-MAX_LINES:]) if len(lines) > MAX_LINES else text.strip()


def _docker_argv(host: Path, args: list[str]) -> list[str]:
    return ["docker", "run", "--rm", "--network", "none", "--cpus", "2", "--memory", "1g", "--pids-limit", "128",
            "--security-opt", "no-new-privileges", "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{host}:/work:ro", "-w", "/work", IMAGE, "python", *args]


@mcp.tool()
def run_tests(folder: str, test_file: str = "") -> str:
    """Run the unittest tests in a workspace folder inside a network-less sandbox and return the last lines of output.
    folder = project folder (e.g. /workspace/proj). test_file = optional single test module such as test_x.py."""
    try:
        host = _resolve(folder)
        if test_file and not _SAFE.match(test_file):
            return "error: bad test_file"
        if test_file:
            module = test_file[:-3] if test_file.endswith(".py") else test_file
            args = ["-m", "unittest", module.replace("/", ".")]
        else:
            args = ["-m", "unittest", "discover", "-s", ".", "-q"]
        r = subprocess.run(_docker_argv(host, args), capture_output=True, text=True, timeout=TIMEOUT)
        out = _tail((r.stdout or "") + (r.stderr or ""))
        return f"exit={r.returncode}\n{out}" if out else f"exit={r.returncode}"
    except subprocess.TimeoutExpired:
        return f"error: timed out after {TIMEOUT}s"
    except ValueError as e:
        return f"error: {e}"
    except Exception as e:  # noqa: BLE001
        return f"error: {type(e).__name__}: {str(e)[:150]}"


@mcp.tool()
def run_python(folder: str, script: str) -> str:
    """Run one Python script from a workspace folder inside a network-less sandbox; returns exit code and last output lines."""
    try:
        host = _resolve(folder)
        if not _SAFE.match(script) or not script.endswith(".py"):
            return "error: script must be a .py path inside the folder"
        r = subprocess.run(_docker_argv(host, [script]), capture_output=True, text=True, timeout=TIMEOUT)
        out = _tail((r.stdout or "") + (r.stderr or ""))
        return f"exit={r.returncode}\n{out}" if out else f"exit={r.returncode}"
    except subprocess.TimeoutExpired:
        return f"error: timed out after {TIMEOUT}s"
    except ValueError as e:
        return f"error: {e}"
    except Exception as e:  # noqa: BLE001
        return f"error: {type(e).__name__}: {str(e)[:150]}"


if __name__ == "__main__":
    mcp.run()
