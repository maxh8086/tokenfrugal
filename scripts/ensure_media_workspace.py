"""Create or verify the shared media workspace folder tree (see router/media_workspace.py).

Usage:
  python scripts/ensure_media_workspace.py               create missing folders, print the tree
  python scripts/ensure_media_workspace.py --check       verify only; exit 1 if anything is missing (creates nothing)
  python scripts/ensure_media_workspace.py --print-path  print the resolved absolute path only (creates nothing)

Folder meanings: Raw / References / Render (video-editor), content/<slug>/ (stage files, created by the roles),
analyst/daily (daily top-5 reports). Idempotent; safe to re-run.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from router.media_workspace import check_tree, ensure_tree, media_dir  # noqa: E402


def run(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="verify only, exit 1 if anything is missing")
    mode.add_argument("--print-path", action="store_true", help="print the resolved path and exit")
    args = ap.parse_args(argv)

    root = media_dir()
    if args.print_path:
        print(root)
        return 0
    try:
        if args.check:
            rows = [(rel, "OK" if ok else "MISSING") for rel, ok in check_tree(root)]
        else:
            rows = ensure_tree(root)
    except OSError as e:
        print(f"error: cannot create {root}: {e}", file=sys.stderr)
        return 2

    print(f"Shared media workspace: {root}")
    for rel, status in rows:
        print(f"  {status:<8} {'' if rel == '.' else rel + '/'}".rstrip())
    missing = any(status == "MISSING" for _, status in rows)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(run())
