#!/usr/bin/env python3
"""Thin wrapper for Month-to-Date executive report.

Delegates everything to ``growthkit.reports.executive`` so that
all real code lives in the installable package.
"""

import sys
from pathlib import Path

# Ensure local package under 'src' is importable when running from repo
repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if src_path.exists():
    sys.path.insert(0, str(src_path))

from growthkit.reports import executive

if __name__ == "__main__":
    executive.main()
