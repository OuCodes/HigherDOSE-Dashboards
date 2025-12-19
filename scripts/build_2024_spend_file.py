#!/usr/bin/env python3
"""
Build 2024 spend aggregation file from Meta + Google daily exports
PLUS monthly spend for other channels from Historical Spend CSV.
Creates a daily spend file comparable to the 2025 Northbeam export.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime


def allocate_monthly_to_daily(monthly_spend, days_in_month, daily_paid_spend):
    """
    Allocate monthly spend to daily based on paid channel intensity.
    
    Args:
        monthly_spend: Total monthly spend for a channel
        days_in_month: DataFrame with date and paid_spend for each day
        daily_paid_spend: Total paid spend per day (for weighting)
    
    Returns:
        Series of daily spend allocations
    """
    if monthly_spend == 0:
        return pd.Series(0, index=days_in_month.index)
    
    # Weight by paid spend intensity (so affiliate/email peaks align with ad pushes)
    total_paid = daily_paid_spend.sum()
    if total_paid > 0:
        weights = daily_paid_spend / total_paid
    else:
        # Fallback to uniform distribution
        weights = pd.Series(1.0 / len(days_in_month), index=days_in_month.index)
    
    return weights * monthly_spend


def main():
    print("=" * 80)
    print("BUILD 2024 SPEND FILE")
    print("=" * 80)
    print("Combining ALL channels for 2024:")
    print("  • Daily: Meta + Google")
    print("  • Monthly: TikTok, Pinterest, Bing, Affiliates, etc.")
    print("=" * 80)
    
    base_dir = Path(__file__).parent.parent
    ads_dir = base_dir / "data" / "ads"
    
    # === Load Meta 2024 daily spend ===
    meta_file = ads_dir / "weekly-report-2024-ads" / "meta-daily-export-jan-1-2024-to-dec-31-2024.csv"
    print(f"\n📊 Loading Meta 2024 data...")
    print(f"   File: {meta_file.name}")
    
    try:
        meta_df = pd.read_csv(meta_file)
        meta_df['Day'] = pd.to_datetime(meta_df['Day'])
        
        # Aggregate to daily total spend
        meta_daily = meta_df.groupby('Day').agg({
            'Amount spent (USD)': 'sum'
        }).reset_index()
        meta_daily.columns = ['date', 'spend']
        meta_daily['platform'] = 'Meta'
        
        print(f"   ✅ Loaded {len(meta_daily)} days")
        print(f"   Total spend: ${meta_daily['spend'].sum():,.2f}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return 1
    
    # === Load Google 2024 daily spend ===
    google_file = ads_dir / "weekly-report-2024-ads" / "google-2024-account-level-daily report.csv"
    print(f"\n📊 Loading Google 2024 data...")
    print(f"   File: {google_file.name}")
    
    try:
        # Google CSV has 2 header rows - skip them
        google_df = pd.read_csv(google_file, skiprows=2)
        google_df['Day'] = pd.to_datetime(google_df['Day'])
        
        # Handle Cost column (might have commas)
        if google_df['Cost'].dtype == 'object':
            google_df['Cost'] = google_df['Cost'].str.replace(',', '').astype(float)
        
        # Aggregate to daily total spend
        google_daily = google_df.groupby('Day').agg({
            'Cost': 'sum'
        }).reset_index()
        google_daily.columns = ['date', 'spend']
        google_daily['platform'] = 'Google'
        
        print(f"   ✅ Loaded {len(google_daily)} days")
        print(f"   Total spend: ${google_daily['spend'].sum():,.2f}")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return 1
    
    # === Load Historical Spend CSV (monthly data for other channels) ===
    # Try main location first, then fallback to q4-planning-2025 subdirectory
    historical_file = ads_dir / "Historical Spend - Historical Spend.csv"
    if not historical_file.exists():
        historical_file = ads_dir / "q4-planning-2025" / "Historical Spend - Historical Spend.csv"
    
    print(f"\n📊 Loading Historical Spend CSV...")
    print(f"   File: {historical_file.name}")
    
    try:
        # Read the CSV - it has merged header rows
        hist_df = pd.read_csv(historical_file)
        
        # Filter to 2024 rows only (Jan-24 through Dec-24)
        hist_2024 = hist_df[hist_df['Month'].str.contains('24', na=False)].copy()
        
        # Parse month names to dates (first day of month)
        hist_2024['month_date'] = pd.to_datetime(hist_2024['Month'], format='%b-%y')
        
        # Extract spend columns (clean currency formatting)
        def clean_currency(val):
            if pd.isna(val) or val == '' or val == '–':
                return 0.0
            return float(str(val).replace('$', '').replace(',', ''))
        
        # Map column names to platform names
        channel_columns = {
            'Facebook\nSpend': 'Meta',
            'TikTok\nSpend': 'TikTok', 
            'Google\nSpend': 'Google',
            'Twitter\nSpend': 'Twitter',
            'Pinterest\nSpend': 'Pinterest',
            'Bing': 'Bing',
            'AppLovin': 'AppLovin',
            'Share-A-Sale\nSpend': 'ShareASale',
            'ShopMy\nSpend': 'ShopMy',
            'Awin\nSpend': 'Awin',
            # NOTE: 'Affiliate Commissions(3)' is excluded - it's a rollup of ShareASale+ShopMy+Awin
            # Including it would cause double-counting of affiliate spend
        }
        
        # Extract monthly spend by channel
        monthly_spend_by_channel = []
        
        for _, row in hist_2024.iterrows():
            month_date = row['month_date']
            
            for col, platform in channel_columns.items():
                if col in hist_df.columns:
                    spend = clean_currency(row[col])
                    if spend > 0:
                        monthly_spend_by_channel.append({
                            'month_date': month_date,
                            'platform': platform,
                            'monthly_spend': spend
                        })
        
        monthly_spend_df = pd.DataFrame(monthly_spend_by_channel)
        
        # Summarize what we found
        if len(monthly_spend_df) > 0:
            print(f"   ✅ Loaded monthly spend for {len(monthly_spend_df['platform'].unique())} channels")
            total_historical = monthly_spend_df['monthly_spend'].sum()
            print(f"   Total historical spend: ${total_historical:,.2f}")
            
            # Show breakdown by platform
            platform_totals = monthly_spend_df.groupby('platform')['monthly_spend'].sum().sort_values(ascending=False)
            print(f"\n   Channel breakdown (2024 annual):")
            for platform, spend in platform_totals.head(10).items():
                print(f"     {platform:12s}: ${spend:>12,.2f}")
        else:
            print(f"   ⚠️  No monthly spend data found in historical CSV")
            monthly_spend_df = pd.DataFrame()
    
    except Exception as e:
        print(f"   ⚠️  ERROR loading historical spend: {e}")
        print(f"   Continuing with Meta + Google only...")
        monthly_spend_df = pd.DataFrame()
    
    # === Allocate monthly spend to daily ===
    print(f"\n🔗 Allocating monthly spend to daily...")
    
    # Combine Meta + Google daily (these are the "paid channels" that drive intensity)
    paid_daily = pd.concat([meta_daily, google_daily])
    paid_by_date = paid_daily.groupby('date')['spend'].sum()
    
    # For each month in historical data, allocate to days
    all_daily_rows = []
    
    # Start with Meta and Google daily data
    all_daily_rows.extend(meta_daily.to_dict('records'))
    all_daily_rows.extend(google_daily.to_dict('records'))
    
    if len(monthly_spend_df) > 0:
        for (month_date, platform), group in monthly_spend_df.groupby(['month_date', 'platform']):
            monthly_spend = group['monthly_spend'].sum()
            
            # Skip if this is Meta or Google (we already have daily data)
            if platform in ['Meta', 'Google']:
                continue
            
            # Get all days in this month
            year = month_date.year
            month = month_date.month
            days_in_month = pd.date_range(
                start=f'{year}-{month:02d}-01',
                end=pd.Timestamp(year, month, 1) + pd.offsets.MonthEnd(1),
                freq='D'
            )
            
            # Get paid spend for these days (for weighting)
            daily_paid = paid_by_date.reindex(days_in_month, fill_value=0)
            
            # Allocate monthly spend across days
            daily_allocation = allocate_monthly_to_daily(
                monthly_spend, 
                pd.DataFrame({'date': days_in_month}),
                daily_paid
            )
            
            # Add to results
            for date, spend in zip(days_in_month, daily_allocation):
                all_daily_rows.append({
                    'date': date,
                    'platform': platform,
                    'spend': spend
                })
    
    # === Combine and format ===
    print(f"\n🔗 Combining all data...")
    combined_df = pd.DataFrame(all_daily_rows)
    combined_df = combined_df.sort_values(['date', 'platform'])
    
    # Add accounting_mode and attribution columns to match 2025 format
    combined_df['accounting_mode'] = 'Cash snapshot'
    combined_df['attribution_model'] = combined_df['platform'].apply(
        lambda x: 'Platform reported' if x in ['Meta', 'Google'] else 'Monthly allocation'
    )
    combined_df['attribution_window'] = '1'
    
    # Reorder columns to match schema
    combined_df = combined_df[['date', 'platform', 'spend', 'accounting_mode', 'attribution_model', 'attribution_window']]
    
    # Calculate totals
    total_spend = combined_df['spend'].sum()
    date_range = f"{combined_df['date'].min().strftime('%Y-%m-%d')} → {combined_df['date'].max().strftime('%Y-%m-%d')}"
    
    print(f"   ✅ Combined {len(combined_df)} rows")
    print(f"   Date range: {date_range}")
    print(f"   Total spend: ${total_spend:,.2f}")
    
    # Calculate platform breakdown
    print(f"\n📊 Platform breakdown (full year):")
    platform_totals = combined_df.groupby('platform')['spend'].sum().sort_values(ascending=False)
    for platform, spend in platform_totals.items():
        pct = spend / total_spend * 100
        print(f"   {platform:12s}: ${spend:>12,.2f} ({pct:>5.1f}%)")
    
    # Save to file
    timestamp = datetime.now().strftime("%Y_%m_%d")
    output_file = ads_dir / f"northbeam_style_daily_2024-{timestamp}.csv"
    
    print(f"\n💾 Saving to file...")
    print(f"   {output_file}")
    
    try:
        combined_df.to_csv(output_file, index=False)
        file_size_mb = output_file.stat().st_size / (1024 * 1024)
        print(f"   ✅ Saved: {file_size_mb:.2f} MB")
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return 1
    
    print("\n" + "=" * 80)
    print("✅ SUCCESS!")
    print("=" * 80)
    print(f"\nFile saved to:")
    print(f"   {output_file}")
    print(f"\nThis file contains:")
    print(f"   • Date range: {date_range}")
    print(f"   • Platforms: {len(platform_totals)} channels")
    print(f"   • Daily spend totals (Meta/Google actual, others allocated)")
    print(f"   • Total 2024 spend: ${total_spend:,.2f}")
    print(f"\nNote: Meta and Google are daily actuals from platform exports.")
    print(f"Other channels are monthly totals from Historical Spend CSV,")
    print(f"allocated to days based on paid channel intensity patterns.")
    print("\n" + "=" * 80)
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
