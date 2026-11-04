#!/usr/bin/env python3
"""Fetch the media assets listed in docker/media-generator/assets.json into the shared media folder.

The destination root is the media folder: VIDEO_EDITOR_DIR from the environment, then .env, resolved as in
router/media_workspace.py. Each entry is {"url": "https://...", "sha256": "<64 hex>", "dest": "<folder>/<path>"}.
  - url must be https. No credentials are read or sent.
  - dest is relative and its first folder must be one of the VIDEO_EDITOR_LAYOUT folders (Raw, References, ...).
  - the file is written to a temp name, checked against sha256, then moved into place. A mismatch deletes it
    and stops the run.
  - a file already in place with the right sha256 is left alone.

Usage:
  python scripts/fetch_media_assets.py            # create the folder structure, fetch what is missing
  python scripts/fetch_media_assets.py --dry-run  # print the plan, change nothing
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from router import media_workspace as mw  # noqa: E402  (loads .env before reading VIDEO_EDITOR_DIR)

MANIFEST = ROOT / "docker" / "media-generator" / "assets.json"
CHUNK = 1 << 20
HEX = set("0123456789abcdef")


class AssetError(Exception):
    pass


def validate(entry: dict, layout_folders: set) -> tuple:
    url = str(entry.get("url", ""))
    if not url.startswith("https://"):
        raise AssetError(f"url must be https: {url!r}")
    sha = str(entry.get("sha256", "")).lower()
    if len(sha) != 64 or not set(sha) <= HEX:
        raise AssetError(f"sha256 must be 64 hex characters: {entry.get('sha256')!r}")
    dest = str(entry.get("dest", ""))
    path = PurePosixPath(dest)
    if not dest or path.is_absolute() or ".." in path.parts or "\\" in dest:
        raise AssetError(f"dest must be a relative path with no '..': {dest!r}")
    if len(path.parts) < 2 or path.parts[0] not in layout_folders:
        raise AssetError(f"dest must sit under one of {sorted(layout_folders)}: {dest!r}")
    return url, sha, dest


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(url: str, sha: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".part")
    os.close(fd)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp, open(tmp, "wb") as out:
            for block in iter(lambda: resp.read(CHUNK), b""):
                out.write(block)
        got = sha256_of(Path(tmp))
        if got != sha:
            raise AssetError(f"sha256 mismatch for {url}: expected {sha}, got {got}")
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch media assets listed in assets.json into the media folder.")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and change nothing")
    args = parser.parse_args(argv)

    entries = json.loads(MANIFEST.read_text(encoding="utf-8")).get("assets", [])
    if not entries:
        print(f"no assets listed in {MANIFEST}; nothing to fetch")
        return 0

    layout_folders = {PurePosixPath(folder).parts[0] for folder in mw.layout()}
    try:
        plan = [validate(entry, layout_folders) for entry in entries]
    except AssetError as exc:
        print(f"manifest error: {exc}", file=sys.stderr)
        return 2

    root = mw.media_dir()
    print(f"media folder: {root}")
    if not args.dry_run:
        for rel, status in mw.ensure_tree(root):
            print(f"folder {status:7s} {rel}")

    for url, sha, dest in plan:
        target = root / dest
        if target.is_file() and sha256_of(target) == sha:
            print(f"OK        {dest}")
            continue
        if args.dry_run:
            print(f"WOULD GET {dest} <- {url}")
            continue
        try:
            fetch(url, sha, target)
        except (AssetError, OSError) as exc:
            print(f"FAILED    {dest}: {exc}", file=sys.stderr)
            return 1
        print(f"FETCHED   {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
