#!/usr/bin/env python3
"""Thin wrapper for LDW YoY report.

Delegates to `growthkit.reports.ldw.main()` so that business logic lives in the
installable package.
"""

import sys
from pathlib import Path


def _bootstrap_src_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))


def main() -> None:
    _bootstrap_src_path()
    from growthkit.reports.ldw import main as run

    run()


if __name__ == "__main__":
    main()


