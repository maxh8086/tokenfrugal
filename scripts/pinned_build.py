"""Clone an upstream repo at a pinned commit and build its helper image locally.

Usage: python scripts/pinned_build.py [name ...] [--pins FILE] [--keep]
Pins live in docker/pins.yaml (repo, sha, image tag, dockerfile). The clone is verified to be exactly the pinned sha.
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SHA = re.compile(r"^[0-9a-f]{40}$")


def load_pins(path: Path) -> dict:
    pins = yaml.safe_load(path.read_text(encoding="utf-8"))["pins"]
    for name, p in pins.items():
        missing = {"repo", "sha", "image", "dockerfile"} - set(p)
        if missing:
            raise ValueError(f"pin {name}: missing {sorted(missing)}")
        if not SHA.match(str(p["sha"])):
            raise ValueError(f"pin {name}: sha must be a full 40-char lowercase commit id")
    return pins


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def clone_at(repo: str, sha: str, dest: Path) -> None:
    """Fetch only `sha` into dest and check it out; fail if the result is not that exact commit."""
    dest.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", cwd=dest)
    _git("fetch", "-q", "--depth", "1", repo, sha, cwd=dest)
    _git("checkout", "-q", "FETCH_HEAD", cwd=dest)
    head = _git("rev-parse", "HEAD", cwd=dest)
    if head != sha:
        raise RuntimeError(f"pinned {sha} but got {head}")


def build(name: str, p: dict, keep: bool = False) -> None:
    tmp = Path(tempfile.mkdtemp(prefix=f"tf-{name}-"))
    try:
        clone_at(p["repo"], p["sha"], tmp)
        print(f"{name}: cloned {p['repo']} @ {p['sha'][:12]}; building {p['image']}")
        subprocess.run(["docker", "build", "-t", p["image"], "-f", str(ROOT / p["dockerfile"]), str(tmp)], check=True)
    finally:
        if keep:
            print(f"{name}: kept clone at {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--pins", default=str(ROOT / "docker" / "pins.yaml"))
    ap.add_argument("--keep", action="store_true", help="keep the temporary clone")
    a = ap.parse_args(argv)
    pins = load_pins(Path(a.pins))
    unknown = [n for n in a.names if n not in pins]
    if unknown:
        print(f"unknown pin(s) {unknown}; available: {sorted(pins)}", file=sys.stderr)
        return 2
    for n in a.names or pins:
        build(n, pins[n], a.keep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
