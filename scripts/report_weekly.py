#!/usr/bin/env python3
"""Run the HigherDOSE weekly product + category analysis."""
from higherdose.analysis import weekly
from higherdose.utils.paths import find_latest_in_repo

google_prev_path = find_latest_in_repo("google-2024*-daily*.csv")
meta_prev_path   = find_latest_in_repo("meta-*2024*export*.csv")

if __name__ == "__main__":
    weekly.main()
