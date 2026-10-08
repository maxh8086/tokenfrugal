"""Look for newer upstream release tags than those pinned in docker/pins.yaml.
Usage: python scripts/check_pins.py [--write]   (exit 0 always; prints one line per pin that can move)
--write rewrites the sha and tag comment in pins.yaml; review the PR, then run scripts/pinned_build.py to test."""
import re
import subprocess
import sys
from pathlib import Path

PINS = Path(__file__).resolve().parent.parent / "docker" / "pins.yaml"
sys.path.insert(0, str(PINS.parent.parent))
from scripts.pinned_build import load_pins  # noqa: E402


def latest(repo, regex):
    """(tag, commit sha) of the highest matching release tag; annotated tags are peeled to their commit."""
    out = subprocess.run(["git", "ls-remote", "--tags", repo], capture_output=True, text=True, check=True).stdout
    shas, best = {}, None
    for ln in out.splitlines():
        sha, ref = ln.split("\t")
        tag = ref.removeprefix("refs/tags/")
        peeled = tag.endswith("^{}")
        tag = tag.removesuffix("^{}")
        if peeled or tag not in shas:
            shas[tag] = sha
    for tag in shas:
        m = re.match(regex, tag)
        if m and (best is None or tuple(map(int, m.groups())) > best[0]):
            best = (tuple(map(int, m.groups())), tag)
    return (best[1], shas[best[1]]) if best else (None, None)


def main(argv):
    pins, text, changed = load_pins(PINS), PINS.read_text(encoding="utf-8"), False
    for name, p in pins.items():
        tag, sha = latest(p["repo"], p["tag_regex"])
        if not tag or sha == p["sha"]:
            continue
        print(f"{name}: {p['sha'][:12]} -> {sha[:12]} ({tag})")
        text = re.sub(rf"(?m)^(\s+sha: ){p['sha']}.*$", rf"\g<1>{sha}   # tag {tag}", text)
        changed = True
    if changed and "--write" in argv:
        PINS.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
