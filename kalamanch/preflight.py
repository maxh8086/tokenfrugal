"""Check that the weights a script needs are on disk; offer to fetch what is missing.

Usage:
    python kalamanch/preflight.py                        # every model some script requires (the full set)
    python kalamanch/preflight.py generators/wan_test.py [pipeline/chain_gen.py ...]
    python kalamanch/preflight.py --fetch [--yes] [...]  # download missing models (asks first unless --yes)
Exit code 0 when everything needed is present, 1 when something is missing.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "common"))
from _models import MODELS, describe, missing, models_root, require  # noqa: E402


def models_for(targets):
    if not targets:
        return [n for n, m in MODELS.items() if m["required_by"]]
    out = []
    for t in targets:
        hits = [n for n, m in MODELS.items() if any(r == t or r.split(":")[0] == t for r in m["required_by"])]
        if not hits and t in MODELS:
            hits = [t]
        if not hits:
            print(f"{t}: no model requirement recorded (nothing to check)")
        out += [h for h in hits if h not in out]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("targets", nargs="*")
    ap.add_argument("--fetch", action="store_true", help="download missing models")
    ap.add_argument("--yes", action="store_true", help="do not ask before downloading (unattended)")
    a = ap.parse_args()
    names = models_for(a.targets)
    print("models folder:", models_root())
    bad = [n for n in names if missing(n)]
    for n in names:
        print(("MISSING " if n in bad else "ok      ") + n)
    if not bad:
        return 0
    if not a.fetch:
        for n in bad:
            print(" ", describe(n))
        print("Run again with --fetch to download (you will be asked first).")
        return 1
    require(*bad, assume_yes=True if a.yes else None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
