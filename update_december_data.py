#!/usr/bin/env python3
"""
Update December data with latest Northbeam and GA4 information
Filter to December only to reduce file sizes
"""

import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).parent
ADS_DIR = BASE_DIR / "data" / "ads"
EXEC_SUM_DIR = ADS_DIR / "exec-sum"
DEC_DIR = ADS_DIR / "december-only"
DEC_DIR.mkdir(exist_ok=True)

print("=" * 70)
print("UPDATING DECEMBER DATA WITH LATEST NORTHBEAM & GA4")
print("=" * 70)

# 1. Filter latest Northbeam to December only
print("\n1. Processing Northbeam data (all channels)...")
nb_file = ADS_DIR / "northbeam-2025-ytd-latest.csv"

if nb_file.exists():
    print(f"   Reading {nb_file.name} ({nb_file.stat().st_size / 1024 / 1024:.1f}MB)...")
    df = pd.read_csv(nb_file, engine='python', on_bad_lines='skip')
    
    print(f"   Total rows: {len(df):,}")
    
    # Filter to Cash snapshot only
    if 'accounting_mode' in df.columns:
        df = df[df['accounting_mode'] == 'Cash snapshot'].copy()
        print(f"   After filtering to Cash snapshot: {len(df):,} rows")
    
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    
    # Filter to December 2024 and 2025
    dec_data = df[
        ((df['date'] >= '2024-12-01') & (df['date'] <= '2024-12-31')) |
        ((df['date'] >= '2025-12-01') & (df['date'] <= '2025-12-31'))
    ].copy()
    
    if len(dec_data) > 0:
        output_file = DEC_DIR / "northbeam-december-2024-2025.csv"
        dec_data.to_csv(output_file, index=False)
        print(f"   ✓ Created {output_file.name}")
        print(f"     December rows: {len(dec_data):,}")
        print(f"     File size: {nb_file.stat().st_size / 1024 / 1024:.1f}MB → {output_file.stat().st_size / 1024 / 1024:.1f}MB")
        
        # Show date range
        print(f"     Date range: {dec_data['date'].min().date()} to {dec_data['date'].max().date()}")
    else:
        print("   ⚠️  No December data found in Northbeam file")
else:
    print(f"   ⚠️  File not found: {nb_file.name}")

# 2. Check for latest GA4 data
print("\n2. Checking GA4 session data...")
ga4_files_2024 = sorted(EXEC_SUM_DIR.glob("daily-traffic_acquisition_Session_default_channel_group-2024-*.csv"))
ga4_files_2025 = sorted(EXEC_SUM_DIR.glob("daily-traffic_acquisition_Session_default_channel_group-2025-*.csv"))

if ga4_files_2024:
    latest_2024 = ga4_files_2024[-1]
    print(f"   ✓ Latest 2024 GA4 file: {latest_2024.name}")
    
if ga4_files_2025:
    latest_2025 = ga4_files_2025[-1]
    print(f"   ✓ Latest 2025 GA4 file: {latest_2025.name}")
    
    # Filter to December 2025
    df = pd.read_csv(latest_2025)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    dec_2025 = df[(df['Date'] >= '2025-12-01') & (df['Date'] <= '2025-12-31')]
    
    if len(dec_2025) > 0:
        output_file = EXEC_SUM_DIR / "ga4-sessions-december-2025.csv"
        dec_2025.to_csv(output_file, index=False)
        print(f"   ✓ Created December 2025 filtered: {output_file.name} ({len(dec_2025)} days)")

# 3. Summary
print("\n" + "=" * 70)
print("✅ UPDATE COMPLETE!")
print("=" * 70)
print("\nFiles created/updated:")
print(f"  • {DEC_DIR}/northbeam-december-2024-2025.csv")
print(f"  • {EXEC_SUM_DIR}/ga4-sessions-december-2025.csv")
print("\nThese filtered files are much smaller and faster to load!")
