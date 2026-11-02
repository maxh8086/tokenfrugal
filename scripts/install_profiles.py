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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.media_workspace import media_dir  # noqa: E402
from scripts.ensure_media_workspace import run as ensure_media  # noqa: E402


def fill(text: str, ws: str, media: str) -> str:
    """Replace the profile placeholders: __WORKSPACE__ (repo/workspace), __MEDIA__ (shared media folder), __REPO__."""
    return text.replace("__WORKSPACE__", ws).replace("__MEDIA__", media).replace("__REPO__", str(ROOT).replace("\\", "/"))


def ensure_images() -> None:
    """Build helper images that no compose service owns (penpot-mcp is built by compose)."""
    img = "maxh8086/chrome-devtools-mcp:1"
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
    if ensure_media([]) != 0:  # create the shared media folder tree before any profile points at it
        return 1
    media = media_dir().as_posix()
    ensure_images()
    with tempfile.TemporaryDirectory() as tmp:
        for src in sorted((ROOT / "profiles").glob("*.yaml")):
            name = src.stem
            out = Path(tmp) / src.name
            out.write_text(fill(src.read_text(encoding="utf-8"), ws, media), encoding="utf-8")
            subprocess.run(["docker", "mcp", "profile", "remove", name], capture_output=True)
            r = subprocess.run(["docker", "mcp", "profile", "import", str(out)], capture_output=True, text=True)
            print(("ok   " if r.returncode == 0 else "FAIL ") + name, (r.stderr or r.stdout).strip()[:200] if r.returncode else "")
            if r.returncode:
                return 1
    print(f"Profiles installed (workspace {ws}, media {media}). Set CC_WORKSPACE in .env to the workspace path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
