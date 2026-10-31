"""Copy a finished output into video-editor/Render so every model writes to the same place.

Folder: VIDEO_EDITOR_DIR/Render (see _paths.py), created if missing. VIDEO_PUBLISH_DIR overrides the target
folder; "0" turns publishing off (the Docker image sets it, /work/Render is already the mounted Render).
"""
import os
import shutil
from pathlib import Path

from _paths import render_dir


def publish(path, name=None):
    target = os.environ.get("VIDEO_PUBLISH_DIR")
    if target == "0":
        return None
    folder = Path(target) if target else render_dir()
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / (name or Path(path).name)
    if dest.resolve() != Path(path).resolve():
        shutil.copy2(path, dest)
    print("published", dest, flush=True)
    return dest
