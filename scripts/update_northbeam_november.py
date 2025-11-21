#!/usr/bin/env python3
"""
Update northbeam-2025-november.csv with Q4 (Oct–Nov 2025) data from the large YTD file.
This keeps the file size manageable for GitHub/Streamlit while still giving the app
access to October + November Northbeam spend.
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
    
    # Filter to Q4 window we care about for the dashboard: Oct 1 – Nov 30, 2025
    q4_data = df[(df['date'] >= '2025-10-01') & (df['date'] < '2025-12-01')].copy()
    
    print(f"Filtered to {len(q4_data)} rows for Oct–Nov 2025")
    print(f"Date range: {q4_data['date'].min()} to {q4_data['date'].max()}")
    
    # Save filtered data
    q4_data.to_csv(OUTPUT_FILE, index=False)
    print(f"✅ Saved to: {OUTPUT_FILE}")
    print(f"File size: {OUTPUT_FILE.stat().st_size / 1024 / 1024:.1f} MB")

if __name__ == "__main__":
    main()

