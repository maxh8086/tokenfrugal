"""One place for the video-editor workspace: Raw / References / Render.

Folder: VIDEO_EDITOR_DIR if set, else <OneDrive>/Videos/video-editor (OneDrive from %OneDrive% when set),
else ~/Videos/video-editor. Missing folders are created on first use.
"""
import os
from pathlib import Path

SUBDIRS = ("Raw", "References", "Render")


def editor_dir():
    env = os.environ.get("VIDEO_EDITOR_DIR")
    if env:
        base = Path(env)
    else:
        one = os.environ.get("OneDrive")
        root = Path(one) if one else (Path.home() / "OneDrive")
        base = (root if root.is_dir() else Path.home()) / "Videos" / "video-editor"
    for sub in SUBDIRS:
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


def render_dir():
    return editor_dir() / "Render"
