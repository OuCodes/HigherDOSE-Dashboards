#!/usr/bin/env python3
"""
Northbeam Export CLI

- Loads API credentials from config/northbeam/.env or environment
- Accepts accounting mode (default: accrual), attribution model/window, date range
- Creates a data export, polls until ready, downloads CSV to output path

Usage:
  python scripts/northbeam_export.py --start 2025-08-14 --end 2025-09-12 \
      --mode accrual --model last_click --window 1d --out data/ads/nb_export.csv
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
import urllib.request

# Ensure src is in path
if str(Path('src')) not in sys.path:
	sys.path.append('src')

from growthkit.connectors.northbeam.config import load_auth
from growthkit.connectors.northbeam.client import NorthbeamClient


def parse_args() -> argparse.Namespace:
	p = argparse.ArgumentParser(description="Northbeam export CLI")
	p.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
	p.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
	p.add_argument("--mode", default="accrual", choices=["accrual", "cash"], help="Accounting mode")
	p.add_argument("--model", default=None, help="Attribution model (e.g., last_click, 1dc, data_driven)")
	p.add_argument("--window", default=None, help="Attribution window (e.g., 1d, 7d, 30d)")
	p.add_argument("--out", default=str(Path("data/ads") / "nb_export.csv"), help="Output CSV path")
	# Optional: allow specifying breakdowns/metrics as comma-separated
	p.add_argument("--metrics", default=None, help="Comma-separated metrics to include")
	p.add_argument("--breakdowns", default=None, help="Comma-separated breakdowns to include")
	return p.parse_args()


def require_creds() -> None:
	auth = load_auth()
	errs = []
	if not auth.api_key:
		errs.append("NB_API_KEY not set")
	if not auth.account_id:
		errs.append("NB_ACCOUNT_ID not set")
	if errs:
		raise SystemExit("; ".join(errs) + " (set in config/northbeam/.env or environment)")


def main() -> None:
	args = parse_args()
	# Validate dates
	try:
		start = datetime.strptime(args.start, "%Y-%m-%d").date()
		end = datetime.strptime(args.end, "%Y-%m-%d").date()
	except ValueError:
		raise SystemExit("Invalid --start/--end date format; use YYYY-MM-DD")
	if start > end:
		raise SystemExit("--start must be <= --end")

	# Validate credentials
	require_creds()

	client = NorthbeamClient()
	metrics = [m.strip() for m in args.metrics.split(",")] if args.metrics else None
	breakdowns = [b.strip() for b in args.breakdowns.split(",")] if args.breakdowns else None

	print("Creating export...")
	export_id = client.create_export(
		start_date=str(start), end_date=str(end), accounting_mode=args.mode,
		attribution_model=args.model, attribution_window=args.window,
		metrics=metrics, breakdowns=breakdowns,
	)
	print(f"Export created: {export_id}")

	print("Waiting for export to be ready...")
	res = client.wait_for_export(export_id)
	print(f"Export status: {res.status}")
	if not res.location:
		raise SystemExit(f"No download location provided in result: {res.payload}")

	out_path = Path(args.out)
	out_path.parent.mkdir(parents=True, exist_ok=True)
	print(f"Downloading CSV to: {out_path}")
	urllib.request.urlretrieve(res.location, out_path)
	print("Done.")


if __name__ == "__main__":
	main() 