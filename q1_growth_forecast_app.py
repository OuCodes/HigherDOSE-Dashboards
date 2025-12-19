#!/usr/bin/env python3
"""
Q1 Growth & Forecast Dashboard
2024 vs 2025 Q1 Analysis with 20% Growth Targets for 2026

Data files: northbeam_style_daily_2024-2025_12_19.csv & northbeam_2025_ytd_spend_daily.csv
Updated: Dec 19, 2025 - Corrected 2024 spend (fixed affiliate double-counting)
Jan 2024: $761,785 (was $889,928) - All Q1 months corrected
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Q1 Growth & Forecast | HigherDOSE",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Paths
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
ADS_DIR = DATA_DIR / "ads"

def load_all_data_v2_dec19():
    """Load 2024 + 2025 sales and spend data - CORRECTED VERSION
    
    NO CACHE - Direct load from Historical Spend CSV
    Version: 2025-12-19 - Fixed affiliate double-counting bug
    """
    
    # === 2024 Sales (Total Sales + Real Revenue) ===
    sales_2024_file = ADS_DIR / "exec-sum" / "Total sales over time - 2024-01-01 - 2024-12-31-DAILY.csv"
    sales_2024 = pd.read_csv(sales_2024_file)
    sales_2024['Day'] = pd.to_datetime(sales_2024['Day'])
    sales_2024 = sales_2024.rename(columns={'Day': 'date', 'Total sales': 'revenue', 'Orders': 'orders'})
    sales_2024['year'] = 2024
    
    # Load Real Revenue for 2024 from daily aggregated CSV (or Historical Spend CSV as fallback)
    real_rev_2024_file = ADS_DIR / "exec-sum" / "real-revenue-daily-2024-q1.csv"
    if real_rev_2024_file.exists():
        st.sidebar.write(f"📊 Loading 2024 Real Revenue from {real_rev_2024_file.name}")
        real_2024_daily = pd.read_csv(real_rev_2024_file)
        real_2024_daily['date'] = pd.to_datetime(real_2024_daily['date'])
        # Merge with sales data - rename orders column to avoid conflict
        real_2024_daily = real_2024_daily.rename(columns={'orders': 'real_revenue_orders'})
        sales_2024 = sales_2024.merge(real_2024_daily[['date', 'real_revenue', 'real_revenue_orders']], on='date', how='left')
        sales_2024['real_revenue'] = sales_2024['real_revenue'].fillna(0)
        sales_2024['real_revenue_orders'] = sales_2024['real_revenue_orders'].fillna(0)
        st.sidebar.write(f"✓ Loaded {len(real_2024_daily)} days of Real Revenue data")
    else:
        st.sidebar.info("ℹ️ Using Historical Spend CSV for 2024 Real Revenue (monthly totals)")
        sales_2024['real_revenue'] = 0  # Will be populated from Historical Spend CSV below
        sales_2024['real_revenue_orders'] = 0
    
    # === 2025 Sales (Total Sales + Real Revenue) ===
    # Find latest 2025 sales file
    sales_2025_files = sorted((ADS_DIR / "exec-sum").glob("Total sales over time - OU - 2025-*.csv"))
    if not sales_2025_files:
        st.error("No 2025 sales file found")
        return None
    
    sales_2025_file = sales_2025_files[-1]
    sales_2025 = pd.read_csv(sales_2025_file)
    sales_2025['Day'] = pd.to_datetime(sales_2025['Day'])
    sales_2025 = sales_2025.rename(columns={'Day': 'date', 'Total sales': 'revenue', 'Orders': 'orders'})
    sales_2025['year'] = 2025
    
    # Load Real Revenue for 2025 from daily aggregated CSV (or Historical Spend CSV as fallback)
    real_rev_2025_file = ADS_DIR / "exec-sum" / "real-revenue-daily-2025-q1.csv"
    if real_rev_2025_file.exists():
        st.sidebar.write(f"📊 Loading 2025 Real Revenue from {real_rev_2025_file.name}")
        real_2025_daily = pd.read_csv(real_rev_2025_file)
        real_2025_daily['date'] = pd.to_datetime(real_2025_daily['date'])
        # Merge with sales data - rename orders column to avoid conflict
        real_2025_daily = real_2025_daily.rename(columns={'orders': 'real_revenue_orders'})
        sales_2025 = sales_2025.merge(real_2025_daily[['date', 'real_revenue', 'real_revenue_orders']], on='date', how='left')
        sales_2025['real_revenue'] = sales_2025['real_revenue'].fillna(0)
        sales_2025['real_revenue_orders'] = sales_2025['real_revenue_orders'].fillna(0)
        st.sidebar.write(f"✓ Loaded {len(real_2025_daily)} days of Real Revenue data")
    else:
        st.sidebar.info("ℹ️ Using Historical Spend CSV for 2025 Real Revenue (monthly totals)")
        sales_2025['real_revenue'] = 0  # Will be populated from Historical Spend CSV below
        sales_2025['real_revenue_orders'] = 0
    
    # === 2024 & 2025 Spend - Load from Historical Spend CSV directly ===
    st.sidebar.write("🔍 Loading spend data from Historical CSV...")
    
    historical_file = ADS_DIR / "q4-planning-2025" / "Historical Spend.csv"
    st.sidebar.write(f"Looking for: {historical_file}")
    st.sidebar.write(f"File exists: {historical_file.exists()}")
    
    if not historical_file.exists():
        st.error(f"❌ Historical Spend CSV not found at: {historical_file}")
        st.error(f"ADS_DIR = {ADS_DIR}")
        st.error(f"Files in q4-planning-2025: {list((ADS_DIR / 'q4-planning-2025').glob('*.csv')) if (ADS_DIR / 'q4-planning-2025').exists() else 'Directory does not exist'}")
        return None
    
    try:
        # Load historical spend data
        hist_df = pd.read_csv(historical_file)
        st.sidebar.write(f"✅ Loaded {len(hist_df)} rows from Historical CSV")
        
        def clean_currency(val):
            if pd.isna(val) or val == '' or val == '–':
                return 0.0
            return float(str(val).replace('$', '').replace(',', ''))
        
        # Extract Real Revenue from Historical CSV (for fallback or supplementing data)
        real_revenue_lookup = {}
        for _, row in hist_df.iterrows():
            if pd.notna(row['Month']):
                month_str = str(row['Month'])
                real_rev = clean_currency(row.get('Real\nRevenue(1)', 0))
                if real_rev > 0:
                    real_revenue_lookup[month_str] = real_rev
        
        st.sidebar.write(f"📊 Real Revenue lookup: {len(real_revenue_lookup)} months")
        
        # Process 2024 data
        hist_2024 = hist_df[hist_df['Month'].str.contains('24', na=False)].copy()
        hist_2024['month_date'] = pd.to_datetime(hist_2024['Month'], format='%b-%y')
        st.sidebar.write(f"✅ Found {len(hist_2024)} months for 2024")
        
        spend_2024_monthly = []
        for _, row in hist_2024.iterrows():
            month_date = row['month_date']
            month_str = row['Month']
            total_spend = clean_currency(row.get('Total Spend', 0))
            real_rev_monthly = real_revenue_lookup.get(month_str, 0)
            
            if total_spend > 0 or real_rev_monthly > 0:
                days_in_month = pd.date_range(
                    start=month_date,
                    end=month_date + pd.offsets.MonthEnd(1),
                    freq='D'
                )
                daily_spend = total_spend / len(days_in_month)
                daily_real_rev = real_rev_monthly / len(days_in_month)
                
                for day in days_in_month:
                    spend_2024_monthly.append({
                        'date': day,
                        'spend': daily_spend,
                        'real_revenue_hist': daily_real_rev
                    })
        
        spend_2024_daily = pd.DataFrame(spend_2024_monthly)
        spend_2024_daily['year'] = 2024
        
        # Process 2025 data
        hist_2025 = hist_df[hist_df['Month'].str.contains('25', na=False)].copy()
        hist_2025['month_date'] = pd.to_datetime(hist_2025['Month'], format='%b-%y')
        st.sidebar.write(f"✅ Found {len(hist_2025)} months for 2025")
        
        spend_2025_monthly = []
        for _, row in hist_2025.iterrows():
            month_date = row['month_date']
            month_str = row['Month']
            total_spend = clean_currency(row.get('Total Spend', 0))
            real_rev_monthly = real_revenue_lookup.get(month_str, 0)
            
            if total_spend > 0 or real_rev_monthly > 0:
                days_in_month = pd.date_range(
                    start=month_date,
                    end=month_date + pd.offsets.MonthEnd(1),
                    freq='D'
                )
                daily_spend = total_spend / len(days_in_month)
                daily_real_rev = real_rev_monthly / len(days_in_month)
                
                for day in days_in_month:
                    spend_2025_monthly.append({
                        'date': day,
                        'spend': daily_spend,
                        'real_revenue_hist': daily_real_rev
                    })
        
        spend_2025_daily = pd.DataFrame(spend_2025_monthly)
        spend_2025_daily['year'] = 2025
        
        # Debug: Show January totals
        jan_2024_check = spend_2024_daily[
            (spend_2024_daily['date'] >= '2024-01-01') & 
            (spend_2024_daily['date'] <= '2024-01-31')
        ]['spend'].sum()
        
        jan_2025_check = spend_2025_daily[
            (spend_2025_daily['date'] >= '2025-01-01') & 
            (spend_2025_daily['date'] <= '2025-01-31')
        ]['spend'].sum()
        
        st.sidebar.success(f"✅ Historical Spend CSV loaded")
        st.sidebar.metric("Jan 2024 Spend", f"${jan_2024_check:,.0f}")
        st.sidebar.metric("Jan 2025 Spend", f"${jan_2025_check:,.0f}")
        
    except Exception as e:
        st.error(f"❌ ERROR loading Historical Spend CSV: {e}")
        import traceback
        st.error(traceback.format_exc())
        return None
    
    # === Merge sales + spend + real revenue for each year ===
    df_2024 = sales_2024.merge(spend_2024_daily[['date', 'spend', 'real_revenue_hist']], on='date', how='left')
    df_2024['spend'] = df_2024['spend'].fillna(0)
    # If real_revenue is 0 (file not found), use Historical Spend CSV fallback
    if df_2024['real_revenue'].sum() == 0:
        df_2024['real_revenue'] = df_2024['real_revenue_hist'].fillna(0)
        st.sidebar.info("✓ Using Historical Spend CSV Real Revenue for 2024")
    df_2024['MER'] = df_2024.apply(lambda x: x['revenue'] / x['spend'] if x['spend'] > 0 else 0, axis=1)
    
    # Debug: Show 2025 spend info
    total_2025_spend = spend_2025_daily['spend'].sum()
    
    df_2025 = sales_2025.merge(spend_2025_daily[['date', 'spend', 'real_revenue_hist']], 
                               on='date', how='left')
    df_2025['spend'] = df_2025['spend'].fillna(0)
    # If real_revenue is 0 (file not found), use Historical Spend CSV fallback
    if df_2025['real_revenue'].sum() == 0:
        df_2025['real_revenue'] = df_2025['real_revenue_hist'].fillna(0)
        st.sidebar.info("✓ Using Historical Spend CSV Real Revenue for 2025")
    df_2025['MER'] = df_2025.apply(lambda x: x['revenue'] / x['spend'] if x['spend'] > 0 else 0, axis=1)
    
    # Show warning if spend data is limited
    days_with_spend = (df_2025['spend'] > 0).sum()
    total_days = len(df_2025)
    
    # Add quarter and month columns
    for df in [df_2024, df_2025]:
        df['quarter'] = df['date'].dt.quarter
        df['month'] = df['date'].dt.month
        df['month_name'] = df['date'].dt.strftime('%B')
        df['day_of_month'] = df['date'].dt.day
    
    # Filter to Q1 only for main analysis
    q1_2024 = df_2024[df_2024['quarter'] == 1].copy()
    q1_2025 = df_2025[df_2025['quarter'] == 1].copy()
    
    # === 2024 Product Sales ===
    product_2024_file = ADS_DIR / "exec-sum" / "Total sales by product - 2024-01-01 - 2024-12-31.csv"
    products_2024 = pd.read_csv(product_2024_file)
    products_2024['Day'] = pd.to_datetime(products_2024['Day'])
    products_2024 = products_2024.rename(columns={'Day': 'date', 'Product title': 'product', 'Total sales': 'revenue', 'Net items sold': 'units'})
    products_2024['year'] = 2024
    products_2024['quarter'] = products_2024['date'].dt.quarter
    
    # === 2025 Product Sales ===
    product_2025_files = sorted((ADS_DIR / "exec-sum").glob("Total sales by product - OU - 2025-*.csv"))
    if product_2025_files:
        product_2025_file = product_2025_files[-1]
        products_2025 = pd.read_csv(product_2025_file)
        products_2025['Day'] = pd.to_datetime(products_2025['Day'])
        products_2025 = products_2025.rename(columns={'Day': 'date', 'Product title': 'product', 'Total sales': 'revenue', 'Net items sold': 'units'})
        products_2025['year'] = 2025
        products_2025['quarter'] = products_2025['date'].dt.quarter
    else:
        products_2025 = pd.DataFrame()
    
    # Q1 product aggregates
    q1_products_2024 = products_2024[products_2024['quarter'] == 1].groupby('product').agg({
        'revenue': 'sum',
        'units': 'sum'
    }).reset_index().sort_values('revenue', ascending=False)
    q1_products_2024['year'] = 2024
    
    if not products_2025.empty:
        q1_products_2025 = products_2025[products_2025['quarter'] == 1].groupby('product').agg({
            'revenue': 'sum',
            'units': 'sum'
        }).reset_index().sort_values('revenue', ascending=False)
        q1_products_2025['year'] = 2025
    else:
        q1_products_2025 = pd.DataFrame()
    
    return {
        'df_2024': df_2024,
        'df_2025': df_2025,
        'q1_2024': q1_2024,
        'q1_2025': q1_2025,
        'sales_2025_file': sales_2025_file.name,
        'spend_2024_file': 'Historical Spend CSV (Total Spend column)',
        'spend_2025_file': 'Historical Spend CSV (Total Spend column)',
        'spend_coverage': {
            'days_with_spend': days_with_spend,
            'total_days': total_days,
            'total_spend': total_2025_spend
        },
        'q1_products_2024': q1_products_2024,
        'q1_products_2025': q1_products_2025,
    }

# Load data
try:
    data = load_all_data_v2_dec19()
    if data is None:
        st.stop()
    
    df_2024 = data['df_2024']
    df_2025 = data['df_2025']
    q1_2024 = data['q1_2024']
    q1_2025 = data['q1_2025']
    
    data_loaded = True
except Exception as e:
    st.error(f"Error loading data: {e}")
    data_loaded = False
    st.stop()

# Sidebar
with st.sidebar:
    st.header("📊 Data Sources")
    st.caption(f"**2024 Spend:**\n{data['spend_2024_file']}")
    st.caption(f"**2025 Spend:**\n{data['spend_2025_file']}")
    st.caption(f"**2025 Sales:**\n{data['sales_2025_file']}")
    
    # Show spend coverage warning
    coverage = data.get('spend_coverage', {})
    if coverage and coverage.get('days_with_spend', 0) < coverage.get('total_days', 0):
        st.warning(f"⚠️ 2025 spend: {coverage['days_with_spend']} of {coverage['total_days']} days")
        st.caption(f"Total 2025 spend: ${coverage['total_spend']:,.0f}")
    
    st.markdown("---")
    st.caption(f"**Last Updated:**\n{datetime.now().strftime('%Y-%m-%d %H:%M')}")

# Header
st.title("📈 Q1 Growth & Forecast Dashboard")
st.markdown("**2024 vs 2025 Q1 Analysis with 20% Growth Targets for 2026**")
st.error("🔄 VERSION: 2025-12-19-FINAL | If you see old spend numbers ($889k), hard refresh and clear browser cache")
st.markdown("---")

# === TAB STRUCTURE ===
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Overview", 
    "📈 Q1 YoY Analysis",
    "🛍️ Product Performance", 
    "🎯 2026 Growth Targets",
    "📢 Campaign Analysis",
    "📋 Data & Methodology"
])

# ===== TAB 1: OVERVIEW =====
with tab1:
    st.header("Executive Summary")
    
    # Calculate Q1 metrics for both years
    q1_2024_revenue = q1_2024['revenue'].sum()
    q1_2024_real_revenue = q1_2024['real_revenue'].sum()
    q1_2024_spend = q1_2024['spend'].sum()
    q1_2024_orders = q1_2024['orders'].sum()
    q1_2024_real_revenue_orders = q1_2024['real_revenue_orders'].sum()
    q1_2024_mer = q1_2024_revenue / q1_2024_spend if q1_2024_spend > 0 else 0
    q1_2024_aov = q1_2024_revenue / q1_2024_orders if q1_2024_orders > 0 else 0
    q1_2024_real_aov = q1_2024_real_revenue / q1_2024_real_revenue_orders if q1_2024_real_revenue_orders > 0 else 0
    
    q1_2025_revenue = q1_2025['revenue'].sum()
    q1_2025_real_revenue = q1_2025['real_revenue'].sum()
    q1_2025_spend = q1_2025['spend'].sum()
    q1_2025_orders = q1_2025['orders'].sum()
    q1_2025_real_revenue_orders = q1_2025['real_revenue_orders'].sum()
    q1_2025_mer = q1_2025_revenue / q1_2025_spend if q1_2025_spend > 0 else 0
    q1_2025_aov = q1_2025_revenue / q1_2025_orders if q1_2025_orders > 0 else 0
    q1_2025_real_aov = q1_2025_real_revenue / q1_2025_real_revenue_orders if q1_2025_real_revenue_orders > 0 else 0
    
    # 2026 goals (20% growth)
    q1_2026_goal_revenue = q1_2025_revenue * 1.20
    q1_2026_goal_daily = q1_2026_goal_revenue / 90  # Q1 = 90 days
    q1_2026_goal_real_revenue = q1_2025_real_revenue * 1.20
    q1_2026_goal_real_daily = q1_2026_goal_real_revenue / 90
    
    # YoY deltas
    revenue_delta = q1_2025_revenue - q1_2024_revenue
    revenue_delta_pct = (revenue_delta / q1_2024_revenue * 100) if q1_2024_revenue > 0 else 0
    spend_delta = q1_2025_spend - q1_2024_spend
    spend_delta_pct = (spend_delta / q1_2024_spend * 100) if q1_2024_spend > 0 else 0
    mer_delta = q1_2025_mer - q1_2024_mer
    
    # Total Sales metrics row
    st.subheader("Total Sales (Shopify)")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Q1 2024 Total Sales", f"${q1_2024_revenue:,.0f}")
        st.caption(f"{q1_2024_orders:,.0f} orders | AOV: ${q1_2024_aov:.2f}")
    
    with col2:
        st.metric("Q1 2025 Total Sales", f"${q1_2025_revenue:,.0f}",
                 delta=f"{revenue_delta_pct:+.1f}% YoY")
        aov_delta = ((q1_2025_aov - q1_2024_aov) / q1_2024_aov * 100) if q1_2024_aov > 0 else 0
        st.caption(f"{q1_2025_orders:,.0f} orders | AOV: ${q1_2025_aov:.2f} ({aov_delta:+.1f}%)")
    
    with col3:
        st.metric("Q1 2026 Goal (+20%)", f"${q1_2026_goal_revenue:,.0f}")
        st.caption(f"Daily target: ${q1_2026_goal_daily:,.0f}")
    
    with col4:
        st.metric("Total Sales YoY", f"{revenue_delta_pct:+.1f}%",
                 delta=f"${revenue_delta:,.0f}")
        st.caption(f"Δ from 2024 to 2025")
    
    # Real Revenue metrics row
    st.subheader("Real Revenue")
    st.caption("💡 Real Revenue = Gross sales + Discounts + Shipping (discounts are negative)")
    
    real_revenue_delta = q1_2025_real_revenue - q1_2024_real_revenue
    real_revenue_delta_pct = (real_revenue_delta / q1_2024_real_revenue * 100) if q1_2024_real_revenue > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Q1 2024 Real Revenue", f"${q1_2024_real_revenue:,.0f}")
        st.caption(f"{int(q1_2024_real_revenue_orders):,} orders | AOV: ${q1_2024_real_aov:.2f}")
    
    with col2:
        st.metric("Q1 2025 Real Revenue", f"${q1_2025_real_revenue:,.0f}",
                 delta=f"{real_revenue_delta_pct:+.1f}% YoY")
        aov_delta_pct = ((q1_2025_real_aov - q1_2024_real_aov) / q1_2024_real_aov * 100) if q1_2024_real_aov > 0 else 0
        st.caption(f"{int(q1_2025_real_revenue_orders):,} orders | AOV: ${q1_2025_real_aov:.2f} ({aov_delta_pct:+.1f}%)")
    
    with col3:
        st.metric("Q1 2026 Goal (+20%)", f"${q1_2026_goal_real_revenue:,.0f}")
        st.caption(f"Daily target: ${q1_2026_goal_real_daily:,.0f}")
    
    with col4:
        st.metric("Real Revenue YoY", f"{real_revenue_delta_pct:+.1f}%",
                 delta=f"${real_revenue_delta:,.0f}")
        st.caption("Gross sales growth")
    
    # Spend metrics row
    st.subheader("Spend Performance")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Q1 2024 Spend", f"${q1_2024_spend:,.0f}")
        st.caption(f"Avg daily: ${q1_2024_spend/90:,.0f}")
    
    with col2:
        st.metric("Q1 2025 Spend", f"${q1_2025_spend:,.0f}", 
                 delta=f"{spend_delta_pct:+.1f}% YoY")
        st.caption(f"Avg daily: ${q1_2025_spend/90:,.0f}")
    
    with col3:
        # 2026 spend at maintained MER
        q1_2026_spend_target = q1_2026_goal_revenue / q1_2025_mer if q1_2025_mer > 0 else 0
        st.metric("Q1 2026 Target (3.47x MER)", f"${q1_2026_spend_target:,.0f}")
        st.caption(f"Avg daily: ${q1_2026_spend_target/90:,.0f}")
    
    with col4:
        st.metric("Spend YoY", f"{spend_delta_pct:+.1f}%", 
                 delta=f"${spend_delta:,.0f}")
        st.caption(f"Δ from 2024 to 2025")
    
    # AOV metrics row
    st.subheader("Average Order Value (AOV)")
    col1, col2, col3, col4 = st.columns(4)
    
    q1_2024_aov = q1_2024_revenue / q1_2024_orders if q1_2024_orders > 0 else 0
    q1_2025_aov = q1_2025_revenue / q1_2025_orders if q1_2025_orders > 0 else 0
    aov_delta = q1_2025_aov - q1_2024_aov
    aov_delta_pct = (aov_delta / q1_2024_aov * 100) if q1_2024_aov > 0 else 0
    
    with col1:
        st.metric("Q1 2024 AOV", f"${q1_2024_aov:,.2f}")
        st.caption(f"{q1_2024_orders:,.0f} orders")
    
    with col2:
        st.metric("Q1 2025 AOV", f"${q1_2025_aov:,.2f}", 
                 delta=f"{aov_delta_pct:+.1f}% YoY")
        st.caption(f"{q1_2025_orders:,.0f} orders")
    
    with col3:
        # 2026 AOV (assume same as 2025 for now, or can project based on revenue/order goals)
        q1_2026_orders_target = q1_2025_orders * 1.20  # Assume 20% more orders
        q1_2026_aov_target = q1_2026_goal_revenue / q1_2026_orders_target if q1_2026_orders_target > 0 else q1_2025_aov
        st.metric("Q1 2026 Target", f"${q1_2026_aov_target:,.2f}")
        st.caption(f"Est. {q1_2026_orders_target:,.0f} orders")
    
    with col4:
        st.metric("AOV YoY", f"${aov_delta:+,.2f}",
                 delta=f"{aov_delta_pct:+.1f}%")
        st.caption(f"${q1_2024_aov:,.2f} → ${q1_2025_aov:,.2f}")
    
    # Real AOV metrics row
    st.subheader("Real Revenue AOV")
    st.caption("💡 Real AOV = Real Revenue ÷ Real Revenue Orders")
    col1, col2, col3, col4 = st.columns(4)
    
    real_aov_delta = q1_2025_real_aov - q1_2024_real_aov
    real_aov_delta_pct = (real_aov_delta / q1_2024_real_aov * 100) if q1_2024_real_aov > 0 else 0
    
    with col1:
        st.metric("Q1 2024 Real AOV", f"${q1_2024_real_aov:,.2f}")
        st.caption(f"{int(q1_2024_real_revenue_orders):,} orders")
    
    with col2:
        st.metric("Q1 2025 Real AOV", f"${q1_2025_real_aov:,.2f}",
                 delta=f"{real_aov_delta_pct:+.1f}% YoY")
        st.caption(f"{int(q1_2025_real_revenue_orders):,} orders")
    
    with col3:
        # 2026 Real AOV target (based on 20% revenue growth)
        q1_2026_real_orders_target = q1_2025_real_revenue_orders * 1.20
        q1_2026_real_aov_target = q1_2026_goal_real_revenue / q1_2026_real_orders_target if q1_2026_real_orders_target > 0 else q1_2025_real_aov
        st.metric("Q1 2026 Target", f"${q1_2026_real_aov_target:,.2f}")
        st.caption(f"Est. {int(q1_2026_real_orders_target):,} orders")
    
    with col4:
        st.metric("Real AOV YoY", f"${real_aov_delta:+,.2f}",
                 delta=f"{real_aov_delta_pct:+.1f}%")
        st.caption(f"${q1_2024_real_aov:,.2f} → ${q1_2025_real_aov:,.2f}")
    
    # MER metrics row
    st.subheader("Marketing Efficiency Ratio (MER)")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Q1 2024 MER", f"{q1_2024_mer:.2f}x")
        st.caption(f"{q1_2024_orders:,.0f} orders")
    
    with col2:
        mer_delta_pct = (mer_delta / q1_2024_mer * 100) if q1_2024_mer > 0 else 0
        st.metric("Q1 2025 MER", f"{q1_2025_mer:.2f}x", 
                 delta=f"{mer_delta_pct:+.1f}% YoY")
        st.caption(f"{q1_2025_orders:,.0f} orders")
    
    with col3:
        # 2026 MER target (assume same as 2025 for now)
        st.metric("Q1 2026 Target", f"{q1_2025_mer:.2f}x")
        st.caption("(Maintain efficiency)")
    
    with col4:
        st.metric("MER YoY", f"{mer_delta:+.2f}x", 
                 delta=f"{mer_delta_pct:+.1f}%")
        st.caption(f"{q1_2024_mer:.2f}x → {q1_2025_mer:.2f}x")
    
    st.markdown("---")
    
    # Callout boxes
    col1, col2 = st.columns(2)
    
    with col1:
        if revenue_delta_pct < 0:
            st.error(f"**⚠️ Q1 2025 Pullback: {revenue_delta_pct:.1f}%**")
            st.write(f"Q1 2025 revenue was **${abs(revenue_delta):,.0f} lower** than Q1 2024.")
            st.write(f"- Spend: {spend_delta_pct:+.1f}%")
            st.write(f"- MER: {q1_2024_mer:.2f}x → {q1_2025_mer:.2f}x ({mer_delta:+.2f}x)")
        else:
            st.success(f"**✅ Q1 2025 Growth: +{revenue_delta_pct:.1f}%**")
            st.write(f"Q1 2025 revenue was **${revenue_delta:,.0f} higher** than Q1 2024.")
            st.write(f"- Spend: {spend_delta_pct:+.1f}%")
            st.write(f"- MER: {q1_2024_mer:.2f}x → {q1_2025_mer:.2f}x ({mer_delta:+.2f}x)")
    
    with col2:
        st.info(f"**🎯 To Hit +20% in Q1 2026**")
        revenue_gap = q1_2026_goal_revenue - q1_2025_revenue
        st.write(f"Need **${revenue_gap:,.0f}** more revenue than Q1 2025")
        
        # Calculate implied spend at current MER
        if q1_2025_mer > 0:
            implied_spend_2026 = q1_2026_goal_revenue / q1_2025_mer
            spend_increase = implied_spend_2026 - q1_2025_spend
            spend_increase_pct = (spend_increase / q1_2025_spend * 100) if q1_2025_spend > 0 else 0
            st.write(f"At Q1 2025 MER ({q1_2025_mer:.2f}x):")
            st.write(f"- Required spend: **${implied_spend_2026:,.0f}**")
            st.write(f"- Increase: **{spend_increase_pct:+.1f}%** (+${spend_increase:,.0f})")
    
    st.markdown("---")
    
    # Monthly summary table
    st.subheader("Q1 Monthly Breakdown")
    st.caption("💡 2024 spend loaded from Historical Spend CSV (Total Spend column)")
    
    # Define month order for sorting
    months_order = ['January', 'February', 'March']
    
    # Calculate monthly aggregates
    monthly_2024 = q1_2024.groupby('month_name').agg({
        'revenue': 'sum',
        'real_revenue': 'sum',
        'spend': 'sum',
        'orders': 'sum'
    }).reset_index()
    monthly_2024['MER'] = monthly_2024['revenue'] / monthly_2024['spend']
    monthly_2024['Year'] = 2024
    
    # Debug: Show what we calculated
    jan_spend_2024 = monthly_2024[monthly_2024['month_name'] == 'January']['spend'].values[0] if len(monthly_2024[monthly_2024['month_name'] == 'January']) > 0 else 0
    st.caption(f"✓ Jan 2024 spend in table: ${jan_spend_2024:,.0f}")
    
    monthly_2025 = q1_2025.groupby('month_name').agg({
        'revenue': 'sum',
        'real_revenue': 'sum',
        'spend': 'sum',
        'orders': 'sum'
    }).reset_index()
    monthly_2025['MER'] = monthly_2025['revenue'] / monthly_2025['spend']
    monthly_2025['Year'] = 2025
    
    # Helper function for color indicators
    def color_delta(delta_val):
        """Return color based on delta value"""
        if delta_val > 0:
            return "🟢"  # Green for positive
        elif delta_val < 0:
            return "🔴"  # Red for negative
        else:
            return "⚪"  # Neutral
    
    # Format 2024 data (no YoY deltas)
    monthly_2024_display = monthly_2024.copy()
    monthly_2024_display['Year'] = '2024'
    monthly_2024_display['revenue'] = monthly_2024_display['revenue'].apply(lambda x: f"${x:,.0f}")
    monthly_2024_display['real_revenue'] = monthly_2024_display['real_revenue'].apply(lambda x: f"${x:,.0f}")
    monthly_2024_display['spend'] = monthly_2024_display['spend'].apply(lambda x: f"${x:,.0f}")
    monthly_2024_display['MER'] = monthly_2024_display['MER'].apply(lambda x: f"{x:.2f}x")
    monthly_2024_display['orders'] = monthly_2024_display['orders'].apply(lambda x: f"{int(x):,}")
    
    # Format 2025 data with YoY deltas
    monthly_2025_display = monthly_2025.copy()
    monthly_2025_display['Year'] = '2025'
    
    # Set indices for lookup
    monthly_2024_sorted = monthly_2024.set_index('month_name')
    
    # Calculate and format each row for 2025
    formatted_rows = []
    for idx, row in monthly_2025.iterrows():
        month = row['month_name']
        if month in monthly_2024_sorted.index:
            # Get 2024 values
            rev_2024 = monthly_2024_sorted.loc[month, 'revenue']
            real_rev_2024 = monthly_2024_sorted.loc[month, 'real_revenue']
            spend_2024 = monthly_2024_sorted.loc[month, 'spend']
            mer_2024 = monthly_2024_sorted.loc[month, 'MER']
            orders_2024 = monthly_2024_sorted.loc[month, 'orders']
            
            # Calculate deltas
            rev_delta = ((row['revenue'] - rev_2024) / rev_2024 * 100) if rev_2024 > 0 else 0
            real_rev_delta = ((row['real_revenue'] - real_rev_2024) / real_rev_2024 * 100) if real_rev_2024 > 0 else 0
            spend_delta = ((row['spend'] - spend_2024) / spend_2024 * 100) if spend_2024 > 0 else 0
            mer_delta = ((row['MER'] - mer_2024) / mer_2024 * 100) if mer_2024 > 0 else 0
            orders_delta = ((row['orders'] - orders_2024) / orders_2024 * 100) if orders_2024 > 0 else 0
            
            formatted_rows.append({
                'Year': '2025',
                'month_name': month,
                'revenue': f"${row['revenue']:,.0f} ({color_delta(rev_delta)}{rev_delta:+.1f}%)",
                'real_revenue': f"${row['real_revenue']:,.0f} ({color_delta(real_rev_delta)}{real_rev_delta:+.1f}%)",
                'spend': f"${row['spend']:,.0f} ({color_delta(spend_delta)}{spend_delta:+.1f}%)",
                'MER': f"{row['MER']:.2f}x ({color_delta(mer_delta)}{mer_delta:+.1f}%)",
                'orders': f"{int(row['orders']):,} ({color_delta(orders_delta)}{orders_delta:+.1f}%)"
            })
    
    monthly_2025_display = pd.DataFrame(formatted_rows)
    
    # Combine 2024 and 2025
    monthly_display = pd.concat([monthly_2024_display, monthly_2025_display], ignore_index=True)
    
    # Sort by month
    monthly_display['month_name'] = pd.Categorical(monthly_display['month_name'], 
                                                     categories=months_order, ordered=True)
    monthly_display = monthly_display.sort_values(['Year', 'month_name'])
    monthly_display = monthly_display[['Year', 'month_name', 'revenue', 'real_revenue', 'spend', 'MER', 'orders']]
    monthly_display.columns = ['Year', 'Month', 'Total Sales', 'Real Revenue', 'Spend', 'MER', 'Orders']
    
    st.dataframe(monthly_display, use_container_width=True, hide_index=True)
    
    st.caption("📊 **Total Sales** = Shopify total sales (after discounts, excluding shipping) | **Real Revenue** = Gross + Discounts + Shipping")
    
    # Note about missing spend data
    if coverage.get('days_with_spend', 0) < 90:  # Q1 should have ~90 days
        st.info("ℹ️ **Note:** 2025 spend data currently only available for January. February and March will show $0 spend until data is updated.")

# ===== TAB 2: Q1 YOY ANALYSIS =====
with tab2:
    st.header("Q1 2024 vs 2025: Year-over-Year Analysis")
    
    # Monthly comparison chart
    st.subheader("Monthly Revenue & MER Comparison")
    
    fig_monthly = make_subplots(
        rows=1, cols=2,
        subplot_titles=("Revenue by Month", "MER by Month"),
        specs=[[{"secondary_y": False}, {"secondary_y": False}]]
    )
    
    # Prepare monthly data
    months_order = ['January', 'February', 'March']
    
    monthly_2024_chart = q1_2024.groupby('month_name').agg({
        'revenue': 'sum',
        'spend': 'sum'
    }).reset_index()
    monthly_2024_chart['MER'] = monthly_2024_chart['revenue'] / monthly_2024_chart['spend']
    monthly_2024_chart['month_name'] = pd.Categorical(monthly_2024_chart['month_name'], 
                                                       categories=months_order, ordered=True)
    monthly_2024_chart = monthly_2024_chart.sort_values('month_name')
    
    monthly_2025_chart = q1_2025.groupby('month_name').agg({
        'revenue': 'sum',
        'spend': 'sum'
    }).reset_index()
    monthly_2025_chart['MER'] = monthly_2025_chart['revenue'] / monthly_2025_chart['spend']
    monthly_2025_chart['month_name'] = pd.Categorical(monthly_2025_chart['month_name'], 
                                                       categories=months_order, ordered=True)
    monthly_2025_chart = monthly_2025_chart.sort_values('month_name')
    
    # Revenue bars
    fig_monthly.add_trace(
        go.Bar(name='2024', x=monthly_2024_chart['month_name'], y=monthly_2024_chart['revenue'],
               marker_color='#4169E1', showlegend=True),
        row=1, col=1
    )
    fig_monthly.add_trace(
        go.Bar(name='2025', x=monthly_2025_chart['month_name'], y=monthly_2025_chart['revenue'],
               marker_color='#32CD32', showlegend=True),
        row=1, col=1
    )
    
    # MER bars
    fig_monthly.add_trace(
        go.Bar(name='2024', x=monthly_2024_chart['month_name'], y=monthly_2024_chart['MER'],
               marker_color='#4169E1', showlegend=False),
        row=1, col=2
    )
    fig_monthly.add_trace(
        go.Bar(name='2025', x=monthly_2025_chart['month_name'], y=monthly_2025_chart['MER'],
               marker_color='#32CD32', showlegend=False),
        row=1, col=2
    )
    
    fig_monthly.update_yaxes(title_text="Revenue ($)", row=1, col=1)
    fig_monthly.update_yaxes(title_text="MER (x)", row=1, col=2)
    fig_monthly.update_layout(height=400, showlegend=True, barmode='group')
    
    st.plotly_chart(fig_monthly, use_container_width=True)
    
    st.markdown("---")
    
    # Daily trends - 4 separate graphs (2x2 grid)
    st.subheader("Daily Trends: Revenue & MER by Year")
    
    # Create normalized dates for comparison (use same year reference)
    q1_2024_normalized = q1_2024.copy()
    q1_2025_normalized = q1_2025.copy()
    
    # Normalize to show same calendar dates (replace year with 2024 for visual alignment)
    q1_2024_normalized['display_date'] = q1_2024_normalized['date']
    q1_2025_normalized['display_date'] = q1_2025_normalized['date'].apply(
        lambda x: x.replace(year=2024)
    )
    
    # Row 1: Revenue charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**2024 Revenue**")
        fig_rev_2024 = go.Figure()
        fig_rev_2024.add_trace(
            go.Scatter(x=q1_2024_normalized['display_date'], y=q1_2024_normalized['revenue'],
                      mode='lines', line=dict(color='#4169E1', width=2),
                      fill='tozeroy', fillcolor='rgba(65, 105, 225, 0.1)')
        )
        fig_rev_2024.update_layout(
            height=300,
            xaxis_title="Date (Q1)",
            yaxis_title="Revenue ($)",
            showlegend=False
        )
        st.plotly_chart(fig_rev_2024, use_container_width=True)
    
    with col2:
        st.markdown("**2025 Revenue**")
        fig_rev_2025 = go.Figure()
        fig_rev_2025.add_trace(
            go.Scatter(x=q1_2025_normalized['display_date'], y=q1_2025_normalized['revenue'],
                      mode='lines', line=dict(color='#32CD32', width=2),
                      fill='tozeroy', fillcolor='rgba(50, 205, 50, 0.1)')
        )
        fig_rev_2025.update_layout(
            height=300,
            xaxis_title="Date (Q1)",
            yaxis_title="Revenue ($)",
            showlegend=False
        )
        st.plotly_chart(fig_rev_2025, use_container_width=True)
    
    # Row 2: MER charts
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("**2024 MER**")
        q1_2024_mer_df = q1_2024_normalized[q1_2024_normalized['MER'] > 0].copy()
        fig_mer_2024 = go.Figure()
        fig_mer_2024.add_trace(
            go.Scatter(x=q1_2024_mer_df['display_date'], y=q1_2024_mer_df['MER'],
                      mode='lines+markers', 
                      line=dict(color='#7C3AED', width=2),
                      marker=dict(size=4))
        )
        fig_mer_2024.add_hline(y=3.0, line_dash="dash", line_color="red", 
                              annotation_text="Target: 3.0x", annotation_position="right")
        fig_mer_2024.update_layout(
            height=300,
            xaxis_title="Date (Q1)",
            yaxis_title="MER (x)",
            showlegend=False
        )
        st.plotly_chart(fig_mer_2024, use_container_width=True)
    
    with col4:
        st.markdown("**2025 MER**")
        q1_2025_mer_df = q1_2025_normalized[q1_2025_normalized['MER'] > 0].copy()
        fig_mer_2025 = go.Figure()
        fig_mer_2025.add_trace(
            go.Scatter(x=q1_2025_mer_df['display_date'], y=q1_2025_mer_df['MER'],
                      mode='lines+markers', 
                      line=dict(color='#F59E0B', width=2),
                      marker=dict(size=4))
        )
        fig_mer_2025.add_hline(y=3.0, line_dash="dash", line_color="red", 
                              annotation_text="Target: 3.0x", annotation_position="right")
        fig_mer_2025.update_layout(
            height=300,
            xaxis_title="Date (Q1)",
            yaxis_title="MER (x)",
            showlegend=False
        )
        st.plotly_chart(fig_mer_2025, use_container_width=True)
    
    st.markdown("---")
    
    # Daily revenue vs spend line charts by month
    st.subheader("Daily Revenue & Spend Patterns by Month")
    
    months_order = ['January', 'February', 'March']
    
    for month in months_order:
        st.markdown(f"### {month}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**2024 {month}**")
            month_2024 = q1_2024[q1_2024['month_name'] == month]
            
            if len(month_2024) > 0:
                fig_2024_month = go.Figure()
                
                # Revenue line
                fig_2024_month.add_trace(
                    go.Scatter(
                        x=month_2024['date'], 
                        y=month_2024['revenue'],
                        mode='lines+markers',
                        name='Revenue',
                        line=dict(color='#4169E1', width=2),
                        marker=dict(size=6),
                        yaxis='y'
                    )
                )
                
                # Spend line (on secondary axis)
                fig_2024_month.add_trace(
                    go.Scatter(
                        x=month_2024['date'], 
                        y=month_2024['spend'],
                        mode='lines+markers',
                        name='Spend',
                        line=dict(color='#FF6B6B', width=2, dash='dash'),
                        marker=dict(size=6),
                        yaxis='y2'
                    )
                )
                
                fig_2024_month.update_layout(
                    height=350,
                    xaxis_title="Date",
                    yaxis=dict(
                        title="Revenue ($)",
                        titlefont=dict(color='#4169E1'),
                        tickfont=dict(color='#4169E1')
                    ),
                    yaxis2=dict(
                        title="Spend ($)",
                        titlefont=dict(color='#FF6B6B'),
                        tickfont=dict(color='#FF6B6B'),
                        overlaying='y',
                        side='right'
                    ),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(fig_2024_month, use_container_width=True)
            else:
                st.info(f"No data available for {month} 2024")
        
        with col2:
            st.markdown(f"**2025 {month}**")
            month_2025 = q1_2025[q1_2025['month_name'] == month]
            
            if len(month_2025) > 0:
                fig_2025_month = go.Figure()
                
                # Revenue line
                fig_2025_month.add_trace(
                    go.Scatter(
                        x=month_2025['date'], 
                        y=month_2025['revenue'],
                        mode='lines+markers',
                        name='Revenue',
                        line=dict(color='#32CD32', width=2),
                        marker=dict(size=6),
                        yaxis='y'
                    )
                )
                
                # Spend line (on secondary axis)
                fig_2025_month.add_trace(
                    go.Scatter(
                        x=month_2025['date'], 
                        y=month_2025['spend'],
                        mode='lines+markers',
                        name='Spend',
                        line=dict(color='#FF6B6B', width=2, dash='dash'),
                        marker=dict(size=6),
                        yaxis='y2'
                    )
                )
                
                fig_2025_month.update_layout(
                    height=350,
                    xaxis_title="Date",
                    yaxis=dict(
                        title="Revenue ($)",
                        titlefont=dict(color='#32CD32'),
                        tickfont=dict(color='#32CD32')
                    ),
                    yaxis2=dict(
                        title="Spend ($)",
                        titlefont=dict(color='#FF6B6B'),
                        tickfont=dict(color='#FF6B6B'),
                        overlaying='y',
                        side='right'
                    ),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                
                st.plotly_chart(fig_2025_month, use_container_width=True)
            else:
                st.info(f"No data available for {month} 2025")
    
    st.markdown("---")
    
    # Daily performance breakdown by month
    st.subheader("Daily Performance by Month")
    
    # Calculate daily averages for each month
    months_order = ['January', 'February', 'March']
    
    daily_breakdown = []
    for month in months_order:
        # 2024 data
        month_2024 = q1_2024[q1_2024['month_name'] == month]
        if len(month_2024) > 0:
            avg_daily_revenue_2024 = month_2024['revenue'].mean()
            avg_daily_spend_2024 = month_2024['spend'].mean()
            avg_daily_mer_2024 = avg_daily_revenue_2024 / avg_daily_spend_2024 if avg_daily_spend_2024 > 0 else 0
            days_2024 = len(month_2024)
        else:
            avg_daily_revenue_2024 = 0
            avg_daily_spend_2024 = 0
            avg_daily_mer_2024 = 0
            days_2024 = 0
        
        # 2025 data
        month_2025 = q1_2025[q1_2025['month_name'] == month]
        if len(month_2025) > 0:
            avg_daily_revenue_2025 = month_2025['revenue'].mean()
            avg_daily_spend_2025 = month_2025['spend'].mean()
            avg_daily_mer_2025 = avg_daily_revenue_2025 / avg_daily_spend_2025 if avg_daily_spend_2025 > 0 else 0
            days_2025 = len(month_2025)
        else:
            avg_daily_revenue_2025 = 0
            avg_daily_spend_2025 = 0
            avg_daily_mer_2025 = 0
            days_2025 = 0
        
        # Calculate YoY changes
        if avg_daily_revenue_2024 > 0:
            revenue_yoy = ((avg_daily_revenue_2025 - avg_daily_revenue_2024) / avg_daily_revenue_2024 * 100)
        else:
            revenue_yoy = 0
            
        if avg_daily_spend_2024 > 0:
            spend_yoy = ((avg_daily_spend_2025 - avg_daily_spend_2024) / avg_daily_spend_2024 * 100)
        else:
            spend_yoy = 0
            
        if avg_daily_mer_2024 > 0:
            mer_yoy = ((avg_daily_mer_2025 - avg_daily_mer_2024) / avg_daily_mer_2024 * 100)
        else:
            mer_yoy = 0
        
        daily_breakdown.append({
            'Month': month,
            '2024 Avg Daily Revenue': avg_daily_revenue_2024,
            '2024 Avg Daily Spend': avg_daily_spend_2024,
            '2024 Avg MER': avg_daily_mer_2024,
            '2024 Days': days_2024,
            '2025 Avg Daily Revenue': avg_daily_revenue_2025,
            '2025 Avg Daily Spend': avg_daily_spend_2025,
            '2025 Avg MER': avg_daily_mer_2025,
            '2025 Days': days_2025,
            'Revenue YoY': revenue_yoy,
            'Spend YoY': spend_yoy,
            'MER YoY': mer_yoy
        })
    
    daily_df = pd.DataFrame(daily_breakdown)
    
    # Format for display
    daily_display = daily_df.copy()
    daily_display['2024 Avg Daily Revenue'] = daily_display['2024 Avg Daily Revenue'].apply(lambda x: f"${x:,.0f}")
    daily_display['2024 Avg Daily Spend'] = daily_display['2024 Avg Daily Spend'].apply(lambda x: f"${x:,.0f}")
    daily_display['2024 Avg MER'] = daily_display['2024 Avg MER'].apply(lambda x: f"{x:.2f}x")
    daily_display['2025 Avg Daily Revenue'] = daily_display['2025 Avg Daily Revenue'].apply(lambda x: f"${x:,.0f}")
    daily_display['2025 Avg Daily Spend'] = daily_display['2025 Avg Daily Spend'].apply(lambda x: f"${x:,.0f}")
    daily_display['2025 Avg MER'] = daily_display['2025 Avg MER'].apply(lambda x: f"{x:.2f}x")
    daily_display['Revenue YoY'] = daily_display['Revenue YoY'].apply(lambda x: f"{x:+.1f}%")
    daily_display['Spend YoY'] = daily_display['Spend YoY'].apply(lambda x: f"{x:+.1f}%")
    daily_display['MER YoY'] = daily_display['MER YoY'].apply(lambda x: f"{x:+.1f}%")
    
    st.dataframe(daily_display, use_container_width=True, hide_index=True)
    
    st.caption("*Note: Averages calculated from actual days with data in each month")
    
    st.markdown("---")
    
    # Daily data tables by month with dropdown
    st.subheader("Day-by-Day Revenue, Spend & MER")
    
    # Month selector dropdown
    selected_month = st.selectbox("Select Month:", ['January', 'February', 'March'])
    
    # Filter data for selected month
    month_2024_detail = q1_2024[q1_2024['month_name'] == selected_month].copy()
    month_2025_detail = q1_2025[q1_2025['month_name'] == selected_month].copy()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**2024 {selected_month} - Daily Performance**")
        if not month_2024_detail.empty:
            daily_2024_table = month_2024_detail[['day_of_month', 'revenue', 'spend', 'MER']].copy()
            daily_2024_table = daily_2024_table.sort_values('day_of_month')
            daily_2024_table['revenue_fmt'] = daily_2024_table['revenue'].apply(lambda x: f"${x:,.0f}")
            daily_2024_table['spend_fmt'] = daily_2024_table['spend'].apply(lambda x: f"${x:,.0f}")
            daily_2024_table['MER_fmt'] = daily_2024_table['MER'].apply(lambda x: f"{x:.2f}x" if x > 0 else "—")
            
            display_2024_table = daily_2024_table[['day_of_month', 'revenue_fmt', 'spend_fmt', 'MER_fmt']].copy()
            display_2024_table.columns = ['Day', 'Revenue', 'Spend', 'MER']
            
            st.dataframe(display_2024_table, use_container_width=True, hide_index=True, height=500)
            
            # Month summary
            total_rev = month_2024_detail['revenue'].sum()
            total_spend = month_2024_detail['spend'].sum()
            avg_mer = total_rev / total_spend if total_spend > 0 else 0
            st.caption(f"**Total:** ${total_rev:,.0f} revenue | ${total_spend:,.0f} spend | {avg_mer:.2f}x MER")
        else:
            st.info("No data available for this month")
    
    with col2:
        st.markdown(f"**2025 {selected_month} - Daily Performance**")
        if not month_2025_detail.empty:
            daily_2025_table = month_2025_detail[['day_of_month', 'revenue', 'spend', 'MER']].copy()
            daily_2025_table = daily_2025_table.sort_values('day_of_month')
            daily_2025_table['revenue_fmt'] = daily_2025_table['revenue'].apply(lambda x: f"${x:,.0f}")
            daily_2025_table['spend_fmt'] = daily_2025_table['spend'].apply(lambda x: f"${x:,.0f}")
            daily_2025_table['MER_fmt'] = daily_2025_table['MER'].apply(lambda x: f"{x:.2f}x" if x > 0 else "—")
            
            display_2025_table = daily_2025_table[['day_of_month', 'revenue_fmt', 'spend_fmt', 'MER_fmt']].copy()
            display_2025_table.columns = ['Day', 'Revenue', 'Spend', 'MER']
            
            st.dataframe(display_2025_table, use_container_width=True, hide_index=True, height=500)
            
            # Month summary
            total_rev = month_2025_detail['revenue'].sum()
            total_spend = month_2025_detail['spend'].sum()
            avg_mer = total_rev / total_spend if total_spend > 0 else 0
            st.caption(f"**Total:** ${total_rev:,.0f} revenue | ${total_spend:,.0f} spend | {avg_mer:.2f}x MER")
            
            # Warning if no spend data
            if total_spend == 0:
                st.warning(f"⚠️ No spend data available for {selected_month} 2025")
        else:
            st.info("No data available for this month")

# ===== TAB 3: PRODUCT PERFORMANCE =====
with tab3:
    st.header("Q1 Product Performance")
    
    q1_products_2024 = data['q1_products_2024']
    q1_products_2025 = data['q1_products_2025']
    
    # Top products by revenue
    st.subheader("Top 20 Products by Q1 Revenue")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**2024 Top Products**")
        top_2024 = q1_products_2024.head(20).copy()
        top_2024['revenue_fmt'] = top_2024['revenue'].apply(lambda x: f"${x:,.0f}")
        top_2024['units_fmt'] = top_2024['units'].apply(lambda x: f"{int(x):,}")
        display_2024 = top_2024[['product', 'revenue_fmt', 'units_fmt']].copy()
        display_2024.columns = ['Product', 'Revenue', 'Units']
        st.dataframe(display_2024, use_container_width=True, hide_index=True, height=600)
    
    with col2:
        st.markdown("**2025 Top Products**")
        if not q1_products_2025.empty:
            top_2025 = q1_products_2025.head(20).copy()
            top_2025['revenue_fmt'] = top_2025['revenue'].apply(lambda x: f"${x:,.0f}")
            top_2025['units_fmt'] = top_2025['units'].apply(lambda x: f"{int(x):,}")
            display_2025 = top_2025[['product', 'revenue_fmt', 'units_fmt']].copy()
            display_2025.columns = ['Product', 'Revenue', 'Units']
            st.dataframe(display_2025, use_container_width=True, hide_index=True, height=600)
        else:
            st.info("2025 product data not available")
    
    st.markdown("---")
    
    # YoY product comparison
    if not q1_products_2025.empty:
        st.subheader("Year-over-Year Product Comparison")
        
        # Merge 2024 and 2025 product data
        product_comparison = q1_products_2024[['product', 'revenue', 'units']].merge(
            q1_products_2025[['product', 'revenue', 'units']],
            on='product',
            how='outer',
            suffixes=('_2024', '_2025')
        )
        product_comparison = product_comparison.fillna(0)
        product_comparison['revenue_change'] = product_comparison['revenue_2025'] - product_comparison['revenue_2024']
        product_comparison['revenue_change_pct'] = (product_comparison['revenue_change'] / product_comparison['revenue_2024'] * 100).replace([float('inf'), -float('inf')], 0)
        
        # Top gainers and losers
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🚀 Top 10 Gainers (YoY)**")
            top_gainers = product_comparison.nlargest(10, 'revenue_change')
            top_gainers['revenue_2024_fmt'] = top_gainers['revenue_2024'].apply(lambda x: f"${x:,.0f}")
            top_gainers['revenue_2025_fmt'] = top_gainers['revenue_2025'].apply(lambda x: f"${x:,.0f}")
            top_gainers['change_fmt'] = top_gainers.apply(lambda x: f"+${x['revenue_change']:,.0f} ({x['revenue_change_pct']:+.0f}%)", axis=1)
            display_gainers = top_gainers[['product', 'revenue_2024_fmt', 'revenue_2025_fmt', 'change_fmt']].copy()
            display_gainers.columns = ['Product', '2024 Revenue', '2025 Revenue', 'Change']
            st.dataframe(display_gainers, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("**📉 Top 10 Declines (YoY)**")
            top_losers = product_comparison.nsmallest(10, 'revenue_change')
            top_losers['revenue_2024_fmt'] = top_losers['revenue_2024'].apply(lambda x: f"${x:,.0f}")
            top_losers['revenue_2025_fmt'] = top_losers['revenue_2025'].apply(lambda x: f"${x:,.0f}")
            top_losers['change_fmt'] = top_losers.apply(lambda x: f"${x['revenue_change']:,.0f} ({x['revenue_change_pct']:+.0f}%)", axis=1)
            display_losers = top_losers[['product', 'revenue_2024_fmt', 'revenue_2025_fmt', 'change_fmt']].copy()
            display_losers.columns = ['Product', '2024 Revenue', '2025 Revenue', 'Change']
            st.dataframe(display_losers, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        # Top sellers with YoY pullback (products needing focus)
        st.subheader("⚠️ Priority Focus: Top Sellers with YoY Pullback")
        
        st.markdown("""
        **Strategic Focus Area:** These products are still generating significant revenue in 2025, 
        but showing declines vs 2024. They represent critical revenue at risk and need immediate attention.
        """)
        
        # Filter for products that:
        # 1. Are in top 30 by 2025 revenue (still major sellers)
        # 2. Have negative revenue change (pullback from 2024)
        # 3. Had revenue in both years (not new products)
        
        top_30_threshold = q1_products_2025.head(30)['revenue'].min() if len(q1_products_2025) >= 30 else 0
        
        focus_products = product_comparison[
            (product_comparison['revenue_2025'] >= top_30_threshold) &  # Top 30 seller in 2025
            (product_comparison['revenue_change'] < 0) &  # Declining revenue
            (product_comparison['revenue_2024'] > 0) &  # Had revenue in 2024
            (product_comparison['revenue_2025'] > 0)  # Has revenue in 2025
        ].copy()
        
        # Sort by 2025 revenue (biggest current sellers first)
        focus_products = focus_products.sort_values('revenue_2025', ascending=False)
        
        if not focus_products.empty:
            # Calculate additional metrics
            focus_products['units_change'] = focus_products['units_2025'] - focus_products['units_2024']
            focus_products['units_change_pct'] = (focus_products['units_change'] / focus_products['units_2024'] * 100).replace([float('inf'), -float('inf')], 0)
            
            # Format for display
            focus_display = focus_products.copy()
            focus_display['2025 Revenue'] = focus_display['revenue_2025'].apply(lambda x: f"${x:,.0f}")
            focus_display['2024 Revenue'] = focus_display['revenue_2024'].apply(lambda x: f"${x:,.0f}")
            focus_display['$ Change'] = focus_display['revenue_change'].apply(lambda x: f"${x:,.0f}")
            focus_display['% Change'] = focus_display['revenue_change_pct'].apply(lambda x: f"{x:.1f}%")
            focus_display['2025 Units'] = focus_display['units_2025'].apply(lambda x: f"{int(x):,}")
            focus_display['Units Change %'] = focus_display['units_change_pct'].apply(lambda x: f"{x:.1f}%")
            
            # Determine severity (color code later if needed)
            def get_severity(pct_change):
                if pct_change < -30:
                    return "🔴 High Risk"
                elif pct_change < -15:
                    return "🟠 Medium Risk"
                else:
                    return "🟡 Monitor"
            
            focus_display['Priority'] = focus_display['revenue_change_pct'].apply(get_severity)
            
            # Reorder columns for display
            final_display = focus_display[[
                'product', 
                'Priority',
                '2025 Revenue',
                '2024 Revenue', 
                '$ Change', 
                '% Change',
                '2025 Units',
                'Units Change %'
            ]].copy()
            final_display.columns = [
                'Product', 
                'Priority Level',
                '2025 Revenue',
                '2024 Revenue', 
                '$ Change', 
                '% Change',
                '2025 Units',
                'Unit Change %'
            ]
            
            st.dataframe(final_display, use_container_width=True, hide_index=True, height=400)
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Products at Risk",
                    len(focus_products),
                    help="Top 30 sellers showing YoY decline"
                )
            
            with col2:
                total_2025_revenue = focus_products['revenue_2025'].sum()
                st.metric(
                    "2025 Revenue at Risk",
                    f"${total_2025_revenue:,.0f}",
                    help="Total Q1 2025 revenue from declining products"
                )
            
            with col3:
                total_revenue_lost = abs(focus_products['revenue_change'].sum())
                st.metric(
                    "Revenue Lost vs 2024",
                    f"${total_revenue_lost:,.0f}",
                    delta=f"{(total_revenue_lost / focus_products['revenue_2024'].sum() * -100):.1f}%",
                    delta_color="inverse"
                )
            
            with col4:
                avg_decline = focus_products['revenue_change_pct'].mean()
                st.metric(
                    "Avg Decline Rate",
                    f"{avg_decline:.1f}%",
                    help="Average YoY percentage decline"
                )
            
            st.info("""
            **💡 Recommended Actions:**
            
            - **🔴 High Risk (>30% decline):** Immediate intervention required - review pricing, positioning, creative, and promotional strategy
            - **🟠 Medium Risk (15-30% decline):** Monitor closely and consider targeted promotions or refreshed marketing
            - **🟡 Monitor (<15% decline):** Track trends and maintain current strategy with minor optimizations
            
            These products collectively represent **${:,.0f}** in current revenue that needs protection and revival strategies for 2026.
            """.format(total_2025_revenue))
        else:
            st.success("✅ Great news! All top-performing products are maintaining or growing revenue YoY.")
            st.info("No major revenue products showing significant pullback from 2024.")

# ===== TAB 4: 2026 GROWTH TARGETS =====
with tab4:
    st.header("2026 Q1 Growth Targets: Scenario Planning")
    
    # Calculate base metrics
    q1_2026_revenue_goal = q1_2025_revenue * 1.20  # +20% revenue growth
    q1_2025_daily_revenue = q1_2025_revenue / 90
    q1_2025_daily_spend = q1_2025_spend / 90
    q1_2026_daily_revenue = q1_2026_revenue_goal / 90
    
    # Scenario A: Maintain 3.47x MER
    mer_scenario_a = q1_2025_mer  # 3.47x
    mer_target_b = 4.0  # Target 4.0x MER for Scenario B
    
    # Calculate spend requirements for each scenario
    spend_scenario_a = q1_2026_revenue_goal / mer_scenario_a  # Maintain current MER
    spend_scenario_b = q1_2026_revenue_goal / mer_target_b  # Target 4.0x MER
    
    daily_spend_scenario_a = spend_scenario_a / 90
    daily_spend_scenario_b = spend_scenario_b / 90
    
    # Summary comparison
    st.subheader("Scenario Overview")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### 📊 Q1 2025 Baseline")
        st.metric("Total Revenue", f"${q1_2025_revenue:,.0f}")
        st.metric("Total Spend", f"${q1_2025_spend:,.0f}")
        st.metric("MER", f"{q1_2025_mer:.2f}x")
        st.caption(f"Avg Daily Revenue: ${q1_2025_daily_revenue:,.0f}")
        st.caption(f"Avg Daily Spend: ${q1_2025_daily_spend:,.0f}")
    
    with col2:
        st.markdown("### 🎯 Scenario A: Maintain MER")
        st.metric("Total Revenue (+20%)", f"${q1_2026_revenue_goal:,.0f}", 
                 delta=f"+${q1_2026_revenue_goal - q1_2025_revenue:,.0f}")
        st.metric("Required Spend", f"${spend_scenario_a:,.0f}",
                 delta=f"+${spend_scenario_a - q1_2025_spend:,.0f}")
        st.metric("MER Target", f"{mer_scenario_a:.2f}x", delta="0.00x (same)")
        st.caption(f"Avg Daily Revenue: ${q1_2026_daily_revenue:,.0f}")
        st.caption(f"Avg Daily Spend: ${daily_spend_scenario_a:,.0f}")
    
    with col3:
        st.markdown("### 🚀 Scenario B: 4.0 MER Target")
        st.metric("Total Revenue (+20%)", f"${q1_2026_revenue_goal:,.0f}",
                 delta=f"+${q1_2026_revenue_goal - q1_2025_revenue:,.0f}")
        st.metric("Required Spend", f"${spend_scenario_b:,.0f}",
                 delta=f"+${spend_scenario_b - q1_2025_spend:,.0f}")
        st.metric("MER Target", f"{mer_target_b:.2f}x",
                 delta=f"+{mer_target_b - q1_2025_mer:.2f}x")
        st.caption(f"Avg Daily Revenue: ${q1_2026_daily_revenue:,.0f}")
        st.caption(f"Avg Daily Spend: ${daily_spend_scenario_b:,.0f}")
    
    st.markdown("---")
    
    # Daily pacing projections
    st.subheader("Daily Pacing Projections")
    
    # Create comparison table
    pacing_data = {
        'Metric': [
            'Daily Revenue',
            'Daily Spend',
            'Daily MER',
            'Revenue Growth vs 2025',
            'Spend Growth vs 2025'
        ],
        '2025 Actual': [
            f"${q1_2025_daily_revenue:,.0f}",
            f"${q1_2025_daily_spend:,.0f}",
            f"{q1_2025_mer:.2f}x",
            "-",
            "-"
        ],
        '2026 Scenario A (Maintain MER)': [
            f"${q1_2026_daily_revenue:,.0f}",
            f"${daily_spend_scenario_a:,.0f}",
            f"{mer_scenario_a:.2f}x",
            f"+{((q1_2026_daily_revenue - q1_2025_daily_revenue) / q1_2025_daily_revenue * 100):.1f}%",
            f"+{((daily_spend_scenario_a - q1_2025_daily_spend) / q1_2025_daily_spend * 100):.1f}%"
        ],
        '2026 Scenario B (4.0x MER)': [
            f"${q1_2026_daily_revenue:,.0f}",
            f"${daily_spend_scenario_b:,.0f}",
            f"{mer_target_b:.2f}x",
            f"+{((q1_2026_daily_revenue - q1_2025_daily_revenue) / q1_2025_daily_revenue * 100):.1f}%",
            f"+{((daily_spend_scenario_b - q1_2025_daily_spend) / q1_2025_daily_spend * 100):.1f}%"
        ]
    }
    
    pacing_df = pd.DataFrame(pacing_data)
    st.dataframe(pacing_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # Key insights
    st.info(f"""
    **💡 Key Insights:**
    
    - **Scenario A** requires **${(spend_scenario_a - q1_2025_spend):,.0f}** more spend (+{((spend_scenario_a - q1_2025_spend) / q1_2025_spend * 100):.1f}%) to achieve +20% revenue while maintaining current MER of {q1_2025_mer:.2f}x
    
    - **Scenario B** requires **${(spend_scenario_b - q1_2025_spend):,.0f}** more spend (+{((spend_scenario_b - q1_2025_spend) / q1_2025_spend * 100):.1f}%) while improving MER to {mer_target_b:.2f}x
    
    - Improving MER by 20% would **save ${(spend_scenario_a - spend_scenario_b):,.0f}** in quarterly spend while achieving the same revenue goal
    """)
    
    st.markdown("---")
    
    # Monthly projections with daily breakdown
    st.subheader("📅 Monthly Projections: Daily Targets")
    
    st.markdown("""
    **Hybrid Model Approach:**
    - Start conservative in January to validate performance
    - Scale in February/March based on January results
    - Both scenarios assume 20% revenue growth over Q1 2025
    """)
    
    months_data = []
    days_per_month = {'January': 31, 'February': 28, 'March': 31}
    
    for month_name, days in days_per_month.items():
        # 2025 actual data for this month
        month_2025 = q1_2025[q1_2025['month_name'] == month_name]
        if len(month_2025) > 0:
            revenue_2025 = month_2025['revenue'].sum()
            spend_2025 = month_2025['spend'].sum()
            orders_2025 = month_2025['orders'].sum()
            mer_2025 = revenue_2025 / spend_2025 if spend_2025 > 0 else 0
        else:
            revenue_2025 = 0
            spend_2025 = 0
            orders_2025 = 0
            mer_2025 = 0
        
        # 2026 projections (+20% revenue)
        revenue_2026 = revenue_2025 * 1.20
        daily_revenue_2026 = revenue_2026 / days
        
        # Scenario A: Maintain 3.47x MER
        spend_2026_a = revenue_2026 / mer_scenario_a
        daily_spend_2026_a = spend_2026_a / days
        
        # Scenario B: Target 4.0x MER
        spend_2026_b = revenue_2026 / mer_target_b
        daily_spend_2026_b = spend_2026_b / days
        
        months_data.append({
            'Month': month_name,
            'Days': days,
            '2025 Revenue': revenue_2025,
            '2026 Revenue Goal': revenue_2026,
            'Daily Revenue Target': daily_revenue_2026,
            'Scenario A Spend (3.47x)': spend_2026_a,
            'Scenario A Daily Spend': daily_spend_2026_a,
            'Scenario B Spend (4.0x)': spend_2026_b,
            'Scenario B Daily Spend': daily_spend_2026_b,
            'Savings (A vs B)': spend_2026_a - spend_2026_b
        })
    
    months_df = pd.DataFrame(months_data)
    
    # Display formatted table for each month
    for idx, row in months_df.iterrows():
        with st.expander(f"📊 {row['Month']} 2026 - {row['Days']} Days", expanded=(idx == 0)):
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("### 📈 Revenue Targets")
                st.metric("Monthly Goal (+20%)", f"${row['2026 Revenue Goal']:,.0f}")
                st.metric("Daily Target", f"${row['Daily Revenue Target']:,.0f}")
                st.caption(f"vs 2025 Actual: ${row['2025 Revenue']:,.0f}")
            
            with col2:
                st.markdown("### 💰 Scenario A: 3.47x MER")
                st.metric("Monthly Spend", f"${row['Scenario A Spend (3.47x)']:,.0f}")
                st.metric("Daily Spend", f"${row['Scenario A Daily Spend']:,.0f}")
                st.caption("Maintain current efficiency")
            
            with col3:
                st.markdown("### 🚀 Scenario B: 4.0x MER")
                st.metric("Monthly Spend", f"${row['Scenario B Spend (4.0x)']:,.0f}")
                st.metric("Daily Spend", f"${row['Scenario B Daily Spend']:,.0f}")
                st.caption(f"Saves: ${row['Savings (A vs B)']:,.0f}")
            
            st.markdown("---")
            
            # Weekly breakdown for this month
            st.markdown(f"**Weekly Breakdown for {row['Month']}:**")
            
            # Calculate weeks in month (roughly 4-5 weeks)
            weeks_in_month = int(row['Days'] / 7)
            remaining_days = row['Days'] % 7
            
            weekly_data = []
            for week_num in range(1, weeks_in_month + 1):
                days_in_week = 7
                week_label = f"Week {week_num}"
                
                weekly_revenue = row['Daily Revenue Target'] * days_in_week
                weekly_spend_a = row['Scenario A Daily Spend'] * days_in_week
                weekly_spend_b = row['Scenario B Daily Spend'] * days_in_week
                
                weekly_data.append({
                    'Week': week_label,
                    'Days': days_in_week,
                    'Revenue Target': f"${weekly_revenue:,.0f}",
                    'Scenario A Spend': f"${weekly_spend_a:,.0f}",
                    'Scenario B Spend': f"${weekly_spend_b:,.0f}",
                    'Daily Revenue': f"${row['Daily Revenue Target']:,.0f}",
                    'Daily Spend A': f"${row['Scenario A Daily Spend']:,.0f}",
                    'Daily Spend B': f"${row['Scenario B Daily Spend']:,.0f}"
                })
            
            # Add remaining days if any
            if remaining_days > 0:
                weekly_revenue = row['Daily Revenue Target'] * remaining_days
                weekly_spend_a = row['Scenario A Daily Spend'] * remaining_days
                weekly_spend_b = row['Scenario B Daily Spend'] * remaining_days
                
                weekly_data.append({
                    'Week': f"Week {weeks_in_month + 1}",
                    'Days': remaining_days,
                    'Revenue Target': f"${weekly_revenue:,.0f}",
                    'Scenario A Spend': f"${weekly_spend_a:,.0f}",
                    'Scenario B Spend': f"${weekly_spend_b:,.0f}",
                    'Daily Revenue': f"${row['Daily Revenue Target']:,.0f}",
                    'Daily Spend A': f"${row['Scenario A Daily Spend']:,.0f}",
                    'Daily Spend B': f"${row['Scenario B Daily Spend']:,.0f}"
                })
            
            weekly_df = pd.DataFrame(weekly_data)
            st.dataframe(weekly_df, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    st.markdown("""
    **📋 Implementation Notes:**
    - Monitor daily performance against these targets
    - Adjust spend allocation based on actual MER performance
    - Use January as validation month before scaling February/March
    - Weekly checkpoints recommended to ensure pacing on track
    """)

# ===== TAB 6: DATA & METHODOLOGY =====
with tab6:
    st.header("Data & Methodology")
    
    st.subheader("Data Sources")
    
    st.markdown("**2024 Data:**")
    st.write("- **Revenue**: Shopify exec summary (Total sales over time - 2024)")
    st.write("- **Spend**: Historical Spend CSV (Total Spend column)")
    st.write(f"  - Source: `{data['spend_2024_file']}`")
    st.write("  - All channels included (Meta, Google, TikTok, Affiliates, etc.)")
    st.write("  - Q1 2024 total: $1,974,535")
    
    st.markdown("**2025 Data:**")
    st.write("- **Revenue**: Shopify exec summary (Total sales over time - OU - 2025)")
    st.write(f"  - File: `{data['sales_2025_file']}`")
    st.write("- **Spend**: Northbeam API export (YTD through Dec 18, 2025)")
    st.write(f"  - File: `{data['spend_2025_file']}`")
    st.write("  - All platforms via Northbeam (Meta, Google, Email, Affiliate, etc.)")
    st.write("  - Accounting mode: Cash snapshot")
    st.write("  - Attribution: Northbeam custom (1-day window)")
    
    st.markdown("---")
    
    st.subheader("Methodology")
    
    st.markdown("**Q1 Definition:**")
    st.write("- January 1 → March 31")
    st.write("- Total of 90 days")
    
    st.markdown("**MER Calculation:**")
    st.write("- MER = Revenue / Spend")
    st.write("- Uses Shopify revenue (not Northbeam attributed revenue)")
    st.write("- For 2024: Spend = Meta + Google only")
    st.write("- For 2025: Spend = All channels via Northbeam")
    
    st.markdown("**2026 Growth Targets:**")
    st.write("- Goal: +20% revenue growth over Q1 2025")
    st.write("- Applied uniformly to each month")
    st.write("- Daily target = Q1 2026 goal revenue / 90 days")
    
    st.markdown("**Limitations:**")
    st.write("- 2024 spend only includes Meta + Google (other channels not available daily)")
    st.write("- 2024 vs 2025 spend comparison is not apples-to-apples due to channel coverage")
    st.write("- For full multi-channel comparison, use 2025 data only")
    
    st.markdown("---")
    
    st.subheader("File Locations")
    
    st.code(f"""
# 2024 spend source
{data['spend_2024_file']}

# 2025 spend file
{data['spend_2025_file']}

# 2025 sales file
{data['sales_2025_file']}
    """, language="text")
