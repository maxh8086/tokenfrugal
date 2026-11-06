#!/usr/bin/env python3
"""Pin the voice image by digest, taking new versions from a moving label.

docker/dhvani/dhvani.pin holds the repo, the label it follows (latest) and the digest the stack runs.
  python scripts/update_dhvani_pin.py             # compare the label's digest with the pin (exit 1 if they differ)
  python scripts/update_dhvani_pin.py --write     # move the pin to the label's digest
  python scripts/update_dhvani_pin.py --offline   # read the local image only, do not pull

A pin moves only when this script runs with --write. A digest that followed the label on every run would not be a pin.
"""
import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIN = ROOT / "docker" / "dhvani" / "dhvani.pin"
REQUIRED = ("repo", "follows", "digest")


def read_pin(path: Path) -> dict:
    pin = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        pin[key.strip()] = value.strip()
    missing = [key for key in REQUIRED if not pin.get(key)]
    if missing:
        raise SystemExit(f"{path}: missing {', '.join(missing)}")
    return pin


def label_digest(repo: str, label: str, pull: bool) -> str:
    ref = f"{repo}:{label}"
    if pull:
        subprocess.run(["docker", "pull", ref], check=True)
    out = subprocess.run(
        ["docker", "image", "inspect", ref, "--format", "{{json .RepoDigests}}"],
        check=True, capture_output=True, text=True,
    ).stdout
    for entry in json.loads(out) or []:
        if entry.startswith(f"{repo}@sha256:"):
            return entry.split("@", 1)[1]
    raise SystemExit(f"{ref} has no repo digest locally. Run without --offline so it can be pulled.")


def rewrite(path: Path, digest: str) -> None:
    today = datetime.date.today().isoformat()
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        key = raw.split("=", 1)[0].strip()
        if raw.strip() and not raw.lstrip().startswith("#") and key == "digest":
            raw = f"digest={digest}"
        elif raw.strip() and not raw.lstrip().startswith("#") and key == "resolved":
            raw = f"resolved={today}"
        lines.append(raw)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Compare or move the voice image pin to its label's digest.")
    parser.add_argument("--write", action="store_true", help="move the pin to the label's digest")
    parser.add_argument("--offline", action="store_true", help="read the local image only; do not pull")
    args = parser.parse_args(argv)

    pin = read_pin(PIN)
    current = label_digest(pin["repo"], pin["follows"], pull=not args.offline)
    if current == pin["digest"]:
        print(f"ok: {pin['repo']}:{pin['follows']} is {current} (matches the pin)")
        return 0
    print(f"pin:    {pin['digest']}")
    print(f"label:  {pin['repo']}:{pin['follows']} is {current}")
    if not args.write:
        print("pin not moved. Re-run with --write to move it.")
        return 1
    rewrite(PIN, current)
    print(f"pin moved to {current} in {PIN.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
