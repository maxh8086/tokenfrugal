"""Look for newer upstream release tags than those pinned in docker/pins.yaml.

Usage: python scripts/check_pins.py [--rebuild] [--push] [--yes]
  (no flags)  report only; exit 0 always
  --rebuild   for each newer release, ask, then build it at the new commit.
              On success the pin moves to the new sha. On failure the old image
              stays as <image> and the pin is left unchanged.
  --push      after a successful rebuild, ask, then `docker push` the image
              (Docker Hub by default; use a ghcr.io/... name for GitHub).
  --yes       answer yes to every prompt (for scripts/CI). Use with care.
Before each rebuild the current image is tagged <name>:rollback, so you can revert with
  docker tag <name>:rollback <name>:1
"""
import re
import subprocess
import sys
from pathlib import Path

PINS = Path(__file__).resolve().parent.parent / "docker" / "pins.yaml"
sys.path.insert(0, str(PINS.parent.parent))
from scripts.pinned_build import build, load_pins  # noqa: E402


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


def _image_exists(img):
    return subprocess.run(["docker", "image", "inspect", img], capture_output=True).returncode == 0


def _ask(question, auto):
    if auto:
        return True
    if not sys.stdin.isatty():
        return False
    return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")


def rebuild(name, p, sha, tag):
    """Build the new release. On failure the old image is restored under its tag. True on success."""
    rollback = p["image"].rsplit(":", 1)[0] + ":rollback"
    had_old = _image_exists(p["image"])
    if had_old:
        subprocess.run(["docker", "tag", p["image"], rollback], check=True)
    try:
        build(name, {**p, "sha": sha})
    except (subprocess.CalledProcessError, RuntimeError) as e:
        print(f"{name}: build of {tag} FAILED ({e}). Keeping {p['image']} at {p['sha'][:12]}; pin unchanged.")
        if had_old:
            subprocess.run(["docker", "tag", rollback, p["image"]], check=False)
        return False
    print(f"{name}: built {tag} as {p['image']}. Previous image kept as {rollback}.")
    return True


def main(argv):
    rebuild_on = "--rebuild" in argv or "--yes" in argv
    auto, push = "--yes" in argv, "--push" in argv
    pins, text = load_pins(PINS), PINS.read_text(encoding="utf-8")
    found = []
    for name, p in pins.items():
        tag, sha = latest(p["repo"], p["tag_regex"])
        if not tag or sha == p["sha"]:
            continue
        print(f"{name}: {p['sha'][:12]} -> {sha[:12]} ({tag})")
        found.append((name, p, tag, sha))
    if not found:
        return 0
    if not rebuild_on:
        print("Run with --rebuild to build a release (old image kept on failure); add --push to publish it.")
        return 0
    changed = False
    for name, p, tag, sha in found:
        if not _ask(f"Rebuild {name} at {tag}?", auto):
            print(f"{name}: skipped.")
            continue
        if not rebuild(name, p, sha, tag):
            continue
        if push and _ask(f"Push {p['image']} to its registry?", auto):
            subprocess.run(["docker", "push", p["image"]], check=True)
        text = re.sub(rf"(?m)^(\s+sha: ){p['sha']}.*$", rf"\g<1>{sha}   # tag {tag}", text)
        changed = True
    if changed:
        PINS.write_text(text, encoding="utf-8")
        print(f"Updated {PINS.name}. Review the diff, then commit it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
