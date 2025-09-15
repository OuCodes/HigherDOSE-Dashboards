#!/usr/bin/env python3
"""
Northbeam YTD Sync (Full metrics, overwrite single CSV)

- Exports YTD (from Jan 1 of current year to today) using Data Export API
- Fetches ALL available metric ids and requests them in one export
- Writes to a fixed CSV path (overwrites on each run)

Usage:
  python scripts/northbeam_sync_ytd.py [--mode accrual] [--model northbeam_custom] [--window 1]
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
	p.add_argument('--daily', action='store_true', help='Export one day at a time and include a date column')
	p.add_argument('--start', help='Start date (YYYY-MM-DD); default is Jan 1 current year')
	p.add_argument('--end', help='End date (YYYY-MM-DD); default is today (UTC)')
	return p.parse_args()


# ... existing code ...

def main() -> None:
	args = parse_args()
	ADS_DIR.mkdir(parents=True, exist_ok=True)

	now = datetime.now(timezone.utc)
	end_day = now.date()
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
	date_key = now.strftime('%Y_%m_%d')
	default_target = ADS_DIR / f'new_ytd_sales_data-higher_dose_llc-{timestamp}.csv'
	# Prefer overwriting an existing file for the same day; remove older duplicates
	existing = sorted(ADS_DIR.glob(f'new_ytd_sales_data-higher_dose_llc-{date_key}_*.csv'), key=lambda p: p.stat().st_mtime, reverse=True)
	if existing:
		target_file = existing[0]
		# Clean up older same-day files
		for old in existing[1:]:
			try:
				old.unlink()
			except Exception:
				pass
	else:
		target_file = default_target

	client = NorthbeamClient()
	# Fetch all metric ids
	metrics_meta = client.list_metrics()
	all_metrics = [m.get('id') for m in metrics_meta if m.get('id')]
	if not all_metrics:
		raise SystemExit('No metrics returned by API')

	if args.daily:
		print(f"Exporting DAILY metrics with date column: {start} → {end} | mode={args.mode} model={args.model} window={args.window} metrics={len(all_metrics)} ids")
		# Stitch per-day exports into a single CSV and insert leading 'date' column
		# Determine if file exists with date header and collect existing dates for de-duplication
		existing_dates: set[str] = set()
		file_has_header = False
		if target_file.exists():
			try:
				with target_file.open('r', encoding='utf-8') as f:
					reader = csv.reader(f)
					head = next(reader, None)
					if head and head and head[0].strip().lower() == 'date':
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

		# Write mode: append if file already exists with header, else write new
		write_mode = 'a' if file_has_header else 'w'
		# Start cursor: if user provided start/end, trust that range; otherwise resume from next day
		cur = start_day if (args.start and args.end) else (resume_from or start_day)
		with target_file.open(write_mode, newline='', encoding='utf-8') as out_f:
			writer = csv.writer(out_f)
			# Write header when creating new file
			if write_mode == 'w':
				# Will set real header after first chunk; initialize placeholder
				writer.writerow(["date"])  # placeholder
			first_chunk = True
			while cur <= end_day:
				start_str = cur.isoformat()
				end_str = cur.isoformat()
				# Skip if this date already present (de-dupe)
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
					)
					res = client.wait_for_export(export_id, interval=1.0, timeout=600.0)
					if not res.location:
						print(f"⚠️  No export location for {start_str}")
						cur += timedelta(days=1)
						continue
					# Download to temp and read
					with tempfile.TemporaryDirectory() as td:
						tmp_path = Path(td) / 'd.csv'
						urllib.request.urlretrieve(res.location, tmp_path)
						with tmp_path.open('r', encoding='utf-8') as in_f:
							reader = csv.reader(in_f)
							head = next(reader, None)
							if head is None:
								cur += timedelta(days=1)
								continue
							# Replace placeholder header on first chunk when creating file
							if first_chunk and write_mode == 'w':
								out_f.seek(0)
								out_f.truncate(0)
								writer.writerow(["date"] + head)
								first_chunk = False
							# Append rows with date prefix
							for row in reader:
								writer.writerow([start_str] + row)
						# Track written date to avoid duplicates on subsequent runs
					existing_dates.add(start_str)
				except Exception as e:
					print(f"⚠️  Failed {start_str}: {e}")
				finally:
					cur += timedelta(days=1)
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