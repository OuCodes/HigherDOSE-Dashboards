#!/usr/bin/env python3
"""Thin wrapper delegating to growthkit.connectors.northbeam.cli:sync_ytd_main"""

import sys
from pathlib import Path

# Ensure local package path
repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))


def main() -> None:
    from growthkit.connectors.northbeam.cli import sync_ytd_main

    sync_ytd_main()


if __name__ == '__main__':
    main() 