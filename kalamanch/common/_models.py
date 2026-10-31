"""Locate, check and fetch model weights for the kalamanch scripts.

Models folder: KALAMANCH_MODELS (legacy TOKENFRUGAL_DIFFUSION_MODELS), else <repo>/models/video_generation.
In a container mount the weights at /models and set KALAMANCH_MODELS=/models.
Missing weights are never fetched silently: require() asks first (KALAMANCH_AUTOFETCH=1 answers yes for unattended runs).
"""
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manifest import MODELS  # noqa: E402


def models_root():
    env = os.environ.get("KALAMANCH_MODELS") or os.environ.get("TOKENFRUGAL_DIFFUSION_MODELS")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "models" / "video_generation"


def missing(name):
    base = models_root() / name
    return [c for c in MODELS[name]["check"] if not (base / c).exists()]


def _size_gb(name):
    """Best-effort download size from the Hugging Face API; None when offline."""
    try:
        import fnmatch
        from huggingface_hub import HfApi
        total = 0
        for repo, patterns, _sub, _remap in MODELS[name]["sources"]:
            for s in HfApi().model_info(repo, files_metadata=True).siblings:
                if patterns is None or any(fnmatch.fnmatch(s.rfilename, p) for p in patterns):
                    total += s.size or 0
        return total / 1e9
    except Exception:
        return None


def fetch(name):
    from huggingface_hub import snapshot_download
    target = models_root() / name
    for repo, patterns, sub, remap in MODELS[name]["sources"]:
        dest = target / sub if sub else target
        print(f"[{name}] {repo} -> {dest}", flush=True)
        if not remap:
            snapshot_download(repo_id=repo, allow_patterns=patterns, local_dir=str(dest))
            continue
        stage = target / ".stage"
        snapshot_download(repo_id=repo, allow_patterns=patterns, local_dir=str(stage))
        for src, dst in remap.items():
            if (dest / dst).exists():
                shutil.rmtree(dest / dst)
            shutil.move(str(stage / src), str(dest / dst))
        shutil.rmtree(stage, ignore_errors=True)
    print(f"[{name}] done", flush=True)


def describe(name):
    gb = _size_gb(name)
    size = f"about {gb:.1f} GB" if gb else "size unknown (offline)"
    gate = "; gated repo: run `huggingface-cli login` and accept the licence first" if MODELS[name].get("gated") else ""
    return f"{name}: {', '.join(missing(name))} missing, download {size}{gate}"


def require(*names, assume_yes=None):
    """Make sure every named model is present; ask the user before downloading, exit if declined or unattended."""
    todo = [n for n in names if n in MODELS and missing(n)]
    if not todo:
        return
    yes = assume_yes if assume_yes is not None else os.environ.get("KALAMANCH_AUTOFETCH") == "1"
    for name in todo:
        print(describe(name), flush=True)
        if not yes:
            if not sys.stdin.isatty():
                sys.exit(f"Model {name} is missing. Ask the user, then run: python kalamanch/preflight.py --fetch {name}")
            try:
                answer = input(f"Download {name} now? [y/N] ").strip().lower()
            except EOFError:
                answer = ""
            if answer != "y":
                alt = "; ".join(MODELS[name]["alternatives"]) or "none listed"
                sys.exit(f"Model {name} not available. Alternatives (ask the user before pulling): {alt}")
        fetch(name)
        if missing(name):
            sys.exit(f"{name} still incomplete after download: {', '.join(missing(name))}")


def use_models_dir():
    """Run from the models folder (scripts use relative model paths); file arguments are made absolute first."""
    media = (".mp4", ".wav", ".png", ".jpg", ".jpeg", ".txt", ".json")
    sys.argv[1:] = [os.path.abspath(a) if os.path.exists(a) or a.lower().endswith(media) else a for a in sys.argv[1:]]
    root = models_root()
    root.mkdir(parents=True, exist_ok=True)
    os.chdir(root)
