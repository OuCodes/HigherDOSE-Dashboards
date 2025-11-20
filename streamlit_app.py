"""
HigherDOSE BFCM Dashboard - Streamlit Version
Automatically refreshes data and displays interactive visualizations
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="HigherDOSE BFCM Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Paths
DATA_DIR = Path(__file__).parent / "data" / "ads"
MAIL_DIR = Path(__file__).parent / "data" / "mail"

# BFCM Sale Start Dates
SALE_START_2024 = pd.Timestamp('2024-11-08')  # Sale started Nov 8, 2024
SALE_START_2025 = pd.Timestamp('2025-11-14')  # Sale started Nov 14, 2025 (6 days later)

@st.cache_data(ttl=1800)  # Cache for 30 minutes (more frequent updates)
def load_all_data():
    """Load all data sources with caching"""
    
    # 2024 Sales
    file_2024 = DATA_DIR / "exec-sum" / "Total sales over time - 2024-01-01 - 2024-12-31-DAILY.csv"
    sales_2024 = pd.read_csv(file_2024)
    sales_2024['Day'] = pd.to_datetime(sales_2024['Day'])
    sales_2024_full = sales_2024[(sales_2024['Day'] >= '2024-11-01') & (sales_2024['Day'] <= '2024-12-02')].copy()
    
    # 2025 Sales - automatically find the most recent file and use latest date
    exec_sum_dir = DATA_DIR / "exec-sum"
    files_2025 = sorted(exec_sum_dir.glob("Total sales over time - OU - 2025-*.csv"))
    file_2025 = files_2025[-1] if files_2025 else exec_sum_dir / "Total sales over time - OU - 2025-01-01 - 2025-11-17.csv"
    
    sales_2025 = pd.read_csv(file_2025)
    sales_2025['Day'] = pd.to_datetime(sales_2025['Day'])
    
    # Automatically detect the last complete day from the data (max date in file)
    last_complete_day = sales_2025['Day'].max()
    
    # Filter to Nov 1 onwards through the last complete day in the data
    sales_2025_full = sales_2025[(sales_2025['Day'] >= '2025-11-01') & 
                                  (sales_2025['Day'] <= last_complete_day)].copy()
    sales_2025_full['total_spend'] = 0.0
    sales_2025_full['MER'] = 0.0
    
    # 2024 Ad Spend
    meta_file = DATA_DIR / "weekly-report-2024-ads" / "meta-daily-export-jan-1-2024-to-dec-31-2024.csv"
    google_file = DATA_DIR / "weekly-report-2024-ads" / "google-2024-account-level-daily report.csv"
    
    meta_2024 = pd.read_csv(meta_file)
    meta_2024['Day'] = pd.to_datetime(meta_2024['Day'])
    meta_2024 = meta_2024[['Day', 'Amount spent (USD)']]
    meta_2024.columns = ['Day', 'meta_spend']
    
    # Google CSV has 2 header rows before data - skip them
    google_2024 = pd.read_csv(google_file, skiprows=2)
    google_2024['Day'] = pd.to_datetime(google_2024['Day'])
    google_2024 = google_2024[['Day', 'Cost']]
    google_2024.columns = ['Day', 'google_spend']
    
    # Merge 2024 spend
    sales_2024_full = sales_2024_full.merge(meta_2024, on='Day', how='left')
    sales_2024_full = sales_2024_full.merge(google_2024, on='Day', how='left')
    sales_2024_full['meta_spend'] = sales_2024_full['meta_spend'].fillna(0)
    sales_2024_full['google_spend'] = sales_2024_full['google_spend'].fillna(0)
    sales_2024_full['total_spend'] = (sales_2024_full['meta_spend'] + sales_2024_full['google_spend']) * 1.15
    sales_2024_full['MER'] = sales_2024_full.apply(
        lambda row: row['Total sales'] / row['total_spend'] if row['total_spend'] > 0 else 0, axis=1
    )
    
    # 2025 Northbeam Spend (November only to keep file size small)
    northbeam_file = DATA_DIR / "northbeam-2025-november.csv"
    try:
        # Read with error handling for large multi-column CSVs
        nb_2025 = pd.read_csv(northbeam_file, on_bad_lines='skip', engine='python')
        nb_2025 = nb_2025[nb_2025['accounting_mode'] == 'Cash snapshot'].copy()
        nb_2025['date'] = pd.to_datetime(nb_2025['date'])
        nb_spend = nb_2025.groupby('date')['spend'].sum().reset_index()  # Column is 'spend', not 'ad_spend'
        nb_spend.columns = ['Day', 'total_spend']
    except Exception as e:
        st.warning(f"Could not load Northbeam data: {e}. Using zero spend for 2025.")
        # Use the same date range as sales data for consistency
        nb_spend = pd.DataFrame({'Day': pd.date_range('2025-11-01', last_complete_day), 'total_spend': 0.0})
    
    sales_2025_full = sales_2025_full.merge(nb_spend, on='Day', how='left', suffixes=('', '_nb'))
    sales_2025_full['total_spend'] = sales_2025_full['total_spend_nb'].fillna(sales_2025_full['total_spend'])
    sales_2025_full.drop(columns=['total_spend_nb'], inplace=True)
    sales_2025_full['MER'] = sales_2025_full.apply(
        lambda row: row['Total sales'] / row['total_spend'] if row['total_spend'] > 0 else 0, axis=1
    )
    
    # Email campaigns
    emails_2024_file = MAIL_DIR / "klaviyo_campaigns_november_2024.csv"
    emails_2025_file = MAIL_DIR / "klaviyo_campaigns_november_2025.csv"
    
    try:
        emails_2024 = pd.read_csv(emails_2024_file, on_bad_lines='skip')
    except:
        emails_2024 = pd.DataFrame()  # Empty fallback
    
    try:
        emails_2025 = pd.read_csv(emails_2025_file, on_bad_lines='skip')
    except:
        emails_2025 = pd.DataFrame()  # Empty fallback
    
    return sales_2024_full, sales_2025_full, emails_2024, emails_2025

# Load data
try:
    sales_2024_full, sales_2025_full, emails_2024, emails_2025 = load_all_data()
    data_loaded = True
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
except Exception as e:
    st.error(f"Error loading data: {e}")
    data_loaded = False

# Header
st.title("📊 HigherDOSE BFCM Dashboard")
st.markdown(f"**Last Updated:** {last_updated if data_loaded else 'N/A'}")

# Sale Start Date Callout
col1, col2 = st.columns(2)
with col1:
    st.info("🔥 **2024 Sale Start:** November 8, 2024")
with col2:
    # Show last complete day for 2025 (from actual data)
    last_day_2025 = sales_2025_full['Day'].max() if len(sales_2025_full) > 0 and data_loaded else pd.Timestamp('2025-11-16')
    st.success(f"🔥 **2025 Sale Start:** November 14, 2025 (6 days later) | Data through {last_day_2025.strftime('%b %d')}")

st.markdown("---")

if not data_loaded:
    st.stop()

# Key Metrics Row
col1, col2, col3, col4 = st.columns(4)

with col1:
    total_rev_2024 = sales_2024_full['Total sales'].sum()
    st.metric("2024 Revenue (Nov 1 - Dec 2)", f"${total_rev_2024:,.0f}")

with col2:
    avg_mer_2024 = sales_2024_full['MER'].mean()
    st.metric("2024 Average MER", f"{avg_mer_2024:.2f}x")

with col3:
    total_rev_2025 = sales_2025_full['Total sales'].sum()
    last_day = sales_2025_full['Day'].max().strftime('%b %d') if len(sales_2025_full) > 0 else 'N/A'
    st.metric(f"2025 Revenue (through {last_day})", f"${total_rev_2025:,.0f}")

with col4:
    avg_mer_2025 = sales_2025_full['MER'].mean() if sales_2025_full['MER'].sum() > 0 else 0
    st.metric("2025 Average MER", f"{avg_mer_2025:.2f}x" if avg_mer_2025 > 0 else "TBD")

st.markdown("---")

# Pacing Analysis
st.subheader("🎯 2025 Pacing vs 2024")
days_2025 = len(sales_2025_full)
comparable_2024 = sales_2024_full.head(days_2025)
revenue_2024_comparable = comparable_2024['Total sales'].sum()
revenue_2025 = sales_2025_full['Total sales'].sum()
pacing_pct = (revenue_2025 / revenue_2024_comparable * 100) if revenue_2024_comparable > 0 else 0

col1, col2, col3 = st.columns(3)
with col1:
    st.metric(f"2024 First {days_2025} Days", f"${revenue_2024_comparable:,.0f}")
with col2:
    st.metric(f"2025 First {days_2025} Days", f"${revenue_2025:,.0f}")
with col3:
    pacing_delta = revenue_2025 - revenue_2024_comparable
    st.metric("Pacing", f"{pacing_pct:.1f}%", f"${pacing_delta:,.0f}", delta_color="normal" if pacing_pct >= 100 else "inverse")

st.markdown("---")

# Weekly Charts
st.subheader("📈 Weekly Revenue + MER Trends")

# Filter 2024 data to Nov 1 - Dec 2
bfcm_period_2024 = sales_2024_full[(sales_2024_full['Day'] >= '2024-11-01') & 
                                    (sales_2024_full['Day'] <= '2024-12-02')].copy()

# Filter 2025 data
bfcm_period_2025 = sales_2025_full[(sales_2025_full['Day'] >= '2025-11-01')].copy()

# Define weeks
weeks = [
    ('2024-11-01', '2024-11-07', '2025-11-01', '2025-11-07', 'Week 1: Nov 1-7'),
    ('2024-11-08', '2024-11-14', '2025-11-08', '2025-11-14', 'Week 2: Nov 8-14'),
    ('2024-11-15', '2024-11-21', '2025-11-15', '2025-11-21', 'Week 3: Nov 15-21'),
    ('2024-11-22', '2024-11-28', '2025-11-22', '2025-11-28', 'Week 4: Nov 22-28'),
    ('2024-11-29', '2024-12-02', '2025-11-28', '2025-12-01', 'BFCM: Nov 29-Dec 2')
]

# Create 5 columns for weekly charts (2 rows, 3 cols each)
row1_cols = st.columns(3)
row2_cols = st.columns(2)

all_cols = row1_cols + row2_cols

for idx, (start_2024, end_2024, start_2025, end_2025, label) in enumerate(weeks):
    week_data_2024 = bfcm_period_2024[(bfcm_period_2024['Day'] >= start_2024) & 
                                      (bfcm_period_2024['Day'] <= end_2024)]
    week_data_2025 = bfcm_period_2025[(bfcm_period_2025['Day'] >= start_2025) & 
                                      (bfcm_period_2025['Day'] <= end_2025)]
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 2024 bars
    fig.add_trace(
        go.Bar(
            x=week_data_2024['Day'].dt.strftime('%b %d'),
            y=week_data_2024['Total sales'],
            name='2024 Revenue',
            marker=dict(color='#2563EB'),
            showlegend=(idx == 0),  # Show legend only on first chart
            legendgroup='2024_rev',
            hovertemplate='<b>2024 %{x}</b><br>Revenue: $%{y:,.2f} USD<extra></extra>'
        ),
        secondary_y=False
    )
    
    # 2025 bars
    if len(week_data_2025) > 0:
        fig.add_trace(
            go.Bar(
                x=week_data_2025['Day'].dt.strftime('%b %d'),
                y=week_data_2025['Total sales'],
                name='2025 Revenue',
                marker=dict(color='#10B981'),
                showlegend=(idx == 0),  # Show legend only on first chart
                legendgroup='2025_rev',
                hovertemplate='<b>2025 %{x}</b><br>Revenue: $%{y:,.2f} USD<extra></extra>'
            ),
            secondary_y=False
        )
    
    # 2024 MER line
    fig.add_trace(
        go.Scatter(
            x=week_data_2024['Day'].dt.strftime('%b %d'),
            y=week_data_2024['MER'],
            name='2024 MER',
            mode='lines+markers',
            line=dict(color='#7C3AED', width=3),
            showlegend=(idx == 0),  # Show legend only on first chart
            legendgroup='2024_mer',
            hovertemplate='<b>2024 %{x}</b><br>MER: %{y:.2f}x<extra></extra>'
        ),
        secondary_y=True
    )
    
    # 2025 MER line
    if len(week_data_2025) > 0 and week_data_2025['MER'].sum() > 0:
        fig.add_trace(
            go.Scatter(
                x=week_data_2025['Day'].dt.strftime('%b %d'),
                y=week_data_2025['MER'],
                name='2025 MER',
                mode='lines+markers',
                line=dict(color='#F59E0B', width=3),
                showlegend=(idx == 0),  # Show legend only on first chart
                legendgroup='2025_mer',
                hovertemplate='<b>2025 %{x}</b><br>MER: %{y:.2f}x<extra></extra>'
            ),
            secondary_y=True
        )
    
    fig.update_layout(title=label, height=300)
    fig.update_yaxes(title_text="Revenue", secondary_y=False)
    fig.update_yaxes(title_text="MER", secondary_y=True)
    
    # Add sale start markers if they fall in this week's range
    # Check if 2024 sale start is in this week
    if SALE_START_2024 in week_data_2024['Day'].values:
        fig.add_shape(
            type="line",
            x0=SALE_START_2024.strftime('%b %d'),
            x1=SALE_START_2024.strftime('%b %d'),
            y0=0, y1=1,
            yref="paper",
            line=dict(color="#DC2626", width=2, dash="dash")
        )
        fig.add_annotation(
            x=SALE_START_2024.strftime('%b %d'),
            y=1.02,
            yref="paper",
            text="🔥 2024 Sale",
            showarrow=False,
            font=dict(size=10, color="#DC2626")
        )
    
    # Check if 2025 sale start is in this week
    if len(week_data_2025) > 0 and SALE_START_2025 in week_data_2025['Day'].values:
        fig.add_shape(
            type="line",
            x0=SALE_START_2025.strftime('%b %d'),
            x1=SALE_START_2025.strftime('%b %d'),
            y0=0, y1=1,
            yref="paper",
            line=dict(color="#10B981", width=2, dash="dash")
        )
        fig.add_annotation(
            x=SALE_START_2025.strftime('%b %d'),
            y=0.98,
            yref="paper",
            text="🔥 2025 Sale",
            showarrow=False,
            font=dict(size=10, color="#10B981")
        )
    
    with all_cols[idx]:
        st.plotly_chart(fig, use_container_width=True)

# Weekly Summary Table
st.markdown("---")
st.subheader("📊 Weekly Totals Summary")

# Calculate weekly totals
weekly_summary_data = []
for start_2024, end_2024, start_2025, end_2025, label in weeks:
    # 2024 data
    week_2024 = bfcm_period_2024[(bfcm_period_2024['Day'] >= start_2024) & 
                                  (bfcm_period_2024['Day'] <= end_2024)]
    # 2025 data
    week_2025 = bfcm_period_2025[(bfcm_period_2025['Day'] >= start_2025) & 
                                  (bfcm_period_2025['Day'] <= end_2025)]
    
    # 2024 totals
    weekly_summary_data.append({
        'Week': label,
        'Year': '2024',
        'Sales': f"${week_2024['Total sales'].sum():,.2f}",
        'Orders': f"{int(week_2024['Orders'].sum()):,}",
        'Spend': f"${week_2024['total_spend'].sum():,.2f}",
        'Avg MER': f"{week_2024['MER'].mean():.2f}x"
    })
    
    # 2025 totals (if data exists)
    if len(week_2025) > 0:
        weekly_summary_data.append({
            'Week': label,
            'Year': '2025',
            'Sales': f"${week_2025['Total sales'].sum():,.2f}",
            'Orders': f"{int(week_2025['Orders'].sum()):,}",
            'Spend': f"${week_2025['total_spend'].sum():,.2f}" if week_2025['total_spend'].sum() > 0 else "TBD",
            'Avg MER': f"{week_2025['MER'].mean():.2f}x" if week_2025['MER'].sum() > 0 else "TBD"
        })

weekly_summary_df = pd.DataFrame(weekly_summary_data)

# Display in two columns
col1, col2 = st.columns(2)

with col1:
    st.markdown("**📊 2024 Weekly Totals**")
    df_2024 = weekly_summary_df[weekly_summary_df['Year'] == '2024'][['Week', 'Sales', 'Orders', 'Spend', 'Avg MER']]
    st.dataframe(df_2024, use_container_width=True, hide_index=True)

with col2:
    st.markdown("**📊 2025 Weekly Totals**")
    df_2025 = weekly_summary_df[weekly_summary_df['Year'] == '2025'][['Week', 'Sales', 'Orders', 'Spend', 'Avg MER']]
    if len(df_2025) > 0:
        st.dataframe(df_2025, use_container_width=True, hide_index=True)
    else:
        st.info("2025 data not yet available for these weeks")

st.markdown("---")

# MER Trend Overview - Side by Side
st.subheader("💰 MER Trend Comparison")

col1, col2 = st.columns(2)

# 2024 MER Chart
with col1:
    st.markdown("**📈 2024 MER Trend**")
    st.caption("Nov 1 - Dec 2, 2024 (32 days)")
    
    fig_2024_mer = go.Figure()
    
    fig_2024_mer.add_trace(
        go.Scatter(
            x=bfcm_period_2024['Day'],
            y=bfcm_period_2024['MER'],
            mode='lines+markers',
            line=dict(color='#7C3AED', width=4),
            marker=dict(size=10, color='#7C3AED'),
            fill='tozeroy',
            fillcolor='rgba(124, 58, 237, 0.1)',
            showlegend=False,
            hovertemplate='<b>%{x|%b %d}</b><br>MER: %{y:.2f}x<extra></extra>'
        )
    )
    
    fig_2024_mer.add_hline(y=3.0, line_dash="dash", line_color="#EF4444", 
                           annotation_text="Target: 3.0x", annotation_position="top right")
    
    # Add sale start marker
    fig_2024_mer.add_shape(
        type="line",
        x0=SALE_START_2024,
        x1=SALE_START_2024,
        y0=0, y1=1,
        yref="paper",
        line=dict(color="#DC2626", width=3, dash="dash")
    )
    fig_2024_mer.add_annotation(
        x=SALE_START_2024,
        y=0.95,
        yref="paper",
        text="🔥 Sale Start (Nov 8)",
        showarrow=False,
        font=dict(size=11, color="#DC2626"),
        bgcolor="rgba(220, 38, 38, 0.1)",
        borderpad=4
    )
    
    # Add stats annotation
    avg_mer_2024_full = bfcm_period_2024['MER'].mean()
    max_mer_2024 = bfcm_period_2024['MER'].max()
    min_mer_2024 = bfcm_period_2024['MER'].min()
    
    fig_2024_mer.add_annotation(
        text=f"Avg: {avg_mer_2024_full:.2f}x | High: {max_mer_2024:.2f}x | Low: {min_mer_2024:.2f}x",
        xref="paper", yref="paper",
        x=0.5, y=1.15,
        showarrow=False,
        font=dict(size=12, color="#7C3AED"),
        bgcolor="rgba(124, 58, 237, 0.1)",
        borderpad=8
    )
    
    fig_2024_mer.update_layout(
        height=350,
        xaxis_title="",
        yaxis_title="MER (x)",
        showlegend=False,
        margin=dict(t=60, b=40, l=40, r=40)
    )
    
    st.plotly_chart(fig_2024_mer, use_container_width=True)

# 2025 MER Chart
with col2:
    st.markdown("**📈 2025 MER Trend**")
    
    # Filter out any days with 0 MER (incomplete/partial data)
    bfcm_2025_with_mer = bfcm_period_2025[bfcm_period_2025['MER'] > 0].copy()
    
    # Update caption with actual days shown
    days_shown = len(bfcm_2025_with_mer)
    last_day_shown = bfcm_2025_with_mer['Day'].max().strftime('%b %d') if len(bfcm_2025_with_mer) > 0 else 'N/A'
    st.caption(f"Nov 1 - {last_day_shown}, 2025 ({days_shown} days with complete data)")
    
    if len(bfcm_2025_with_mer) > 0:
        fig_2025_mer = go.Figure()
        
        fig_2025_mer.add_trace(
            go.Scatter(
                x=bfcm_2025_with_mer['Day'],
                y=bfcm_2025_with_mer['MER'],
                mode='lines+markers',
                line=dict(color='#F59E0B', width=4),
                marker=dict(size=10, color='#F59E0B'),
                showlegend=False,
                hovertemplate='<b>%{x|%b %d}</b><br>MER: %{y:.2f}x<extra></extra>'
            )
        )
        
        fig_2025_mer.add_hline(y=3.0, line_dash="dash", line_color="#EF4444", 
                               annotation_text="Target: 3.0x", annotation_position="top right")
        
        # Add sale start marker (if in date range)
        if SALE_START_2025 in bfcm_2025_with_mer['Day'].values:
            fig_2025_mer.add_shape(
                type="line",
                x0=SALE_START_2025,
                x1=SALE_START_2025,
                y0=0, y1=1,
                yref="paper",
                line=dict(color="#10B981", width=3, dash="dash")
            )
            fig_2025_mer.add_annotation(
                x=SALE_START_2025,
                y=0.95,
                yref="paper",
                text="🔥 Sale Start (Nov 14)",
                showarrow=False,
                font=dict(size=11, color="#10B981"),
                bgcolor="rgba(16, 185, 129, 0.1)",
                borderpad=4
            )
        
        # Add stats annotation
        avg_mer_2025_full = bfcm_2025_with_mer['MER'].mean()
        max_mer_2025 = bfcm_2025_with_mer['MER'].max()
        min_mer_2025 = bfcm_2025_with_mer['MER'].min()
        
        fig_2025_mer.add_annotation(
            text=f"Avg: {avg_mer_2025_full:.2f}x | High: {max_mer_2025:.2f}x | Low: {min_mer_2025:.2f}x",
            xref="paper", yref="paper",
            x=0.5, y=1.15,
            showarrow=False,
            font=dict(size=12, color="#F59E0B"),
            bgcolor="rgba(245, 158, 11, 0.1)",
            borderpad=8
        )
        
        # Set y-axis range dynamically based on actual MER values (not starting at 0)
        min_mer = bfcm_2025_with_mer['MER'].min()
        max_mer = bfcm_2025_with_mer['MER'].max()
        y_padding = (max_mer - min_mer) * 0.2  # Add 20% padding
        
        fig_2025_mer.update_layout(
            height=350,
            xaxis_title="",
            yaxis_title="MER (x)",
            showlegend=False,
            margin=dict(t=60, b=40, l=40, r=40),
            yaxis=dict(range=[max(0, min_mer - y_padding), max_mer + y_padding])  # Dynamic range
        )
        
        st.plotly_chart(fig_2025_mer, use_container_width=True)
    else:
        st.info("📊 2025 MER data will appear as spend data is tracked")

st.markdown("---")

# Daily Performance Tables
st.subheader("📋 Daily Performance Comparison")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**📊 2024 Daily Performance**")
    st.caption(f"{len(sales_2024_full)} days | Nov 1 - Dec 2")
    
    # Format for display
    sales_2024_display = sales_2024_full[['Day', 'Total sales', 'Orders', 'total_spend', 'MER']].copy()
    
    # Sort by Day (datetime) first, descending (most recent first)
    sales_2024_display = sales_2024_display.sort_values('Day', ascending=False)
    
    # Then format Date as string
    sales_2024_display['Date'] = sales_2024_display['Day'].dt.strftime('%b %d, %Y')
    
    # Format currency columns as USD
    sales_2024_display['Sales (USD)'] = sales_2024_display['Total sales'].apply(lambda x: f"${x:,.2f}")
    sales_2024_display['Spend (USD)'] = sales_2024_display['total_spend'].apply(lambda x: f"${x:,.2f}")
    
    # Format MER to 2 decimal places
    sales_2024_display['MER'] = sales_2024_display['MER'].apply(lambda x: f"{x:.2f}x")
    
    # Add sale marker
    sales_2024_display[''] = sales_2024_display['Day'].apply(
        lambda x: '🔥 SALE START' if x == SALE_START_2024 else ''
    )
    
    sales_2024_display = sales_2024_display.drop(columns=['Day', 'Total sales', 'total_spend'])
    sales_2024_display = sales_2024_display[['', 'Date', 'Sales (USD)', 'Orders', 'Spend (USD)', 'MER']]
    
    st.dataframe(
        sales_2024_display,
        use_container_width=True,
        hide_index=True,
        height=400
    )

with col2:
    st.markdown("**📊 2025 Daily Performance**")
    # Show actual last day with data
    last_day_2025 = sales_2025_full['Day'].max() if len(sales_2025_full) > 0 else pd.Timestamp.now()
    st.caption(f"{len(sales_2025_full)} days | Nov 1 - {last_day_2025.strftime('%b %d')} (complete days only)")
    
    # Format for display
    sales_2025_display = sales_2025_full[['Day', 'Total sales', 'Orders', 'total_spend', 'MER']].copy()
    
    # Sort by Day (datetime) first, descending (most recent first)
    sales_2025_display = sales_2025_display.sort_values('Day', ascending=False)
    
    # Then format Date as string
    sales_2025_display['Date'] = sales_2025_display['Day'].dt.strftime('%b %d, %Y')
    
    # Format currency columns as USD
    sales_2025_display['Sales (USD)'] = sales_2025_display['Total sales'].apply(lambda x: f"${x:,.2f}")
    sales_2025_display['Spend (USD)'] = sales_2025_display['total_spend'].apply(lambda x: f"${x:,.2f}" if x > 0 else "TBD")
    
    # Format MER to 2 decimal places
    sales_2025_display['MER'] = sales_2025_display['MER'].apply(lambda x: f"{x:.2f}x" if x > 0 else "TBD")
    
    # Add sale marker
    sales_2025_display[''] = sales_2025_display['Day'].apply(
        lambda x: '🔥 SALE START' if x == SALE_START_2025 else ''
    )
    
    sales_2025_display = sales_2025_display.drop(columns=['Day', 'Total sales', 'total_spend'])
    sales_2025_display = sales_2025_display[['', 'Date', 'Sales (USD)', 'Orders', 'Spend (USD)', 'MER']]
    
    st.dataframe(
        sales_2025_display,
        use_container_width=True,
        hide_index=True,
        height=400
    )

st.markdown("---")

# Email Campaign Tables
st.subheader("📧 Email Campaign Comparison")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**📧 2024 Email Campaigns (November)**")
    if len(emails_2024) > 0:
        # Filter for sent campaigns
        emails_2024_display = emails_2024[emails_2024.get('status', 'Sent') == 'Sent'].copy() if 'status' in emails_2024.columns else emails_2024.copy()
        
        # Filter for November 2024 only
        if 'send_datetime' in emails_2024_display.columns:
            try:
                emails_2024_display['send_dt'] = pd.to_datetime(emails_2024_display['send_datetime'], errors='coerce')
                # Remove any rows where datetime parsing failed
                emails_2024_display = emails_2024_display.dropna(subset=['send_dt'])
                
                emails_2024_display = emails_2024_display[
                    (emails_2024_display['send_dt'] >= '2024-11-01') & 
                    (emails_2024_display['send_dt'] < '2024-12-01')
                ].copy()
                
                # Sort by date descending (most recent first)
                emails_2024_display = emails_2024_display.sort_values('send_dt', ascending=False)
            except Exception as e:
                st.warning(f"Error processing 2024 email dates: {e}")
                emails_2024_display = pd.DataFrame()  # Empty on error
        
        # Format year as string to prevent comma formatting
        if 'year' in emails_2024_display.columns:
            emails_2024_display['year'] = emails_2024_display['year'].astype(str)
        
        # Select and rename columns for cleaner display
        display_cols = {}
        if 'campaign_name' in emails_2024_display.columns:
            display_cols['campaign_name'] = 'Campaign Name'
        if 'send_datetime' in emails_2024_display.columns:
            emails_2024_display['Date'] = emails_2024_display['send_dt'].dt.strftime('%b %d, %Y')
            display_cols['Date'] = 'Date'
        if 'status' in emails_2024_display.columns:
            display_cols['status'] = 'Status'
        
        # Rename columns
        emails_2024_display = emails_2024_display.rename(columns=display_cols)
        
        # Select only the renamed columns
        final_cols = list(display_cols.values())
        
        st.caption(f"{len(emails_2024_display)} campaigns in November 2024")
        st.dataframe(
            emails_2024_display[final_cols] if final_cols else emails_2024_display,
            use_container_width=True,
            hide_index=True,
            height=500
        )
    else:
        st.info("No 2024 email campaigns found")

with col2:
    st.markdown("**📧 2025 Email Campaigns (November)**")
    if len(emails_2025) > 0:
        # Filter out cancelled campaigns
        emails_2025_display = emails_2025[emails_2025.get('status', '') != 'Cancelled'].copy() if 'status' in emails_2025.columns else emails_2025.copy()
        
        # Filter for November 2025 only
        if 'send_datetime' in emails_2025_display.columns:
            try:
                emails_2025_display['send_dt'] = pd.to_datetime(emails_2025_display['send_datetime'], errors='coerce')
                # Remove any rows where datetime parsing failed
                emails_2025_display = emails_2025_display.dropna(subset=['send_dt'])
                
                emails_2025_display = emails_2025_display[
                    (emails_2025_display['send_dt'] >= '2025-11-01') & 
                    (emails_2025_display['send_dt'] < '2025-12-01')
                ].copy()
                
                # Sort by date descending (most recent first)
                emails_2025_display = emails_2025_display.sort_values('send_dt', ascending=False)
            except Exception as e:
                st.warning(f"Error processing 2025 email dates: {e}")
                emails_2025_display = pd.DataFrame()  # Empty on error
        
        # Format year as string to prevent comma formatting
        if 'year' in emails_2025_display.columns:
            emails_2025_display['year'] = emails_2025_display['year'].astype(str)
        
        # Select and rename columns for cleaner display
        display_cols = {}
        if 'campaign_name' in emails_2025_display.columns:
            display_cols['campaign_name'] = 'Campaign Name'
        if 'send_datetime' in emails_2025_display.columns:
            emails_2025_display['Date'] = emails_2025_display['send_dt'].dt.strftime('%b %d, %Y')
            display_cols['Date'] = 'Date'
        if 'status' in emails_2025_display.columns:
            # Add status emoji
            status_map = {
                'Sent': '✅ Sent',
                'Scheduled': '📅 Scheduled',
                'Draft': '📝 Draft',
                'Adding Recipients': '⏳ Adding Recipients'
            }
            emails_2025_display['Status'] = emails_2025_display['status'].map(status_map).fillna(emails_2025_display['status'])
            display_cols['Status'] = 'Status'
        
        # Rename columns
        emails_2025_display = emails_2025_display.rename(columns=display_cols)
        
        # Select only the renamed columns
        final_cols = list(display_cols.values())
        
        st.caption(f"{len(emails_2025_display)} campaigns in November 2025 (sent + scheduled)")
        st.dataframe(
            emails_2025_display[final_cols] if final_cols else emails_2025_display,
            use_container_width=True,
            hide_index=True,
            height=500
        )
    else:
        st.info("No 2025 email campaigns found")

# Footer
st.markdown("---")
st.caption("🔄 Data refreshes every 6 hours • Built with Streamlit")

