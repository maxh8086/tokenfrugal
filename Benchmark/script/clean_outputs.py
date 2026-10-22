"""Remove local scratch that is no longer needed once benchmark.csv holds the model's result.

    python Benchmark/script/clean_outputs.py            # delete
    python Benchmark/script/clean_outputs.py --dry-run  # list only

Called at the end of build_report.py, so every batch of run_queue.sh cleans up after its CSV write.

What is removed:
- results/tracker/logs/*.log for a model whose run is already in results/benchmark.csv.
- results/backups/ CSV copies, keeping the newest KEEP_BACKUPS per file (older copies are restore points we no longer need).
- results/raw/ run JSON, including raw/suites/. Once the CSVs are written this is no longer the source for anything;
  benchmark.csv raw_json entries will point at files that are gone.

What is never removed: the published CSVs and results/coding/.
"""
import argparse
import re
from pathlib import Path

RESULTS = Path(__file__).resolve().parent.parent / "results"
RAW = RESULTS / "raw"
LOGS = RESULTS / "tracker" / "logs"
BACKUPS = RESULTS / "backups"
BENCH_CSV = RESULTS / "benchmark.csv"
KEEP_BACKUPS = 3


def _csv_text():
    try:
        return BENCH_CSV.read_text(encoding="utf-8", errors="replace").lower()
    except OSError:
        return ""


def clean_logs(dry_run=False):
    """Delete a per-model log once its model tag appears in benchmark.csv."""
    text = _csv_text()
    if not text or not LOGS.is_dir():
        return 0, 0
    removed = kept = 0
    for log in sorted(LOGS.glob("*.log")):
        # queue log names use "_" for ":" (ts-qwen3-4b-65536_latest.log -> ts-qwen3-4b-65536-latest)
        tag = log.stem.lower().replace("_", "-")
        if tag and tag in text:
            if not dry_run:
                log.unlink()
            removed += 1
        else:
            kept += 1
    return removed, kept


def clean_backups(dry_run=False):
    """Keep the newest KEEP_BACKUPS copies of each CSV; delete the rest."""
    if not BACKUPS.is_dir():
        return 0, 0
    groups = {}
    for f in BACKUPS.glob("*.csv"):
        # name is <base>-<YYYYMMDD-HHMMSS>-<digits>.csv; base may contain "_"
        m = re.match(r"^(.+?)-\d{8}-\d{6}-\d+\.csv$", f.name)
        base = m.group(1) if m else f.name
        groups.setdefault(base, []).append(f)
    removed = kept = 0
    for files in groups.values():
        files.sort(key=lambda p: p.name)  # timestamp in the name sorts oldest first
        old, new = files[:-KEEP_BACKUPS], files[-KEEP_BACKUPS:]
        for f in old:
            if not dry_run:
                f.unlink()
            removed += 1
        kept += len(new)
    return removed, kept


def clean_raw(dry_run=False):
    """Delete the raw run JSON and its suite/markdown/csv outputs."""
    if not RAW.is_dir():
        return 0
    removed = 0
    for f in list(RAW.rglob("*")):
        if f.is_file():
            if not dry_run:
                f.unlink()
            removed += 1
    if not dry_run:
        for d in sorted((p for p in RAW.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            try:
                d.rmdir()
            except OSError:
                pass
    return removed


def run(dry_run=False):
    if not BENCH_CSV.exists():
        print("cleanup skipped: benchmark.csv not found")
        return
    lr, lk = clean_logs(dry_run)
    br, bk = clean_backups(dry_run)
    rr = clean_raw(dry_run)
    verb = "would remove" if dry_run else "removed"
    print(f"cleanup: {verb} {lr} model log(s) (kept {lk}); {verb} {br} old backup(s) (kept {bk}); {verb} {rr} raw file(s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="list what would be removed")
    run(ap.parse_args().dry_run)
