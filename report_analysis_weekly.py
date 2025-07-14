#!/usr/bin/env python3
"""
HigherDOSE Weekly Growth Report Analysis
Analysis of 7-day sales data for weekly performance reporting
"""

import pandas as pd
import numpy as np
from datetime import datetime

def load_and_clean_data():
    """Load and clean the 7-day sales data"""
    try:
        df = pd.read_csv('stats/7d-sales_data-higher_dose_llc-2025_07_13_22_54_02_734538-000000000000.csv')
        print(f"✅ Successfully loaded data with {len(df)} rows")
        
        # Clean and convert numeric columns
        numeric_cols = ['spend', 'cac', 'cac_1st_time', 'roas', 'roas_1st_time', 
                       'aov', 'aov_1st_time', 'ecr', 'ecr_1st_time', 'ecpnv',
                       'platformreported_cac', 'platformreported_roas', 
                       'new_customer_percentage', 'attributed_rev', 'attributed_rev_1st_time',
                       'transactions', 'transactions_1st_time', 'visits']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Fill NaN values with 0 for analysis
        df = df.fillna(0)
        
        return df
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None

def analyze_channel_performance(df):
    """Analyze performance by marketing channel"""
    print("\n" + "="*60)
    print("📊 CHANNEL PERFORMANCE ANALYSIS")
    print("="*60)
    
    # Filter for Accrual Performance data only (for campaign optimization)
    accrual_df = df[df['accounting_mode'] == 'Accrual performance'].copy()
    
    if len(accrual_df) == 0:
        print("⚠️ No Accrual Performance data found")
        return {}
    
    # Group by platform for channel-level analysis
    channel_summary = accrual_df.groupby('breakdown_platform_northbeam').agg({
        'spend': 'sum',
        'attributed_rev': 'sum',
        'attributed_rev_1st_time': 'sum',
        'transactions': 'sum',
        'transactions_1st_time': 'sum',
        'visits': 'sum',
        'new_visits': 'sum'
    }).round(2)
    
    # Calculate key metrics
    channel_summary['roas'] = (channel_summary['attributed_rev'] / channel_summary['spend']).replace([np.inf], 0).round(2)
    channel_summary['roas_1st_time'] = (channel_summary['attributed_rev_1st_time'] / channel_summary['spend']).replace([np.inf], 0).round(2)
    channel_summary['cac'] = (channel_summary['spend'] / channel_summary['transactions']).replace([np.inf], 0).round(2)
    channel_summary['cac_1st_time'] = (channel_summary['spend'] / channel_summary['transactions_1st_time']).replace([np.inf], 0).round(2)
    channel_summary['aov'] = (channel_summary['attributed_rev'] / channel_summary['transactions']).replace([np.inf], 0).round(2)
    channel_summary['ecr'] = (channel_summary['transactions'] / channel_summary['visits']).replace([np.inf], 0).round(4)
    channel_summary['percent_new_visits'] = (channel_summary['new_visits'] / channel_summary['visits'] * 100).replace([np.inf], 0).round(1)
    
    # Sort by spend (descending)
    channel_summary = channel_summary.sort_values('spend', ascending=False)
    
    print("\nTOP PERFORMING CHANNELS BY SPEND:")
    print("-" * 60)
    for platform, row in channel_summary.head(10).iterrows():
        if row['spend'] > 0:
            print(f"{platform:<20} | Spend: ${row['spend']:>10,.2f} | ROAS: {row['roas']:>5.2f} | CAC: ${row['cac']:>7.2f} | AOV: ${row['aov']:>6.2f}")
    
    return channel_summary

def analyze_campaign_performance(df):
    """Analyze individual campaign performance"""
    print("\n" + "="*60)
    print("🚀 TOP CAMPAIGN PERFORMANCE")
    print("="*60)
    
    # Filter for campaigns with significant spend
    accrual_df = df[df['accounting_mode'] == 'Accrual performance'].copy()
    significant_campaigns = accrual_df[accrual_df['spend'] > 100].copy()
    
    if len(significant_campaigns) == 0:
        print("⚠️ No campaigns with significant spend found")
        return {}
    
    # Calculate performance metrics
    significant_campaigns['roas'] = (significant_campaigns['attributed_rev'] / significant_campaigns['spend']).replace([np.inf], 0)
    significant_campaigns['cac'] = (significant_campaigns['spend'] / significant_campaigns['transactions']).replace([np.inf], 0)
    significant_campaigns['aov'] = (significant_campaigns['attributed_rev'] / significant_campaigns['transactions']).replace([np.inf], 0)
    
    # Sort by ROAS (descending)
    top_roas = significant_campaigns.nlargest(10, 'roas')
    
    print("\nTOP 10 CAMPAIGNS BY ROAS:")
    print("-" * 100)
    for _, row in top_roas.iterrows():
        if row['roas'] > 0:
            print(f"{row['breakdown_platform_northbeam']:<12} | {row['campaign_name'][:40]:<40} | ROAS: {row['roas']:>5.2f} | Spend: ${row['spend']:>8,.2f}")
    
    # Sort by spend (descending)
    top_spend = significant_campaigns.nlargest(10, 'spend')
    
    print("\nTOP 10 CAMPAIGNS BY SPEND:")
    print("-" * 100)
    for _, row in top_spend.iterrows():
        print(f"{row['breakdown_platform_northbeam']:<12} | {row['campaign_name'][:40]:<40} | Spend: ${row['spend']:>8,.2f} | ROAS: {row['roas']:>5.2f}")
    
    return significant_campaigns

def analyze_first_time_metrics(df):
    """Analyze first-time customer metrics by channel"""
    print("\n" + "="*60)
    print("👥 FIRST-TIME CUSTOMER METRICS BY CHANNEL")
    print("="*60)
    
    # Group by platform for first-time metrics
    first_time_metrics = df.groupby('breakdown_platform_northbeam').agg({
        'spend': 'sum',
        'cac_1st_time': lambda x: (df.loc[x.index, 'spend'].sum() / df.loc[x.index, 'transactions_1st_time'].sum()) if df.loc[x.index, 'transactions_1st_time'].sum() > 0 else 0,
        'roas_1st_time': lambda x: (df.loc[x.index, 'attributed_rev_1st_time'].sum() / df.loc[x.index, 'spend'].sum()) if df.loc[x.index, 'spend'].sum() > 0 else 0,
        'aov_1st_time': lambda x: (df.loc[x.index, 'attributed_rev_1st_time'].sum() / df.loc[x.index, 'transactions_1st_time'].sum()) if df.loc[x.index, 'transactions_1st_time'].sum() > 0 else 0,
        'attributed_rev_1st_time': 'sum',
        'transactions_1st_time': 'sum'
    }).round(2)
    
    # Sort by spend
    first_time_metrics = first_time_metrics.sort_values('spend', ascending=False)
    
    print("\nTOP CHANNELS - FIRST-TIME CUSTOMER METRICS:")
    print("-" * 100)
    for platform, row in first_time_metrics.head(10).iterrows():
        if row['spend'] > 100:  # Only show channels with significant spend
            print(f"{platform:<15} | CAC 1st: ${row['cac_1st_time']:>7.2f} | ROAS 1st: {row['roas_1st_time']:>5.2f} | AOV 1st: ${row['aov_1st_time']:>7.2f} | Spend: ${row['spend']:>8.2f}")
    
    return first_time_metrics

def generate_executive_summary(channel_summary):
    """Generate executive summary metrics"""
    print("\n" + "="*60)
    print("📈 EXECUTIVE SUMMARY METRICS")
    print("="*60)
    
    # Total performance across all channels
    total_spend = channel_summary['spend'].sum()
    total_revenue = channel_summary['attributed_rev'].sum()
    total_transactions = channel_summary['transactions'].sum()
    total_visits = channel_summary['visits'].sum()
    
    overall_roas = total_revenue / total_spend if total_spend > 0 else 0
    overall_cac = total_spend / total_transactions if total_transactions > 0 else 0
    overall_aov = total_revenue / total_transactions if total_transactions > 0 else 0
    overall_ecr = total_transactions / total_visits if total_visits > 0 else 0
    
    print(f"💰 Total Spend: ${total_spend:,.2f}")
    print(f"💵 Total Revenue: ${total_revenue:,.2f}")
    print(f"🎯 Overall ROAS: {overall_roas:.2f}")
    print(f"💸 Overall CAC: ${overall_cac:.2f}")
    print(f"🛒 Overall AOV: ${overall_aov:.2f}")
    print(f"📊 Overall ECR: {overall_ecr:.4f} ({overall_ecr*100:.2f}%)")
    print(f"🔄 Total Transactions: {int(total_transactions)}")
    print(f"👥 Total Visits: {int(total_visits)}")
    
    # Top 3 channels by spend
    top_3_channels = channel_summary.head(3)
    print(f"\n🏆 TOP 3 CHANNELS BY SPEND:")
    for i, (platform, row) in enumerate(top_3_channels.iterrows(), 1):
        if row['spend'] > 0:
            print(f"   {i}. {platform}: ${row['spend']:,.2f} (ROAS: {row['roas']:.2f})")
    
    return {
        'total_spend': total_spend,
        'total_revenue': total_revenue,
        'overall_roas': overall_roas,
        'overall_cac': overall_cac,
        'overall_aov': overall_aov,
        'overall_ecr': overall_ecr,
        'total_transactions': total_transactions,
        'total_visits': total_visits
    }

def analyze_attribution_modes(df):
    """Compare Cash vs Accrual accounting modes"""
    print("\n" + "="*60)
    print("🔍 ATTRIBUTION MODE COMPARISON")
    print("="*60)
    
    mode_summary = df.groupby('accounting_mode').agg({
        'spend': 'sum',
        'attributed_rev': 'sum',
        'rev': 'sum',
        'transactions': 'sum',
        'visits': 'sum'
    }).round(2)
    
    for mode, row in mode_summary.iterrows():
        print(f"\n{mode.upper()}:")
        print(f"  Spend: ${row['spend']:,.2f}")
        if mode == 'Accrual performance':
            revenue = row['attributed_rev']
            print(f"  Attributed Revenue: ${revenue:,.2f}")
        else:
            revenue = row['rev']
            print(f"  Cash Revenue: ${revenue:,.2f}")
        
        roas = revenue / row['spend'] if row['spend'] > 0 else 0
        print(f"  ROAS: {roas:.2f}")
        print(f"  Transactions: {int(row['transactions'])}")
        print(f"  Visits: {int(row['visits'])}")

def identify_opportunities(channel_summary):
    """Identify growth opportunities and challenges"""
    print("\n" + "="*60)
    print("🎯 OPPORTUNITIES & INSIGHTS")
    print("="*60)
    
    opportunities = []
    challenges = []
    
    for platform, row in channel_summary.iterrows():
        if row['spend'] == 0:
            continue
            
        roas = row['roas']
        cac = row['cac_1st_time'] if row['cac_1st_time'] > 0 else row['cac']
        spend = row['spend']
        
        # Identify high-performing channels (good candidates for scaling)
        if roas > 2.5 and spend > 1000:
            opportunities.append(f"🚀 SCALE UP: {platform} - Strong ROAS ({roas:.2f}) with significant spend (${spend:,.2f})")
        elif roas > 3.0 and spend < 1000:
            opportunities.append(f"💰 POTENTIAL: {platform} - Excellent ROAS ({roas:.2f}) but low spend (${spend:,.2f}) - consider increasing budget")
        
        # Identify underperforming channels
        if roas < 1.0 and spend > 500:
            challenges.append(f"⚠️ UNDERPERFORMING: {platform} - Poor ROAS ({roas:.2f}) with ${spend:,.2f} spend - needs optimization or pause")
        elif cac > 500 and roas > 0:
            challenges.append(f"💸 HIGH CAC: {platform} - CAC of ${cac:.2f} may be unsustainable")
    
    print("\n🌟 OPPORTUNITIES:")
    for opp in opportunities[:5]:  # Top 5 opportunities
        print(f"  {opp}")
    
    print("\n⚠️ CHALLENGES:")
    for challenge in challenges[:5]:  # Top 5 challenges
        print(f"  {challenge}")
    
    if not opportunities:
        print("  📊 Consider testing new channels or optimizing existing campaigns")
    
    if not challenges:
        print("  ✅ No major performance issues identified")

def main():
    """Main analysis function"""
    print("HigherDOSE Weekly Growth Report Analysis")
    print("Data Period: 7-Day Performance Review")
    print(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Load data
    df = load_and_clean_data()
    if df is None:
        return
    
    # Print basic data info
    print(f"📋 Data Overview:")
    print(f"   • Total rows: {len(df):,}")
    print(f"   • Date range: {df['accounting_mode'].value_counts()}")
    print(f"   • Platforms: {df['breakdown_platform_northbeam'].nunique()}")
    print(f"   • Campaigns: {df['campaign_name'].nunique()}")
    
    # Run analyses
    channel_summary = analyze_channel_performance(df)
    if len(channel_summary) > 0:
        executive_metrics = generate_executive_summary(channel_summary)
        campaign_analysis = analyze_campaign_performance(df)
        first_time_metrics = analyze_first_time_metrics(df)
        analyze_attribution_modes(df)
        identify_opportunities(channel_summary)
    
    print("\n" + "="*60)
    print("✅ ANALYSIS COMPLETE")
    print("="*60)
    print("📄 Use these insights to populate your weekly growth report template")

if __name__ == "__main__":
    main() 