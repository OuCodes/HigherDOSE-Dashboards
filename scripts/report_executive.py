#!/usr/bin/env python3
"""
HigherDOSE Automated High-Level Report Generator (wrapper)

This script is an alias for `report_mtd_automated.py`.
Running this script will execute the same reporting workflow.
"""

from report_mtd_automated import MTDReportGenerator
import argparse


def main() -> None:
    from datetime import datetime, timedelta

    parser = argparse.ArgumentParser(
        description="HigherDOSE executive report (wrapper around report_mtd_automated.py)"
    )

    # ------------------------------------------------------------------
    # Mutually-exclusive date flags (if supplied non-interactively)
    # ------------------------------------------------------------------
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument("--mtd", action="store_true", help="Force Month-to-Date (default if no dates provided)")
    date_group.add_argument("--month", help="Report on full month – format YYYY-MM")
    date_group.add_argument("--start", help="Start date – format YYYY-MM-DD (requires --end)")

    parser.add_argument("--end", help="End date – format YYYY-MM-DD (use with --start)")
    parser.add_argument("--output-dir", "-o", help="Output directory (e.g. executive)")
    parser.add_argument("--choose-files", action="store_true", help="Interactively choose CSV files for *both* years")
    parser.add_argument("--choose-current-only", action="store_true", help="Interactively choose CSV files for the current year only (skip previous-year prompts)")

    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Interactive date-range prompt if no explicit date flags supplied
    # ------------------------------------------------------------------
    start: str | None = None
    end: str | None = None

    if not (args.mtd or args.month or args.start):
        print("\nChoose reporting period:")
        print("1) Month-to-Date (MTD)")
        print("2) Custom date range")
        choice = input("Select option [1/2] (default 1): ").strip() or "1"

        if choice == "2":
            # Custom range
            start = input("Start date (YYYY-MM-DD): ").strip()
            end = input("End date   (YYYY-MM-DD): ").strip()
        else:
            args.mtd = True  # treat as MTD

    # ------------------------------------------------------------------
    # Non-interactive resolution of explicit flags
    # ------------------------------------------------------------------
    if args.mtd and not (args.month or args.start):
        # No further action – generator will auto-detect current MTD
        pass
    elif args.month:
        month_dt = datetime.strptime(args.month + "-01", "%Y-%m-%d")
        next_month = (month_dt.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_dt = next_month - timedelta(days=1)
        start = month_dt.strftime("%Y-%m-%d")
        end = end_dt.strftime("%Y-%m-%d")
    elif args.start:
        start = args.start
        end = args.end  # may be None – generator will default appropriately

    # ------------------------------------------------------------------
    # Determine whether to prompt for CSV file selection
    # ------------------------------------------------------------------
    choose_files = args.choose_files or args.choose_current_only
    choose_current_only = args.choose_current_only
    if not (args.choose_files or args.choose_current_only):
        try:
            prompt = input("\nWould you like to choose which CSV files to use for each data source? [Y/n]: ").strip().lower() or "y"
            choose_files = prompt in {"y", "yes"}
            if choose_files:
                prev_prompt = (
                    "Also choose previous-year files (2024 and earlier)? [y/N]: "
                )
                choose_prev = input(prev_prompt).strip().lower() or "n"
                choose_current_only = choose_prev not in {"y", "yes"}
        except (EOFError, KeyboardInterrupt):
            # In non-interactive environments default to automatic file selection
            choose_files = False

    # ------------------------------------------------------------------
    # Run the underlying MTDReportGenerator
    # ------------------------------------------------------------------
    generator = MTDReportGenerator(
        start_date=start,
        end_date=end,
        output_dir=args.output_dir,
        choose_files=choose_files,
        choose_files_current_only=choose_current_only,
        interactive=True,
    )
    generator.run()


if __name__ == "__main__":
    main() 