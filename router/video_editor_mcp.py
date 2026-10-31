"""Video editor (stdio). Lists the Raw and Render folders and runs vedit on one raw clip in the video-editor container."""
import os
import re
import subprocess
from pathlib import Path

from fastmcp import FastMCP

from router.media_workspace import media_dir

mcp = FastMCP("video-editor")

REPO = Path(__file__).resolve().parent.parent
COMPOSE_FILE = REPO / "docker-compose.yml"
TIMEOUT = 900
MAX_LINES = 20
_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_ .()-]{0,119}")


def _workspace() -> Path:
    """Shared media folder (Raw / References / Render live here). Resolved by router/media_workspace.py."""
    return media_dir()


def _check(name: str, what: str) -> str:
    """A bare file name only: no path separators, no '..', no leading dash."""
    n = (name or "").strip()
    if not _NAME.fullmatch(n) or ".." in n:
        raise ValueError(f"bad {what} name")
    return n


def _names(folder: Path) -> list[str]:
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.iterdir() if p.is_file())


@mcp.tool()
def list_raw() -> str:
    """List the raw clip file names in the video-editor workspace Raw folder."""
    names = _names(_workspace() / "Raw")
    return "\n".join(names) if names else "no clips in Raw"


@mcp.tool()
def list_renders() -> str:
    """List the finished file names in the video-editor workspace Render folder."""
    names = _names(_workspace() / "Render")
    return "\n".join(names) if names else "no files in Render"


@mcp.tool()
def vedit(clip: str, out_name: str = "", no_music: bool = False) -> str:
    """Turn one clip from Raw into a captioned 9:16 short in Render. clip = bare file name in Raw.
    out_name = optional output name. no_music = True skips the music bed. Returns the last output lines and the Render path."""
    try:
        clip = _check(clip, "clip")
        out_name = _check(out_name, "output") if out_name else ""
        ws = _workspace()
        if not (ws / "Raw" / clip).is_file():
            return "error: clip not found in Raw"
        render = ws / "Render"
        before = set(_names(render))
        argv = ["docker", "compose", "-f", str(COMPOSE_FILE), "--profile", "video", "run", "--rm", "-T",
                "video-editor", "vedit", clip]
        if out_name:
            argv += ["--out", out_name]
        if no_music:
            argv.append("--no-music")
        env = dict(os.environ)
        env["VIDEO_EDITOR_DIR"] = str(ws)  # compose mounts this same resolved folder at /work
        env.setdefault("TF_SECRETS_DIR", str(Path.home() / ".docker" / "mcp" / "secrets"))
        r = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT, env=env)
        lines = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        out = "\n".join(lines[-MAX_LINES:])
        new = sorted(set(_names(render)) - before)
        path = render / out_name if out_name else (render / new[0] if new else render)
        return f"exit={r.returncode}\n{out}\nRender: {path}"
    except subprocess.TimeoutExpired:
        return f"error: timed out after {TIMEOUT} s"
    except ValueError as e:
        return f"error: {e}"
    except Exception as e:  # noqa: BLE001
        return f"error: {type(e).__name__}: {str(e)[:150]}"


if __name__ == "__main__":
    mcp.run()
