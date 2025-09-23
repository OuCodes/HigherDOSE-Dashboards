#!/usr/bin/env python3
"""
Northbeam - Export All Metrics

- Lists all available metric ids and requests a Data Export including all of them
- Period: FIXED start/end (defaults to YTD)
- Model/Mode/Window: defaults to model=northbeam_custom, mode=accrual, window=1
- If a single export fails due to payload limits, falls back to chunking metrics
  into batches and writes multiple CSV files with an index suffix.

Output:
  data/ads/all_metrics-<start>_<end>-b<idx>.csv (one or many files)

Usage:
  python scripts/northbeam_export_all_metrics.py [--start YYYY-MM-DD --end YYYY-MM-DD] \
      [--model northbeam_custom] [--mode accrual] [--window 1] [--batch 120]
"""

import sys
import argparse
from pathlib import Path
from datetime import date
import urllib.request

# Ensure src is on path
if str(Path('src')) not in sys.path:
	sys.path.append('src')

from growthkit.connectors.northbeam.client import NorthbeamClient

OUT_DIR = Path('data/ads')


def parse_args() -> argparse.Namespace:
	p = argparse.ArgumentParser(description='Northbeam export all metrics')
	p.add_argument('--start', default=None, help='Start date (YYYY-MM-DD), default: Jan 1 current year')
	p.add_argument('--end', default=None, help='End date (YYYY-MM-DD), default: today')
	p.add_argument('--model', default='northbeam_custom', help='Attribution model id')
	p.add_argument('--mode', default='accrual', choices=['accrual','cash'], help='Accounting mode')
	p.add_argument('--window', default='1', help='Attribution window (string)')
	p.add_argument('--batch', type=int, default=200, help='Batch size if chunking is required')
	return p.parse_args()


def export_all(args: argparse.Namespace) -> None:
	c = NorthbeamClient()
	# Dates
	if args.start and args.end:
		start = args.start
		end = args.end
	else:
		today = date.today()
		start = f"{today.year}-01-01"
		end = str(today)

	OUT_DIR.mkdir(parents=True, exist_ok=True)
	base_name = OUT_DIR / f"all_metrics-{start}_{end}"

	# List metrics
	metrics_meta = c.list_metrics()
	metric_ids = [m.get('id') for m in metrics_meta if m.get('id')]
	if not metric_ids:
		raise SystemExit('No metrics returned by API')
	print(f"Found {len(metric_ids)} metrics. Attempting single export...")

	def do_export(ids, idx_suffix: str = ""):
		print(f"Creating export with {len(ids)} metrics {idx_suffix}...")
		export_id = c.create_export(start_date=start, end_date=end,
									  accounting_mode=args.mode,
									  attribution_model=args.model,
									  attribution_window=str(args.window),
									  metrics=ids)
		print('Export ID:', export_id)
		res = c.wait_for_export(export_id, interval=1.0, timeout=600.0)
		print('Status:', res.status)
		if not res.location:
			raise SystemExit('No export location returned')
		outfile = Path(f"{base_name}{idx_suffix}.csv")
		urllib.request.urlretrieve(res.location, outfile)
		print('Saved:', outfile)

	# Try single export first
	try:
		do_export(metric_ids, idx_suffix="")
		return
	except Exception as e:
		print(f"Single export failed, will chunk: {e}")

	# Chunking fallback
	b = max(10, int(args.batch))
	for i in range(0, len(metric_ids), b):
		chunk = metric_ids[i:i+b]
		do_export(chunk, idx_suffix=f"-b{i//b}")


def main() -> None:
	args = parse_args()
	export_all(args)


if __name__ == '__main__':
	main() 