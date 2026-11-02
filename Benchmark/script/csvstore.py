"""Safe append of one benchmark row to a results CSV.

Rules, so a run's data can never be silently lost or misaligned:
  1. The run record goes to an append-only JSONL log (runs.jsonl) first.
  2. The existing CSV is copied to <csv dir>/backups/ before it is rewritten.
  3. The header is validated: no duplicate names, no unknown names. Older, narrower headers are
     migrated by column name; rows are never realigned by position.
  4. Every existing row must match its header width, otherwise nothing is written.
"""
import csv
import json
import re
import shutil
from datetime import datetime
from pathlib import Path


class CsvSchemaError(Exception):
    pass


# Value for a column that older rows do not have (or leave blank). Columns not listed migrate to "" as before.
COLUMN_DEFAULTS = {"loop_version": "1",  # rows written before loop_version existed ran the loop v1
                   "thinking_level": "not sent"}  # rows written before a thinking level was sent


def read_rows(path, cols):
    """Existing rows as dicts keyed by header name. Raises CsvSchemaError on any mismatch."""
    with Path(path).open(encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    if not rows:
        return []
    head = rows[0]
    dup = sorted({h for h in head if head.count(h) > 1})
    if dup:
        raise CsvSchemaError(f"{path}: duplicate header names {dup}; fix the header or use a new --csv file")
    unknown = [h for h in head if h not in cols]
    if unknown:
        raise CsvSchemaError(f"{path}: header has columns this script does not write {unknown}; "
                             "refusing to drop data. Use a new --csv file or migrate the file by hand")
    out = []
    for i, r in enumerate(rows[1:], start=2):
        if len(r) != len(head):
            raise CsvSchemaError(f"{path}: line {i} has {len(r)} fields, header has {len(head)}; refusing to rewrite")
        out.append(dict(zip(head, r)))
    for k, default in COLUMN_DEFAULTS.items():
        if k in cols:
            for row in out:
                if row.get(k, "") == "":
                    row[k] = default
    return out


def log_run(log_path, rec, status="ok"):
    """Append one JSON line per run; never rewritten."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = {"logged_at": datetime.now().isoformat(timespec="seconds"), "status": status, **rec}
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


_FRAC = re.compile(r"^\d+/\d+$")


def excel_safe(v):
    """Prefix n/m cells with an apostrophe so Excel keeps them as text, not dates."""
    v = "" if v is None else str(v)
    return "'" + v if _FRAC.match(v) else v


def unquote(v):
    """Strip the Excel apostrophe before parsing a cell."""
    return "" if v is None else str(v).lstrip("'")


def append_row(dst, cols, rec, log_path=None):
    """Validate, back up, then rewrite `dst` with `rec` appended. Returns the backup path (or None)."""
    dst = Path(dst)
    if log_path:
        log_run(log_path, rec)
    old = read_rows(dst, cols) if dst.exists() and dst.stat().st_size else []
    backup = None
    if dst.exists() and dst.stat().st_size:
        bdir = dst.parent / "backups"
        bdir.mkdir(exist_ok=True)
        backup = bdir / f"{dst.stem}-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.csv"
        shutil.copy2(dst, backup)
    tmp = dst.with_suffix(".csv.tmp")  # write beside the target, then swap in, so a failed write never truncates it
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, restval="")
        w.writeheader()
        w.writerows(old)
        w.writerow({k: excel_safe(v) for k, v in rec.items()})
    tmp.replace(dst)
    return backup
