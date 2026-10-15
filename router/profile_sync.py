"""Keep the Docker MCP profiles imported with the current workspace path.

The profile YAMLs carry a __WORKSPACE__ placeholder. ensure_profiles() re-imports them only when the
workspace changes, and records the workspace in a marker file so repeat runs are free.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

MARKER = Path(__file__).parent / "profiles_workspace.json"
PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def resolve_workspace(real_env, cwd_root, configured, root):
    """First truthy candidate, in priority order: real env, cwd repo root, .env value, package root."""
    return real_env or cwd_root or configured or root


def _recorded(marker: Path):
    try:
        return json.loads(marker.read_text(encoding="utf-8")).get("workspace")
    except (OSError, ValueError, AttributeError):
        return None


def ensure_profiles(workspace, marker=MARKER, profiles_dir=PROFILES_DIR, run=subprocess.run) -> bool:
    """Import every profile for `workspace`. Returns True only when a full re-import succeeded."""
    if _recorded(marker) == workspace:
        return False
    try:
        with tempfile.TemporaryDirectory() as tmp:
            for path in sorted(Path(profiles_dir).glob("*.yaml")):
                name = path.stem
                text = path.read_text(encoding="utf-8").replace("__WORKSPACE__", workspace)
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
    Path(marker).write_text(json.dumps({"workspace": workspace}), encoding="utf-8")
    return True
