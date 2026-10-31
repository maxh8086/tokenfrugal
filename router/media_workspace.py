"""Shared media workspace: one folder used by content-writer, content-analyst, the content-* roles and video-editor.

Resolution order (identical everywhere, stdlib only):
  1. env VIDEO_EDITOR_DIR
  2. %OneDrive%\\Videos\\video-editor            when the OneDrive env var is set
  3. <user profile>\\OneDrive\\Videos\\video-editor  when <user profile>\\OneDrive is an existing folder
  4. <user profile>\\Videos\\video-editor
"""
import os
from pathlib import Path

ENV_VAR = "VIDEO_EDITOR_DIR"
FOLDER = ("Videos", "video-editor")
# Folders under the root, relative and '/'-separated. The root itself is always checked too.
LAYOUT = ("Raw", "References", "Render", "content", "analyst", "analyst/daily")


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
    return ["."] + list(LAYOUT)


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
