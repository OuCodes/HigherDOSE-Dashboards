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
    # Find latest 2025 YTD file
    spend_2025_files = sorted(ADS_DIR.glob("ytd_sales_data-higher_dose_llc-2025_12_18-*.csv"))
    if not spend_2025_files:
        st.error("No 2025 Northbeam YTD file found. Run scripts/pull_northbeam_ytd_2025.py first.")
        return None
    
    spend_2025_file = spend_2025_files[-1]
    spend_2025 = pd.read_csv(spend_2025_file)
    spend_2025['date'] = pd.to_datetime(spend_2025['date'])
    
    # Filter to Cash snapshot mode to avoid double counting
    spend_2025 = spend_2025[spend_2025['accounting_mode'] == 'Cash snapshot'].copy()
    
    # Aggregate to daily brand level
    spend_2025_daily = spend_2025.groupby('date').agg({
        'spend': 'sum',
        'rev': 'sum',
        'transactions': 'sum'
    }).reset_index()
    spend_2025_daily = spend_2025_daily.rename(columns={'rev': 'nb_revenue', 'transactions': 'nb_transactions'})
    spend_2025_daily['year'] = 2025
    
    # === Merge sales + spend for each year ===
    df_2024 = sales_2024.merge(spend_2024_daily[['date', 'spend']], on='date', how='left')
    df_2024['spend'] = df_2024['spend'].fillna(0)
    df_2024['MER'] = df_2024.apply(lambda x: x['revenue'] / x['spend'] if x['spend'] > 0 else 0, axis=1)
    
    df_2025 = sales_2025.merge(spend_2025_daily[['date', 'spend', 'nb_revenue', 'nb_transactions']], 
                               on='date', how='left')
    df_2025['spend'] = df_2025['spend'].fillna(0)
    df_2025['MER'] = df_2025.apply(lambda x: x['revenue'] / x['spend'] if x['spend'] > 0 else 0, axis=1)
    
    # Add quarter and month columns
    for df in [df_2024, df_2025]:
        df['quarter'] = df['date'].dt.quarter
        df['month'] = df['date'].dt.month
        df['month_name'] = df['date'].dt.strftime('%B')
        df['day_of_month'] = df['date'].dt.day
    
    # Filter to Q1 only for main analysis
    q1_2024 = df_2024[df_2024['quarter'] == 1].copy()
    q1_2025 = df_2025[df_2025['quarter'] == 1].copy()
    
    return {
        'df_2024': df_2024,
        'df_2025': df_2025,
        'q1_2024': q1_2024,
        'q1_2025': q1_2025,
        'sales_2025_file': sales_2025_file.name,
        'spend_2024_file': spend_2024_file.name,
        'spend_2025_file': spend_2025_file.name,
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
    st.markdown("---")
    st.caption(f"**Last Updated:**\n{datetime.now().strftime('%Y-%m-%d %H:%M')}")

# Header
st.title("📈 Q1 Growth & Forecast Dashboard")
st.markdown("**2024 vs 2025 Q1 Analysis with 20% Growth Targets for 2026**")
st.markdown("---")

# === TAB STRUCTURE ===
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Overview", 
    "📈 Q1 YoY Analysis", 
    "🎯 2026 Growth Targets", 
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
    monthly_combined['revenue'] = monthly_combined['revenue'].apply(lambda x: f"${x:,.0f}")
    monthly_combined['spend'] = monthly_combined['spend'].apply(lambda x: f"${x:,.0f}")
    monthly_combined['MER'] = monthly_combined['MER'].apply(lambda x: f"{x:.2f}x")
    monthly_combined['orders'] = monthly_combined['orders'].apply(lambda x: f"{int(x):,}")
    monthly_combined.columns = ['Year', 'Month', 'Revenue', 'Spend', 'MER', 'Orders']
    
    st.dataframe(monthly_combined, use_container_width=True, hide_index=True)

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
    
    # Daily trend comparison
    st.subheader("Daily Revenue Trends")
    
    fig_daily = go.Figure()
    
    fig_daily.add_trace(
        go.Scatter(x=q1_2024['date'], y=q1_2024['revenue'],
                  name='2024', mode='lines', line=dict(color='#4169E1', width=2))
    )
    
    fig_daily.add_trace(
        go.Scatter(x=q1_2025['date'], y=q1_2025['revenue'],
                  name='2025', mode='lines', line=dict(color='#32CD32', width=2))
    )
    
    fig_daily.update_layout(
        height=400,
        xaxis_title="Date",
        yaxis_title="Daily Revenue ($)",
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_daily, use_container_width=True)
    
    st.markdown("---")
    
    # MER trend comparison
    st.subheader("Daily MER Trends")
    
    fig_mer = go.Figure()
    
    # Filter out zero MER values
    q1_2024_mer = q1_2024[q1_2024['MER'] > 0].copy()
    q1_2025_mer = q1_2025[q1_2025['MER'] > 0].copy()
    
    fig_mer.add_trace(
        go.Scatter(x=q1_2024_mer['date'], y=q1_2024_mer['MER'],
                  name='2024', mode='lines+markers', 
                  line=dict(color='#7C3AED', width=2),
                  marker=dict(size=4))
    )
    
    fig_mer.add_trace(
        go.Scatter(x=q1_2025_mer['date'], y=q1_2025_mer['MER'],
                  name='2025', mode='lines+markers', 
                  line=dict(color='#F59E0B', width=2),
                  marker=dict(size=4))
    )
    
    fig_mer.add_hline(y=3.0, line_dash="dash", line_color="red", 
                      annotation_text="Target: 3.0x MER", annotation_position="right")
    
    fig_mer.update_layout(
        height=400,
        xaxis_title="Date",
        yaxis_title="MER (x)",
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_mer, use_container_width=True)

# ===== TAB 3: 2026 GROWTH TARGETS =====
with tab3:
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

# ===== TAB 4: DATA & METHODOLOGY =====
with tab4:
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
