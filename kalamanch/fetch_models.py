"""Fetch video model weights from Hugging Face on demand. Weights are never stored in the repo.

Usage:
    python kalamanch/fetch_models.py --list
    python kalamanch/fetch_models.py <name> [<name> ...]
    python kalamanch/fetch_models.py --all

Models land in KALAMANCH_MODELS (default <repo>/models/video_generation). Re-running skips files already downloaded.
For a check-then-fetch with a size prompt use preflight.py.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "common"))
from _models import MODELS, fetch, missing, models_root  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("names", nargs="*", help="model names from --list")
    parser.add_argument("--list", action="store_true", help="print the models, their state and exit")
    parser.add_argument("--all", action="store_true", help="fetch every model (large downloads)")
    args = parser.parse_args()
    if args.list:
        print("models folder:", models_root())
        for name, m in MODELS.items():
            print(f"{name:34} {'missing' if missing(name) else 'present':8} " + ", ".join(r for r, *_ in m["sources"]))
        return 0
    names = list(MODELS) if args.all else args.names
    if not names:
        parser.print_help()
        return 2
    unknown = [n for n in names if n not in MODELS]
    if unknown:
        print("unknown model(s):", ", ".join(unknown), file=sys.stderr)
        return 2
    for name in names:
        fetch(name)
    return 0


if __name__ == "__main__":
    sys.exit(main())
