#!/usr/bin/env python3
"""
Q1 Growth & Forecast Dashboard
2024 vs 2025 Q1 Analysis with 20% Growth Targets for 2026
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

@st.cache_data(ttl=3600)
def load_campaign_data():
    """Load Q1 campaign-level data for 2024 and 2025"""
    
    campaign_dir = DATA_DIR / "reports" / "campaign"
    
    campaigns_2024_file = campaign_dir / "q1_2024_campaigns.csv"
    campaigns_2025_file = campaign_dir / "q1_2025_campaigns.csv"
    
    campaigns_2024 = pd.DataFrame()
    campaigns_2025 = pd.DataFrame()
    
    if campaigns_2024_file.exists():
        campaigns_2024 = pd.read_csv(campaigns_2024_file)
        if 'Day' in campaigns_2024.columns:
            campaigns_2024['Day'] = pd.to_datetime(campaigns_2024['Day'])
        elif 'date' in campaigns_2024.columns:
            campaigns_2024['date'] = pd.to_datetime(campaigns_2024['date'])
    
    if campaigns_2025_file.exists():
        campaigns_2025 = pd.read_csv(campaigns_2025_file)
        campaigns_2025['date'] = pd.to_datetime(campaigns_2025['date'])
    
    return campaigns_2024, campaigns_2025

@st.cache_data(ttl=3600)
def load_all_data():
    """Load 2024 + 2025 sales and spend data"""
    
    # === 2024 Sales ===
    sales_2024_file = ADS_DIR / "exec-sum" / "Total sales over time - 2024-01-01 - 2024-12-31-DAILY.csv"
    sales_2024 = pd.read_csv(sales_2024_file)
    sales_2024['Day'] = pd.to_datetime(sales_2024['Day'])
    sales_2024 = sales_2024.rename(columns={'Day': 'date', 'Total sales': 'revenue', 'Orders': 'orders'})
    sales_2024['year'] = 2024
    
    # === 2025 Sales ===
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
    
    # === 2024 Spend (Meta + Google) ===
    spend_2024_files = sorted(ADS_DIR.glob("northbeam_style_daily_2024-*.csv"))
    if not spend_2024_files:
        st.error("No 2024 spend file found. Run scripts/build_2024_spend_file.py first.")
        return None
    
    spend_2024_file = spend_2024_files[-1]
    spend_2024 = pd.read_csv(spend_2024_file)
    spend_2024['date'] = pd.to_datetime(spend_2024['date'])
    
    # Aggregate to daily brand level
    spend_2024_daily = spend_2024.groupby('date').agg({
        'spend': 'sum'
    }).reset_index()
    spend_2024_daily['year'] = 2024
    
    # === 2025 Spend (Northbeam YTD) ===
    # Try lightweight daily file first, fallback to full YTD file
    spend_2025_file = ADS_DIR / "northbeam_2025_ytd_spend_daily.csv"
    
    if not spend_2025_file.exists():
        # Fallback to full YTD files
        spend_2025_files = sorted(ADS_DIR.glob("ytd_sales_data-higher_dose_llc-2025_12_18-*.csv"))
        if not spend_2025_files:
            st.error("No 2025 Northbeam spend file found.")
            return None
        
        spend_2025_file = spend_2025_files[-1]
        spend_2025 = pd.read_csv(spend_2025_file)
        spend_2025['date'] = pd.to_datetime(spend_2025['date'])
        
        # Filter to Cash snapshot mode to avoid double counting
        spend_2025 = spend_2025[spend_2025['accounting_mode'] == 'Cash snapshot'].copy()
        
        # Aggregate to daily brand level
        spend_2025_daily = spend_2025.groupby('date').agg({
            'spend': 'sum'
        }).reset_index()
        spend_2025_daily['year'] = 2025
    else:
        # Use lightweight file (already aggregated daily)
        spend_2025_daily = pd.read_csv(spend_2025_file)
        spend_2025_daily['date'] = pd.to_datetime(spend_2025_daily['date'])
        # Ensure 'year' column exists
        if 'year' not in spend_2025_daily.columns:
            spend_2025_daily['year'] = 2025
    
    # === Merge sales + spend for each year ===
    df_2024 = sales_2024.merge(spend_2024_daily[['date', 'spend']], on='date', how='left')
    df_2024['spend'] = df_2024['spend'].fillna(0)
    df_2024['MER'] = df_2024.apply(lambda x: x['revenue'] / x['spend'] if x['spend'] > 0 else 0, axis=1)
    
    # Debug: Show 2025 spend info
    total_2025_spend = spend_2025_daily['spend'].sum()
    
    df_2025 = sales_2025.merge(spend_2025_daily[['date', 'spend']], 
                               on='date', how='left')
    df_2025['spend'] = df_2025['spend'].fillna(0)
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
        'spend_2024_file': spend_2024_file.name,
        'spend_2025_file': spend_2025_file.name,
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
    data = load_all_data()
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
st.markdown("---")

# === TAB STRUCTURE ===
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Overview", 
    "📈 Q1 YoY Analysis", 
    "🎯 2026 Growth Targets",
    "📢 Campaign Analysis",
    "📋 Data & Methodology"
])

# ===== TAB 1: OVERVIEW =====
with tab1:
    st.header("Executive Summary")
    
    # Calculate Q1 metrics for both years
    q1_2024_revenue = q1_2024['revenue'].sum()
    q1_2024_spend = q1_2024['spend'].sum()
    q1_2024_orders = q1_2024['orders'].sum()
    q1_2024_mer = q1_2024_revenue / q1_2024_spend if q1_2024_spend > 0 else 0
    
    q1_2025_revenue = q1_2025['revenue'].sum()
    q1_2025_spend = q1_2025['spend'].sum()
    q1_2025_orders = q1_2025['orders'].sum()
    q1_2025_mer = q1_2025_revenue / q1_2025_spend if q1_2025_spend > 0 else 0
    
    # 2026 goal (20% growth)
    q1_2026_goal_revenue = q1_2025_revenue * 1.20
    q1_2026_goal_daily = q1_2026_goal_revenue / 90  # Q1 = 90 days
    
    # YoY deltas
    revenue_delta = q1_2025_revenue - q1_2024_revenue
    revenue_delta_pct = (revenue_delta / q1_2024_revenue * 100) if q1_2024_revenue > 0 else 0
    spend_delta = q1_2025_spend - q1_2024_spend
    spend_delta_pct = (spend_delta / q1_2024_spend * 100) if q1_2024_spend > 0 else 0
    mer_delta = q1_2025_mer - q1_2024_mer
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Q1 2024 Revenue", f"${q1_2024_revenue:,.0f}")
        st.caption(f"Spend: ${q1_2024_spend:,.0f} | MER: {q1_2024_mer:.2f}x")
    
    with col2:
        st.metric("Q1 2025 Revenue", f"${q1_2025_revenue:,.0f}", 
                 delta=f"{revenue_delta_pct:+.1f}% YoY")
        st.caption(f"Spend: ${q1_2025_spend:,.0f} | MER: {q1_2025_mer:.2f}x")
    
    with col3:
        st.metric("Q1 2026 Goal (+20%)", f"${q1_2026_goal_revenue:,.0f}")
        st.caption(f"Daily target: ${q1_2026_goal_daily:,.0f}")
    
    with col4:
        st.metric("2025 vs 2024", f"{revenue_delta_pct:+.1f}%", 
                 delta=f"${revenue_delta:,.0f}")
        st.caption(f"MER Δ: {mer_delta:+.2f}x")
    
    st.markdown("---")
    
    # Callout boxes
    col1, col2 = st.columns(2)
    
    with col1:
        if revenue_delta_pct < 0:
            st.error(f"**⚠️ Q1 2025 Pullback: {revenue_delta_pct:.1f}%**")
            st.write(f"Q1 2025 revenue was **${abs(revenue_delta):,.0f} lower** than Q1 2024.")
            st.write(f"- Spend: {spend_delta_pct:+.1f}%")
            st.write(f"- MER: {mer_delta:+.2f}x change")
        else:
            st.success(f"**✅ Q1 2025 Growth: +{revenue_delta_pct:.1f}%**")
            st.write(f"Q1 2025 revenue was **${revenue_delta:,.0f} higher** than Q1 2024.")
    
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
    
    # Calculate monthly aggregates
    monthly_2024 = q1_2024.groupby('month_name').agg({
        'revenue': 'sum',
        'spend': 'sum',
        'orders': 'sum'
    }).reset_index()
    monthly_2024['MER'] = monthly_2024['revenue'] / monthly_2024['spend']
    monthly_2024['Year'] = 2024
    
    monthly_2025 = q1_2025.groupby('month_name').agg({
        'revenue': 'sum',
        'spend': 'sum',
        'orders': 'sum'
    }).reset_index()
    monthly_2025['MER'] = monthly_2025['revenue'] / monthly_2025['spend']
    monthly_2025['Year'] = 2025
    
    # Combine and format
    monthly_combined = pd.concat([monthly_2024, monthly_2025])
    monthly_combined = monthly_combined[['Year', 'month_name', 'revenue', 'spend', 'MER', 'orders']]
    
    # Format display columns (keep Year as string to control formatting)
    monthly_display = monthly_combined.copy()
    monthly_display['Year'] = monthly_display['Year'].astype(int).astype(str)  # Convert to string to prevent comma formatting
    monthly_display['revenue'] = monthly_display['revenue'].apply(lambda x: f"${x:,.0f}")
    monthly_display['spend'] = monthly_display['spend'].apply(lambda x: f"${x:,.0f}")
    monthly_display['MER'] = monthly_display['MER'].apply(lambda x: f"{x:.2f}x")
    monthly_display['orders'] = monthly_display['orders'].apply(lambda x: f"{int(x):,}")
    monthly_display.columns = ['Year', 'Month', 'Revenue', 'Spend', 'MER', 'Orders']
    
    st.dataframe(monthly_display, use_container_width=True, hide_index=True)
    
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
    
    # Row 1: Revenue charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**2024 Revenue**")
        fig_rev_2024 = go.Figure()
        fig_rev_2024.add_trace(
            go.Scatter(x=q1_2024['date'], y=q1_2024['revenue'],
                      mode='lines', line=dict(color='#4169E1', width=2),
                      fill='tozeroy', fillcolor='rgba(65, 105, 225, 0.1)')
        )
        fig_rev_2024.update_layout(
            height=300,
            xaxis_title="Date",
            yaxis_title="Revenue ($)",
            showlegend=False
        )
        st.plotly_chart(fig_rev_2024, use_container_width=True)
    
    with col2:
        st.markdown("**2025 Revenue**")
        fig_rev_2025 = go.Figure()
        fig_rev_2025.add_trace(
            go.Scatter(x=q1_2025['date'], y=q1_2025['revenue'],
                      mode='lines', line=dict(color='#32CD32', width=2),
                      fill='tozeroy', fillcolor='rgba(50, 205, 50, 0.1)')
        )
        fig_rev_2025.update_layout(
            height=300,
            xaxis_title="Date",
            yaxis_title="Revenue ($)",
            showlegend=False
        )
        st.plotly_chart(fig_rev_2025, use_container_width=True)
    
    # Row 2: MER charts
    col3, col4 = st.columns(2)
    
    with col3:
        st.markdown("**2024 MER**")
        q1_2024_mer_df = q1_2024[q1_2024['MER'] > 0].copy()
        fig_mer_2024 = go.Figure()
        fig_mer_2024.add_trace(
            go.Scatter(x=q1_2024_mer_df['date'], y=q1_2024_mer_df['MER'],
                      mode='lines+markers', 
                      line=dict(color='#7C3AED', width=2),
                      marker=dict(size=4))
        )
        fig_mer_2024.add_hline(y=3.0, line_dash="dash", line_color="red", 
                              annotation_text="Target: 3.0x", annotation_position="right")
        fig_mer_2024.update_layout(
            height=300,
            xaxis_title="Date",
            yaxis_title="MER (x)",
            showlegend=False
        )
        st.plotly_chart(fig_mer_2024, use_container_width=True)
    
    with col4:
        st.markdown("**2025 MER**")
        q1_2025_mer_df = q1_2025[q1_2025['MER'] > 0].copy()
        fig_mer_2025 = go.Figure()
        fig_mer_2025.add_trace(
            go.Scatter(x=q1_2025_mer_df['date'], y=q1_2025_mer_df['MER'],
                      mode='lines+markers', 
                      line=dict(color='#F59E0B', width=2),
                      marker=dict(size=4))
        )
        fig_mer_2025.add_hline(y=3.0, line_dash="dash", line_color="red", 
                              annotation_text="Target: 3.0x", annotation_position="right")
        fig_mer_2025.update_layout(
            height=300,
            xaxis_title="Date",
            yaxis_title="MER (x)",
            showlegend=False
        )
        st.plotly_chart(fig_mer_2025, use_container_width=True)

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

# ===== TAB 4: 2026 GROWTH TARGETS =====
with tab4:
    st.header("2026 Q1 Growth Targets (+20% Scenario)")
    
    # Monthly growth targets
    st.subheader("Monthly Revenue Targets")
    
    # Calculate 2026 goals by month
    monthly_goals = []
    for month_name in ['January', 'February', 'March']:
        rev_2024 = q1_2024[q1_2024['month_name'] == month_name]['revenue'].sum()
        rev_2025 = q1_2025[q1_2025['month_name'] == month_name]['revenue'].sum()
        rev_2026_goal = rev_2025 * 1.20
        
        spend_2024 = q1_2024[q1_2024['month_name'] == month_name]['spend'].sum()
        spend_2025 = q1_2025[q1_2025['month_name'] == month_name]['spend'].sum()
        mer_2025 = rev_2025 / spend_2025 if spend_2025 > 0 else 0
        
        monthly_goals.append({
            'Month': month_name,
            '2024 Actual': rev_2024,
            '2025 Actual': rev_2025,
            '2026 Goal (+20%)': rev_2026_goal,
            'Gap to 2026': rev_2026_goal - rev_2025,
            '2025 Spend': spend_2025,
            '2025 MER': mer_2025
        })
    
    goals_df = pd.DataFrame(monthly_goals)
    
    # Display table
    goals_display = goals_df.copy()
    for col in ['2024 Actual', '2025 Actual', '2026 Goal (+20%)', 'Gap to 2026', '2025 Spend']:
        goals_display[col] = goals_display[col].apply(lambda x: f"${x:,.0f}")
    goals_display['2025 MER'] = goals_display['2025 MER'].apply(lambda x: f"{x:.2f}x")
    
    st.dataframe(goals_display, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # Visualization
    st.subheader("Revenue Targets by Month")
    
    fig_goals = go.Figure()
    
    fig_goals.add_trace(
        go.Bar(name='2024 Actual', x=goals_df['Month'], y=goals_df['2024 Actual'],
               marker_color='#94A3B8')
    )
    
    fig_goals.add_trace(
        go.Bar(name='2025 Actual', x=goals_df['Month'], y=goals_df['2025 Actual'],
               marker_color='#32CD32')
    )
    
    fig_goals.add_trace(
        go.Bar(name='2026 Goal (+20%)', x=goals_df['Month'], y=goals_df['2026 Goal (+20%)'],
               marker_color='#F59E0B', marker_pattern_shape="/")
    )
    
    fig_goals.update_layout(
        height=400,
        barmode='group',
        xaxis_title="Month",
        yaxis_title="Revenue ($)"
    )
    
    st.plotly_chart(fig_goals, use_container_width=True)
    
    st.markdown("---")
    
    # Scenario analysis
    st.subheader("Scenario Analysis: How to Hit +20%")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Scenario 1: Hold MER Constant**")
        st.write(f"Current Q1 2025 MER: **{q1_2025_mer:.2f}x**")
        
        required_spend_2026 = q1_2026_goal_revenue / q1_2025_mer if q1_2025_mer > 0 else 0
        spend_increase = required_spend_2026 - q1_2025_spend
        spend_increase_pct = (spend_increase / q1_2025_spend * 100) if q1_2025_spend > 0 else 0
        
        st.metric("Required Q1 2026 Spend", f"${required_spend_2026:,.0f}",
                 delta=f"+${spend_increase:,.0f} ({spend_increase_pct:+.1f}%)")
        
        st.caption(f"To hit +20% revenue at the same MER, increase spend by {spend_increase_pct:.1f}%")
    
    with col2:
        st.markdown("**Scenario 2: Hold Spend Constant**")
        st.write(f"Current Q1 2025 Spend: **${q1_2025_spend:,.0f}**")
        
        required_mer_2026 = q1_2026_goal_revenue / q1_2025_spend if q1_2025_spend > 0 else 0
        mer_increase = required_mer_2026 - q1_2025_mer
        mer_increase_pct = (mer_increase / q1_2025_mer * 100) if q1_2025_mer > 0 else 0
        
        st.metric("Required Q1 2026 MER", f"{required_mer_2026:.2f}x",
                 delta=f"+{mer_increase:.2f}x ({mer_increase_pct:+.1f}%)")
        
        st.caption(f"To hit +20% revenue at the same spend, improve MER by {mer_increase_pct:.1f}%")
    
    st.markdown("---")
    
    # Daily pacing
    st.subheader("Daily Revenue Pacing")
    
    q1_2025_daily_avg = q1_2025_revenue / len(q1_2025)
    q1_2026_daily_target = q1_2026_goal_revenue / 90  # Q1 = 90 days
    daily_increase = q1_2026_daily_target - q1_2025_daily_avg
    daily_increase_pct = (daily_increase / q1_2025_daily_avg * 100) if q1_2025_daily_avg > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Q1 2025 Avg Daily Revenue", f"${q1_2025_daily_avg:,.0f}")
    
    with col2:
        st.metric("Q1 2026 Target Daily Revenue", f"${q1_2026_daily_target:,.0f}",
                 delta=f"+${daily_increase:,.0f}")
    
    with col3:
        st.metric("Daily Increase Required", f"{daily_increase_pct:+.1f}%")

# ===== TAB 4: CAMPAIGN ANALYSIS =====
with tab4:
    st.header("Q1 Campaign Performance: 2024 vs 2025")
    
    # Load campaign data
    try:
        campaigns_2024, campaigns_2025 = load_campaign_data()
        
        if campaigns_2024.empty and campaigns_2025.empty:
            st.warning("⚠️ No campaign data available. Run `python3 scripts/analyze_q1_campaigns.py` first.")
        else:
            # Summary metrics
            st.subheader("Platform Spend Summary")
            
            col1, col2, col3 = st.columns(3)
            
            if not campaigns_2024.empty:
                total_2024 = campaigns_2024['spend'].sum()
                google_2024 = campaigns_2024[campaigns_2024['platform'] == 'Google']['spend'].sum()
                meta_2024 = campaigns_2024[campaigns_2024['platform'] == 'Meta']['spend'].sum()
                
                with col1:
                    st.metric("2024 Q1 Total Spend", f"${total_2024:,.0f}")
                    st.caption(f"Google: ${google_2024:,.0f} ({google_2024/total_2024*100:.1f}%)")
                    st.caption(f"Meta: ${meta_2024:,.0f} ({meta_2024/total_2024*100:.1f}%)")
            
            if not campaigns_2025.empty:
                total_2025 = campaigns_2025['spend'].sum()
                google_2025 = campaigns_2025[campaigns_2025['platform'] == 'Google']['spend'].sum()
                meta_2025 = campaigns_2025[campaigns_2025['platform'] == 'Meta']['spend'].sum()
                
                with col2:
                    st.metric("2025 Q1 Total Spend", f"${total_2025:,.0f}")
                    st.caption(f"Google: ${google_2025:,.0f} ({google_2025/total_2025*100:.1f}%)")
                    st.caption(f"Meta: ${meta_2025:,.0f} ({meta_2025/total_2025*100:.1f}%)")
                    st.caption("⚠️ January only")
            
            if not campaigns_2024.empty and not campaigns_2025.empty:
                # Compare January only (apples to apples)
                jan_2024 = campaigns_2024[campaigns_2024['month_name'] == 'January']['spend'].sum()
                jan_2025 = total_2025  # 2025 is January only
                delta = jan_2025 - jan_2024
                delta_pct = (delta / jan_2024 * 100) if jan_2024 > 0 else 0
                
                with col3:
                    st.metric("January YoY Change", f"{delta_pct:+.1f}%", 
                             delta=f"${delta:+,.0f}")
                    st.caption(f"2024 Jan: ${jan_2024:,.0f}")
                    st.caption(f"2025 Jan: ${jan_2025:,.0f}")
            
            st.markdown("---")
            
            # Monthly breakdown by platform
            st.subheader("Monthly Spend by Platform")
            
            # Create comparison chart
            fig = make_subplots(
                rows=1, cols=2,
                subplot_titles=("2024 Q1 Spend by Month", "2025 Q1 Spend by Month"),
                specs=[[{"type": "bar"}, {"type": "bar"}]]
            )
            
            if not campaigns_2024.empty:
                monthly_2024 = campaigns_2024.groupby(['month_name', 'platform'])['spend'].sum().reset_index()
                monthly_2024['month_name'] = pd.Categorical(
                    monthly_2024['month_name'], 
                    categories=['January', 'February', 'March'], 
                    ordered=True
                )
                monthly_2024 = monthly_2024.sort_values('month_name')
                
                for platform in ['Google', 'Meta']:
                    platform_data = monthly_2024[monthly_2024['platform'] == platform]
                    color = '#4285F4' if platform == 'Google' else '#1877F2'
                    fig.add_trace(
                        go.Bar(
                            name=platform,
                            x=platform_data['month_name'],
                            y=platform_data['spend'],
                            marker_color=color,
                            showlegend=True
                        ),
                        row=1, col=1
                    )
            
            if not campaigns_2025.empty:
                monthly_2025 = campaigns_2025.groupby(['month_name', 'platform'])['spend'].sum().reset_index()
                monthly_2025['month_name'] = pd.Categorical(
                    monthly_2025['month_name'], 
                    categories=['January', 'February', 'March'], 
                    ordered=True
                )
                monthly_2025 = monthly_2025.sort_values('month_name')
                
                for platform in ['Google', 'Meta']:
                    platform_data = monthly_2025[monthly_2025['platform'] == platform]
                    color = '#4285F4' if platform == 'Google' else '#1877F2'
                    fig.add_trace(
                        go.Bar(
                            name=platform,
                            x=platform_data['month_name'],
                            y=platform_data['spend'],
                            marker_color=color,
                            showlegend=False
                        ),
                        row=1, col=2
                    )
            
            fig.update_xaxes(title_text="Month", row=1, col=1)
            fig.update_xaxes(title_text="Month", row=1, col=2)
            fig.update_yaxes(title_text="Spend ($)", row=1, col=1)
            fig.update_yaxes(title_text="Spend ($)", row=1, col=2)
            fig.update_layout(height=400, barmode='group')
            
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            
            # Top campaigns by platform
            st.subheader("Top Campaigns by Spend")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🔍 Google Ads - Top 10 Campaigns (2025)**")
                if not campaigns_2025.empty:
                    google_campaigns = campaigns_2025[campaigns_2025['platform'] == 'Google'].groupby('campaign_name')['spend'].sum().nlargest(10).reset_index()
                    google_campaigns['spend_fmt'] = google_campaigns['spend'].apply(lambda x: f"${x:,.0f}")
                    google_campaigns.columns = ['Campaign Name', 'Spend', 'Formatted']
                    display_google = google_campaigns[['Campaign Name', 'Formatted']].copy()
                    display_google.columns = ['Campaign', 'Spend']
                    st.dataframe(display_google, use_container_width=True, hide_index=True, height=400)
                else:
                    st.info("No 2025 Google campaign data available")
            
            with col2:
                st.markdown("**📘 Meta Ads - Top 10 Campaigns (2025)**")
                if not campaigns_2025.empty:
                    meta_campaigns = campaigns_2025[campaigns_2025['platform'] == 'Meta'].groupby('campaign_name')['spend'].sum().nlargest(10).reset_index()
                    meta_campaigns['spend_fmt'] = meta_campaigns['spend'].apply(lambda x: f"${x:,.0f}")
                    meta_campaigns.columns = ['Campaign Name', 'Spend', 'Formatted']
                    display_meta = meta_campaigns[['Campaign Name', 'Formatted']].copy()
                    display_meta.columns = ['Campaign', 'Spend']
                    st.dataframe(display_meta, use_container_width=True, hide_index=True, height=400)
                else:
                    st.info("No 2025 Meta campaign data available")
            
            st.markdown("---")
            
            # Full campaign list with filters
            st.subheader("All Campaigns - Detailed View")
            
            year_filter = st.radio("Select Year:", ["2024", "2025", "Both"], horizontal=True)
            platform_filter = st.multiselect("Filter by Platform:", ["Google", "Meta"], default=["Google", "Meta"])
            
            filtered_campaigns = pd.DataFrame()
            
            if year_filter in ["2024", "Both"] and not campaigns_2024.empty:
                df_2024 = campaigns_2024[campaigns_2024['platform'].isin(platform_filter)].copy()
                df_2024['year'] = 2024
                filtered_campaigns = pd.concat([filtered_campaigns, df_2024], ignore_index=True)
            
            if year_filter in ["2025", "Both"] and not campaigns_2025.empty:
                df_2025 = campaigns_2025[campaigns_2025['platform'].isin(platform_filter)].copy()
                df_2025['year'] = 2025
                filtered_campaigns = pd.concat([filtered_campaigns, df_2025], ignore_index=True)
            
            if not filtered_campaigns.empty:
                # Aggregate by campaign
                campaign_summary = filtered_campaigns.groupby(['year', 'platform', 'campaign_name', 'month_name'])['spend'].sum().reset_index()
                campaign_summary = campaign_summary.sort_values(['year', 'platform', 'spend'], ascending=[False, True, False])
                
                # Format for display
                campaign_summary['spend_fmt'] = campaign_summary['spend'].apply(lambda x: f"${x:,.0f}")
                display_campaigns = campaign_summary[['year', 'month_name', 'platform', 'campaign_name', 'spend_fmt']].copy()
                display_campaigns.columns = ['Year', 'Month', 'Platform', 'Campaign', 'Spend']
                
                st.dataframe(display_campaigns, use_container_width=True, hide_index=True, height=600)
                
                # Download button
                csv = campaign_summary.to_csv(index=False)
                st.download_button(
                    label="📥 Download Campaign Data (CSV)",
                    data=csv,
                    file_name=f"q1_campaigns_{year_filter.lower()}_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No campaigns match the selected filters")
                
    except Exception as e:
        st.error(f"Error loading campaign data: {e}")
        st.info("Run `python3 scripts/analyze_q1_campaigns.py` to generate campaign data.")

# ===== TAB 5: DATA & METHODOLOGY =====
with tab5:
    st.header("Data & Methodology")
    
    st.subheader("Data Sources")
    
    st.markdown("**2024 Data:**")
    st.write("- **Revenue**: Shopify exec summary (Total sales over time - 2024)")
    st.write("- **Spend**: Meta + Google daily exports")
    st.write(f"  - File: `{data['spend_2024_file']}`")
    st.write("  - Platforms: Meta (69.8%), Google (30.2%)")
    st.write("  - Total 2024 spend: $7,538,825")
    
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
# 2024 spend file
{data['spend_2024_file']}

# 2025 Northbeam YTD file
{data['spend_2025_file']}

# 2025 sales file
{data['sales_2025_file']}
    """, language="text")
