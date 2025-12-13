#!/usr/bin/env python3
"""
Filter datasets to only December 2024 and December 2025 data
This reduces file sizes and focuses the dashboard on the comparison period
"""

import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ADS_DIR = DATA_DIR / "ads"
EXEC_SUM_DIR = ADS_DIR / "exec-sum"
MAIL_DIR = DATA_DIR / "mail"

def filter_shopify_sales():
    """Filter Shopify sales data to December only"""
    print("Filtering Shopify sales data...")
    
    # 2024 Sales - December only
    sales_2024_file = EXEC_SUM_DIR / "Total sales over time - 2024-01-01 - 2024-12-31-DAILY.csv"
    if sales_2024_file.exists():
        df = pd.read_csv(sales_2024_file)
        df['Day'] = pd.to_datetime(df['Day'])
        dec_2024 = df[(df['Day'] >= '2024-12-01') & (df['Day'] <= '2024-12-31')]
        
        output_file = EXEC_SUM_DIR / "Total sales over time - 2024-12-DECEMBER-ONLY.csv"
        dec_2024.to_csv(output_file, index=False)
        print(f"  ✓ Created {output_file.name} ({len(dec_2024)} days)")
    
    # 2025 Sales - December only (if available)
    sales_2025_file = EXEC_SUM_DIR / "Total sales over time - OU - 2025-01-01 - 2025-12-01.csv"
    if sales_2025_file.exists():
        df = pd.read_csv(sales_2025_file)
        df['Day'] = pd.to_datetime(df['Day'])
        dec_2025 = df[(df['Day'] >= '2025-12-01') & (df['Day'] <= '2025-12-31')]
        
        if len(dec_2025) > 0:
            output_file = EXEC_SUM_DIR / "Total sales over time - 2025-12-DECEMBER-ONLY.csv"
            dec_2025.to_csv(output_file, index=False)
            print(f"  ✓ Created {output_file.name} ({len(dec_2025)} days)")
        else:
            print("  ! No December 2025 data yet")

def filter_ga4_traffic():
    """Filter GA4 traffic data to December only"""
    print("\nFiltering GA4 traffic data...")
    
    # 2024 GA4
    ga4_2024_file = EXEC_SUM_DIR / "daily-traffic_acquisition_Session_default_channel_group-2024-01-01-2024-12-31..csv"
    if ga4_2024_file.exists():
        df = pd.read_csv(ga4_2024_file, comment='#')
        df['Date'] = pd.to_datetime(df['Date'].astype(str), format='%Y%m%d', errors='coerce')
        dec_2024 = df[(df['Date'] >= '2024-12-01') & (df['Date'] <= '2024-12-31')]
        
        output_file = EXEC_SUM_DIR / "ga4-traffic-2024-12-DECEMBER-ONLY.csv"
        dec_2024.to_csv(output_file, index=False)
        print(f"  ✓ Created {output_file.name} ({len(dec_2024)} days)")
    
    # 2025 GA4
    ga4_2025_file = EXEC_SUM_DIR / "daily-traffic_acquisition_Session_default_channel_group-2025-01-01-2025-12-01.csv"
    if ga4_2025_file.exists():
        df = pd.read_csv(ga4_2025_file)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        dec_2025 = df[(df['Date'] >= '2025-12-01') & (df['Date'] <= '2025-12-31')]
        
        if len(dec_2025) > 0:
            output_file = EXEC_SUM_DIR / "ga4-traffic-2025-12-DECEMBER-ONLY.csv"
            dec_2025.to_csv(output_file, index=False)
            print(f"  ✓ Created {output_file.name} ({len(dec_2025)} days)")

def filter_meta_ads():
    """Filter Meta ads data to December only"""
    print("\nFiltering Meta ads data...")
    
    # 2024 Meta
    meta_2024_file = ADS_DIR / "weekly-report-2024-ads" / "meta-daily-export-jan-1-2024-to-dec-31-2024.csv"
    if meta_2024_file.exists():
        df = pd.read_csv(meta_2024_file)
        df['Day'] = pd.to_datetime(df['Day'])
        dec_2024 = df[(df['Day'] >= '2024-12-01') & (df['Day'] <= '2024-12-31')]
        
        output_dir = ADS_DIR / "december-only"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "meta-2024-12-DECEMBER-ONLY.csv"
        dec_2024.to_csv(output_file, index=False)
        print(f"  ✓ Created {output_file.name} ({len(dec_2024)} days)")
    
    # 2025 Meta
    meta_2025_file = ADS_DIR / "meta-mtd-export-jan-01-2025-to-nov-24-2025.auto.csv"
    if meta_2025_file.exists():
        df = pd.read_csv(meta_2025_file)
        df['Day'] = pd.to_datetime(df['Day'])
        dec_2025 = df[(df['Day'] >= '2025-12-01') & (df['Day'] <= '2025-12-31')]
        
        if len(dec_2025) > 0:
            output_dir = ADS_DIR / "december-only"
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / "meta-2025-12-DECEMBER-ONLY.csv"
            dec_2025.to_csv(output_file, index=False)
            print(f"  ✓ Created {output_file.name} ({len(dec_2025)} days)")

def filter_google_ads():
    """Filter Google Ads data to December only"""
    print("\nFiltering Google Ads data...")
    
    # 2024 Google
    google_2024_file = ADS_DIR / "weekly-report-2024-ads" / "google-2024-account-level-daily report.csv"
    if google_2024_file.exists():
        df = pd.read_csv(google_2024_file, skiprows=2)
        df['Day'] = pd.to_datetime(df['Day'])
        dec_2024 = df[(df['Day'] >= '2024-12-01') & (df['Day'] <= '2024-12-31')]
        
        output_dir = ADS_DIR / "december-only"
        output_dir.mkdir(exist_ok=True)
        output_file = output_dir / "google-2024-12-DECEMBER-ONLY.csv"
        dec_2024.to_csv(output_file, index=False)
        print(f"  ✓ Created {output_file.name} ({len(dec_2024)} days)")
    
    # 2025 Google
    google_2025_file = ADS_DIR / "google-mtd-export-jan-01-to-nov-24-2025-account-level-daily report.csv"
    if google_2025_file.exists():
        df = pd.read_csv(google_2025_file, skiprows=2)
        df['Day'] = pd.to_datetime(df['Day'])
        dec_2025 = df[(df['Day'] >= '2025-12-01') & (df['Day'] <= '2025-12-31')]
        
        if len(dec_2025) > 0:
            output_dir = ADS_DIR / "december-only"
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / "google-2025-12-DECEMBER-ONLY.csv"
            dec_2025.to_csv(output_file, index=False)
            print(f"  ✓ Created {output_file.name} ({len(dec_2025)} days)")

def filter_northbeam():
    """Filter Northbeam data to December only"""
    print("\nFiltering Northbeam data...")
    
    # This file is huge (67MB), let's filter to December only
    nb_file = ADS_DIR / "northbeam-2025-november.csv"
    if nb_file.exists():
        print("  Reading Northbeam file (this may take a moment)...")
        df = pd.read_csv(nb_file, engine='python', on_bad_lines='skip')
        
        if 'accounting_mode' in df.columns:
            df = df[df['accounting_mode'] == 'Cash snapshot']
        
        df['date'] = pd.to_datetime(df['date'])
        dec_data = df[(df['date'] >= '2024-12-01') & (df['date'] <= '2025-12-31')]
        
        if len(dec_data) > 0:
            output_dir = ADS_DIR / "december-only"
            output_dir.mkdir(exist_ok=True)
            output_file = output_dir / "northbeam-DECEMBER-ONLY.csv"
            dec_data.to_csv(output_file, index=False)
            print(f"  ✓ Created {output_file.name} ({len(dec_data)} rows)")
            print(f"    Original: {nb_file.stat().st_size / 1024 / 1024:.1f}MB → Filtered: {output_file.stat().st_size / 1024 / 1024:.1f}MB")

if __name__ == "__main__":
    print("=" * 60)
    print("FILTERING DATA TO DECEMBER 2024 & 2025 ONLY")
    print("=" * 60)
    
    filter_shopify_sales()
    filter_ga4_traffic()
    filter_meta_ads()
    filter_google_ads()
    filter_northbeam()
    
    print("\n" + "=" * 60)
    print("✅ FILTERING COMPLETE!")
    print("=" * 60)
    print("\nFiltered files created in:")
    print("  - data/ads/exec-sum/*-DECEMBER-ONLY.csv")
    print("  - data/ads/december-only/")

