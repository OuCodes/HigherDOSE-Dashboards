#!/usr/bin/env python3
"""
HigherDOSE Weekly Growth Report Analysis
Analysis of 7-day sales data for weekly performance reporting
"""

from datetime import datetime

import pandas as pd
import numpy as np
from utils.io.file_selector import select_csv_file

def load_and_clean_data():
    """Load and clean the 7-day sales data"""
    # Interactive file selection
    csv_file = select_csv_file(
        directory="stats",
        file_pattern="*.csv",
        prompt_message="\nSelect CSV file for weekly analysis: "
    )
    if not csv_file:
        print("No file selected. Exiting.")
        return None
    
    try:
        df = pd.read_csv(csv_file)
        print(f"✅ Successfully loaded data with {len(df)} rows")
        
        # Clean and convert numeric columns
        numeric_cols = ['spend', 'cac', 'cac_1st_time', 'roas', 'roas_1st_time', 
                       'aov', 'aov_1st_time', 'ecr', 'ecr_1st_time', 'ecpnv',
                       'platformreported_cac', 'platformreported_roas', 
                       'new_customer_percentage', 'attributed_rev', 'attributed_rev_1st_time',
                       'transactions', 'transactions_1st_time', 'visits',
                       'web_revenue', 'web_transactions']
        
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Fill NaN values with 0 for analysis
        df = df.fillna(0)

        # -------------------------------------------------------------
        # Fallback for channels that only report cash-style web metrics
        # (e.g., AWIN, ShopMyShelf).  If a row has spend plus positive
        # web_revenue but zero attributed revenue, promote the web_*  
        # figures so that downstream ROAS / CAC calculations are
        # meaningful and the campaign isn't shown as all-zeros.
        # -------------------------------------------------------------
        if {'web_revenue', 'web_transactions'}.issubset(df.columns):
            mask_web_only = (df['attributed_rev'] == 0) & (df['web_revenue'] > 0)

            if mask_web_only.any():
                # Promote web revenue/transactions into attributed cols
                df.loc[mask_web_only, 'attributed_rev'] = df.loc[mask_web_only, 'web_revenue']

                # Assume all web revenue is first-time revenue if first-time column exists
                if 'attributed_rev_1st_time' in df.columns:
                    df.loc[mask_web_only, 'attributed_rev_1st_time'] = df.loc[mask_web_only, 'web_revenue']

                # Same for transactions
                if 'transactions' in df.columns:
                    df.loc[mask_web_only, 'transactions'] = df.loc[mask_web_only, 'web_transactions']
                if 'transactions_1st_time' in df.columns:
                    df.loc[mask_web_only, 'transactions_1st_time'] = df.loc[mask_web_only, 'web_transactions']

                # Optional flag for auditing
                df.loc[mask_web_only, 'used_web_metrics'] = True
                print(f"ℹ️  Applied web-metric fallback for {mask_web_only.sum()} rows (AWIN / ShopMyShelf etc.)")
            else:
                df['used_web_metrics'] = False

        # -------------------------------------------------------------
        # Ensure the dataset has the required platform column expected
        # throughout the rest of this script.  Northbeam occasionally
        # changes the column nomenclature (e.g., 'platform', 'channel',
        # 'breakdown_platform').  If the canonical
        # 'breakdown_platform_northbeam' column is absent, look for a
        # known alternative and copy / rename it.  If none are present
        # create a placeholder so downstream code does not crash.
        # -------------------------------------------------------------
        REQUIRED_PLATFORM_COL = 'breakdown_platform_northbeam'
        if REQUIRED_PLATFORM_COL not in df.columns:
            alternative_cols = ['platform', 'channel', 'breakdown_platform']
            found = False
            for alt in alternative_cols:
                if alt in df.columns:
                    df[REQUIRED_PLATFORM_COL] = df[alt]
                    print(f"ℹ️  Mapped column '{alt}' -> '{REQUIRED_PLATFORM_COL}' for compatibility")
                    found = True
                    break

            if not found:
                # Fallback – create a placeholder so groupby operations
                # continue to work without raising KeyError.
                print("⚠️  No platform column found. Inserting placeholder 'Unknown'.")
                df[REQUIRED_PLATFORM_COL] = 'Unknown'
 
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

    # Identify campaigns with $0 spend but meaningful revenue (e.g., email/SMS, affiliate)
    revenue_only = accrual_df[(accrual_df['spend'] == 0) & (accrual_df['attributed_rev'] > 0)].copy()

    # Compute AOV for revenue_only rows (transactions may be fractional)
    if not revenue_only.empty:
        revenue_only['aov'] = revenue_only.apply(
            lambda r: (r['attributed_rev'] / r['transactions']) if r['transactions'] else 0, axis=1
        )
    
    if len(significant_campaigns) == 0:
        print("⚠️ No campaigns with significant spend found")
        return {}
    
    # Calculate performance metrics
    significant_campaigns['roas'] = (significant_campaigns['attributed_rev'] / significant_campaigns['spend']).replace([np.inf], 0)
    significant_campaigns['cac'] = (significant_campaigns['spend'] / significant_campaigns['transactions']).replace([np.inf], 0)
    # First-time CAC (cost per first-time customer)
    if 'transactions_1st_time' in significant_campaigns.columns:
        significant_campaigns['cac_1st_time'] = (
            significant_campaigns['spend'] / significant_campaigns['transactions_1st_time']
        ).replace([np.inf], 0)
    else:
        significant_campaigns['cac_1st_time'] = 0
    significant_campaigns['aov'] = (significant_campaigns['attributed_rev'] / significant_campaigns['transactions']).replace([np.inf], 0)
    # First-time AOV (average order value for first-time customers)
    if 'attributed_rev_1st_time' in significant_campaigns.columns and 'transactions_1st_time' in significant_campaigns.columns:
        significant_campaigns['aov_1st_time'] = (
            significant_campaigns['attributed_rev_1st_time'] / significant_campaigns['transactions_1st_time']
        ).replace([np.inf], 0)
    else:
        significant_campaigns['aov_1st_time'] = 0
    # First-time ROAS at campaign level
    if 'attributed_rev_1st_time' in significant_campaigns.columns:
        significant_campaigns['roas_1st_time'] = (
            significant_campaigns['attributed_rev_1st_time'] / significant_campaigns['spend']
        ).replace([np.inf], 0)
    else:
        significant_campaigns['roas_1st_time'] = 0
    
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
    
    return significant_campaigns, revenue_only

def analyze_first_time_metrics(df):
    """Analyze first-time customer metrics by channel (Accrual performance only)"""
    print("\n" + "=" * 60)
    print("👥 FIRST-TIME CUSTOMER METRICS BY CHANNEL")
    print("=" * 60)

    # Use only Accrual performance rows to avoid double-counting spend / transactions
    accrual_df = df[df['accounting_mode'] == 'Accrual performance'].copy()

    if len(accrual_df) == 0:
        print("⚠️ No Accrual Performance data found")
        return {}

    # Aggregate sums needed for metric calculations
    grouped = accrual_df.groupby('breakdown_platform_northbeam').agg({
        'spend': 'sum',
        'attributed_rev_1st_time': 'sum',
        'transactions_1st_time': 'sum'
    })

    # Calculate metrics in accordance with definitions (Accrual mode)
    grouped['cac_1st_time'] = (grouped['spend'] / grouped['transactions_1st_time']).replace([np.inf], 0)
    grouped['roas_1st_time'] = (grouped['attributed_rev_1st_time'] / grouped['spend']).replace([np.inf], 0)
    grouped['aov_1st_time'] = (grouped['attributed_rev_1st_time'] / grouped['transactions_1st_time']).replace([np.inf], 0)

    # Round for tidy output
    first_time_metrics = grouped.round(2).sort_values('spend', ascending=False)

    print("\nTOP CHANNELS ‑ FIRST-TIME CUSTOMER METRICS:")
    print("-" * 100)
    for platform, row in first_time_metrics.head(10).iterrows():
        if row['spend'] > 100:  # Only show channels with significant spend
            print(
                f"{platform:<15} | CAC 1st: ${row['cac_1st_time']:>7.2f} | "
                f"ROAS 1st: {row['roas_1st_time']:>5.2f} | "
                f"AOV 1st: ${row['aov_1st_time']:>7.2f} | "
                f"Spend: ${row['spend']:>8.2f}"
            )

    return first_time_metrics

def generate_executive_summary(channel_summary):
    """Generate executive summary metrics"""
    print("\n" + "="*60)
    print("📈 EXECUTIVE SUMMARY METRICS")
    print("="*60)
    
    # Total performance across all channels
    total_spend = channel_summary['spend'].sum()
    total_revenue = channel_summary['attributed_rev'].sum()
    total_revenue_1st_time = channel_summary['attributed_rev_1st_time'].sum()
    total_transactions = channel_summary['transactions'].sum()
    total_visits = channel_summary['visits'].sum()
    
    overall_roas = total_revenue / total_spend if total_spend > 0 else 0
    overall_roas_1st_time = total_revenue_1st_time / total_spend if total_spend > 0 else 0
    overall_cac = total_spend / total_transactions if total_transactions > 0 else 0
    overall_aov = total_revenue / total_transactions if total_transactions > 0 else 0
    overall_ecr = total_transactions / total_visits if total_visits > 0 else 0
    
    print(f"💰 Total Spend: ${total_spend:,.2f}")
    print(f"💵 Total Revenue: ${total_revenue:,.2f}")
    print(f"🎯 Overall ROAS: {overall_roas:.2f} (First-Time: {overall_roas_1st_time:.2f})")
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
        'overall_roas_1st_time': overall_roas_1st_time,
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
        roas1 = row['roas_1st_time']
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

def export_markdown_report(executive_metrics, channel_summary, campaign_analysis, revenue_only_df, first_time_metrics):
    """Generate a markdown report string from the computed metrics"""
    lines = []
    report_date = datetime.now().strftime('%Y-%m-%d')

    # --- Front-matter & title ---
    lines.append("---")
    lines.append(f"title: \"Weekly Growth Report\"")
    lines.append(f"description: \"Weekly Growth Report for HigherDOSE covering 7-day performance period ending {report_date}\"")
    lines.append("recipient: \"Ingrid\"")
    lines.append("report_type: \"Weekly Growth Report\"")
    lines.append(f"date: \"{report_date}\"")
    lines.append("period: \"7-Day Review\"")
    lines.append("---\n")

    lines.append(f"# Weekly Growth Report — {report_date}\n\n---\n")

    # 1. Executive Summary
    lines.append("## 1. Executive Summary\n")
    total_spend = executive_metrics['total_spend']
    total_revenue = executive_metrics['total_revenue']
    overall_roas = executive_metrics['overall_roas']
    overall_roas_1st_time = executive_metrics['overall_roas_1st_time']
    overall_cac = executive_metrics['overall_cac']

    # --- Paid-media aggregates (channels with spend > 0) ---
    paid_df_exec = channel_summary[channel_summary['spend'] > 0]
    paid_spend_exec = paid_df_exec['spend'].sum()
    paid_revenue_exec = paid_df_exec['attributed_rev'].sum()
    paid_transactions_exec = paid_df_exec['transactions'].sum()
    paid_roas_exec = paid_revenue_exec / paid_spend_exec if paid_spend_exec else 0
    paid_cac_exec = paid_spend_exec / paid_transactions_exec if paid_transactions_exec else 0

    lines.append(
        f"**Overall Performance**: Total DTC spend reached **${total_spend:,.0f}** across all channels with **{overall_roas:.2f} ROAS**, "
        f"generating **${total_revenue:,.0f}** in revenue and blended **CAC of ${overall_cac:,.2f}**. "
        f"Paid Media delivered **${paid_revenue_exec:,.0f}** revenue at **{paid_roas_exec:.2f} ROAS** with **CAC of ${paid_cac_exec:,.2f}**, across **{int(paid_transactions_exec)} transactions**. "
        f"The business achieved **{int(executive_metrics['total_transactions'])} total transactions** during this 7-day period.\n\n"
    )

    # 2. Channel Performance table (top 10 by spend)
    lines.append("## 2. DTC Performance — 7-Day Snapshot (Northbeam)\n")
    headers = [
        "Channel",
        "Period Spend",
        "% of Total",
        "CAC",
        "CAC 1st",
        "ROAS",
        "ROAS 1st",
        "AOV",
        "Transactions",
        "Revenue",
    ]
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["-" * len(h) for h in headers]) + "|")

    total_transactions = executive_metrics['total_transactions']
    # Add All row first
    overall_cac_1st = (
        total_spend / channel_summary['transactions_1st_time'].sum()
        if channel_summary['transactions_1st_time'].sum() > 0
        else 0
    )
    lines.append(
        f"| **All DTC** | **${total_spend:,.0f}** | **100%** | **${overall_cac:,.2f}** | **${overall_cac_1st:.2f}** | **{overall_roas:.2f}** | **{executive_metrics['overall_roas_1st_time']:.2f}** | **${executive_metrics['overall_aov']:.0f}** | **{int(total_transactions)}** | **${total_revenue:,.0f}** |")

    # NEW: Aggregate paid-media-only metrics (channels with spend > 0)
    paid_df = channel_summary[channel_summary['spend'] > 0]
    if not paid_df.empty:
        paid_spend = paid_df['spend'].sum()
        paid_revenue = paid_df['attributed_rev'].sum()
        paid_revenue_1st = paid_df['attributed_rev_1st_time'].sum()
        paid_transactions = paid_df['transactions'].sum()
        paid_transactions_1st = paid_df['transactions_1st_time'].sum()
        paid_roas = paid_revenue / paid_spend if paid_spend else 0
        paid_roas_1st = paid_revenue_1st / paid_spend if paid_spend else 0
        paid_cac = paid_spend / paid_transactions if paid_transactions else 0
        paid_cac_1st = paid_spend / paid_transactions_1st if paid_transactions_1st else 0
        paid_aov = paid_revenue / paid_transactions if paid_transactions else 0
        percent_total_paid = paid_spend / total_spend * 100 if total_spend > 0 else 0
        lines.append(
            f"| **Paid Media** | ${paid_spend:,.0f} | {percent_total_paid:.1f}% | ${paid_cac:.2f} | ${paid_cac_1st:.2f} | {paid_roas:.2f} | {paid_roas_1st:.2f} | ${paid_aov:,.0f} | {int(paid_transactions)} | ${paid_revenue:,.0f} |")

    # Prepare top channels
    total_spend_safe = total_spend if total_spend != 0 else 1  # prevent div 0
    for platform, row in channel_summary.iterrows():
        spend = row['spend']
        if spend <= 0:
            continue
        percent_total = spend / total_spend_safe * 100
        cac = row['cac']
        cac1 = row['cac_1st_time']
        roas = row['roas']
        roas1 = row['roas_1st_time']
        aov = row['aov']
        transactions = row['transactions']
        revenue = row['attributed_rev']
        lines.append(
            f"| {platform} | ${spend:,.0f} | {percent_total:.1f}% | ${cac:,.2f} | ${cac1:.2f} | {roas:.2f} | {roas1:.2f} | ${aov:,.0f} | {int(transactions)} | ${revenue:,.0f} |")

    lines.append("\n---\n")

    # 3. Top Campaigns by ROAS & Spend
    if not campaign_analysis.empty:
        lines.append("## 3. Top Campaign Performance Analysis\n")
        # Top campaign by ROAS for each channel (ensures representation across platforms)
        # 1. Identify the campaign with the highest ROAS within each platform
        # Exclude campaigns with zero ROAS before selecting winners
        subset_roas = campaign_analysis[campaign_analysis['roas'] > 0]

        idx = (
            subset_roas
            .groupby('breakdown_platform_northbeam')['roas']
            .idxmax()
        )

        top_roas = (
            subset_roas.loc[idx]
            .sort_values('roas', ascending=False)
        )
        # Optional: If the list is very long, you can limit to the top N overall while still preserving one per channel
        # top_roas = top_roas.head(10)  # Uncomment to limit rows in the report
        lines.append("### 🏆 Best Performing Campaigns by ROAS\n")
        headers2 = ["Platform", "Campaign Name", "ROAS", "ROAS 1st", "CAC", "CAC 1st", "AOV", "AOV 1st", "Spend", "Revenue"]
        lines.append("| " + " | ".join(headers2) + " |")
        lines.append("|" + "|".join(["-" * len(h) for h in headers2]) + "|")
        for _, row in top_roas.iterrows():
            platform = row['breakdown_platform_northbeam']
            campaign = row['campaign_name'][:50].replace('|', '\\|')
            roas_val = row['roas']
            spend_val = row['spend']
            rev_val = row['attributed_rev']
            roas1_val = row.get('roas_1st_time', 0)
            cac_val = row.get('cac', 0)
            cac1_val = row.get('cac_1st_time', 0)
            aov_val = row.get('aov', 0)
            aov1_val = row.get('aov_1st_time', 0)
            lines.append(f"| {platform} | **{campaign}** | **{roas_val:.2f}** | {roas1_val:.2f} | ${cac_val:.2f} | ${cac1_val:.2f} | ${aov_val:.2f} | ${aov1_val:.2f} | ${spend_val:,.0f} | ${rev_val:,.0f} |")

        # Top 5 by Spend
        top_spend = campaign_analysis.sort_values('spend', ascending=False).head(5)
        lines.append("\n### 💰 Highest Spend Campaigns\n")
        headers3 = ["Platform", "Campaign Name", "Spend", "ROAS", "ROAS 1st", "CAC", "CAC 1st", "AOV", "AOV 1st", "Revenue"]
        lines.append("| " + " | ".join(headers3) + " |")
        lines.append("|" + "|".join(["-" * len(h) for h in headers3]) + "|")
        for _, row in top_spend.iterrows():
            platform = row['breakdown_platform_northbeam']
            campaign = row['campaign_name'][:50].replace('|', '\\|')
            spend_val = row['spend']
            roas_val = row['roas']
            roas1_val = row.get('roas_1st_time', 0)
            cac_val = row.get('cac', 0)
            cac1_val = row.get('cac_1st_time', 0)
            aov_val = row.get('aov', 0)
            aov1_val = row.get('aov_1st_time', 0)
            rev_val = row['attributed_rev']
            lines.append(f"| {platform} | **{campaign}** | ${spend_val:,.0f} | {roas_val:.2f} | {roas1_val:.2f} | ${cac_val:.2f} | ${cac1_val:.2f} | ${aov_val:.2f} | ${aov1_val:.2f} | ${rev_val:,.0f} |")

        # Zero-Spend but Revenue campaigns
        # Revenue-only table – drop low-signal placeholder platforms and keep one per channel
        exclude_platforms = {"Untattributed", "Excluded", "(not set)"}
        rev_filtered = revenue_only_df[~revenue_only_df['breakdown_platform_northbeam'].isin(exclude_platforms)]

        if not rev_filtered.empty:
            idx_rev = rev_filtered.groupby('breakdown_platform_northbeam')['attributed_rev'].idxmax()
            top_rev = rev_filtered.loc[idx_rev].sort_values('attributed_rev', ascending=False)

            # Limit to top 10 channels
            top_rev = top_rev.head(10)

            lines.append("\n### 📧 Revenue-Only Campaigns ($0 Spend)\n")
            headers0 = ["Platform", "Campaign Name", "Revenue", "Transactions", "AOV"]
            lines.append("| " + " | ".join(headers0) + " |")
            lines.append("|" + "|".join(["-" * len(h) for h in headers0]) + "|")
            for _, row in top_rev.iterrows():
                platform = row['breakdown_platform_northbeam']
                campaign = row['campaign_name'][:50].replace('|','\\|')
                revenue = row['attributed_rev']
                txns = row['transactions']
                aov = row.get('aov', 0)
                lines.append(f"| {platform} | **{campaign}** | ${revenue:,.0f} | {txns:.2f} | ${aov:.2f} |")

    # 4. Channel Performance Metrics (overall, not first-time)
    if isinstance(channel_summary, pd.DataFrame) and not channel_summary.empty:
        lines.append("\n## 4. Channel Performance Metrics\n")
        headers_g = ["Channel", "Spend", "Revenue", "CAC", "ROAS", "AOV", "Transactions"]
        lines.append("| " + " | ".join(headers_g) + " |")
        lines.append("|" + "|".join(["-" * len(h) for h in headers_g]) + "|")

        # Combine spend-priority and revenue-priority ordering
        high_spend = channel_summary[channel_summary['spend'] > 0].copy()
        high_spend = high_spend.sort_values('spend', ascending=False)

        rev_only = channel_summary[channel_summary['spend'] == 0].copy()
        rev_only = rev_only.sort_values('attributed_rev', ascending=False)

        combined = pd.concat([high_spend, rev_only])

        for platform, row in combined.iterrows():
            spend = row['spend']
            revenue = row['attributed_rev']
            cac = row['cac']
            roas_val = row['roas']
            aov_val = row['aov']
            txns = row['transactions']
            lines.append(f"| {platform} | ${spend:,.0f} | ${revenue:,.0f} | ${cac:.2f} | {roas_val:.2f} | ${aov_val:.2f} | {int(txns)} |")

    lines.append("\n---\n")
    lines.append(f"**Report Compiled**: {report_date}\n")

    return "\n".join(lines)


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
        campaign_analysis, revenue_only_df = analyze_campaign_performance(df)
        first_time_metrics = analyze_first_time_metrics(df)
        analyze_attribution_modes(df)
        identify_opportunities(channel_summary)

        # Export markdown report
        markdown_report = export_markdown_report(executive_metrics, channel_summary, campaign_analysis, revenue_only_df, first_time_metrics)
        report_filename = f"weekly-growth-report-{datetime.now().strftime('%Y-%m-%d')}.md"
        with open(report_filename, "w") as md_file:
            md_file.write(markdown_report)
        print(f"📝 Markdown report saved to {report_filename}")
    
    print("\n" + "="*60)
    print("✅ ANALYSIS COMPLETE")
    print("="*60)
    print("📄 Use these insights to populate your weekly growth report template")

if __name__ == "__main__":
    main() 