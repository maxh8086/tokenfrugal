"""Clone an upstream repo at a pinned commit and build its helper image locally.

Usage: python scripts/pinned_build.py [name ...] [--pins FILE] [--keep]
Pins live in docker/pins.yaml (repo, sha, image, dockerfile). The clone is verified to be exactly the pinned sha.

Pins with `nodes:` (ComfyUI) are staged first: ComfyUI and each custom node are cloned at their pinned commit, each
tree is checked against tree_sha (git rev-parse HEAD^{tree}), each node's requirements.txt must be covered by the
hash-locked lockfile, and only then is the image built (the Dockerfile installs with --require-hashes).
Pins without `repo` (the forwarder) are base-image pins: the Dockerfile pins its own base and packages.
"""
import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SHA = re.compile(r"^[0-9a-f]{40}$")
PLACEHOLDER = "<written by the first build>"
NAME = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)")


def _check_tree(label: str, value) -> None:
    if str(value) != PLACEHOLDER and not SHA.match(str(value)):
        raise ValueError(f"{label}: tree_sha must be a full 40-char tree id or the placeholder")


def _check_nodes(name: str, p: dict) -> None:
    for n in p.get("nodes") or []:
        missing = {"repo", "node_sha", "tree_sha", "folder"} - set(n)
        if missing:
            raise ValueError(f"pin {name}: node {n.get('folder', n)} missing {sorted(missing)}")
        if not SHA.match(str(n["node_sha"])):
            raise ValueError(f"pin {name}: node {n['folder']} node_sha must be a full 40-char commit id")
        _check_tree(f"pin {name}: node {n['folder']}", n["tree_sha"])
        if not re.fullmatch(r"[A-Za-z0-9._-]+", str(n["folder"])) or n["folder"] in (".", ".."):
            raise ValueError(f"pin {name}: node folder {n['folder']!r} must be a plain folder name")


def load_pins(path: Path) -> dict:
    pins = yaml.safe_load(path.read_text(encoding="utf-8"))["pins"]
    for name, p in pins.items():
        base_only = "repo" not in p and "base_image" in p
        required = {"image", "dockerfile", "base_image"} if base_only else {"repo", "sha", "image", "dockerfile"}
        missing = required - set(p)
        if missing:
            raise ValueError(f"pin {name}: missing {sorted(missing)}")
        if "sha" in p and not SHA.match(str(p["sha"])):
            raise ValueError(f"pin {name}: sha must be a full 40-char lowercase commit id")
        if "tree_sha" in p:
            _check_tree(f"pin {name}", p["tree_sha"])
        _check_nodes(name, p)
    return pins


def _git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _rm(path: Path) -> None:
    def retry(func, p, _exc):  # git pack files are read-only on Windows
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=retry)


def clone_at(repo: str, sha: str, dest: Path) -> None:
    """Fetch only `sha` into dest and check it out; fail if the result is not that exact commit."""
    dest.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", cwd=dest)
    _git("fetch", "-q", "--depth", "1", repo, sha, cwd=dest)
    _git("checkout", "-q", "FETCH_HEAD", cwd=dest)
    head = _git("rev-parse", "HEAD", cwd=dest)
    if head != sha:
        raise RuntimeError(f"pinned {sha} but got {head}")


def verify_tree(dest: Path, expected: str, label: str) -> None:
    """Check the checked-out tree hash. A placeholder fails and prints the value to write into pins.yaml."""
    actual = _git("rev-parse", "HEAD^{tree}", cwd=dest)
    if str(expected) == PLACEHOLDER:
        raise RuntimeError(f"{label}: tree_sha is still the placeholder. Write this into docker/pins.yaml: tree_sha: {actual}")
    if actual != expected:
        raise RuntimeError(f"{label}: tree {actual} does not match pinned tree_sha {expected}")


def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def lock_names(text: str) -> set[str]:
    """Top-level package names in a lockfile (column-0 requirement lines; comments, options and hash lines skipped)."""
    names = set()
    for ln in text.splitlines():
        if not ln or ln[0] in "# \t-":
            continue
        m = NAME.match(ln)
        if m:
            names.add(_norm(m.group(1)))
    return names


def requirement_names(text: str, src: Path) -> set[str]:
    names = set()
    for raw in text.splitlines():
        s = raw.split("#", 1)[0].strip()
        if not s:
            continue
        if s.startswith("-") or "://" in s or s.startswith("git+"):
            raise ValueError(f"{src}: unsupported requirement {s!r}; only name specifiers can be checked against the lockfile")
        m = NAME.match(s)
        if not m:
            raise ValueError(f"{src}: cannot read a package name from {s!r}")
        names.add(_norm(m.group(1)))
    return names


def check_lockfile_coverage(lock_path: Path, req_files: list[Path]) -> None:
    text = lock_path.read_text(encoding="utf-8")
    if "--hash=" not in text:
        raise RuntimeError(f"{lock_path.name} has no hashes; generate it with pip-compile --generate-hashes at the first build")
    have = lock_names(text)
    missing: dict[str, list[str]] = {}
    for f in req_files:
        if f.exists():
            for n in requirement_names(f.read_text(encoding="utf-8"), f):
                if n not in have:
                    missing.setdefault(n, []).append(f.parent.name)
    if missing:
        detail = "; ".join(f"{n} (from {', '.join(sorted(set(srcs)))})" for n, srcs in sorted(missing.items()))
        raise RuntimeError(f"packages named by node requirements.txt but missing from {lock_path.name}: {detail}")


def stage_comfyui(name: str, p: dict, stage: Path) -> None:
    """Clone ComfyUI and each node at its pinned commit into stage/app, verify trees, check lockfile coverage."""
    app = stage / "app"
    clone_at(p["repo"], p["sha"], app)
    verify_tree(app, p.get("tree_sha", PLACEHOLDER), name)
    _rm(app / ".git")
    for n in p["nodes"]:
        node_dir = app / "custom_nodes" / n["folder"]
        clone_at(n["repo"], n["node_sha"], node_dir)
        verify_tree(node_dir, n["tree_sha"], f"{name} node {n['folder']}")
        _rm(node_dir / ".git")
    check_lockfile_coverage(ROOT / p["lockfile"],
                            [app / "custom_nodes" / n["folder"] / "requirements.txt" for n in p["nodes"]])
    shutil.copy(ROOT / p["lockfile"], stage / "requirements.lock")
    shutil.copy(ROOT / Path(p["dockerfile"]).parent / "extra_model_paths.yaml", stage / "extra_model_paths.yaml")


def _build_args(p: dict) -> list[str]:
    """--build-arg values from the pin, so docker/pins.yaml is the one place the base image and versions are set."""
    args = []
    if p.get("base_image"):
        args += ["--build-arg", f"BASE={p['base_image']}"]
    if p.get("socat_version"):
        args += ["--build-arg", f"SOCAT_VERSION={p['socat_version']}"]
    return args


def build_comfyui(name: str, p: dict, keep: bool = False) -> None:
    stage = Path(tempfile.mkdtemp(prefix=f"tf-{name}-"))
    try:
        stage_comfyui(name, p, stage)
        print(f"{name}: staged ComfyUI {p['sha'][:12]} with {len(p['nodes'])} node(s); building {p['image']}")
        subprocess.run(["docker", "build", *_build_args(p), "-t", p["image"], "-f", str(ROOT / p["dockerfile"]), str(stage)],
                       check=True)
    finally:
        if keep:
            print(f"{name}: kept staging folder at {stage}")
        else:
            _rm(stage)


def build(name: str, p: dict, keep: bool = False) -> None:
    if p.get("nodes"):
        return build_comfyui(name, p, keep)
    if p.get("context") == "folder":
        # The Dockerfile fetches and sha-checks its own upstream source (if any); build from its folder.
        ctx = ROOT / Path(p["dockerfile"]).parent
        print(f"{name}: building {p['image']} from {ctx.relative_to(ROOT)}")
        subprocess.run(["docker", "build", *_build_args(p), "-t", p["image"], "-f", str(ROOT / p["dockerfile"]), str(ctx)],
                       check=True)
        return
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
