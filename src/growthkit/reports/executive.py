#!/usr/bin/env python3
"""
Automated MTD Performance Report Generator

This script automates the creation of Month-to-Date performance summaries
by prompting for date ranges and data sources, then generating a comprehensive
markdown report similar to the weekly growth reports.

CLI:
    python -m growthkit.reports.executive --mtd
    gk-exec --mtd

Requirements:
    - GA4 export files (session data by source/medium and default channel group)
    - Shopify exports (total sales, new vs returning customers, product sales)
    - Northbeam spend data (if available)
"""

import argparse
import glob
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Iterable, Callable
import re

import pandas as pd
# Import data-source config patterns from central config file within the package
from .exec_config import DATA_SOURCE_CONFIG, get_report_template

# ------------------------------------------------------------------
# Helper utilities
# ------------------------------------------------------------------

def assert_columns(df: pd.DataFrame, required: Iterable[str], file_path: str) -> None:
    """Validate *df* has *required* columns; raise ValueError if any are missing."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"{file_path} is missing required column(s): {', '.join(missing)}"
        )

def _extract_date_from_filename(filename: str) -> Optional[datetime]:
    """
    Extract the most recent date from various filename patterns.
    
    Args:
        filename: The filename to parse
        
    Returns:
        datetime object of the most recent date found, or None if no date found
        
    Examples:
        "Total sales over time - 2025-01-01 - 2025-08-04.csv" -> 2025-08-04
        "ytd-sales_data-higher_dose_llc-2025_08_04_23_29_33_820441.csv" -> 2025-08-04
        "daily-traffic-2025-07-01-2025-08-03-2025.csv" -> 2025-08-03
    """
    basename = os.path.basename(filename)
    
    # Pattern 1: Date ranges with hyphens (YYYY-MM-DD - YYYY-MM-DD)
    date_range_pattern = r'(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})'
    date_ranges = re.findall(date_range_pattern, basename)
    if date_ranges:
        # Return the latest end date from all ranges found
        latest_date = None
        for start_date, end_date in date_ranges:
            try:
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                if latest_date is None or end_dt > latest_date:
                    latest_date = end_dt
            except ValueError:
                continue
        if latest_date:
            return latest_date
    
    # Pattern 2: Underscored dates (YYYY_MM_DD) - common in timestamped exports
    underscore_pattern = r'(\d{4}_\d{2}_\d{2})'
    underscore_dates = re.findall(underscore_pattern, basename)
    if underscore_dates:
        latest_date = None
        for date_str in underscore_dates:
            try:
                dt = datetime.strptime(date_str, '%Y_%m_%d')
                if latest_date is None or dt > latest_date:
                    latest_date = dt
            except ValueError:
                continue
        if latest_date:
            return latest_date
    
    # Pattern 3: Single dates with hyphens (YYYY-MM-DD)
    single_date_pattern = r'(\d{4}-\d{2}-\d{2})'
    single_dates = re.findall(single_date_pattern, basename)
    # Pattern 4: Single dates with hyphens in US order (MM-DD-YYYY)
    us_date_pattern = r'(\d{2}-\d{2}-\d{4})'
    us_single_dates = re.findall(us_date_pattern, basename)
    latest_date = None
    # Evaluate YYYY-MM-DD first
    for date_str in single_dates:
        try:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            if latest_date is None or dt > latest_date:
                latest_date = dt
        except ValueError:
            continue
    # Evaluate MM-DD-YYYY
    for date_str in us_single_dates:
        try:
            dt = datetime.strptime(date_str, '%m-%d-%Y')
            if latest_date is None or dt > latest_date:
                latest_date = dt
        except ValueError:
            continue
    if latest_date:
        return latest_date
    
    return None

# Date-range presets used by the interactive menu (key → label + generator)
PRESET_RANGES: dict[str, tuple[str, Callable[[datetime.date], tuple[datetime.date, datetime.date]]]] = {
    "1": ("Month-to-Date", lambda today: (today.replace(day=1), today - timedelta(days=1))),
    "2": ("Year-to-Date",  lambda today: (today.replace(month=1, day=1), today - timedelta(days=1))),
    "3": ("Last 7 Days",   lambda today: (today - timedelta(days=7),  today - timedelta(days=1))),
    "4": ("Last 30 Days",  lambda today: (today - timedelta(days=30), today - timedelta(days=1))),
    # Full previous calendar month
    "6": ("Last Month", lambda today: (
        # start: first day of previous month
        (today.replace(day=1) - timedelta(days=1)).replace(day=1),
        # end: last day of previous month
        (today.replace(day=1) - timedelta(days=1))
    )),
    # Mid-month (1st–15th) of the current month relative to today
    "7": ("Mid Month (1st–15th)", lambda today: (
        today.replace(day=1),
        today.replace(day=15)
    )),
}

def get_yoy_change(current: float, previous: float) -> str:
    """Calculate Year-over-Year percentage change and format it as a string."""
    if previous == 0:
        return "N/A"
    change = ((current - previous) / previous) * 100
    return f"{change:+.1f}%"

class MTDReportGenerator:
    """
    Generates a Month-to-Date performance summary report.

    This class handles the entire report generation process, from data loading to
    report generation and saving. It's designed to be flexible and extensible,
    allowing for different report templates and data sources.

    Attributes:
        start_date: Optional explicit start date (YYYY-MM-DD).
        end_date:   Optional explicit end date   (YYYY-MM-DD).
        output_dir: Optional output directory (default: "data/reports/weekly").
        choose_files: Whether to prompt for file selection (default: False).
        choose_files_current_only: Whether to only prompt for current year files (default: False).
        interactive: Whether to prompt for file selection interactively (default: False).
        template_name: The name of the report template to use (default: "mtd_performance").
    """
    def __init__(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        output_dir: Optional[str] = None,
        choose_files: bool = False,
        choose_files_current_only: bool = False,
        interactive: bool = False,
        template_name: str = "mtd_performance",
    ):
        """Initialise the generator.

        Args:
            start_date: Optional explicit start date (YYYY-MM-DD).
            end_date:   Optional explicit end date   (YYYY-MM-DD).
        """
        self.data_dir = Path("data/ads")
        # Determine report directory
        if output_dir is None:
            output_dir = "data/reports/executive"

        # Allow shorthand values for convenience
        if output_dir.lower() in {"executive", "exec", "exec-sum"}:
            output_dir = "data/reports/executive"

        self.reports_dir = Path(output_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # Interactive file selection flag
        self.choose_files = choose_files or choose_files_current_only  # master flag
        self.choose_files_current_only = choose_files_current_only
        self.interactive = interactive

        # Store template selection
        self.template_name = template_name
        self.data_sources_needed = self._determine_data_sources()

        # Store optional overrides
        self._start_override = start_date
        self._end_override = end_date

        # Initialize data containers for current and previous year
        self.ga4_data_current: Dict[str, Any] = {}
        self.shopify_data_current: Dict[str, Any] = {}
        self.ga4_data_previous: Dict[str, Any] = {}
        self.shopify_data_previous: Dict[str, Any] = {}

        # Date ranges will be set automatically
        self.mtd_date_range_current: Dict[str, Any] = {}
        self.mtd_date_range_previous: Dict[str, Any] = {}

    def _determine_data_sources(self) -> set[str]:
        """Return the union of required & optional data-source keys for the chosen template.
        Falls back to *all* data sources when the template is not found."""
        tmpl = get_report_template(self.template_name)
        if tmpl is None:
            return set(DATA_SOURCE_CONFIG.keys())
        needed: set[str] = set()
        for section in tmpl.sections:
            needed.update(section.required_data)
            if section.optional_data:
                needed.update(section.optional_data)
        return needed

    def _set_date_ranges(self):
        """Set reporting date ranges.

        If explicit overrides were supplied at initialisation, those are used.
        Otherwise, the default behaviour mirrors the previous logic (Month-to-Date).
        """

        # ================================================================
        # CURRENT PERIOD
        # ================================================================
        if self._start_override and self._end_override:
            start_current = datetime.strptime(self._start_override, "%Y-%m-%d").date()
            end_current = datetime.strptime(self._end_override, "%Y-%m-%d").date()
        else:
            today = datetime.today().date()
            end_current = today - timedelta(days=1)
            start_current = end_current.replace(day=1)

        self.mtd_date_range_current = {
            'start': start_current.strftime("%Y-%m-%d"),
            'end': end_current.strftime("%Y-%m-%d"),
            'start_dt': datetime.combine(start_current, datetime.min.time()),
            'end_dt': datetime.combine(end_current, datetime.min.time()),
            'year': start_current.year
        }
        print(f"✅ Current period set: {self.mtd_date_range_current['start']} → "
              f"{self.mtd_date_range_current['end']}")

        # ================================================================
        # PREVIOUS-YEAR COMPARISON PERIOD (same range in prior year)
        # ================================================================
        previous_year = self.mtd_date_range_current['year'] - 1
        start_prev = start_current.replace(year=previous_year)
        end_prev = end_current.replace(year=previous_year)

        self.mtd_date_range_previous = {
            'start': start_prev.strftime("%Y-%m-%d"),
            'end': end_prev.strftime("%Y-%m-%d"),
            'start_dt': datetime.combine(start_prev, datetime.min.time()),
            'end_dt': datetime.combine(end_prev, datetime.min.time()),
            'year': previous_year
        }
        print(f"✅ Previous-year period set: {self.mtd_date_range_previous['start']} → "
              f"{self.mtd_date_range_previous['end']}")


    def _report_missing_data(self) -> None:
        """Check which key data sets are missing and alert the user"""
        missing_sources = []
        # Check current year data
        if 'new_returning' not in self.shopify_data_current:
            missing_sources.append("Shopify 'New vs Returning' (Current Year)")
        if 'products' not in self.shopify_data_current:
            missing_sources.append("Shopify Product Sales (Current Year)")
        if 'channel_group' not in self.ga4_data_current:
            missing_sources.append("GA4 Channel Group (Current Year)")

        if missing_sources:
            print("\n⚠️  The following data sources were NOT found. "
                  "Corresponding sections will be omitted or incomplete:")
            for src in missing_sources:
                print(f"   • {src}")
        else:
            print("\n✅ All key data sources are available for this report.")

    def _find_and_select_files(self) -> Dict[str, Dict[str, str]]:
        """Finds data files for current and previous years. If self.choose_files is True,
        prompt user for which file to use when multiple candidates exist."""
        # Build file patterns from central DATA_SOURCE_CONFIG
        # Limit patterns to only the data sources the current template needs
        file_patterns = {
            key: cfg['pattern']
            for key, cfg in DATA_SOURCE_CONFIG.items()
            if key in self.data_sources_needed
        }

        selected_files = {'current': {}, 'previous': {}}
        current_year = str(self.mtd_date_range_current['year'])
        previous_year = str(self.mtd_date_range_previous['year'])

        print("\n=== SCANNING FOR DATA FILES (CURRENT & PREVIOUS YEAR) ===")

        for file_type, pattern in file_patterns.items():
            # Support single pattern string or list of patterns
            files: list[str] = []
            if isinstance(pattern, (list, tuple)):
                for patt in pattern:
                    files.extend(glob.glob(str(self.data_dir / "**" / patt), recursive=True))
            else:
                files = glob.glob(str(self.data_dir / "**" / pattern), recursive=True)

            current_year_files = [f for f in files if current_year in f]
            previous_year_files = [f for f in files if previous_year in f]

            # Prioritise DAILY exports (they include a Date column) over aggregated totals
            def _select_latest(file_list: list[str]) -> str:
                """Return the file with the most recent date in filename, prioritizing daily files."""
                if not file_list:
                    raise ValueError("file_list cannot be empty")
                
                daily = [f for f in file_list if 'daily-' in os.path.basename(f).lower()]
                target_pool = daily if daily else file_list
                
                def _file_sort_key(filepath: str) -> tuple:
                    """Sort key: (end_date, start_date_for_tiebreak, modification_time).
                    Prefer latest end date; when equal, prefer the file whose start date is later (shorter span).
                    """
                    basename = os.path.basename(filepath)
                    # Extract potential start/end from 'YYYY-MM-DD - YYYY-MM-DD'
                    rng = re.findall(r'(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})', basename)
                    end_dt = _extract_date_from_filename(filepath) or datetime(1970, 1, 1)
                    start_dt = datetime(1970, 1, 1)
                    if rng:
                        try:
                            # Use the latest pair by end date
                            pairs = [(datetime.strptime(a, '%Y-%m-%d'), datetime.strptime(b, '%Y-%m-%d')) for a,b in rng]
                            pairs.sort(key=lambda x: x[1])
                            start_dt, end_dt = pairs[-1]
                        except Exception:
                            pass
                    return (end_dt, start_dt, os.path.getmtime(filepath))
                
                return max(target_pool, key=_file_sort_key)

            def _select_best_with_coverage(file_list: list[str], required_end: datetime) -> str:
                """Prefer files whose inferred end date >= required_end; fallback to latest otherwise.
                Within candidates, keep the same sorting behavior as _select_latest."""
                if not file_list:
                    raise ValueError("file_list cannot be empty")
                def _infer_range(filepath: str) -> tuple[datetime, datetime]:
                    basename = os.path.basename(filepath)
                    rng = re.findall(r'(\d{4}-\d{2}-\d{2})\s*-\s*(\d{4}-\d{2}-\d{2})', basename)
                    end_dt = _extract_date_from_filename(filepath) or datetime(1970, 1, 1)
                    start_dt = datetime(1970, 1, 1)
                    if rng:
                        try:
                            pairs = [(datetime.strptime(a, '%Y-%m-%d'), datetime.strptime(b, '%Y-%m-%d')) for a,b in rng]
                            pairs.sort(key=lambda x: x[1])
                            start_dt, end_dt = pairs[-1]
                        except Exception:
                            pass
                    return start_dt, end_dt
                # First, try to find files that meet coverage
                covered = []
                for f in file_list:
                    _, end_dt = _infer_range(f)
                    if end_dt.date() >= required_end.date():
                        covered.append(f)
                pool = covered if covered else file_list
                # Now apply the usual latest selection logic (with daily preference as tie-breaker only)
                daily = [f for f in pool if 'daily-' in os.path.basename(f).lower()]
                target_pool = daily if daily else pool
                def _sort_key(f: str) -> tuple:
                    s, e = _infer_range(f)
                    return (e, s, os.path.getmtime(f))
                return max(target_pool, key=_sort_key)

            # Helper for interactive selection
            def _prompt_choice(file_list):
                print("   Choose a file (most-recent by filename date first):")
                for idx, f in enumerate(file_list, start=1):
                    basename = os.path.basename(f)
                    extracted_date = _extract_date_from_filename(f)
                    if extracted_date:
                        date_info = f"data: {extracted_date.strftime('%Y-%m-%d')}"
                    else:
                        mtime = datetime.fromtimestamp(os.path.getmtime(f)).strftime('%Y-%m-%d %H:%M')
                        date_info = f"modified: {mtime}"
                    print(f"     {idx}) {basename}  [{date_info}]")
                choice = input("   Enter number (default 1): ").strip() or "1"
                try:
                    return file_list[int(choice) - 1]
                except Exception:
                    print("   Invalid choice – defaulting to first (most-recent) item.")
                    return file_list[0]

            def _check_coverage(filepath: str, end_date: datetime) -> None:
                """Warn if the latest date inferred from filename precedes the report end date."""
                inferred = _extract_date_from_filename(filepath)
                if inferred and inferred.date() < end_date.date():
                    print(f"⚠️  {file_type}: Selected '{os.path.basename(filepath)}' appears to end {inferred.date()} which is before the report end {end_date.date()}. Consider updating exports.")

            if current_year_files:
                if self.choose_files:  # always prompt for current when enabled
                    # Present DAILY files first in the selection list for clarity
                    def _display_sort_key(filepath: str) -> tuple:
                        """Sort key for display: (is_not_daily, -extracted_date, -modification_time)"""
                        is_daily = 'daily-' in os.path.basename(filepath).lower()
                        extracted_date = _extract_date_from_filename(filepath)
                        if extracted_date:
                            # Convert to negative timestamp for reverse chronological order
                            date_score = -extracted_date.timestamp()
                        else:
                            # Use modification time as fallback, also negative for reverse order
                            date_score = -os.path.getmtime(filepath)
                        return (not is_daily, date_score)
                    
                    display_list = sorted(current_year_files, key=_display_sort_key)
                    latest_current = _prompt_choice(display_list)
                else:
                    # For GA4 channel groups and source/medium, prefer coverage of required end date
                    if file_type in {'ga4_channel_group', 'ga4_source_medium'}:
                        latest_current = _select_best_with_coverage(current_year_files, self.mtd_date_range_current['end_dt'])
                    else:
                        latest_current = _select_latest(current_year_files)
                selected_files['current'][file_type] = latest_current
                print(f"✅ {file_type} (Current Year): Selected '{os.path.basename(latest_current)}'")
                # Coverage check: warn if stale
                _check_coverage(latest_current, self.mtd_date_range_current['end_dt'])
            else:
                print(f"⚠️  {file_type} (Current Year): No files found for {current_year}")

            if previous_year_files:
                if self.choose_files and not self.choose_files_current_only:
                    display_list = sorted(previous_year_files, key=_display_sort_key)
                    latest_previous = _prompt_choice(display_list)
                else:
                    if file_type in {'ga4_channel_group', 'ga4_source_medium'}:
                        latest_previous = _select_best_with_coverage(previous_year_files, self.mtd_date_range_previous['end_dt'])
                    else:
                        latest_previous = _select_latest(previous_year_files)
                selected_files['previous'][file_type] = latest_previous
                print(
                    f"✅ {file_type} (Previous Year): Selected '{os.path.basename(latest_previous)}'"
                )
                _check_coverage(latest_previous, self.mtd_date_range_previous['end_dt'])
            else:
                print(f"⚠️  {file_type} (Previous Year): No files found for {previous_year}")

        return selected_files

    def load_data_for_period(self, selected_files: Dict[str, str],
                            date_range: Dict) -> Tuple[Dict, Dict]:
        """Loads and processes data for a given period (current or previous)."""
        ga4_data, shopify_data = {}, {}
        start_date = date_range['start_dt']
        end_date = date_range['end_dt']

        # ------------------------------------------------------------------
        # Helper to standardise "Date" column in GA4 exports (varies: Date, Day)
        # ------------------------------------------------------------------
        def _standardise_ga4_dates(df: pd.DataFrame) -> pd.DataFrame:
            # Clean column names of stray whitespace / non-printables
            df.columns = df.columns.str.encode('utf-8').str.decode('utf-8', 'ignore').str.strip()

            if 'Date' not in df.columns:
                candidate = next((c for c in df.columns if 'date' in c.lower()), None)
                if not candidate:
                    raise ValueError("No date column found in GA4 file; columns = " + ", ".join(df.columns))
                df.rename(columns={candidate: 'Date'}, inplace=True)
            # Robustly parse YYYYMMDD formats that often come in as ints
            date_series = df['Date']
            try:
                # Detect 8-digit numeric-like values
                as_str = date_series.astype(str).str.strip()
                if as_str.str.match(r'^\d{8}$').all():
                    df['Date'] = pd.to_datetime(as_str, format='%Y%m%d', errors='coerce')
                else:
                    df['Date'] = pd.to_datetime(date_series, errors='coerce')
            except Exception:
                df['Date'] = pd.to_datetime(date_series, errors='coerce')
            return df

        # Load GA4 data
        if 'ga4_source_medium' in selected_files:
            try:
                df = pd.read_csv(selected_files['ga4_source_medium'], comment='#')
            except Exception:
                df = pd.read_csv(selected_files['ga4_source_medium'], skiprows=9, engine='python')
            assert_columns(df, DATA_SOURCE_CONFIG['ga4_source_medium']['required_columns'], selected_files['ga4_source_medium'])
            df = _standardise_ga4_dates(df)
            df_filtered = df[(df['Date'] >= start_date) &
                            (df['Date'] <= end_date)]
            df_filtered['Total revenue'] = pd.to_numeric(
                df_filtered['Total revenue'], errors='coerce').fillna(0)
            ga4_data['source_medium'] = df_filtered
        else:
            print("⚠️  GA4 Source Medium data not found. Skipping GA4 source/medium metrics.")

        if 'ga4_channel_group' in selected_files:
            try:
                df = pd.read_csv(selected_files['ga4_channel_group'], comment='#')
            except Exception:
                df = pd.read_csv(selected_files['ga4_channel_group'], skiprows=9, engine='python')
            # Normalize possible GA4 header variants to a single expected name
            for candidate in ['Default channel group', 'Session default channel group']:
                if candidate in df.columns:
                    if candidate != 'Default channel group':
                        df = df.rename(columns={candidate: 'Default channel group'})
                    break
            assert_columns(df, DATA_SOURCE_CONFIG['ga4_channel_group']['required_columns'], selected_files['ga4_channel_group'])
            df = _standardise_ga4_dates(df)
            df_filtered = df[(df['Date'] >= start_date) &
                            (df['Date'] <= end_date)]
            df_filtered['Total revenue'] = pd.to_numeric(
                df_filtered['Total revenue'], errors='coerce').fillna(0)
            ga4_data['channel_group'] = df_filtered
            # Store the unfiltered dataframe for broader quarter/year calculations
            ga4_data['channel_group_full'] = df.copy()
        else:
            print("⚠️  GA4 Channel Group data not found. Skipping GA4 channel group metrics.")

        # Load Shopify data
        if 'shopify_total_sales' in selected_files:
            try:
                df = pd.read_csv(selected_files['shopify_total_sales'])
                assert_columns(df, DATA_SOURCE_CONFIG['shopify_total_sales']['required_columns'], selected_files['shopify_total_sales'])
                # This file is often not filtered by date on load, but used for monthly trends
                shopify_data['total_sales'] = df
            except Exception:
                pass

        if 'shopify_new_returning' in selected_files:
            try:
                df = pd.read_csv(selected_files['shopify_new_returning'])
                assert_columns(df, DATA_SOURCE_CONFIG['shopify_new_returning']['required_columns'], selected_files['shopify_new_returning'])
                # Assuming this file contains monthly data, it's handled in metric calculation
                shopify_data['new_returning'] = df
            except Exception:
                pass

        if 'shopify_products' in selected_files:
            try:
                df = pd.read_csv(selected_files['shopify_products'])
                assert_columns(df, DATA_SOURCE_CONFIG['shopify_products']['required_columns'], selected_files['shopify_products'])
                # Normalize date columns if present and filter to range
                df_filtered = df.copy()
                date_filtered = False
                # Prefer Day
                for day_col in ['Day', 'day', 'Date', 'date']:
                    if day_col in df_filtered.columns:
                        df_filtered[day_col] = pd.to_datetime(df_filtered[day_col], errors='coerce')
                        m = (df_filtered[day_col] >= start_date) & (df_filtered[day_col] <= end_date)
                        df_filtered = df_filtered[m]
                        date_filtered = True
                        break
                # Fallback to Month granularity when available (single-month ranges)
                if not date_filtered and 'Month' in df_filtered.columns:
                    # Normalize month strings to Period('M')
                    df_filtered['_month_norm'] = (
                        pd.to_datetime(df_filtered['Month'], errors='coerce').dt.to_period('M').astype(str)
                    )
                    start_month = start_date.strftime('%Y-%m')
                    end_month = end_date.strftime('%Y-%m')
                    if start_month == end_month:
                        df_filtered = df_filtered[df_filtered['_month_norm'] == start_month]
                        date_filtered = True
                    else:
                        # If range spans multiple months, include those months (best-effort)
                        months = pd.period_range(start=start_month, end=end_month, freq='M').astype(str).tolist()
                        df_filtered = df_filtered[df_filtered['_month_norm'].isin(months)]
                        date_filtered = True
                # Coerce numeric fields to avoid string sums
                for col in ['Total sales', 'Net items sold', 'New customers', 'Returning customers']:
                    if col in df_filtered.columns:
                        df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce').fillna(0)
                shopify_data['products'] = df_filtered
            except Exception:
                pass

        # Load Northbeam spend data (if present)
        if 'northbeam_spend' in selected_files:
            try:
                df = pd.read_csv(selected_files['northbeam_spend'], thousands=',')
                # Normalize date column to 'date'
                for candidate in ['date', 'Date', 'day', 'Day']:
                    if candidate in df.columns:
                        if candidate != 'date':
                            df = df.rename(columns={candidate: 'date'})
                        break
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'], errors='coerce')
                # allow full YTD up to current end
                df_filtered = df[(df['date'] <= end_date)].copy()

                # Normalize expected columns with case-insensitive lookup
                col_map = {}
                for col in df_filtered.columns:
                    low = col.lower()
                    if low == 'spend':
                        col_map[col] = 'spend'
                    elif low == 'rev':
                        # Keep cash revenue as 'rev'
                        col_map[col] = 'rev'
                    elif low in {'attributed_rev', 'revenue', 'attributed_revenue'}:
                        # Normalize accrual-like revenue to 'attributed_rev'
                        col_map[col] = 'attributed_rev'
                    elif low in {'transactions', 'orders'}:
                        col_map[col] = 'transactions'
                    elif low in {'new_customer_percentage', 'new_customer_%'}:
                        col_map[col] = 'new_customer_percentage'

                df_filtered = df_filtered.rename(columns=col_map)

                # Secondary normalization: if neither 'rev' nor 'attributed_rev' present, try to infer
                if ('rev' not in df_filtered.columns) and ('attributed_rev' not in df_filtered.columns):
                    revenue_like = [c for c in df_filtered.columns if 'revenue' in c.lower() or 'rev' in c.lower()]
                    if revenue_like:
                        # Prefer columns that mention 'rev' (cash) first
                        ranked = sorted(
                            revenue_like,
                            key=lambda c: (
                                ('rev' in c.lower()),
                                ('attributed' in c.lower()),
                                len(c)
                            ),
                            reverse=True,
                        )
                        # Assign the first to 'rev' and, if available, next to 'attributed_rev'
                        first = ranked[0]
                        df_filtered = df_filtered.rename(columns={first: 'rev'})
                        if len(ranked) > 1:
                            second = next((c for c in ranked[1:] if c != first), None)
                            if second:
                                df_filtered = df_filtered.rename(columns={second: 'attributed_rev'})

                # Ensure platform breakdown column exists
                if 'breakdown_platform_northbeam' not in df_filtered.columns:
                    df_filtered['breakdown_platform_northbeam'] = df_filtered.get('platform', 'Unknown')

                # Remove duplicate column names that can break downstream numeric casting
                df_filtered = df_filtered.loc[:, ~df_filtered.columns.duplicated()]

                # Coerce numeric for key columns
                for c in ['spend', 'rev', 'attributed_rev', 'transactions']:
                    if c in df_filtered.columns:
                        df_filtered[c] = pd.to_numeric(df_filtered[c], errors='coerce').fillna(0)

                ga4_data['northbeam'] = df_filtered  # store under ga4_data for convenience
            except Exception:
                pass

        return ga4_data, shopify_data

    def calculate_ga4_metrics(self, ga4_data: Dict) -> Dict:
        """Calculate key metrics from GA4 data for a single period."""
        metrics = {}
        if not ga4_data:
            return metrics

        if 'channel_group' in ga4_data:
            df = ga4_data['channel_group']
            if 'Default channel group' in df.columns:
                channel_group_performance = df.groupby('Default channel group').agg({
                    'Sessions': 'sum',
                    'Total revenue': 'sum'
                }).sort_values('Total revenue', ascending=False)
                metrics['channel_group_performance'] = channel_group_performance

                # Totals for GA4 metrics
                total_sessions = df['Sessions'].sum()
                total_rev = df['Total revenue'].sum()

                # Define paid channel set to estimate paid-media revenue
                paid_channels = {
                    'Paid Search', 'Paid Social', 'Affiliate', 'Cross-network',
                    'SMS', 'Display', 'Shopping', 'AppLovin', 'Referral',
                    'Bing Ads', 'Pinterest Ads', 'TikTok Ads'
                }

                paid_rev = df[df['Default channel group'].isin(paid_channels)][
                    'Total revenue'].sum()

                metrics['totals'] = {
                    'sessions': total_sessions,
                    'ga_revenue': total_rev,
                    'paid_revenue': paid_rev,
                }

        # --------------------------------------------------------------
        # Custom channel mapping (Paid Search, Paid Social, etc.)
        # --------------------------------------------------------------
        source_rev_df = None
        if 'source_medium' in ga4_data:
            source_rev_df = ga4_data['source_medium']

            # Ensure we have the expected columns
            src_col = None
            for col in source_rev_df.columns:
                if col.lower().startswith('session source'):
                    src_col = col
                    break
            if src_col and 'Total revenue' in source_rev_df.columns:
                def _map(row_val: str) -> str | None:
                    val = str(row_val).lower()
                    if 'awin' in val:
                        return 'Awin (Paid Affiliate)'
                    if 'shopmy' in val or 'shop my shelf' in val or 'shopmyshelf' in val:
                        return 'ShopMyShelf (Influencer)'
                    if 'applovin' in val:
                        return 'AppLovin'
                    if any(tok in val for tok in ['bing / cpc', 'bing ads', 'microsoft', 'bing / ppc', 'msn / cpc', 'ads.microsoft']):
                        return 'Bing Ads'
                    if 'pinterest' in val or 'pin / cpc' in val:
                        return 'Pinterest Ads'
                    if any(tok in val for tok in ['tiktok', 'ttads', 'tiktokads', 'tt / cpc']):
                        # require paid signal unless clearly ads
                        if any(t in val for t in ['cpc','ppc','paid','ads']):
                            return 'TikTok Ads'
                    # Google paid
                    if any(tok in val for tok in ['google / cpc', 'google ads', 'google / ppc', 'google / paid', 'gads / cpc']):
                        return 'Paid Search'
                    # Meta/Facebook/Instagram paid (avoid pure referral)
                    if any(tok in val for tok in ['facebook', 'instagram', 'meta', 'fb', 'ig', 'insta']):
                        if any(t in val for t in ['cpc','ppc','paid','paid_social','paid social','ads']):
                            return 'Paid Social'
                    return None

                source_rev_df['__custom_channel__'] = source_rev_df[src_col].apply(_map)
                revenue_df = (
                    source_rev_df.dropna(subset=['__custom_channel__'])
                    .groupby('__custom_channel__')
                    .agg({'Total revenue': 'sum'})
                )

                # -----------------------------
                # Merge with spend (Northbeam)
                # -----------------------------
                if 'northbeam' in ga4_data:
                    nb = ga4_data['northbeam']
                    # Choose platform column
                    platform_col = 'breakdown_platform_northbeam' if 'breakdown_platform_northbeam' in nb.columns else (
                        'platform' if 'platform' in nb.columns else None
                    )
                    if platform_col is not None:
                        # Robust mapping from platform names to custom channels
                        def _platform_to_channel(name: Any) -> Optional[str]:
                            val = str(name).lower()
                            if 'google' in val:
                                return 'Paid Search'
                            if 'bing' in val or 'microsoft' in val:
                                return 'Bing Ads'
                            if 'meta' in val or 'facebook' in val or 'instagram' in val:
                                return 'Paid Social'
                            if 'tiktok' in val:
                                return 'TikTok Ads'
                            if 'pinterest' in val:
                                return 'Pinterest Ads'
                            if 'applovin' in val:
                                return 'AppLovin'
                            if 'awin' in val:
                                return 'Awin (Paid Affiliate)'
                            if 'shopmy' in val or 'shopmyshelf' in val:
                                return 'ShopMyShelf (Influencer)'
                            return None

                        nb = nb.copy()
                        nb['__custom_channel__'] = nb[platform_col].apply(_platform_to_channel)
                        agg_spec = {}
                        if 'spend' in nb.columns:
                            agg_spec['spend'] = 'sum'
                        if 'attributed_rev' in nb.columns:
                            agg_spec['attributed_rev'] = 'sum'
                        if 'transactions' in nb.columns:
                            agg_spec['transactions'] = 'sum'
                        if agg_spec:
                            spend_df = (
                                nb.dropna(subset=['__custom_channel__'])
                                  .groupby('__custom_channel__')
                                  .agg(agg_spec)
                            )
                        else:
                            spend_df = pd.DataFrame(columns=['spend', 'attributed_rev', 'transactions'])
                    else:
                        spend_df = pd.DataFrame(columns=['spend', 'attributed_rev'])

                    merged = (revenue_df.join(spend_df[['spend']], how='left')
                             .fillna(0))
                    merged['ROAS'] = merged.apply(
                        lambda r: r['Total revenue'] / r['spend'] if r['spend'] else 0,
                        axis=1)
                    metrics['custom_channel_performance'] = merged
                else:
                    metrics['custom_channel_performance'] = revenue_df

        return metrics

    def calculate_shopify_metrics(self, shopify_data: Dict, date_range: Dict) -> Dict:
        """Calculate key metrics from Shopify data for a single period.
        Returns a dict that both aggregates high-level MTD metrics *and* surfaces
        raw DataFrames required by downstream helpers (e.g. total_sales for
        Q2 YoY calculations)."""
        metrics = {}
        if not shopify_data:
            return metrics

        # -------------------------------------------------------------
        # Surface raw data frames needed by later reporting sections
        # -------------------------------------------------------------
        for key in ['total_sales', 'products', 'new_returning']:
            if key in shopify_data:
                metrics[key] = shopify_data[key]

        # Customer mix from new vs returning data
        if 'new_returning' in shopify_data:
            df = shopify_data['new_returning']
            if 'Month' in df.columns:
                # Normalise month values – they might be in YYYY-MM or
                # YYYY-MM-DD form.
                # Convert to pandas Period('M') for reliable comparisons.
                df['_month_norm'] = (
                    pd.to_datetime(df['Month'], errors='coerce')
                    .dt.to_period('M')
                    .astype(str)
                )
 
                month_str = date_range['start_dt'].strftime('%Y-%m')
                current_data = df[df['_month_norm'] == month_str].copy()
                # Restrict to exact MTD window when Day column exists
                if 'Day' in current_data.columns:
                    current_data['Day'] = pd.to_datetime(current_data['Day'], errors='coerce')
                    current_data = current_data[(current_data['Day'] >= date_range['start_dt']) & (current_data['Day'] <= date_range['end_dt'])]
 
                if not current_data.empty:
                    # Sum across all days within the month by New/Returning
                    def _sum_for(label: str) -> tuple[float, int]:
                        sub = current_data[current_data['New or returning customer'] == label]
                        rev = pd.to_numeric(sub['Total sales'], errors='coerce').fillna(0).sum()
                        ords = pd.to_numeric(sub['Orders'], errors='coerce').fillna(0).sum()
                        return rev, int(ords)

                    new_rev, new_ord = _sum_for('New')
                    ret_rev, ret_ord = _sum_for('Returning')

                    metrics['customer_mix'] = {
                        'new_revenue': new_rev, 'new_orders': new_ord,
                        'returning_revenue': ret_rev, 'returning_orders': ret_ord,
                        'total_revenue': new_rev + ret_rev, 'total_orders': new_ord + ret_ord
                    }

        # Product performance
        if 'products' in shopify_data:
            df = shopify_data['products']
            if 'Product title' in df.columns and 'Total sales' in df.columns:
                agg_cols = {
                    'Total sales': 'sum',
                    'Net items sold': 'sum',
                }
                if {'New customers', 'Returning customers'}.issubset(df.columns):
                    agg_cols['New customers'] = 'sum'
                    agg_cols['Returning customers'] = 'sum'

                full_perf = (
                    df.groupby('Product title').agg(agg_cols)
                    .sort_values('Total sales', ascending=False)
                )

                top_n = 25
                metrics['product_performance'] = full_perf.head(top_n)

                if {'New customers', 'Returning customers'}.issubset(full_perf.columns):
                    other_slice = full_perf.iloc[top_n:]
                    if not other_slice.empty:
                        other_totals = {
                            'Total sales': other_slice['Total sales'].sum(),
                            'New customers': other_slice['New customers'].sum(),
                            'Returning customers': other_slice['Returning customers'].sum(),
                        }
                        metrics['product_other'] = other_totals
                else:
                    other_slice = full_perf.iloc[top_n:]
                    if not other_slice.empty:
                        metrics['product_other'] = {'Total sales': other_slice['Total sales'].sum()}

        # Overall totals
        if 'customer_mix' in metrics:
            metrics['total_revenue'] = metrics['customer_mix']['total_revenue']
            metrics['total_orders'] = metrics['customer_mix']['total_orders']
            metrics['aov'] = (metrics['total_revenue'] / metrics['total_orders']
                             if metrics['total_orders'] > 0 else 0)

        # Fallback: if total_revenue missing or zero, derive from daily total_sales within MTD
        if not metrics.get('total_revenue'):
            ts = metrics.get('total_sales')
            if isinstance(ts, pd.DataFrame) and 'Day' in ts.columns and 'Total sales' in ts.columns:
                df = ts.copy()
                df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
                m = (df['Day'] >= date_range['start_dt']) & (df['Day'] <= date_range['end_dt'])
                sub = df[m]
                if not sub.empty:
                    total_rev_fallback = pd.to_numeric(sub['Total sales'], errors='coerce').fillna(0).sum()
                    total_orders_fallback = int(pd.to_numeric(sub.get('Orders', 0), errors='coerce').fillna(0).sum()) if 'Orders' in sub.columns else 0
                    metrics['total_revenue'] = total_rev_fallback
                    # Preserve existing orders if present; otherwise set from fallback when available
                    if not metrics.get('total_orders'):
                        metrics['total_orders'] = total_orders_fallback
                    metrics['aov'] = (metrics['total_revenue'] / metrics['total_orders'] if metrics.get('total_orders') else 0)

        return metrics

    def generate_report(self, metrics_current: Dict, metrics_previous: Dict) -> str:
        """Generate the markdown report in the desired format."""

        # ----------------------------------------------------------------
        # Header (title, period & date)
        # ----------------------------------------------------------------
        start_dt = self.mtd_date_range_current['start_dt']
        end_dt   = self.mtd_date_range_current['end_dt']

        if start_dt.month == end_dt.month:
            period_str = f"{start_dt.strftime('%B')} {start_dt.day} - {end_dt.day}"
        else:
            period_str = (f"{start_dt.strftime('%B')} {start_dt.day} - "
                         f"{end_dt.strftime('%B')} {end_dt.day}")

        report_date = datetime.now().strftime("%B %d, %Y")

        report = (
            "# HigherDOSE Month-to-Date Performance Summary\n\n"
            f"**Time Period:** {period_str}  \n"
            f"**Date:** {report_date}\n\n"
            "---\n\n"
        )

        # ----------------------------------------------------------------
        # EXECUTIVE SUMMARY
        # ----------------------------------------------------------------
        report += self._generate_executive_summary(
            shopify_curr=metrics_current.get('shopify', {}),
            ga4_curr=metrics_current.get('ga4', {}),
            shopify_prev=metrics_previous.get('shopify', {})
        )

        # ----------------------------------------------------------------
        # CUSTOMER MIX
        # ----------------------------------------------------------------
        report += self._generate_customer_mix_table(metrics_current.get('shopify', {}))

        # ----------------------------------------------------------------
        # MONTHLY TRENDS
        # ----------------------------------------------------------------
        report += self._generate_monthly_trends_table()

        # ----------------------------------------------------------------
        # YoY BUSINESS IMPACT
        # ----------------------------------------------------------------
        report += self._generate_yoy_impact_table_mtd(
            shopify_curr=metrics_current.get('shopify', {}),
            shopify_prev=metrics_previous.get('shopify', {}),
            ga4_curr=metrics_current.get('ga4', {}),
            ga4_prev=metrics_previous.get('ga4', {}),
        )

        # ----------------------------------------------------------------
        # PERFORMANCE BY PRODUCT
        # ----------------------------------------------------------------
        report += self._generate_product_performance_table(
            metrics_current.get('shopify', {}),
            metrics_previous.get('shopify', {})
        )

        # ----------------------------------------------------------------
        # (OPTIONAL) CHANNEL PERFORMANCE
        # ----------------------------------------------------------------
        report += self._generate_channel_performance_table(
            metrics_current.get('ga4', {}), metrics_previous.get('ga4', {}))

        report += f"\n*Report generated on {report_date}*\n"
        return report

    def _generate_executive_summary(self, shopify_curr: Dict, ga4_curr: Dict, shopify_prev: Dict) -> str:
        """Create the EXECUTIVE SUMMARY section with complete MTD metrics."""
        section = "## EXECUTIVE SUMMARY\n\n"
 
        bullets: List[str] = []
 
        total_rev = shopify_curr.get('total_revenue', 0)
        total_orders = shopify_curr.get('total_orders', 0)
        aov = shopify_curr.get('aov', 0)
 
        if total_rev:
            bullets.append(f"- **Total Revenue:** ${total_rev:,.0f}")
        if total_orders:
            bullets.append(f"- **Total Orders:** {total_orders:,}")
        if aov:
            bullets.append(f"- **Average Order Value (AOV):** ${aov:,.0f}")
 
        cm = shopify_curr.get('customer_mix')
        new_pct = None
        new_aov_val = None
        ret_aov_val = None
        if cm:
            new_pct = (cm['new_revenue'] / cm['total_revenue']) * 100 if cm['total_revenue'] else 0
            ret_pct = 100 - new_pct
            bullets.append(f"- **New to Brand Contribution:** {new_pct:.0f}%  ")
            bullets.append(f"- **Returning Customer Contribution:** {ret_pct:.0f}%  ")
            # AOVs by cohort
            new_aov_val = (cm['new_revenue'] / cm['new_orders']) if cm.get('new_orders', 0) else 0
            ret_aov_val = (cm['returning_revenue'] / cm['returning_orders']) if cm.get('returning_orders', 0) else 0
 
        # Paid-media contribution and blended ROAS/CAC from Northbeam + GA4
        paid_rev = 0
        total_sessions = 0
        if 'totals' in ga4_curr:
            paid_rev = ga4_curr['totals'].get('paid_revenue', 0)
            total_sessions = ga4_curr['totals'].get('sessions', 0)
 
        # Compute MTD spend and transactions from Northbeam
        mtd_spend = 0
        mtd_transactions = 0
        if 'northbeam' in self.ga4_data_current:
            nb = self.ga4_data_current['northbeam']
            start_dt = self.mtd_date_range_current['start_dt']
            end_dt = self.mtd_date_range_current['end_dt']
            if 'date' in nb.columns:
                m = (nb['date'] >= start_dt) & (nb['date'] <= end_dt)
                nb_mtd = nb[m].copy()
            else:
                nb_mtd = nb.copy()
            # Use Accrual performance rows only and positive spend
            if 'accounting_mode' in nb_mtd.columns:
                nb_accrual = nb_mtd[nb_mtd['accounting_mode'].str.contains('Accrual', case=False, na=False)]
                # Fallback: if accrual filter removes all rows, keep original
                nb_mtd = nb_accrual if not nb_accrual.empty else nb_mtd
            if 'spend' in nb_mtd.columns:
                nb_mtd['spend'] = pd.to_numeric(nb_mtd['spend'], errors='coerce').fillna(0)
                nb_mtd = nb_mtd[nb_mtd['spend'] > 0]
            if 'spend' in nb_mtd.columns:
                mtd_spend = pd.to_numeric(nb_mtd['spend'], errors='coerce').fillna(0).sum()
            if 'transactions' in nb_mtd.columns:
                mtd_transactions = pd.to_numeric(nb_mtd['transactions'], errors='coerce').fillna(0).sum()
 
        blended_roas = (total_rev / mtd_spend) if mtd_spend else 0
        # CAC per order over entire customers (total orders)
        cac = (mtd_spend / total_orders) if total_orders else 0
        paid_contrib_pct = (paid_rev / total_rev * 100) if total_rev else 0
 
        # Revenue YoY (MTD) – prefer Day-sliced Shopify
        def _mtd_rev(shopify_dict: Dict, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> Optional[float]:
            # Try total-sales daily
            ts = shopify_dict.get('total_sales')
            if isinstance(ts, pd.DataFrame) and 'Day' in ts.columns and 'Total sales' in ts.columns:
                df = ts.copy()
                df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
                sub = df[(df['Day'] >= start_dt) & (df['Day'] <= end_dt)]
                if not sub.empty:
                    return pd.to_numeric(sub['Total sales'], errors='coerce').fillna(0).sum()
            # Try new/returning daily (sum both cohorts)
            nr = shopify_dict.get('new_returning')
            if isinstance(nr, pd.DataFrame) and 'Day' in nr.columns and 'Total sales' in nr.columns:
                df = nr.copy()
                df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
                sub = df[(df['Day'] >= start_dt) & (df['Day'] <= end_dt)]
                if not sub.empty:
                    return pd.to_numeric(sub['Total sales'], errors='coerce').fillna(0).sum()
            return None
 
        cur_start = self.mtd_date_range_current['start_dt']
        cur_end = self.mtd_date_range_current['end_dt']
        prev_start = self.mtd_date_range_previous['start_dt']
        prev_end = self.mtd_date_range_previous['end_dt']
 
        cur_rev_for_yoy = _mtd_rev(self.shopify_data_current, cur_start, cur_end) or total_rev
        prev_rev_for_yoy = _mtd_rev(self.shopify_data_previous, prev_start, prev_end) or shopify_prev.get('total_revenue', 0)
        yoy_rev = get_yoy_change(cur_rev_for_yoy, prev_rev_for_yoy) if prev_rev_for_yoy else "N/A"
 
        # Rev-to-Net from Shopify total sales over time (if available)
        rev_to_net = "N/A"
        if 'total_sales' in self.shopify_data_current:
            ts = self.shopify_data_current['total_sales'].copy()
            if 'Day' in ts.columns and 'Total sales' in ts.columns and 'Net sales' in ts.columns:
                ts['Day'] = pd.to_datetime(ts['Day'], errors='coerce')
                m = (ts['Day'] >= self.mtd_date_range_current['start_dt']) & (ts['Day'] <= self.mtd_date_range_current['end_dt'])
                sub = ts[m]
                gross = pd.to_numeric(sub['Total sales'], errors='coerce').fillna(0).sum()
                net = pd.to_numeric(sub['Net sales'], errors='coerce').fillna(0).sum()
                if gross:
                    rev_to_net = f"{(net / gross * 100):.0f}%"
 
        # Always display Total Spend for clarity
        bullets.append(f"- **Total Spend:** ${mtd_spend:,.0f}")
 
        bullets.extend([
            f"- **Rev-to-Net:** {rev_to_net}  ",
            f"- **Blended ROAS:** {blended_roas:.2f}  ",
            f"- **Customer Acquisition Cost (CAC):** ${cac:,.0f}  ",
            f"- **Paid Media Contribution to Total Business Revenue:** {paid_contrib_pct:.0f}%  ",
            f"- **Total Business Revenue YoY:** {yoy_rev}  ",
        ])
 
        section += "\n".join(bullets) + "\n\n"
 
        # Build a concise, data-driven insight line
        parts: list[str] = []
        if total_rev and mtd_spend:
            parts.append(f"Revenue ${total_rev:,.0f} on ${mtd_spend:,.0f} spend (ROAS {blended_roas:.2f})")
        elif total_rev:
            parts.append(f"Revenue ${total_rev:,.0f}")
        if new_pct is not None and new_aov_val is not None and ret_aov_val is not None:
            parts.append(f"NTB {new_pct:.0f}% (AOV ${new_aov_val:,.0f} vs ${ret_aov_val:,.0f} returning)")
        if total_orders and cac:
            parts.append(f"CAC ${cac:,.0f} across {total_orders:,} orders")
        if paid_contrib_pct:
            parts.append(f"paid media drove {paid_contrib_pct:.0f}% of revenue")
        if yoy_rev and yoy_rev != "N/A":
            parts.append(f"YoY {yoy_rev}")
        insight_text = "; ".join(parts) if parts else "Performance stable; metrics pending."
        section += f"**Summary Insight:**  \n> {insight_text}\n\n---\n\n"
        return section

    def _generate_yoy_impact_table(self, shopify_curr: Dict, shopify_prev: Dict,
                                  ga4_curr: Dict, ga4_prev: Dict) -> str:
        """Compare Q2 totals (Apr–Jun) YoY when Shopify total-sales is available;
        fallback to MTD mix."""

        table = "## Year-over-Year Business Impact\n"
        table += "| Metric | This Year | Last Year | YoY Change |\n"
        table += "|---|---|---|---|\n"

        # Attempt Q2 aggregation first
        def _q2_totals(shopify_dict: Dict):
            if 'total_sales' not in shopify_dict:
                return None
            df = shopify_dict['total_sales'].copy()
            if 'Day' in df.columns:
                df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
                df = df.dropna(subset=['Day'])
                q2 = df[(df['Day'].dt.month.isin([4,5,6]))]
                rev = pd.to_numeric(q2['Total sales'], errors='coerce').sum()
                ords = (pd.to_numeric(q2['Orders'], errors='coerce').sum()
                       if 'Orders' in q2.columns else 0)
            elif 'Month' in df.columns:
                df['_m'] = pd.to_datetime(df['Month'], errors='coerce')
                q2 = df[df['_m'].dt.month.isin([4,5,6])]
                rev = pd.to_numeric(q2['Total sales'], errors='coerce').sum()
                ords = (pd.to_numeric(q2['Orders'], errors='coerce').sum()
                       if 'Orders' in q2.columns else 0)
            else:
                return None
            aov = rev / ords if ords else 0
            return rev, ords, aov

        q2_curr = _q2_totals(shopify_curr)
        q2_prev = _q2_totals(shopify_prev)

        if q2_curr and q2_prev:
            curr_rev, curr_ord, curr_aov = q2_curr
            prev_rev, prev_ord, prev_aov = q2_prev
        else:
            # Fallback to customer-mix totals (MTD)
            curr_rev = shopify_curr.get('total_revenue', 0)
            prev_rev = shopify_prev.get('total_revenue', 0)
            curr_ord = shopify_curr.get('total_orders', 0)
            prev_ord = shopify_prev.get('total_orders', 0)
            curr_aov = shopify_curr.get('aov', 0)
            prev_aov = shopify_prev.get('aov', 0)

        table += (f"| Total Revenue | ${curr_rev:,.0f} | ${prev_rev:,.0f} | "
                  f"{get_yoy_change(curr_rev, prev_rev)} |\n")
        table += (f"| Total Orders | {curr_ord:,} | {prev_ord:,} | "
                  f"{get_yoy_change(curr_ord, prev_ord)} |\n")
        table += (f"| Average Order Value | ${curr_aov:,.2f} | ${prev_aov:,.2f} | "
                  f"{get_yoy_change(curr_aov, prev_aov)} |\n")

        # Conversion Rate & Traffic
        # -----------------------------------------------------
        # GA4 Q2 totals helper
        # -----------------------------------------------------
        def _ga_q2(df_dict: Dict, yr: int):
            # Ensure we have some form of channel-group dataframe
            if 'channel_group_full' not in df_dict and 'channel_group' not in df_dict:
                return 0, 0  # sessions_total, paid_rev
            df = df_dict.get('channel_group_full') or df_dict.get('channel_group')
            if df is None:
                return 0, 0
 
            start_q2 = pd.Timestamp(year=yr, month=4, day=1)
            end_q2 = pd.Timestamp(year=yr, month=6, day=30)
            # Ensure Date is datetime
            if not pd.api.types.is_datetime64_any_dtype(df['Date']):
                df = df.copy()
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            mask = (df['Date'] >= start_q2) & (df['Date'] <= end_q2)
            sub = df[mask].copy()
 
            # Normalise numeric columns that we need
            for col in ['Sessions', 'Total revenue']:
                if col in sub.columns:
                    sub[col] = pd.to_numeric(sub[col], errors='coerce').fillna(0)
 
            # Detect correct channel-group column name
            channel_col = None
            for candidate in ['Default channel group', 'Session default channel group']:
                if candidate in sub.columns:
                    channel_col = candidate
                    break
 
            sessions_total = sub['Sessions'].sum() if 'Sessions' in sub.columns else 0
 
            if channel_col:
                paid_channels = {
                    'Paid Search', 'Paid Social', 'Affiliate', 'Cross-network',
                    'SMS', 'Display', 'Shopping', 'AppLovin', 'Referral',
                    'Bing Ads', 'Pinterest Ads', 'TikTok Ads'
                }
                paid_mask = sub[channel_col].isin(paid_channels)
                paid_rev = sub.loc[paid_mask, 'Total revenue'].sum()
            else:
                paid_rev = 0
            return sessions_total, paid_rev

        year_cur = self.mtd_date_range_current['year']
        year_prev = year_cur - 1
        curr_sessions, curr_paid_rev = _ga_q2(ga4_curr, year_cur)
        prev_sessions, prev_paid_rev = _ga_q2(ga4_prev, year_prev)

        curr_cvr = curr_ord / curr_sessions * 100 if curr_sessions else 0
        prev_cvr = prev_ord / prev_sessions * 100 if prev_sessions else 0

        curr_paid_pct = curr_paid_rev / curr_rev * 100 if curr_rev else 0
        prev_paid_pct = prev_paid_rev / prev_rev * 100 if prev_rev else 0

        table += (f"| Conversion Rate | {curr_cvr:.2f}% | {prev_cvr:.2f}% | "
                  f"{get_yoy_change(curr_cvr, prev_cvr)} |\n")
        table += (f"| Paid Revenue % of Total | {curr_paid_pct:.0f}% | "
                  f"{prev_paid_pct:.0f}% | "
                  f"{get_yoy_change(curr_paid_pct, prev_paid_pct)} |\n")
        table += (f"| Website Traffic (All) | {curr_sessions:,} | "
                  f"{prev_sessions:,} | "
                  f"{get_yoy_change(curr_sessions, prev_sessions)} |\n")
        return table + "---\n"

    def _generate_yoy_impact_table_mtd(self, shopify_curr: Dict, shopify_prev: Dict, ga4_curr: Dict, ga4_prev: Dict) -> str:
        """MTD YoY comparisons for revenue, orders, AOV, CVR, paid revenue share, and sessions."""
        table = "## Year-over-Year Business Impact\n"
        table += "| Metric | This Year | Last Year | YoY Change |\n"
        table += "|---|---|---|---|\n"
 
        # Prefer exact MTD filter from Shopify total-sales (Day) for both years
        def _mtd_from_total_sales(shopify_dict: Dict, start_dt: pd.Timestamp, end_dt: pd.Timestamp):
            if 'total_sales' not in shopify_dict:
                return None
            df = shopify_dict['total_sales']
            if 'Day' not in df.columns:
                return None
            ts = df.copy()
            ts['Day'] = pd.to_datetime(ts['Day'], errors='coerce')
            mask = (ts['Day'] >= start_dt) & (ts['Day'] <= end_dt)
            sub = ts[mask]
            if sub.empty:
                return None
            rev = pd.to_numeric(sub['Total sales'], errors='coerce').fillna(0).sum()
            ords = pd.to_numeric(sub['Orders'], errors='coerce').fillna(0).sum() if 'Orders' in sub.columns else 0
            aov = (rev / ords) if ords else 0
            return rev, int(ords), aov

        # Alternate: derive from daily New vs Returning (sum both cohorts)
        def _mtd_from_new_returning(shopify_dict: Dict, start_dt: pd.Timestamp, end_dt: pd.Timestamp):
            if 'new_returning' not in shopify_dict:
                return None
            df = shopify_dict['new_returning']
            if 'Day' not in df.columns:
                return None
            nr = df.copy()
            nr['Day'] = pd.to_datetime(nr['Day'], errors='coerce')
            mask = (nr['Day'] >= start_dt) & (nr['Day'] <= end_dt)
            sub = nr[mask]
            if sub.empty:
                return None
            rev = pd.to_numeric(sub['Total sales'], errors='coerce').fillna(0).sum()
            ords = pd.to_numeric(sub['Orders'], errors='coerce').fillna(0).sum()
            aov = (rev / ords) if ords else 0
            return rev, int(ords), aov
 
        cur_start = self.mtd_date_range_current['start_dt']
        cur_end = self.mtd_date_range_current['end_dt']
        prev_start = self.mtd_date_range_previous['start_dt']
        prev_end = self.mtd_date_range_previous['end_dt']
 
        cur_mtd = (_mtd_from_new_returning(shopify_curr, cur_start, cur_end) or
                   _mtd_from_total_sales(shopify_curr, cur_start, cur_end))
        prev_mtd = (_mtd_from_new_returning(shopify_prev, prev_start, prev_end) or
                    _mtd_from_total_sales(shopify_prev, prev_start, prev_end))
 
        if cur_mtd and prev_mtd:
            curr_rev, curr_ord, curr_aov = cur_mtd
            prev_rev, prev_ord, prev_aov = prev_mtd
        else:
            # Fallback to customer-mix totals
            curr_rev = shopify_curr.get('total_revenue', 0)
            prev_rev = shopify_prev.get('total_revenue', 0)
            curr_ord = shopify_curr.get('total_orders', 0)
            prev_ord = shopify_prev.get('total_orders', 0)
            curr_aov = shopify_curr.get('aov', 0)
            prev_aov = shopify_prev.get('aov', 0)
 
        table += (f"| Total Revenue | ${curr_rev:,.0f} | ${prev_rev:,.0f} | {get_yoy_change(curr_rev, prev_rev)} |\n")
        table += (f"| Total Orders | {curr_ord:,} | {prev_ord:,} | {get_yoy_change(curr_ord, prev_ord)} |\n")
        table += (f"| Average Order Value | ${curr_aov:,.2f} | ${prev_aov:,.2f} | {get_yoy_change(curr_aov, prev_aov)} |\n")
 
        # Sessions and paid revenue share (MTD) from precomputed totals if available
        def _totals_from_metrics(metrics: Dict) -> tuple[int, float]:
            t = metrics.get('totals', {}) if isinstance(metrics, dict) else {}
            sessions = t.get('sessions', 0)
            paid_rev = t.get('paid_revenue', 0)
            return sessions, paid_rev
 
        curr_sessions, curr_paid_rev = _totals_from_metrics(ga4_curr)
        prev_sessions, prev_paid_rev = _totals_from_metrics(ga4_prev)
 
        curr_cvr = (curr_ord / curr_sessions * 100) if curr_sessions else 0
        prev_cvr = (prev_ord / prev_sessions * 100) if prev_sessions else 0
        curr_paid_pct = (curr_paid_rev / curr_rev * 100) if curr_rev else 0
        prev_paid_pct = (prev_paid_rev / prev_rev * 100) if prev_rev else 0
 
        table += (f"| Conversion Rate | {curr_cvr:.2f}% | {prev_cvr:.2f}% | {get_yoy_change(curr_cvr, prev_cvr)} |\n")
        table += (f"| Paid Revenue % of Total | {curr_paid_pct:.0f}% | {prev_paid_pct:.0f}% | {get_yoy_change(curr_paid_pct, prev_paid_pct)} |\n")
        table += (f"| Website Traffic (All) | {curr_sessions:,} | {prev_sessions:,} | {get_yoy_change(curr_sessions, prev_sessions)} |\n")
        return table + "---\n"

    def _generate_monthly_trends_table(self) -> str:
        """Return last four available months with Spend/ROAS/CAC/New-User%/Revenue."""

        table_header = "## Monthly Trends"
 
        if 'northbeam' not in self.ga4_data_current:
            return f"{table_header}\n⚠️ Northbeam spend data not available.\n---\n"
 
        nb = self.ga4_data_current['northbeam'].copy()
        if nb.empty or 'date' not in nb.columns:
            return f"{table_header}\n⚠️ Northbeam data missing 'date' column.\n---\n"
 
        # Normalize numeric fields
        for col in ['spend', 'attributed_rev', 'transactions',
                    'attributed_rev_1st_time']:
            if col in nb.columns:
                nb[col] = pd.to_numeric(nb[col], errors='coerce').fillna(0)
 
        # Use only accrual-performance rows to avoid duplicate zero-value
        # cash snapshots
        if 'accounting_mode' in nb.columns:
            nb = nb[nb['accounting_mode'].str.contains('Accrual', case=False,
                                                      na=False)]
 
        # Keep rows with a positive spend value
        nb = nb[nb['spend'] > 0]
 
        nb['Month'] = nb['date'].dt.to_period('M')
 
        # Determine last four distinct months present in data
        month_values = sorted(nb['Month'].unique())
        if not month_values:
            return f"{table_header}\n⚠️ No monthly rows found in Northbeam dataset.\n---\n"
        last_four = month_values[-4:]
        sub_df = nb[nb['Month'].isin(last_four)]
        if sub_df.empty:
            return f"{table_header}\n⚠️ No recent monthly rows found in Northbeam dataset.\n---\n"
 
        # Human-friendly header, e.g., (May–Aug)
        months_fmt = [str(m) for m in last_four]
        table = f"{table_header} ({months_fmt[0]}–{months_fmt[-1]})\n"
 
        spend_df = sub_df.groupby('Month').agg({
            'spend': 'sum',
            'attributed_rev_1st_time': 'sum',
            'transactions': 'sum',
            'attributed_rev': 'sum',
        }).reset_index()

        # --------------------------------------------
        # Shopify revenue by month (total business)
        # --------------------------------------------
        rev_month_df = None
        if 'total_sales' in self.shopify_data_current:
            ts = self.shopify_data_current['total_sales'].copy()
            if 'Day' in ts.columns:
                ts['Day'] = pd.to_datetime(ts['Day'], errors='coerce')
                ts = ts.dropna(subset=['Day'])
                # Clip to report end date so current month reflects MTD
                end_dt = self.mtd_date_range_current['end_dt']
                ts = ts[ts['Day'] <= end_dt]
                ts['Month'] = ts['Day'].dt.to_period('M')
                rev_month_df = ts.groupby('Month').agg({'Total sales': 'sum'}).reset_index()
            elif 'Month' in ts.columns:
                # Normalize to month Periods and drop months after report end month
                ts['_m'] = pd.to_datetime(ts['Month'], errors='coerce').dt.to_period('M')
                end_month = pd.Timestamp(self.mtd_date_range_current['end_dt']).to_period('M')
                ts = ts[ts['_m'] <= end_month]
                rev_month_df = (ts.groupby('_m').agg({'Total sales': 'sum'})
                               .reset_index().rename(columns={'_m': 'Month'}))

        # Merge spend with revenue
        agg = (spend_df.merge(rev_month_df, on='Month', how='left')
               if rev_month_df is not None else spend_df)

        # Ensure revenue column exists even if Shopify total-sales wasn't loaded
        if 'Total sales' not in agg.columns:
            agg['Total sales'] = 0

        # Fill NaNs
        agg['Total sales'] = agg['Total sales'].fillna(0)

        # Derived metrics
        agg['new_customer_percentage'] = agg.apply(
            lambda r: (r['attributed_rev_1st_time'] / r['attributed_rev'] * 100
                      if r['attributed_rev'] else 0), axis=1)
        agg['ROAS'] = agg.apply(
            lambda r: r['Total sales'] / r['spend'] if r['spend'] else 0, axis=1)
        agg['CAC'] = agg.apply(
            lambda r: r['spend'] / r['transactions'] if r['transactions'] else 0,
            axis=1)
        # Rename for clarity
        agg.rename(columns={'Total sales': 'revenue'}, inplace=True)

        # Build markdown table
        # Ensure we include all target months even if no spend rows exist
        month_index = pd.period_range(start=last_four[0], end=last_four[-1], freq='M')
        scaffold = pd.DataFrame({'Month': month_index})
        agg = scaffold.merge(agg, on='Month', how='left').fillna(0)

        table += "| Month | Spend | ROAS | CAC | New User % | Revenue |\n"
        table += "|-------|-------|------|-----|------------|---------|\n"

        for _, row in agg.iterrows():
            # row['Month'] is a Period[M]; format as abbreviated month name
            m_name = row['Month'].strftime('%b') if hasattr(row['Month'], 'strftime') else str(row['Month'])
            table += (
                f"| {m_name} | ${row['spend']:,.0f} | {row['ROAS']:.2f} | ${row['CAC']:,.0f} "
                f"| {row['new_customer_percentage']:.0f}% | ${row['revenue']:,.0f} |\n"
            )

        # Apr–Jul total row
        tot_spend = agg['spend'].sum()
        tot_rev = agg['revenue'].sum()
        tot_txn = agg['transactions'].sum()
        tot_roas = tot_rev / tot_spend if tot_spend else 0
        tot_cac = tot_spend / tot_txn if tot_txn else 0
        tot_new_pct = ((agg['attributed_rev_1st_time'].sum() /
                       agg['attributed_rev'].sum() * 100)
                      if agg['attributed_rev'].sum() else 0)

        table += (
            f"| **Total** | **${tot_spend:,.0f}** | **{tot_roas:.2f}** | **${tot_cac:,.0f}** "
            f"| **{tot_new_pct:.0f}%** | **${tot_rev:,.0f}** |\n"
        )
        return table + "---\n"

    def _generate_customer_mix_table(self, shopify_curr: Dict) -> str:
        table = "## Customer Mix (New vs. Returning)\n"
        if 'customer_mix' not in shopify_curr:
            return table + "⚠️ Customer mix data not available.\n---\n"

        cm = shopify_curr['customer_mix']

        new_rev = cm['new_revenue']
        new_ord = cm['new_orders']
        ret_rev = cm['returning_revenue']
        ret_ord = cm['returning_orders']
        total_rev = cm['total_revenue']
        total_ord = cm['total_orders']

        new_aov = new_rev / new_ord if new_ord else 0
        ret_aov = ret_rev / ret_ord if ret_ord else 0
        total_aov = total_rev / total_ord if total_ord else 0

        new_pct = (new_rev / total_rev) * 100 if total_rev else 0
        ret_pct = 100 - new_pct

        table += "| Segment | Revenue | Orders | AOV | % of Total Revenue |\n"
        table += "|-----------------------|---------|--------|-----|-------------------|\n"
        table += (f"| New-to-Brand Users | ${new_rev:,.0f} | {new_ord:,} | "
                  f"${new_aov:,.0f} | {new_pct:.1f}% |\n")
        table += (f"| Returning Customers | ${ret_rev:,.0f} | {ret_ord:,} | "
                  f"${ret_aov:,.0f} | {ret_pct:.1f}% |\n")
        table += (f"| **Total** | ${total_rev:,.0f} | {total_ord:,} | "
                  f"${total_aov:,.0f} | **100%** |\n\n")

        insight = (
            f"**Insight:**  \n> New customers generated {new_pct:.0f}% of revenue with an AOV"
            f" ${new_aov:,.0f} vs ${ret_aov:,.0f} for returning buyers."
        )

        return table + "\n" + insight + "\n\n---\n"

    def _generate_channel_performance_table(self, ga4_curr: Dict, ga4_prev: Dict) -> str:
        table = "## Channel Performance (Cash Reporting)\n"
 
        desired_channels = [
            "Google Ads",
            "Paid Social",
            "AppLovin",
            "Bing Ads",
            "Pinterest Ads",
            "TikTok Ads",
            "Awin (Paid Affiliate)",
            "ShopMyShelf (Influencer)",
        ]
 
        nb = self.ga4_data_current.get('northbeam')
        if nb is None or nb.empty:
            table += "| Channel | Spend | Revenue | ROAS |\n"
            table += "|---|---|---|---|\n"
            for ch in desired_channels:
                table += f"| {ch} | $0 | $0 | 0.00 |\n"
            return table + "---\n"
 
        # Restrict to MTD
        df = nb.copy()
        if 'date' in df.columns:
            m = (df['date'] >= self.mtd_date_range_current['start_dt']) & (df['date'] <= self.mtd_date_range_current['end_dt'])
            df = df[m]
        # Filter to Cash rows only if accounting_mode exists
        if 'accounting_mode' in df.columns:
            df = df[df['accounting_mode'].str.contains('Cash', case=False, na=False)]
        # Numeric normalization
        for c in ['spend','attributed_rev']:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
 
        # Choose platform column
        platform_col = 'breakdown_platform_northbeam' if 'breakdown_platform_northbeam' in df.columns else (
            'platform' if 'platform' in df.columns else None
        )
        if platform_col is None:
            table += "| Channel | Spend | Revenue | ROAS |\n"
            table += "|---|---|---|---|\n"
            for ch in desired_channels:
                table += f"| {ch} | $0 | $0 | 0.00 |\n"
            return table + "---\n"
 
        def _plat_to_channel(v: Any) -> Optional[str]:
            s = str(v).lower()
            if 'google' in s:
                return 'Google Ads'
            if 'bing' in s or 'microsoft' in s:
                return 'Bing Ads'
            if 'meta' in s or 'facebook' in s or 'instagram' in s:
                return 'Paid Social'
            if 'tiktok' in s:
                return 'TikTok Ads'
            if 'pinterest' in s:
                return 'Pinterest Ads'
            if 'applovin' in s:
                return 'AppLovin'
            if 'awin' in s:
                return 'Awin (Paid Affiliate)'
            if 'shopmy' in s or 'shopmyshelf' in s or 'shop my shelf' in s:
                return 'ShopMyShelf (Influencer)'
            return None
 
        df['__channel__'] = df[platform_col].apply(_plat_to_channel)
        # Detect revenue column if normalization missed it
        revenue_col = None
        for cand in ['rev', 'revenue', 'attributed_rev', 'attributed_revenue']:
            if cand in df.columns:
                revenue_col = cand
                break
        if revenue_col and revenue_col != 'attributed_rev':
            # Coalesce into 'attributed_rev' without losing existing values
            if 'attributed_rev' in df.columns:
                df['attributed_rev'] = pd.to_numeric(df['attributed_rev'], errors='coerce').fillna(0)
                df['__rev_cash__'] = pd.to_numeric(df[revenue_col], errors='coerce').fillna(0)
                df['attributed_rev'] = df['attributed_rev'].where(df['attributed_rev'] != 0, df['__rev_cash__'])
                df = df.drop(columns=['__rev_cash__'])
            else:
                df = df.rename(columns={revenue_col: 'attributed_rev'})
 
        grouped_cash = (df.dropna(subset=['__channel__'])
                          .groupby('__channel__')
                          .agg({'spend':'sum','attributed_rev':'sum'}) if 'attributed_rev' in df.columns else
                        (df.dropna(subset=['__channel__'])
                           .groupby('__channel__')
                           .agg({'spend':'sum'})))
 
        # If cash revenue is entirely zero but spend exists, fallback to Accrual revenue for readability
        total_spend_cash = float(grouped_cash['spend'].sum()) if 'spend' in grouped_cash.columns else 0.0
        total_rev_cash = float(grouped_cash['attributed_rev'].sum()) if 'attributed_rev' in grouped_cash.columns else 0.0
        grouped = grouped_cash.copy()
        if total_spend_cash > 0 and (('attributed_rev' not in grouped_cash.columns) or total_rev_cash == 0.0):
            acc = nb.copy()
            if 'date' in acc.columns:
                m2 = (acc['date'] >= self.mtd_date_range_current['start_dt']) & (acc['date'] <= self.mtd_date_range_current['end_dt'])
                acc = acc[m2]
            if 'accounting_mode' in acc.columns:
                acc = acc[acc['accounting_mode'].str.contains('Accrual', case=False, na=False)]
            # Revenue normalization
            rev_col2 = None
            for c in ['rev','revenue','attributed_rev','attributed_revenue']:
                if c in acc.columns:
                    rev_col2 = c; break
            if rev_col2 is not None:
                acc['__channel__'] = acc[platform_col].apply(_plat_to_channel)
                grouped_rev = (acc.dropna(subset=['__channel__'])
                                 .groupby('__channel__')
                                 .agg({rev_col2:'sum'}))
                # Join with suffix to avoid overlapping column names, then combine
                grouped = grouped.join(grouped_rev.rename(columns={rev_col2: 'attributed_rev_acc'}), how='left')
                if 'attributed_rev' in grouped.columns:
                    grouped['attributed_rev'] = grouped['attributed_rev'].where(grouped['attributed_rev'] != 0, grouped['attributed_rev_acc']).fillna(0)
                else:
                    grouped = grouped.rename(columns={'attributed_rev_acc': 'attributed_rev'})
                if 'attributed_rev_acc' in grouped.columns:
                    grouped = grouped.drop(columns=['attributed_rev_acc'])

        # Build table (MER = Revenue / Spend)
        table += "| Channel | Spend | Revenue | MER |\n"
        table += "|---|---|---|---|\n"
        for ch in desired_channels:
            row = grouped.loc[ch] if ch in grouped.index else None
            spend = float(row['spend']) if row is not None and 'spend' in row else 0.0
            rev = float(row['attributed_rev']) if row is not None and 'attributed_rev' in row else 0.0
            mer = (rev / spend) if spend else 0.0
            table += f"| {ch} | ${spend:,.0f} | ${rev:,.0f} | {mer:.2f} |\n"
        return table + "---\n"

    def _generate_product_performance_table(self, shopify_curr: Dict, shopify_prev: Dict | None = None) -> str:
        table = "## Performance By Product\n"
        if 'product_performance' not in shopify_curr:
            return table + "⚠️ Product performance data not available.\n---\n"

        df_cur = shopify_curr['product_performance']
        df_prev = None
        if shopify_prev and 'product_performance' in shopify_prev:
            df_prev = shopify_prev['product_performance']

        # Detect availability of NTB columns
        has_new_cols_cur = {'New customers', 'Returning customers'}.issubset(df_cur.columns)
        has_new_cols_prev = bool(df_prev is not None and {'New customers', 'Returning customers'}.issubset(df_prev.columns))

        # Prepare previous lookups for quick matching
        prev_lookup = {}
        if df_prev is not None:
            for product, row in df_prev.iterrows():
                prev_lookup[product] = {
                    'rev': float(row.get('Total sales', 0) or 0),
                    'new': float(row.get('New customers', 0) or 0),
                    'ret': float(row.get('Returning customers', 0) or 0),
                }

        # Build header with YoY columns
        cur_year = self.mtd_date_range_current.get('year')
        prev_year = self.mtd_date_range_previous.get('year')
        ntb_label = f"New-to-Brand % ({cur_year})" if cur_year else "New-to-Brand %"
        table += (
            f"| Product Name | {cur_year} Revenue | {prev_year} Revenue | Rev Δ % | {ntb_label} | YoY NTB Δ |\n"
        )
        table += "|--------------|----------------|----------------|---------|--------------------|-----------|\n"
 
        for product, row in df_cur.iterrows():
            cur_rev = float(row.get('Total sales', 0) or 0)
            if has_new_cols_cur:
                cur_new = float(row.get('New customers', 0) or 0)
                cur_ret = float(row.get('Returning customers', 0) or 0)
                cur_pct = cur_new / (cur_new + cur_ret) * 100 if (cur_new + cur_ret) else 0
                cur_pct_str = f"{cur_pct:.0f}%"
            else:
                cur_new = cur_ret = 0.0
                cur_pct = None
                cur_pct_str = "N/A"
 
            # Previous-period values for this product
            prev_data = prev_lookup.get(product, None)
            prev_rev = float(prev_data['rev']) if prev_data else 0.0
            if prev_data:
                rev_delta_pct_str = get_yoy_change(cur_rev, prev_rev)
                if has_new_cols_prev and (prev_data['new'] + prev_data['ret']) > 0 and cur_pct is not None:
                    prev_pct = prev_data['new'] / (prev_data['new'] + prev_data['ret']) * 100
                    ntb_delta = cur_pct - prev_pct
                    ntb_delta_str = f"{ntb_delta:+.0f}%"
                else:
                    ntb_delta_str = "N/A"
            else:
                rev_delta_pct_str = get_yoy_change(cur_rev, 0)
                ntb_delta_str = "N/A"
 
            table += f"| {product} | ${cur_rev:,.0f} | ${prev_rev:,.0f} | {rev_delta_pct_str} | {cur_pct_str} | {ntb_delta_str} |\n"
 
        # Append row for remaining products if available
        other_cur = shopify_curr.get('product_other')
        other_prev = shopify_prev.get('product_other') if shopify_prev else None
        if other_cur:
            other_rev = float(other_cur.get('Total sales', 0) or 0)
            if 'New customers' in other_cur and 'Returning customers' in other_cur:
                cur_other_new = float(other_cur.get('New customers', 0) or 0)
                cur_other_ret = float(other_cur.get('Returning customers', 0) or 0)
                pct_other = cur_other_new / (cur_other_new + cur_other_ret) * 100 if (cur_other_new + cur_other_ret) else 0
                pct_other_str = f"{pct_other:.0f}%"
            else:
                pct_other = None
                pct_other_str = "N/A"
 
            prev_other_rev = 0.0
            rev_delta_other_pct_str = get_yoy_change(other_rev, 0)
            ntb_delta_other_str = "N/A"
            if other_prev:
                prev_other_rev = float(other_prev.get('Total sales', 0) or 0)
                rev_delta_other_pct_str = get_yoy_change(other_rev, prev_other_rev)
                if 'New customers' in other_prev and 'Returning customers' in other_prev and pct_other is not None:
                    prev_on = float(other_prev.get('New customers', 0) or 0)
                    prev_or = float(other_prev.get('Returning customers', 0) or 0)
                    if (prev_on + prev_or) > 0:
                        prev_pct_other = prev_on / (prev_on + prev_or) * 100
                        ntb_delta_other = pct_other - prev_pct_other
                        ntb_delta_other_str = f"{ntb_delta_other:+.0f}%"
 
            table += (
                f"| **All Other Products** | **${other_rev:,.0f}** | **${prev_other_rev:,.0f}** | **{rev_delta_other_pct_str}** | **{pct_other_str}** | **{ntb_delta_other_str}** |\n"
            )

        return table + "---\n"

    def save_report(self, report_content: str) -> str:
        """Save the report to a file"""
        report_date_str = datetime.now().strftime("%Y-%m-%d")

        # Create filename
        filename = f"automated-performance-report-{report_date_str}.md"
        filepath = self.reports_dir / filename

        # Save report
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report_content)

        print(f"✅ Report saved to: {filepath}")
        return str(filepath)

    def run(self):
        """Main execution flow for automated report generation."""
        print("🚀 HigherDOSE Automated Performance Report Generator")
        print("=" * 50)

        # Step 1: Set date ranges automatically
        self._set_date_ranges()

        # Step 2: Find files for both years
        selected_files = self._find_and_select_files()

        # Step 3: Load data for both periods
        print("\n=== LOADING CURRENT YEAR DATA ===")
        self.ga4_data_current, self.shopify_data_current = self.load_data_for_period(selected_files.get('current', {}), self.mtd_date_range_current)
        print("\n=== LOADING PREVIOUS YEAR DATA ===")
        self.ga4_data_previous, self.shopify_data_previous = self.load_data_for_period(selected_files.get('previous', {}), self.mtd_date_range_previous)

        # Step 4: Check for missing data
        self._report_missing_data()

        # Step 5: Calculate metrics for both periods
        print("\n=== CALCULATING METRICS ===")
        metrics_current = {
            'ga4': self.calculate_ga4_metrics(self.ga4_data_current),
            'shopify': self.calculate_shopify_metrics(self.shopify_data_current, self.mtd_date_range_current)
        }
        metrics_previous = {
            'ga4': self.calculate_ga4_metrics(self.ga4_data_previous),
            'shopify': self.calculate_shopify_metrics(self.shopify_data_previous, self.mtd_date_range_previous)
        }

        # Step 6: Generate report
        print("\n=== GENERATING REPORT ===")
        report_content = self.generate_report(metrics_current, metrics_previous)

        # Step 7: Save report
        filepath = self.save_report(report_content)

        print("\n🎉 Report generation complete!")
        print(f"📄 Report available at: {filepath}")

        # Ask if user wants to open the report, but only in interactive mode
        try:
            if sys.stdout.isatty():
                open_report = input("\n📖 Open the report now? (y/n): ").strip().lower()
                if open_report in ['y', 'yes']:
                    os.system(f"open '{filepath}'")
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Goodbye!")

def main():
    """CLI entry-point."""

    parser = argparse.ArgumentParser(description="HigherDOSE automated performance report generator")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--mtd", action="store_true", help="Generate report for current Month-To-Date (default if no dates provided)")
    group.add_argument("--month", help="Generate report for an entire month (YYYY-MM)")
    group.add_argument("--start", help="Start date (YYYY-MM-DD)")

    # --end is only valid if --start is provided
    parser.add_argument("--end", help="End date (YYYY-MM-DD) (use with --start)")
    parser.add_argument("--output-dir", "-o", help="Directory to save the report (e.g., executive)")
    parser.add_argument("--choose-files", action="store_true",
                        help="Interactively choose each data file instead of "
                             "auto-selecting latest")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Force interactive prompts even in non-TTY "
                             "environments")

    args = parser.parse_args()

    # Resolve date overrides
    start, end = None, None
    # ------------------------------------------------------------------
    # If the user didn't specify any date flags, fall back to an interactive
    # prompt *regardless* of whether stdin is a TTY. This mirrors the behaviour
    # of report_weekly.py and removes the need for the -i flag.
    # ------------------------------------------------------------------

    if not (args.mtd or args.month or args.start):
        print("\nChoose reporting period:")
        options = PRESET_RANGES.copy()
        options["5"] = ("Custom Range", None)
 
 
        print("Choose reporting period:")
        for key, (label, _) in options.items():
            print(f"{key}) {label}")

        choice = input("Select option [1-5] (default 1): ").strip() or "1"
        if choice not in options:
            choice = "1"

        if choice == "5":
            # Custom
            start = input("Start date (YYYY-MM-DD): ").strip()
            end   = input("End date   (YYYY-MM-DD): ").strip()
            args.start = start
            args.end = end
        else:
            today = datetime.today().date()
            start_dt, end_dt = options[choice][1](today)
            start = start_dt.strftime("%Y-%m-%d")
            end   = end_dt.strftime("%Y-%m-%d")
            # Pretend user provided explicit dates so later validation passes
            args.start = start
            args.end = end

    # ------------------------------------------------------------------
    # Non-interactive resolution of other flags
    # ------------------------------------------------------------------

    if args.mtd and not (args.month or args.start):
        # MTD – leave start/end as None so generator uses default Month-to-Date range
        pass
    elif args.month:
        # Compute first/last day of the requested month
        month_dt = datetime.strptime(args.month + "-01", "%Y-%m-%d")
        next_month = (month_dt.replace(day=28) + timedelta(days=4)).replace(day=1)  # first day of following month
        end_dt = next_month - timedelta(days=1)
        start = month_dt.strftime("%Y-%m-%d")
        end = end_dt.strftime("%Y-%m-%d")
    elif args.start:
        start = args.start
        end = args.end
    else:
        parser.error("Provide either --mtd, --month YYYY-MM, or --start YYYY-MM-DD [--end YYYY-MM-DD]")

    try:
        generator = MTDReportGenerator(start_date=start, end_date=end,
                                  output_dir=args.output_dir,
                                  choose_files=args.choose_files,
                                  interactive=args.interactive)
        generator.run()
    except KeyboardInterrupt:
        print("\n\n👋 Report generation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
