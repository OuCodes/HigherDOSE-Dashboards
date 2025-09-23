#!/usr/bin/env python3
"""
Northbeam YTD Sync (Full metrics or incremental daily updates)

- By default runs in "daily update" mode: fetches one day at a time (Jan 1 → yesterday)
  and appends to a rolling CSV, resuming from the last available date.
  When run in an interactive shell it will prompt you for parameters, showing defaults
  in brackets so you can just press Enter.
- Pass `--full` to request a single export covering the entire period and overwrite the
  CSV in one shot.
- Exports ALL available metric ids using the Data-Export API.

Usage examples
--------------
Daily incremental (default):
  python scripts/northbeam_sync_ytd.py

Single full-period export:
  python scripts/northbeam_sync_ytd.py --full

Optional arguments:
  --mode accrual|cash          Accounting mode (default: accrual)
  --model northbeam_custom     Attribution model id (default: northbeam_custom)
  --window 1                   Attribution window in days (default: 1)
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timezone, date, timedelta
import urllib.request
import csv
import tempfile
import os

# Ensure src is on path
if str(Path('src')) not in sys.path:
	sys.path.append('src')

from growthkit.connectors.northbeam.client import NorthbeamClient

ADS_DIR = Path('data/ads')
# ... existing code ...

def parse_args() -> argparse.Namespace:
	p = argparse.ArgumentParser(description='Northbeam YTD Sync - Full Metrics')
	p.add_argument('--mode', default='accrual', choices=['accrual', 'cash'], help='Accounting mode')
	p.add_argument('--model', default='northbeam_custom', help='Attribution model id (e.g., northbeam_custom)')
	p.add_argument('--window', default='1', help='Attribution window (e.g., 1, 3, 7, 30)')
	# Daily export is now the default; use --full to request a single YTD export
	p.add_argument('--full', action='store_true', help='Export the entire period in a single CSV (disables daily/resume mode)')
	# Start a brand-new YTD file instead of resuming the latest one
	p.add_argument('--new', action='store_true', help='Start fresh – ignore/resume no previous CSV and create a new file')
	p.add_argument('--start', help='Start date (YYYY-MM-DD); default is Jan 1 current year')
	p.add_argument('--end', help='End date (YYYY-MM-DD); default is today (UTC)')
	return p.parse_args()


# ... existing code ...

def main() -> None:
	args = parse_args()

	# Interactive prompts so user can just press Enter to keep defaults
	if sys.stdin.isatty():
		# Helper for prompting with default
		def ask(prompt: str, current: str) -> str:
			try:
				resp = input(f"{prompt} [{current}]: ").strip()
			except EOFError:
				# Non-interactive (piped) execution – fallback to current
				return current
			return resp or current

		args.mode = ask("Accounting mode (accrual/cash)", args.mode)
		args.model = ask("Attribution model id", args.model)
		args.window = ask("Attribution window (days)", str(args.window))

		# Date prompts (keep ISO format)
		now_iso_yday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
		start_default_iso = f"{now_iso_yday[:4]}-01-01"
		args.start = ask("Start date (YYYY-MM-DD)", args.start or start_default_iso)
		args.end = ask("End date (YYYY-MM-DD)", args.end or now_iso_yday)

		full_resp = ask("Full export (single CSV)? y/N", 'Y' if args.full else 'N').lower()
		args.full = full_resp.startswith('y')

		new_resp = ask("Start fresh (ignore existing CSVs)? y/N", 'Y' if args.new else 'N').lower()
		args.new = new_resp.startswith('y')

	ADS_DIR.mkdir(parents=True, exist_ok=True)

	# Default end date is yesterday (UTC) so we always have a complete final day
	now = datetime.now(timezone.utc)
	end_day = now.date() - timedelta(days=1)
	# Resolve date range
	if args.start and args.end:
		try:
			start_day = datetime.strptime(args.start, '%Y-%m-%d').date()
			end_day = datetime.strptime(args.end, '%Y-%m-%d').date()
		except ValueError:
			raise SystemExit('Invalid --start/--end date format; use YYYY-MM-DD')
		if start_day > end_day:
			raise SystemExit('--start must be <= --end')
	else:
		start_day = date(end_day.year, 1, 1)

	start = str(start_day)
	end = str(end_day)
	# Build dynamic filename matching prior format: new_ytd_sales_data-higher_dose_llc-YYYY_MM_DD_HH_MM_SS.csv
	timestamp = now.strftime('%Y_%m_%d_%H_%M_%S')
	# Decide whether to resume or start new
	pattern = ADS_DIR.glob('new_ytd_sales_data-higher_dose_llc-*.csv')
	latest_files = sorted(pattern, key=lambda p: p.stat().st_mtime, reverse=True)

	resume_mode = False
	if not args.new and latest_files:
		target_file = latest_files[0]
		resume_mode = True
	else:
		target_file = ADS_DIR / f'new_ytd_sales_data-higher_dose_llc-{timestamp}.csv'

	client = NorthbeamClient()
	# Fetch all metric ids
	metrics_meta = client.list_metrics()
	all_metrics = [m.get('id') for m in metrics_meta if m.get('id')]
	if not all_metrics:
		raise SystemExit('No metrics returned by API')

	if not args.full:
		print(f"Exporting DAILY metrics with date column: {start} → {end} | mode={args.mode} model={args.model} window={args.window} metrics={len(all_metrics)} ids")
		# Determine Platform breakdown values
		platform_values: list[str] = []
		try:
			for bd in client.list_breakdowns():
				if bd.get('key') == 'Platform (Northbeam)':
					platform_values = [v for v in bd.get('values', []) if v]
					break
		except Exception:
			platform_values = []
		breakdowns = [{"key": "Platform (Northbeam)", "values": platform_values}] if platform_values else None

		# Stitch per-day exports into a single CSV and insert leading 'date' column
		# Determine if file exists with date header AND platform column; if not, rewrite header
		existing_dates: set[str] = set()
		file_has_header = False
		if target_file.exists():
			try:
				with target_file.open('r', encoding='utf-8') as f:
					reader = csv.reader(f)
					head = next(reader, None)
					platform_col_present = False
					if head:
						for h in head:
							if h and h.strip().lower() == 'breakdown_platform_northbeam':
								platform_col_present = True
								break
					if head and head and head[0].strip().lower() == 'date' and platform_col_present:
						file_has_header = True
						for row in reader:
							if row and row[0]:
								existing_dates.add(row[0])
			except Exception:
				file_has_header = False

		# Compute resume_from only if we're continuing forward in time without user-specified range
		resume_from: date | None = None
		if not (args.start and args.end) and file_has_header and existing_dates:
			try:
				max_date_str = max(existing_dates)
				resume_from = datetime.strptime(max_date_str, '%Y-%m-%d').date() + timedelta(days=1)
			except Exception:
				resume_from = None

		# Write mode: append if file already exists with proper header, else write new (overwrite)
		write_mode = 'a' if file_has_header else 'w'
		cur = start_day if (args.start and args.end) else (resume_from or start_day)
		with target_file.open(write_mode, newline='', encoding='utf-8') as out_f:
			writer = csv.writer(out_f)
			# Write placeholder header when creating new file (will be replaced after first chunk)
			first_chunk = True
			if write_mode == 'w':
				writer.writerow(["date"])  # placeholder
			while cur <= end_day:
				start_str = cur.isoformat()
				end_str = cur.isoformat()
				# Skip if date already present
				if start_str in existing_dates:
					cur += timedelta(days=1)
					continue
				try:
					export_id = client.create_export(
						start_date=start_str,
						end_date=end_str,
						accounting_mode=args.mode,
						attribution_model=args.model,
						attribution_window=str(args.window),
						metrics=all_metrics,
						breakdowns=breakdowns,
					)
					res = client.wait_for_export(export_id, interval=1.0, timeout=600.0)
					if not res.location:
						print(f"⚠️  No export location for {start_str}")
						cur += timedelta(days=1)
						continue
					with tempfile.TemporaryDirectory() as td:
						tmp_path = Path(td) / 'd.csv'
						urllib.request.urlretrieve(res.location, tmp_path)
						with tmp_path.open('r', encoding='utf-8') as in_f:
							reader = csv.reader(in_f)
							head = next(reader, None)
							if head is None:
								cur += timedelta(days=1)
								continue
							# Replace placeholder header on first chunk when creating new file
							if first_chunk and write_mode == 'w':
								out_f.seek(0)
								out_f.truncate(0)
								writer.writerow(["date"] + head)
								first_chunk = False
							for row in reader:
								writer.writerow([start_str] + row)
					existing_dates.add(start_str)
				except Exception as e:
					print(f"⚠️  Failed {start_str}: {e}")
				finally:
					cur += timedelta(days=1)
		# If we resumed an old file, rename it to include current timestamp after update
		if resume_mode:
			new_target = ADS_DIR / f'new_ytd_sales_data-higher_dose_llc-{timestamp}.csv'
			if target_file != new_target:
				try:
					target_file.rename(new_target)
					target_file = new_target
				except Exception:
					pass
		print('Saved:', target_file)
		return

	print(f"Exporting YTD FULL metrics: {start} → {end} | mode={args.mode} model={args.model} window={args.window} metrics={len(all_metrics)} ids")
	export_id = client.create_export(
		start_date=start,
		end_date=end,
		accounting_mode=args.mode,
		attribution_model=args.model,
		attribution_window=str(args.window),
		metrics=all_metrics,
	)
	print('Export ID:', export_id)
	res = client.wait_for_export(export_id, interval=1.0, timeout=600.0)
	print('Status:', res.status)
	if not res.location:
		raise SystemExit('No export location returned')

	urllib.request.urlretrieve(res.location, target_file)
	print('Saved:', target_file)


if __name__ == '__main__':
	main() 