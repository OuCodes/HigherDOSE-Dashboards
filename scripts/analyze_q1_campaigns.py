#!/usr/bin/env python3
"""
Analyze Q1 2024 vs 2025 Campaign Performance
Extract campaign-level spend by month for Google & Meta
"""

import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data" / "ads"

def load_2024_campaigns():
    """Load 2024 Meta + Google campaign data"""
    
    # Meta 2024 - daily aggregated data (no campaign names in this export)
    meta_2024 = DATA_DIR / "weekly-report-2024-ads" / "meta-daily-export-jan-1-2024-to-dec-31-2024.csv"
    google_2024 = DATA_DIR / "weekly-report-2024-ads" / "google-2024-account-level-daily report.csv"
    
    campaigns_2024 = []
    
    # Try loading Google 2024
    if google_2024.exists():
        df = pd.read_csv(google_2024, skiprows=2)  # Skip 2 header rows
        df.columns = df.columns.str.strip()
        df['Day'] = pd.to_datetime(df['Day'])
        df = df[df['Day'].dt.quarter == 1].copy()
        df['month'] = df['Day'].dt.month
        df['month_name'] = df['Day'].dt.strftime('%B')
        df['platform'] = 'Google'
        df['campaign_name'] = 'Google Ads (Aggregated)'
        df['spend'] = df['Cost']
        campaigns_2024.append(df[['Day', 'month', 'month_name', 'platform', 'campaign_name', 'spend']])
    
    # Try loading Meta 2024
    if meta_2024.exists():
        df = pd.read_csv(meta_2024)
        df['Day'] = pd.to_datetime(df['Day'])
        df = df[df['Day'].dt.quarter == 1].copy()
        df['month'] = df['Day'].dt.month
        df['month_name'] = df['Day'].dt.strftime('%B')
        df['platform'] = 'Meta'
        df['campaign_name'] = 'Meta Ads (Aggregated)'
        df['spend'] = df['Amount spent (USD)']
        campaigns_2024.append(df[['Day', 'month', 'month_name', 'platform', 'campaign_name', 'spend']])
    
    if campaigns_2024:
        return pd.concat(campaigns_2024, ignore_index=True)
    return pd.DataFrame()


def load_2025_campaigns():
    """Load 2025 campaign data from Northbeam January export"""
    
    jan_2025 = DATA_DIR / "northbeam-january-2025.csv"
    
    if not jan_2025.exists():
        print(f"❌ January 2025 Northbeam file not found: {jan_2025}")
        return pd.DataFrame()
    
    print(f"📊 Loading 2025 campaigns from: {jan_2025.name}")
    
    df = pd.read_csv(jan_2025)
    df['date'] = pd.to_datetime(df['date'])
    
    # Filter to Cash snapshot and Q1 only
    df = df[(df['accounting_mode'] == 'Cash snapshot') & (df['date'].dt.quarter == 1)].copy()
    
    # Extract month info
    df['month'] = df['date'].dt.month
    df['month_name'] = df['date'].dt.strftime('%B')
    
    # Rename platform column and normalize names
    df['platform'] = df['breakdown_platform_northbeam'].map({
        'Google Ads': 'Google',
        'Facebook Ads': 'Meta',
        'Google': 'Google',
        'Meta': 'Meta'
    }).fillna(df['breakdown_platform_northbeam'])
    
    # Filter to Google and Meta only
    df = df[df['platform'].isin(['Google', 'Meta'])].copy()
    
    # Keep relevant columns
    campaigns_2025 = df[['date', 'month', 'month_name', 'platform', 'campaign_name', 'spend']].copy()
    
    return campaigns_2025


def analyze_campaigns():
    """Main analysis function"""
    
    print("\n" + "="*80)
    print("Q1 CAMPAIGN ANALYSIS: 2024 vs 2025")
    print("="*80 + "\n")
    
    # Load data
    campaigns_2024 = load_2024_campaigns()
    campaigns_2025 = load_2025_campaigns()
    
    if campaigns_2024.empty and campaigns_2025.empty:
        print("❌ No campaign data loaded")
        return
    
    print(f"✅ 2024 campaigns: {len(campaigns_2024)} records")
    print(f"✅ 2025 campaigns: {len(campaigns_2025)} records\n")
    
    # Aggregate by month and platform
    if not campaigns_2024.empty:
        print("\n📊 2024 Q1 SPEND BY PLATFORM & MONTH")
        print("-" * 60)
        monthly_2024 = campaigns_2024.groupby(['month_name', 'platform'])['spend'].sum().reset_index()
        monthly_2024 = monthly_2024.pivot(index='month_name', columns='platform', values='spend').fillna(0)
        monthly_2024['Total'] = monthly_2024.sum(axis=1)
        print(monthly_2024.to_string())
        print(f"\nQ1 2024 Total Spend: ${monthly_2024['Total'].sum():,.2f}\n")
    
    if not campaigns_2025.empty:
        print("\n📊 2025 Q1 SPEND BY PLATFORM & MONTH")
        print("-" * 60)
        monthly_2025 = campaigns_2025.groupby(['month_name', 'platform'])['spend'].sum().reset_index()
        monthly_2025 = monthly_2025.pivot(index='month_name', columns='platform', values='spend').fillna(0)
        monthly_2025['Total'] = monthly_2025.sum(axis=1)
        print(monthly_2025.to_string())
        print(f"\nQ1 2025 Total Spend: ${monthly_2025['Total'].sum():,.2f}\n")
    
    # Top campaigns by platform
    if not campaigns_2025.empty:
        print("\n📊 TOP 2025 CAMPAIGNS BY SPEND (January)")
        print("-" * 60)
        
        for platform in ['Google', 'Meta']:
            platform_data = campaigns_2025[campaigns_2025['platform'] == platform].copy()
            if not platform_data.empty:
                top_campaigns = platform_data.groupby('campaign_name')['spend'].sum().nlargest(10)
                print(f"\n{platform} - Top 10 Campaigns:")
                for idx, (campaign, spend) in enumerate(top_campaigns.items(), 1):
                    print(f"  {idx:2d}. {campaign[:60]:60s} ${spend:>12,.2f}")
    
    # Save processed data
    output_dir = DATA_DIR.parent / "reports" / "campaign"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not campaigns_2024.empty:
        output_2024 = output_dir / "q1_2024_campaigns.csv"
        campaigns_2024.to_csv(output_2024, index=False)
        print(f"\n💾 Saved 2024 campaigns: {output_2024}")
    
    if not campaigns_2025.empty:
        output_2025 = output_dir / "q1_2025_campaigns.csv"
        campaigns_2025.to_csv(output_2025, index=False)
        print(f"💾 Saved 2025 campaigns: {output_2025}")
    
    print("\n✅ Campaign analysis complete!\n")


if __name__ == "__main__":
    analyze_campaigns()
