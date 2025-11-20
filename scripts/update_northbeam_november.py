#!/usr/bin/env python3
"""
Update northbeam-2025-november.csv with the latest data from the YTD file.
This keeps the file size manageable for GitHub commits.
"""

import pandas as pd
from pathlib import Path

# Paths
DATA_DIR = Path(__file__).parent.parent / "data" / "ads"
INPUT_FILE = DATA_DIR / "ytd_sales_data-higher_dose_llc-2025_10_07_22_43_36.csv"
OUTPUT_FILE = DATA_DIR / "northbeam-2025-november.csv"

def main():
    print(f"Reading Northbeam YTD data from: {INPUT_FILE}")
    
    # Read the large YTD file
    df = pd.read_csv(INPUT_FILE)
    
    # Convert date column
    df['date'] = pd.to_datetime(df['date'])
    
    # Filter to November 2025 only
    november_data = df[(df['date'] >= '2025-11-01') & (df['date'] < '2025-12-01')].copy()
    
    print(f"Filtered to {len(november_data)} rows for November 2025")
    print(f"Date range: {november_data['date'].min()} to {november_data['date'].max()}")
    
    # Save filtered data
    november_data.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Saved to: {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")

if __name__ == "__main__":
    main()

