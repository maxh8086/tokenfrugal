#!/usr/bin/env python3
"""Append one benchmark CSV data row to Benchmark/model-comparison.md.

Usage: python scripts/bench_append.py <csv_path> --date YYYY-MM-DD [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import tempfile
from pathlib import Path

TABLE_HEADER_PREFIX = "| Model / run tag"
REPO_ROOT = Path(__file__).resolve().parent.parent
MD_PATH = REPO_ROOT / "Benchmark" / "model-comparison.md"
SUFFIX_TEMPLATE = "{tag} (tested {date})"
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")


def escape_cell(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    return value.replace("|", "\\|").replace("\n", "<br>")


def split_row(line: str) -> list[str]:
    """Split a markdown table row into raw cell strings (escaped pipes kept)."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    return [c.strip() for c in UNESCAPED_PIPE.split(body)]


def read_csv_row(csv_path: Path) -> list[str]:
    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    if len(rows) < 2:
        raise ValueError("CSV must contain a header row and one data row")
    data = rows[1]
    if not data:
        raise ValueError("CSV data row is empty")
    return data


def build_cells(data: list[str], date: str) -> list[str]:
    tag = data[0]
    first = SUFFIX_TEMPLATE.format(tag=tag, date=date)
    return [escape_cell(first)] + [escape_cell(c) for c in data[1:]]


def find_table(lines: list[str]) -> tuple[int, int]:
    """Return (first_line_index, last_data_line_index) of the first matching table."""
    for i, line in enumerate(lines):
        if line.lstrip().startswith(TABLE_HEADER_PREFIX):
            last = i + 1  # separator row
            j = i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                last = j
                j += 1
            return i, last
    raise ValueError(f"no table starting with '{TABLE_HEADER_PREFIX}' found")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--date", required=True, help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
        print("error: --date must be YYYY-MM-DD", file=sys.stderr)
        return 2

    data = read_csv_row(args.csv_path)
    tag = data[0]
    cells = build_cells(data, args.date)
    new_row_text = "| " + " | ".join(cells) + " |"

    with MD_PATH.open(newline="", encoding="utf-8") as fh:
        text = fh.read()
    lines = text.splitlines(keepends=True)

    header_idx, last_idx = find_table(lines)
    header_line = lines[header_idx]
    eol = "\r\n" if header_line.endswith("\r\n") else "\n"

    expected_first = escape_cell(SUFFIX_TEMPLATE.format(tag=tag, date=args.date))
    for j in range(header_idx + 2, last_idx + 1):
        row_cells = split_row(lines[j])
        if row_cells and row_cells[0] == expected_first:
            print(
                f"error: {tag} (tested {args.date}) already present in {MD_PATH.name}",
                file=sys.stderr,
            )
            return 1

    if args.dry_run:
        print(new_row_text)
        return 0

    new_lines = list(lines)
    if not new_lines[last_idx].endswith(("\n", "\r")):
        new_lines[last_idx] += eol
    new_lines.insert(last_idx + 1, new_row_text + eol)
    out_text = "".join(new_lines)

    fd, tmp_name = tempfile.mkstemp(dir=str(MD_PATH.parent), prefix=".bench_append_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as tmp:
            tmp.write(out_text)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, MD_PATH)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise

    print(f"appended {tag} to Benchmark/model-comparison.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
