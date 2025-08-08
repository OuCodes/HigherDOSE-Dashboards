#!/usr/bin/env python3
"""Thin wrapper for Month-to-Date executive report.

Delegates everything to ``higherdose.analysis.mtd`` so that
all real code lives in the installable package.
"""

from growthkit.reports import executive

if __name__ == "__main__":
    executive.main()
