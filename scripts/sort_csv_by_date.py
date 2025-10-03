#!/usr/bin/env python3
"""Sort a CSV by its date column (oldest first), preserving header.

This script uses Python's csv module to robustly handle quoted fields and
embedded commas/newlines. It detects a date-like column by name
(case-insensitive: one of 'date', 'day', 'report_date'); if none found,
it sorts by the first column.

The original file is backed up to <filename>.bak before writing.
"""

from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if not argv:
        print("Usage: sort_csv_by_date.py <path-to-csv>")
        return 2

    csv_path = Path(argv[0])
    if not csv_path.exists():
        print(f"File not found: {csv_path}")
        return 1

    backup_path = csv_path.with_suffix(csv_path.suffix + ".bak")
    shutil.copy2(csv_path, backup_path)

    # Read with csv module to preserve quoting and handle embedded newlines
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            # Empty file
            return 0
        rows = list(reader)

    # Identify date column index by common names; fall back to first column
    date_idx = 0
    for i, name in enumerate(header):
        if name and name.strip().lower() in {"date", "day", "report_date"}:
            date_idx = i
            break

    def sort_key(row: list[str]) -> str:
        try:
            return (row[date_idx] or "").strip().strip('"').strip("'")
        except Exception:
            return ""

    rows.sort(key=sort_key)

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"Sorted: {csv_path}\nBackup: {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))



