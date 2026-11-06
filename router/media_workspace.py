"""Shared media workspace: one folder used by content-writer, content-analyst, the content-* roles and media-generator.

Resolution order (identical everywhere, stdlib only):
  1. env VIDEO_EDITOR_DIR (read from the real environment, then .env)
  2. %OneDrive%\\Videos\\video-editor            when the OneDrive env var is set
  3. <user profile>\\OneDrive\\Videos\\video-editor  when <user profile>\\OneDrive is an existing folder
  4. <user profile>\\Videos\\video-editor
"""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")  # real environment variables win over .env

ENV_VAR = "VIDEO_EDITOR_DIR"
FOLDER = ("Videos", "video-editor")
LAYOUT_ENV = "VIDEO_EDITOR_LAYOUT"  # comma list, relative '/'-separated folders under the root
RENDER_ENV = "VIDEO_EDITOR_RENDER_DIR"  # name of the render folder under the root
DEFAULT_RENDER = "Render"
RAW = "Raw"  # incoming clips; fixed name, not configurable


def render_name() -> str:
    """Name of the render folder under the root. Read at call time from VIDEO_EDITOR_RENDER_DIR (default Render)."""
    return os.environ.get(RENDER_ENV, "").strip() or DEFAULT_RENDER


def layout() -> tuple[str, ...]:
    """Folders under the root, read at call time from VIDEO_EDITOR_LAYOUT (comma list). Unset = the default set.
    The render folder is always included, so ensure_tree() creates it."""
    raw = os.environ.get(LAYOUT_ENV, "").strip()
    if raw:
        parts = [part.strip().strip("/") for part in raw.split(",")]
    else:
        parts = [RAW, "References", render_name(), "content", "analyst", "analyst/daily"]
    parts = [part for part in parts if part]
    if render_name() not in parts:
        parts.append(render_name())
    return tuple(parts)


def render_dir(root: Path) -> Path:
    return root / render_name()


OUTPUT_ENV = "MEDIA_OUTPUT_DIR"  # where finished films are written; unset = the render folder


def output_dir(root: Path) -> Path:
    """Folder that receives finished films. MEDIA_OUTPUT_DIR (read at call time, .env included) wins;
    otherwise the render folder under the root. Creates nothing."""
    value = os.environ.get(OUTPUT_ENV, "").strip()
    if value:
        return Path(os.path.abspath(os.path.expanduser(value)))
    return render_dir(root)


FILMS = "films"  # render_film output (HyperFrames film from a scenes brief), under output_dir()
SHORTS = "shorts"  # mgen output (captioned 9:16 short from a Raw clip), under output_dir()


def films_dir(root: Path) -> Path:
    """Folder for films rendered by the render engine: <output_dir>/films. Creates nothing."""
    return output_dir(root) / FILMS


def shorts_dir(root: Path) -> Path:
    """Folder for shorts made from Raw clips by mgen: <output_dir>/shorts. Creates nothing."""
    return output_dir(root) / SHORTS


def raw_dir(root: Path) -> Path:
    return root / RAW


def media_dir(environ=None, home=None) -> Path:
    """Absolute path of the shared media folder. Creates nothing."""
    env = os.environ if environ is None else environ
    value = env.get(ENV_VAR)
    if value:
        return Path(os.path.abspath(os.path.expanduser(value)))
    profile = Path(home) if home is not None else Path.home()
    onedrive = env.get("OneDrive")
    if onedrive:
        return Path(onedrive).joinpath(*FOLDER)
    if (profile / "OneDrive").is_dir():
        return profile.joinpath("OneDrive", *FOLDER)
    return profile.joinpath(*FOLDER)


def _rel_paths() -> list[str]:
    return ["."] + list(layout())


def check_tree(root: Path) -> list[tuple[str, bool]]:
    """(relative path, exists) for the root and every layout folder. Creates nothing."""
    return [(rel, (root / rel).is_dir()) for rel in _rel_paths()]


def ensure_tree(root: Path) -> list[tuple[str, str]]:
    """Create every missing folder (idempotent). Returns (relative path, 'OK' or 'CREATED')."""
    rows = []
    for rel, exists in check_tree(root):
        (root / rel).mkdir(parents=True, exist_ok=True)
        rows.append((rel, "OK" if exists else "CREATED"))
    return rows
