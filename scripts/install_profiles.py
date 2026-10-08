"""Register TokenFrugal's Docker MCP profiles (profiles/*.yaml) with Docker Desktop's MCP Toolkit.

Usage: python scripts/install_profiles.py [--workspace PATH]
The workspace (mounted into the file/git tools) defaults to CC_WORKSPACE from .env, else the repo root.
Safe to re-run: existing profiles with the same name are replaced.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def ensure_images() -> None:
    """Build helper images that no compose service owns (penpot-mcp is built by compose)."""
    img = "tokenfrugal/chrome-devtools-mcp:1"
    if subprocess.run(["docker", "image", "inspect", img], capture_output=True).returncode:
        print("building", img)
        subprocess.run(["docker", "build", "-t", img, str(ROOT / "docker" / "chrome-devtools-mcp")], check=True)
    img = "tokenfrugal/penpot-mcp:1"
    if subprocess.run(["docker", "image", "inspect", img], capture_output=True).returncode:
        print("building", img)
        subprocess.run(["docker", "build", "-t", img, str(ROOT / "docker" / "penpot-mcp")], check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=None)
    ws = ap.parse_args().workspace
    if not ws:
        try:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
        except ImportError:
            pass
        ws = os.getenv("CC_WORKSPACE") or ROOT.as_posix()
    ws = Path(ws).resolve().as_posix()
    ensure_images()
    with tempfile.TemporaryDirectory() as tmp:
        for src in sorted((ROOT / "profiles").glob("*.yaml")):
            name = src.stem
            out = Path(tmp) / src.name
            out.write_text(src.read_text(encoding="utf-8").replace("__WORKSPACE__", ws), encoding="utf-8")
            subprocess.run(["docker", "mcp", "profile", "remove", name], capture_output=True)
            r = subprocess.run(["docker", "mcp", "profile", "import", str(out)], capture_output=True, text=True)
            print(("ok   " if r.returncode == 0 else "FAIL ") + name, (r.stderr or r.stdout).strip()[:200] if r.returncode else "")
            if r.returncode:
                return 1
    print(f"Profiles installed (workspace {ws}). Set CC_WORKSPACE in .env to this exact path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
