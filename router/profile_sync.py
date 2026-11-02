"""Keep the Docker MCP profiles imported with the current workspace path.

The profile YAMLs carry a __WORKSPACE__ placeholder (repo workspace) and a __MEDIA__ placeholder (shared media
folder, router/media_workspace.py). ensure_profiles() re-imports them only when either path changes, and records
both in a marker file so repeat runs are free.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from router.media_workspace import media_dir

MARKER = Path(__file__).parent / "profiles_workspace.json"
PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def resolve_workspace(real_env, cwd_root, configured, root):
    """First truthy candidate, in priority order: real env, cwd repo root, .env value, package root."""
    return real_env or cwd_root or configured or root


def _recorded(marker: Path) -> dict:
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, AttributeError):
        return {}


def ensure_profiles(workspace, marker=MARKER, profiles_dir=PROFILES_DIR, run=subprocess.run, media=None) -> bool:
    """Import every profile for `workspace` and the shared media folder (default: media_dir()).
    Returns True only when a full re-import succeeded."""
    media = str(media) if media else media_dir().as_posix()
    rec = _recorded(marker)
    if rec.get("workspace") == workspace and rec.get("media") == media:
        return False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for path in sorted(Path(profiles_dir).glob("*.yaml")):
                name = path.stem
                text = (path.read_text(encoding="utf-8")
                        .replace("__WORKSPACE__", workspace)
                        .replace("__MEDIA__", media))
                tmpfile = Path(tmp) / path.name
                tmpfile.write_text(text, encoding="utf-8")
                run(["docker", "mcp", "profile", "remove", name], capture_output=True)
                r = run(["docker", "mcp", "profile", "import", str(tmpfile)], capture_output=True, text=True)
                if r.returncode != 0:
                    print(f"warning: could not import profile '{name}' for workspace {workspace}: "
                          f"{(r.stderr or r.stdout or '').strip()[:200]}", file=sys.stderr)
                    return False
    except OSError as e:
        print(f"warning: docker profile sync skipped: {e}", file=sys.stderr)
        return False
    Path(marker).write_text(json.dumps({"workspace": workspace, "media": media}), encoding="utf-8")
    return True
