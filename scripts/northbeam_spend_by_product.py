#!/usr/bin/env python3
"""Thin wrapper around growthkit.reports.northbeam_spend_by_product"""

import sys
from pathlib import Path


def _bootstrap_src_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))


def main() -> None:
    _bootstrap_src_path()
    from growthkit.reports.northbeam_spend_by_product import main as run

    raise SystemExit(run())


if __name__ == "__main__":
    main()