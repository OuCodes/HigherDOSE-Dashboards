#!/usr/bin/env python3
"""
Pull Northbeam 2025 YTD data (Jan 1 - Dec 18, 2025)
Matches the October export schema with all metrics and Platform breakdown.
"""

import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from growthkit.connectors.northbeam.client import NorthbeamClient
from growthkit.connectors.northbeam.config import load_auth
import urllib.request


def main():
    print("=" * 80)
    print("NORTHBEAM 2025 YTD EXPORT")
    print("=" * 80)
    print("Date range: 2025-01-01 → 2025-12-18")
    print("Mode: Single API export with DAILY aggregation")
    print("=" * 80)
    
    # Check credentials
    try:
        auth = load_auth()
        if not auth.api_key or not auth.account_id:
            print("\n❌ ERROR: Northbeam credentials not found.")
            print("Please set NB_API_KEY and NB_ACCOUNT_ID in config/northbeam/.env")
            return 1
    except Exception as e:
        print(f"\n❌ ERROR loading credentials: {e}")
        return 1
    
    # Initialize client
    client = NorthbeamClient()
    
    # Get all available metrics
    print("\n📊 Fetching available metrics from Northbeam API...")
    try:
        metrics_meta = client.list_metrics()
        all_metrics = [m.get("id") for m in metrics_meta if m.get("id")]
        print(f"   Found {len(all_metrics)} metrics")
    except Exception as e:
        print(f"\n❌ ERROR fetching metrics: {e}")
        return 1
    
    if not all_metrics:
        print("\n❌ ERROR: No metrics returned by API")
        return 1
    
    # Get Platform breakdown values
    print("\n🔍 Fetching Platform (Northbeam) breakdown values...")
    try:
        platform_values = []
        for bd in client.list_breakdowns():
            if bd.get("key") == "Platform (Northbeam)":
                platform_values = [v for v in bd.get("values", []) if v]
                break
        if platform_values:
            print(f"   Found {len(platform_values)} platforms: {', '.join(platform_values[:5])}...")
        else:
            print("   ⚠️  No platform values found, will export without breakdown")
    except Exception as e:
        print(f"   ⚠️  Could not fetch breakdown values: {e}")
        platform_values = []
    
    # Prepare export parameters
    start_date = "2025-01-01"
    end_date = "2025-12-18"
    accounting_mode = "cash"
    attribution_model = "northbeam_custom"
    attribution_window = "1"
    
    breakdowns = None
    if platform_values:
        breakdowns = [{"key": "Platform (Northbeam)", "values": platform_values}]
    
    # Create export
    print(f"\n📤 Creating export...")
    print(f"   Accounting mode: {accounting_mode}")
    print(f"   Attribution model: {attribution_model}")
    print(f"   Attribution window: {attribution_window}")
    print(f"   Metrics: {len(all_metrics)} (all available)")
    print(f"   Breakdown: Platform (Northbeam)" if breakdowns else "   Breakdown: None")
    
    try:
        export_id = client.create_export(
            start_date=start_date,
            end_date=end_date,
            accounting_mode=accounting_mode,
            attribution_model=attribution_model,
            attribution_window=attribution_window,
            metrics=all_metrics,
            breakdowns=breakdowns,
            level="ad",
            time_granularity="DAILY",
            options={
                "export_aggregation": "DATE",
                "aggregate_data": False,
                "remove_zero_spend": False,
                "include_ids": False,
                "include_kind_and_platform": False,
            }
        )
        print(f"   Export ID: {export_id}")
    except Exception as e:
        print(f"\n❌ ERROR creating export: {e}")
        return 1
    
    # Wait for export to complete
    print("\n⏳ Waiting for export to complete...")
    try:
        result = client.wait_for_export(export_id, interval=2.0, timeout=600.0)
        print(f"   Status: {result.status}")
    except Exception as e:
        print(f"\n❌ ERROR waiting for export: {e}")
        return 1
    
    if not result.location:
        print("\n❌ ERROR: No download location provided")
        return 1
    
    # Download to file
    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    output_dir = Path(__file__).parent.parent / "data" / "ads"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"ytd_sales_data-higher_dose_llc-2025_12_18-{timestamp}.csv"
    
    print(f"\n⬇️  Downloading export...")
    print(f"   URL: {result.location[:80]}...")
    print(f"   Destination: {output_file}")
    
    try:
        urllib.request.urlretrieve(result.location, output_file)
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"   ✅ Downloaded: {file_size_mb:.1f} MB")
    except Exception as e:
        print(f"\n❌ ERROR downloading file: {e}")
        return 1
    
    # Count rows
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            line_count = sum(1 for _ in f) - 1  # minus header
        print(f"   📊 Rows: {line_count:,}")
    except Exception:
        pass
    
    print("\n" + "=" * 80)
    print("✅ SUCCESS!")
    print("=" * 80)
    print(f"\nFile saved to:")
    print(f"   {output_file}")
    print(f"\nThis file contains:")
    print(f"   • Date range: {start_date} → {end_date}")
    print(f"   • All Northbeam metrics (~300+ columns)")
    print(f"   • Daily aggregation by Platform (Northbeam)")
    print(f"   • Accounting mode: {accounting_mode}")
    print(f"   • Attribution: {attribution_model} ({attribution_window})")
    print("\n" + "=" * 80)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
