#!/usr/bin/env python3
"""Thin wrapper delegating to growthkit.connectors.northbeam.cli:export_main"""

import sys
from pathlib import Path


def _bootstrap_src_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    src_path = repo_root / "src"
    if src_path.exists():
        sys.path.insert(0, str(src_path))


def main() -> None:
    _bootstrap_src_path()
    from growthkit.connectors.northbeam.cli import export_main

    export_main()


if __name__ == "__main__":
    main()