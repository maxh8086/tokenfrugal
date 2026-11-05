"""Media generator (stdio). Lists the Raw and Render folders and runs mgen on one raw clip in the media-generator container."""
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from fastmcp import FastMCP

from router.events import emit
from router.media_workspace import (
    FILMS, SHORTS, films_dir, media_dir, output_dir, raw_dir, render_dir, render_name, shorts_dir,
)
from router.model_sync import ensure_models

mcp = FastMCP("media-generator")

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
    """List the raw clip file names in the media workspace Raw folder."""
    names = _names(raw_dir(_workspace()))
    return "\n".join(names) if names else "no clips in Raw"


@mcp.tool()
def list_renders() -> str:
    """List the finished files: films/ (render_film) and shorts/ (mgen) under the output folder."""
    ws = _workspace()
    rows = [f"{FILMS}/{n}" for n in _names(films_dir(ws))] + [f"{SHORTS}/{n}" for n in _names(shorts_dir(ws))]
    return "\n".join(rows) if rows else "no files in Render"


@mcp.tool()
def mgen(clip: str, out_name: str = "", no_music: bool = False, captions: str = "auto") -> str:
    """Turn one clip from Raw into a captioned 9:16 short, saved to the shorts folder. clip = bare file name in Raw.
    out_name = optional output name. no_music = True skips the music bed. captions = auto (default, skips word captions when the clip has burned-in subtitles), on (always add them) or off (never add them). Returns the last output lines and the Render path."""
    try:
        clip = _check(clip, "clip")
        out_name = _check(out_name, "output") if out_name else ""
        if captions not in ("auto", "on", "off"):
            raise ValueError("bad captions value")
        ws = _workspace()
        if not (raw_dir(ws) / clip).is_file():
            return "error: clip not found in Raw"
        err = ensure_models()  # pull models only after the request is valid
        if err:
            return err
        render = render_dir(ws)
        before = set(_names(render))
        argv = ["docker", "compose", "-f", str(COMPOSE_FILE), "--profile", "video", "run", "--rm", "-T",
                "media-generator", "mgen", clip, "--captions", captions]
        if out_name:
            argv += ["--out", out_name]
        if no_music:
            argv.append("--no-music")
        env = dict(os.environ)
        env["VIDEO_EDITOR_DIR"] = str(ws)  # compose mounts this same resolved folder at /work
        env["VIDEO_EDITOR_RENDER_DIR"] = render_name()  # the container writes its output to this folder name
        env.setdefault("TF_SECRETS_DIR", str(Path.home() / ".docker" / "mcp" / "secrets"))
        r = subprocess.run(argv, capture_output=True, text=True, timeout=TIMEOUT, env=env)
        lines = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()
        out = "\n".join(lines[-MAX_LINES:])
        new = sorted(set(_names(render)) - before)
        stem = out_name[:-4] if out_name.endswith(".mp4") else out_name
        src = render / f"{stem}.mp4" if out_name else (render / new[0] if new else None)
        path = _place_short(src, ws) if src is not None and src.is_file() else (src or render)
        return f"exit={r.returncode}\n{out}\nSaved: {path}"
    except subprocess.TimeoutExpired:
        return f"error: timed out after {TIMEOUT} s"
    except ValueError as e:
        return f"error: {e}"
    except Exception as e:  # noqa: BLE001
        return f"error: {type(e).__name__}: {str(e)[:150]}"


FILM_FPS = (24, 30, 60)
FILM_SCENES_MAX = 10
FILM_TEXT_MAX = 80
FILM_SUB_MAX = 120
FILM_SECONDS_MIN = 0.83
FILM_SECONDS_MAX = 8
FILM_TOTAL_MAX = 60
FILM_TIMEOUT = 900
FILM_REPLY_MAX = 300
RENDER_ENGINE_DEFAULT = "http://127.0.0.1:3000"
NOT_RUNNING = "render engine is not running: start it with docker compose --profile video up -d render-engine"


def _cap(text: str) -> str:
    return text if len(text) <= FILM_REPLY_MAX else text[: FILM_REPLY_MAX - 3] + "..."


def _engine_base() -> str:
    return (os.environ.get("RENDER_ENGINE_URL") or RENDER_ENGINE_DEFAULT).strip().rstrip("/")


def _validate_scenes(scenes_json: str) -> tuple[list[dict], float]:
    """Parse and check a scenes brief. Returns (scenes as the engine expects them, total seconds). Raises ValueError."""
    try:
        data = json.loads(scenes_json)
    except (TypeError, ValueError):
        raise ValueError("scenes_json is not valid JSON") from None
    if not isinstance(data, list):
        raise ValueError("scenes_json must be a JSON array")
    if not 1 <= len(data) <= FILM_SCENES_MAX:
        raise ValueError(f"scenes_json must have 1 to {FILM_SCENES_MAX} scenes, got {len(data)}")
    scenes = []
    for i, item in enumerate(data, 1):
        if not isinstance(item, dict):
            raise ValueError(f"scene {i} must be an object")
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"scene {i} text must be a non-empty string")
        if len(text.strip()) > FILM_TEXT_MAX:
            raise ValueError(f"scene {i} text is longer than {FILM_TEXT_MAX} characters")
        sub = item.get("sub", item.get("subtitle"))
        if sub is None:
            sub = ""
        if not isinstance(sub, str):
            raise ValueError(f"scene {i} sub must be a string")
        if len(sub.strip()) > FILM_SUB_MAX:
            raise ValueError(f"scene {i} sub is longer than {FILM_SUB_MAX} characters")
        seconds = item.get("seconds", item.get("duration"))
        if (isinstance(seconds, bool) or not isinstance(seconds, (int, float))
                or not FILM_SECONDS_MIN <= seconds <= FILM_SECONDS_MAX):
            raise ValueError(f"scene {i} seconds must be a number from {FILM_SECONDS_MIN} to {FILM_SECONDS_MAX}")
        scenes.append({"text": text.strip(), "sub": sub.strip(), "seconds": float(seconds)})
    total = round(sum(s["seconds"] for s in scenes), 2)
    if total > FILM_TOTAL_MAX:
        raise ValueError(f"scenes total {total} seconds, the limit is {FILM_TOTAL_MAX}")
    return scenes, total


def _free_name(folder: Path, stem: str) -> str:
    candidate, n = f"{stem}.mp4", 2
    while (folder / candidate).exists():
        candidate = f"{stem}-{n}.mp4"
        n += 1
    return candidate


def _place_short(src: Path, root: Path) -> Path:
    """Move a finished short from the render folder into the shorts folder, keeping its name unless taken.
    Returns the new path, or src when the move fails."""
    folder = shorts_dir(root)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / _free_name(folder, src.stem)
        os.replace(src, dest)
        return dest
    except OSError:
        return src


def _render_film_call(scenes_json: str, fps: int, music: bool, narration: bool, name: str) -> tuple[str, str, str]:
    """Returns (reply, status, error). status is the HTTP code, or validation, unreachable, timeout or error."""
    try:
        scenes, total = _validate_scenes(scenes_json)
        if fps not in FILM_FPS:
            raise ValueError(f"fps must be one of {', '.join(map(str, FILM_FPS))}")
        stem = _check(name or "film", "name")
    except ValueError as e:
        return _cap(f"error: {e}"), "validation", str(e)

    body = {"scenes": scenes, "fps": fps, "narration": bool(narration), "music": bool(music)}
    req = urllib.request.Request(_engine_base() + "/render", data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=FILM_TIMEOUT) as resp:
            status = str(resp.status)
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read().decode("utf-8", "replace") or "{}")
        except ValueError:
            payload = {}
        err = str(payload.get("error", "")) if isinstance(payload, dict) else ""
        if e.code == 400:
            findings = payload.get("findings") if isinstance(payload, dict) else None
            detail = f" findings={json.dumps(findings, ensure_ascii=False)}" if findings else ""
            return _cap(f"error: render engine rejected the film: {err}.{detail}"), "400", err or "rejected"
        return _cap(f"error: render engine HTTP {e.code}: {err}"), str(e.code), err or f"HTTP {e.code}"
    except urllib.error.URLError as e:
        if isinstance(e.reason, ConnectionRefusedError):
            return NOT_RUNNING, "unreachable", "render engine not running"
        if isinstance(e.reason, TimeoutError):
            return f"error: timed out after {FILM_TIMEOUT} s", "timeout", "timeout"
        return _cap(f"error: render engine unreachable: {e.reason}"), "unreachable", "render engine unreachable"
    except ConnectionRefusedError:
        return NOT_RUNNING, "unreachable", "render engine not running"
    except TimeoutError:
        return f"error: timed out after {FILM_TIMEOUT} s", "timeout", "timeout"
    except (ValueError, OSError):
        return "error: render engine returned an unreadable reply", "error", "bad reply"

    file_name = str(result.get("file", ""))
    if not file_name.endswith(".mp4") or "/" in file_name or "\\" in file_name:
        return "error: render engine returned an unexpected file name", "error", "bad file name"

    # Compose mounts the engine's OUTPUT_DIR at the output folder (MEDIA_OUTPUT_DIR, default the Render folder),
    # so the engine's <uuid>.mp4 is usually already there at the output root. It is moved into the films folder
    # under the requested stem. Otherwise download it over HTTP.
    root_out = output_dir(_workspace())
    folder = films_dir(_workspace())
    folder.mkdir(parents=True, exist_ok=True)
    out_name = _free_name(folder, stem)
    dest = folder / out_name
    local = root_out / file_name
    try:
        if local.is_file():
            os.replace(local, dest)
        else:
            part = folder / (out_name + ".part")
            try:
                with urllib.request.urlopen(f"{_engine_base()}/output/{file_name}", timeout=FILM_TIMEOUT) as resp, part.open("wb") as f:
                    shutil.copyfileobj(resp, f)
                os.replace(part, dest)
            finally:
                part.unlink(missing_ok=True)
    except (OSError, ValueError) as e:
        return _cap(f"error: could not place the film in the films folder: {type(e).__name__}"), "error", "copy failed"

    warnings = len(result.get("warnings") or [])
    audio = "+".join(x for x, on in (("narration", narration), ("music", music)) if on) or "none"
    reply = _cap(f"rendered {dest} | seconds={total:g} fps={fps} audio={audio} warnings={warnings}")
    return reply, status, ""


@mcp.tool()
def render_film(scenes_json: str, fps: int = 30, music: bool = False, narration: bool = False, name: str = "film") -> str:
    """Render a film from a scenes brief through the render engine (docker compose --profile video, service render-engine).
    scenes_json = JSON array of 1 to 10 scenes: {text (max 80 chars), sub or subtitle (optional, max 120), seconds or duration (0.83 to 8)}; total <= 60 s.
    fps = 24, 30 or 60. music = deterministic ffmpeg bed; narration = offline Piper voice (one clip per scene).
    name = short output file stem. The finished MP4 is placed in the films folder. Returns the path, seconds, fps, audio and warning count, or the error."""
    reply, status, error = _render_film_call(scenes_json, fps, music, narration, name)
    emit("render_film", name=str(name)[:60], ok=not error, status=status, error=error[:120])
    return reply


if __name__ == "__main__":
    mcp.run()
