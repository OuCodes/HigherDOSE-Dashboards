#!/usr/bin/env python3
"""Northbeam CLI entrypoints.

Provides console-script compatible main() functions that delegate to
`NorthbeamClient` and related helpers. Mirrors previous script behavior.
"""

from __future__ import annotations

import argparse
import csv
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .client import NorthbeamClient
from .config import load_auth


def _require_creds() -> None:
    auth = load_auth()
    errs = []
    if not auth.api_key:
        errs.append("NB_API_KEY not set")
    if not auth.account_id:
        errs.append("NB_ACCOUNT_ID not set")
    if errs:
        raise SystemExit("; ".join(errs) + " (set in config/northbeam/.env or environment)")


def export_main() -> None:
    """Create a Northbeam export and download CSV to the specified path."""
    p = argparse.ArgumentParser(description="Northbeam export CLI")
    p.add_argument("--start", required=True, help="Start date (YYYY-MM-DD)")
    p.add_argument("--end", required=True, help="End date (YYYY-MM-DD)")
    p.add_argument("--mode", default="accrual", choices=["accrual", "cash"], help="Accounting mode")
    p.add_argument("--model", default=None, help="Attribution model (e.g., last_click, 1dc, data_driven)")
    p.add_argument("--window", default=None, help="Attribution window (e.g., 1d, 7d, 30d)")
    p.add_argument("--out", default=str(Path("data/ads") / "nb_export.csv"), help="Output CSV path")
    p.add_argument("--metrics", default=None, help="Comma-separated metrics to include")
    p.add_argument("--breakdowns", default=None, help="Comma-separated breakdowns to include")
    args = p.parse_args()

    # Validate dates
    try:
        start = datetime.strptime(args.start, "%Y-%m-%d").date()
        end = datetime.strptime(args.end, "%Y-%m-%d").date()
    except ValueError:
        raise SystemExit("Invalid --start/--end date format; use YYYY-MM-DD")
    if start > end:
        raise SystemExit("--start must be <= --end")

    _require_creds()

    client = NorthbeamClient()
    metrics = [m.strip() for m in args.metrics.split(",")] if args.metrics else None
    breakdowns = [b.strip() for b in args.breakdowns.split(",")] if args.breakdowns else None

    print("Creating export…")
    export_id = client.create_export(
        start_date=str(start),
        end_date=str(end),
        accounting_mode=args.mode,
        attribution_model=args.model,
        attribution_window=args.window,
        metrics=metrics,
        breakdowns=breakdowns,
    )
    print("Export created:", export_id)
    print("Waiting for export to be ready…")
    res = client.wait_for_export(export_id)
    print("Export status:", res.status)
    if not res.location:
        raise SystemExit(f"No download location provided in result: {res.payload}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print("Downloading CSV to:", out_path)
    urllib.request.urlretrieve(res.location, out_path)
    print("Done.")


def export_all_metrics_main() -> None:
    """Export all available metric ids, chunking if necessary."""
    p = argparse.ArgumentParser(description="Northbeam export all metrics")
    p.add_argument("--start", default=None, help="Start date (YYYY-MM-DD), default: Jan 1 current year")
    p.add_argument("--end", default=None, help="End date (YYYY-MM-DD), default: today")
    p.add_argument("--model", default="northbeam_custom", help="Attribution model id")
    p.add_argument("--mode", default="accrual", choices=["accrual", "cash"], help="Accounting mode")
    p.add_argument("--window", default="1", help="Attribution window (string)")
    p.add_argument("--batch", type=int, default=200, help="Batch size if chunking is required")
    p.add_argument("--out-dir", default=str(Path("data/ads")), help="Output directory")
    args = p.parse_args()

    _require_creds()
    c = NorthbeamClient()

    # Dates
    if args.start and args.end:
        start = args.start
        end = args.end
    else:
        today = date.today()
        start = f"{today.year}-01-01"
        end = str(today)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    base_name = out_dir / f"all_metrics-{start}_{end}"

    metrics_meta = c.list_metrics()
    metric_ids = [m.get("id") for m in metrics_meta if m.get("id")]
    if not metric_ids:
        raise SystemExit("No metrics returned by API")
    print(f"Found {len(metric_ids)} metrics. Attempting single export…")

    def do_export(ids: list[str], idx_suffix: str = "") -> None:
        print(f"Creating export with {len(ids)} metrics {idx_suffix}…")
        export_id = c.create_export(
            start_date=start,
            end_date=end,
            accounting_mode=args.mode,
            attribution_model=args.model,
            attribution_window=str(args.window),
            metrics=ids,
        )
        print("Export ID:", export_id)
        res = c.wait_for_export(export_id, interval=1.0, timeout=600.0)
        print("Status:", res.status)
        if not res.location:
            raise SystemExit("No export location returned")
        outfile = Path(f"{base_name}{idx_suffix}.csv")
        urllib.request.urlretrieve(res.location, outfile)
        print("Saved:", outfile)

    try:
        do_export(metric_ids, idx_suffix="")
        return
    except Exception as e:  # pragma: no cover - best-effort chunking
        print(f"Single export failed, will chunk: {e}")

    b = max(10, int(args.batch))
    for i in range(0, len(metric_ids), b):
        chunk = metric_ids[i : i + b]
        do_export(chunk, idx_suffix=f"-b{i//b}")


def sync_ytd_main() -> None:
    """Incremental YTD sync (daily stitching) or full-period export."""
    p = argparse.ArgumentParser(description="Northbeam YTD Sync - Full Metrics")
    p.add_argument("--mode", default="accrual", choices=["accrual", "cash"], help="Accounting mode")
    p.add_argument("--model", default="northbeam_custom", help="Attribution model id (e.g., northbeam_custom)")
    p.add_argument("--window", default="1", help="Attribution window (e.g., 1, 3, 7, 30)")
    p.add_argument("--full", action="store_true", help="Export the entire period in a single CSV (disables daily/resume mode)")
    p.add_argument("--new", action="store_true", help="Start fresh – ignore/resume no previous CSV and create a new file")
    p.add_argument("--start", help="Start date (YYYY-MM-DD); default is Jan 1 current year")
    p.add_argument("--end", help="End date (YYYY-MM-DD); default is yesterday (UTC)")
    p.add_argument("--out-dir", default=str(Path("data/ads")), help="Output directory for CSV")
    args = p.parse_args()

    _require_creds()

    ads_dir = Path(args.out_dir)
    ads_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    end_day = now.date() - timedelta(days=1)
    if args.start and args.end:
        try:
            start_day = datetime.strptime(args.start, "%Y-%m-%d").date()
            end_day = datetime.strptime(args.end, "%Y-%m-%d").date()
        except ValueError:
            raise SystemExit("Invalid --start/--end date format; use YYYY-MM-DD")
        if start_day > end_day:
            raise SystemExit("--start must be <= --end")
    else:
        start_day = date(end_day.year, 1, 1)

    start = str(start_day)
    end = str(end_day)
    timestamp = now.strftime("%Y_%m_%d_%H_%M_%S")
    pattern = ads_dir.glob("new_ytd_sales_data-higher_dose_llc-*.csv")
    latest_files = sorted(pattern, key=lambda p: p.stat().st_mtime, reverse=True)

    resume_mode = False
    if not args.new and latest_files:
        target_file = latest_files[0]
        resume_mode = True
    else:
        target_file = ads_dir / f"new_ytd_sales_data-higher_dose_llc-{timestamp}.csv"

    client = NorthbeamClient()
    metrics_meta = client.list_metrics()
    all_metrics = [m.get("id") for m in metrics_meta if m.get("id")]
    if not all_metrics:
        raise SystemExit("No metrics returned by API")

    if not args.full:
        print(
            f"Exporting DAILY metrics with date column: {start} → {end} | mode={args.mode} model={args.model} window={args.window} metrics={len(all_metrics)} ids"
        )
        # Determine Platform breakdown values
        platform_values: list[str] = []
        try:
            for bd in client.list_breakdowns():
                if bd.get("key") == "Platform (Northbeam)":
                    platform_values = [v for v in bd.get("values", []) if v]
                    break
        except Exception:
            platform_values = []
        breakdowns = (
            [{"key": "Platform (Northbeam)", "values": platform_values}] if platform_values else None
        )

        # Stitch per-day exports into a single CSV and insert leading 'date' column
        existing_dates: set[str] = set()
        file_has_header = False
        if target_file.exists():
            try:
                with target_file.open("r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    head = next(reader, None)
                    platform_col_present = False
                    if head:
                        for h in head:
                            if h and h.strip().lower() == "breakdown_platform_northbeam":
                                platform_col_present = True
                                break
                    if head and head and head[0].strip().lower() == "date" and platform_col_present:
                        file_has_header = True
                        for row in reader:
                            if row and row[0]:
                                existing_dates.add(row[0])
            except Exception:
                file_has_header = False

        resume_from: date | None = None
        if not (args.start and args.end) and file_has_header and existing_dates:
            try:
                max_date_str = max(existing_dates)
                resume_from = datetime.strptime(max_date_str, "%Y-%m-%d").date() + timedelta(days=1)
            except Exception:
                resume_from = None

        write_mode = "a" if file_has_header else "w"
        cur = start_day if (args.start and args.end) else (resume_from or start_day)
        with target_file.open(write_mode, newline="", encoding="utf-8") as out_f:
            writer = csv.writer(out_f)
            first_chunk = True
            if write_mode == "w":
                writer.writerow(["date"])  # placeholder
            while cur <= end_day:
                start_str = cur.isoformat()
                end_str = cur.isoformat()
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
                        tmp_path = Path(td) / "d.csv"
                        urllib.request.urlretrieve(res.location, tmp_path)
                        with tmp_path.open("r", encoding="utf-8") as in_f:
                            reader = csv.reader(in_f)
                            head = next(reader, None)
                            if head is None:
                                cur += timedelta(days=1)
                                continue
                            if first_chunk and write_mode == "w":
                                out_f.seek(0)
                                out_f.truncate(0)
                                writer.writerow(["date"] + head)
                                first_chunk = False
                            for row in reader:
                                writer.writerow([start_str] + row)
                    existing_dates.add(start_str)
                except Exception as e:  # pragma: no cover - best-effort loop
                    print(f"⚠️  Failed {start_str}: {e}")
                finally:
                    cur += timedelta(days=1)
        if resume_mode:
            new_target = ads_dir / f"new_ytd_sales_data-higher_dose_llc-{timestamp}.csv"
            if target_file != new_target:
                try:
                    target_file.rename(new_target)
                    target_file = new_target
                except Exception:
                    pass
        print("Saved:", target_file)
        return

    print(
        f"Exporting YTD FULL metrics: {start} → {end} | mode={args.mode} model={args.model} window={args.window} metrics={len(all_metrics)} ids"
    )
    export_id = client.create_export(
        start_date=start,
        end_date=end,
        accounting_mode=args.mode,
        attribution_model=args.model,
        attribution_window=str(args.window),
        metrics=all_metrics,
    )
    print("Export ID:", export_id)
    res = client.wait_for_export(export_id, interval=1.0, timeout=600.0)
    print("Status:", res.status)
    if not res.location:
        raise SystemExit("No export location returned")
    urllib.request.urlretrieve(res.location, target_file)
    print("Saved:", target_file)



