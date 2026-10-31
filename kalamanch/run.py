"""Run a kalamanch script after the model pre-check.

Usage: python kalamanch/run.py generators/generate_ltx.py <args...>
       python kalamanch/run.py pipeline/chain_gen.py ltx <photo> <audio.wav> <out.mp4>
Missing weights are listed with their size and you are asked before anything downloads.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "common"))
from _models import MODELS, require  # noqa: E402


def needed(script, args):
    key = script.replace("\\", "/")
    names = []
    for n, m in MODELS.items():
        for r in m["required_by"]:
            path, _, variant = r.partition(":")
            if path == key and (not variant or (args and args[0] == variant)):
                names.append(n)
    return names


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    script, args = sys.argv[1], sys.argv[2:]
    require(*needed(script, args))
    return subprocess.call([sys.executable, os.path.join(HERE, script), *args])


if __name__ == "__main__":
    sys.exit(main())
