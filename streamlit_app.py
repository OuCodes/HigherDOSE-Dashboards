"""
HigherDOSE Q4 Performance Tracker - Comprehensive Dashboard
Tracks Q4 2025 vs Q4 2024 across all key metrics
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="HigherDOSE Q4 Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Paths
DATA_DIR = Path(__file__).parent / "data" / "ads"
MAIL_DIR = Path(__file__).parent / "data" / "mail"

# Key Date Ranges
Q4_START = '10-01'  # October 1
BFCM_START_2024 = pd.Timestamp('2024-11-08')
BFCM_START_2025 = pd.Timestamp('2025-11-14')

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def load_q4_data():
    """Load all Q4 data sources with caching"""
    
    exec_sum_dir = DATA_DIR / "exec-sum"
    
    # ===== SALES DATA =====
    # 2024 Sales
    sales_2024_file = exec_sum_dir / "Total sales over time - 2024-01-01 - 2024-12-31-DAILY.csv"
    sales_2024 = pd.read_csv(sales_2024_file)
    sales_2024['Day'] = pd.to_datetime(sales_2024['Day'])
    sales_2024 = sales_2024[sales_2024['Day'] >= '2024-10-01'].copy()
    
    # 2025 Sales - auto-detect latest file
    files_2025 = sorted(exec_sum_dir.glob("Total sales over time - OU - 2025-*.csv"))
    sales_2025_file = files_2025[-1] if files_2025 else None
    if not sales_2025_file:
        st.error("No 2025 sales data found!")
        return None
    
    sales_2025 = pd.read_csv(sales_2025_file)
    sales_2025['Day'] = pd.to_datetime(sales_2025['Day'])
    sales_2025 = sales_2025[sales_2025['Day'] >= '2025-10-01'].copy()
    last_complete_day = sales_2025['Day'].max()
    
    # ===== SESSIONS DATA (Shopify) =====
    # 2025 Sessions
    sessions_2025_file = exec_sum_dir / f"Sessions over time - OU - 2025-01-01 - {last_complete_day.strftime('%Y-%m-%d')}.csv"
    if not sessions_2025_file.exists():
        # Find most recent
        session_files = sorted(exec_sum_dir.glob("Sessions over time - OU - 2025-*.csv"))
        sessions_2025_file = session_files[-1] if session_files else None
    
    if sessions_2025_file and sessions_2025_file.exists():
        sessions_2025 = pd.read_csv(sessions_2025_file)
        sessions_2025['Day'] = pd.to_datetime(sessions_2025['Day'])
        sessions_2025 = sessions_2025[sessions_2025['Day'] >= '2025-10-01'].copy()
        # Keep key columns
        sessions_2025 = sessions_2025[['Day', 'Online store visitors', 'Sessions', 
                                       'Conversion rate', 'Average order value', 'Transactions']]
    else:
        sessions_2025 = pd.DataFrame()
    
    # ===== NEW VS RETURNING CUSTOMERS =====
    # 2025 Customer Split
    customers_2025_file = exec_sum_dir / f"New vs returning customer sales - OU - 2025-01-01 - {last_complete_day.strftime('%Y-%m-%d')}.csv"
    if not customers_2025_file.exists():
        cust_files = sorted(exec_sum_dir.glob("New vs returning customer sales - OU - 2025-*.csv"))
        customers_2025_file = cust_files[-1] if cust_files else None
    
    if customers_2025_file and customers_2025_file.exists():
        customers_2025 = pd.read_csv(customers_2025_file)
        customers_2025['Day'] = pd.to_datetime(customers_2025['Day'])
        customers_2025 = customers_2025[customers_2025['Day'] >= '2025-10-01'].copy()
    else:
        customers_2025 = pd.DataFrame()
    
    # ===== PRODUCT SALES =====
    # 2024 Products
    products_2024_file = exec_sum_dir / "Total sales by product - 2024-01-01 - 2024-12-31.csv"
    if products_2024_file.exists():
        products_2024 = pd.read_csv(products_2024_file)
        products_2024['Day'] = pd.to_datetime(products_2024['Day'])
        products_2024 = products_2024[products_2024['Day'] >= '2024-10-01'].copy()
    else:
        products_2024 = pd.DataFrame()
    
    # 2025 Products
    prod_files_2025 = sorted(exec_sum_dir.glob("Total sales by product - OU - 2025-*.csv"))
    products_2025_file = prod_files_2025[-1] if prod_files_2025 else None
    if products_2025_file and products_2025_file.exists():
        products_2025 = pd.read_csv(products_2025_file)
        products_2025['Day'] = pd.to_datetime(products_2025['Day'])
        products_2025 = products_2025[products_2025['Day'] >= '2025-10-01'].copy()
    else:
        products_2025 = pd.DataFrame()
    
    # ===== TRAFFIC BY CHANNEL (GA4) =====
    # 2025 Traffic
    traffic_files = sorted(exec_sum_dir.glob("daily-traffic_acquisition_Session_default_channel_group-2025-*.csv"))
    traffic_2025_file = traffic_files[-1] if traffic_files else None
    if traffic_2025_file and traffic_2025_file.exists():
        traffic_2025 = pd.read_csv(traffic_2025_file)
        traffic_2025['Date'] = pd.to_datetime(traffic_2025['Date'])
        traffic_2025 = traffic_2025[traffic_2025['Date'] >= '2025-10-01'].copy()
    else:
        traffic_2025 = pd.DataFrame()
    
    # 2024 Traffic
    traffic_2024_file = exec_sum_dir / "daily-traffic_acquisition_Session_default_channel_group-2024-01-01-2024-12-31..csv"
    if traffic_2024_file.exists():
        traffic_2024 = pd.read_csv(traffic_2024_file)
        traffic_2024['Date'] = pd.to_datetime(traffic_2024['Date'])
        traffic_2024 = traffic_2024[traffic_2024['Date'] >= '2024-10-01'].copy()
    else:
        traffic_2024 = pd.DataFrame()
    
    # ===== SPEND DATA =====
    # 2024 Meta + Google Spend
    meta_2024_file = DATA_DIR / "weekly-report-2024-ads" / "Campaign Performance - All Time (Day) - Campaign Performance - All Time (Day).csv"
    google_2024_file = DATA_DIR / "weekly-report-2024-ads" / "google-2024-account-level-daily report.csv"
    
    meta_2024 = pd.read_csv(meta_2024_file)
    meta_2024['Day'] = pd.to_datetime(meta_2024['Day'], dayfirst=True)
    meta_2024 = meta_2024[['Day', 'Amount spent (USD)']].rename(columns={'Amount spent (USD)': 'meta_spend'})
    
    google_2024 = pd.read_csv(google_2024_file, skiprows=2)
    google_2024['Day'] = pd.to_datetime(google_2024['Day'])
    google_2024 = google_2024[['Day', 'Cost']].rename(columns={'Cost': 'google_spend'})
    
    spend_2024 = meta_2024.merge(google_2024, on='Day', how='outer')
    spend_2024['meta_spend'] = spend_2024['meta_spend'].fillna(0)
    spend_2024['google_spend'] = spend_2024['google_spend'].fillna(0)
    spend_2024['total_spend'] = (spend_2024['meta_spend'] + spend_2024['google_spend']) * 1.15
    spend_2024 = spend_2024[spend_2024['Day'] >= '2024-10-01'].copy()
    
    sales_2024 = sales_2024.merge(spend_2024[['Day', 'total_spend']], on='Day', how='left')
    sales_2024['total_spend'] = sales_2024['total_spend'].fillna(0)
    sales_2024['MER'] = sales_2024.apply(
        lambda row: row['Total sales'] / row['total_spend'] if row['total_spend'] > 0 else 0, axis=1
    )
    
    # 2025 Northbeam Spend
    northbeam_file = DATA_DIR / "northbeam-2025-november.csv"
    try:
        nb_2025 = pd.read_csv(northbeam_file, on_bad_lines='skip', engine='python')
        nb_2025 = nb_2025[nb_2025['accounting_mode'] == 'Cash snapshot'].copy()
        nb_2025['date'] = pd.to_datetime(nb_2025['date'])
        nb_spend = nb_2025.groupby('date')['spend'].sum().reset_index()
        nb_spend.columns = ['Day', 'total_spend']
        nb_spend = nb_spend[nb_spend['Day'] >= '2025-10-01'].copy()
    except Exception as e:
        st.warning(f"Could not load Northbeam data: {e}. Using zero spend for 2025.")
        nb_spend = pd.DataFrame({'Day': pd.date_range('2025-10-01', last_complete_day), 'total_spend': 0.0})
    
    sales_2025 = sales_2025.merge(nb_spend, on='Day', how='left', suffixes=('', '_nb'))
    sales_2025['total_spend'] = sales_2025['total_spend_nb'].fillna(0)
    sales_2025.drop(columns=['total_spend_nb'], inplace=True, errors='ignore')
    sales_2025['MER'] = sales_2025.apply(
        lambda row: row['Total sales'] / row['total_spend'] if row['total_spend'] > 0 else 0, axis=1
    )
    
    # ===== EMAIL CAMPAIGNS =====
    emails_2024_file = MAIL_DIR / "klaviyo_campaigns_november_2024.csv"
    emails_2025_file = MAIL_DIR / "klaviyo_campaigns_november_2025.csv"
    
    try:
        emails_2024 = pd.read_csv(emails_2024_file, on_bad_lines='skip')
    except:
        emails_2024 = pd.DataFrame()
    
    try:
        emails_2025 = pd.read_csv(emails_2025_file, on_bad_lines='skip')
    except:
        emails_2025 = pd.DataFrame()
    
    return {
        'sales_2024': sales_2024,
        'sales_2025': sales_2025,
        'sessions_2025': sessions_2025,
        'customers_2025': customers_2025,
        'products_2024': products_2024,
        'products_2025': products_2025,
        'traffic_2024': traffic_2024,
        'traffic_2025': traffic_2025,
        'emails_2024': emails_2024,
        'emails_2025': emails_2025,
        'last_complete_day': last_complete_day
    }

# Load data
with st.spinner('Loading Q4 data...'):
    data = load_q4_data()

if data is None:
    st.error("Failed to load data. Please check file paths.")
    st.stop()

# Extract data
sales_2024 = data['sales_2024']
sales_2025 = data['sales_2025']
sessions_2025 = data['sessions_2025']
customers_2025 = data['customers_2025']
products_2024 = data['products_2024']
products_2025 = data['products_2025']
traffic_2024 = data['traffic_2024']
traffic_2025 = data['traffic_2025']
emails_2024 = data['emails_2024']
emails_2025 = data['emails_2025']
last_complete_day = data['last_complete_day']

# ===== DASHBOARD TITLE =====
st.title("📊 HigherDOSE Q4 Performance Tracker")
st.markdown(f"**Last Updated:** {datetime.now().strftime('%B %d, %Y at %I:%M %p')} | **Data through:** {last_complete_day.strftime('%B %d, %Y')}")
st.markdown("---")

# ===== Q4 SUMMARY =====
st.header("🎯 Q4 Summary: 2024 vs 2025")

# Calculate Q4 totals
q4_2024_revenue = sales_2024['Total sales'].sum()
q4_2024_spend = sales_2024['total_spend'].sum()
q4_2024_mer = q4_2024_revenue / q4_2024_spend if q4_2024_spend > 0 else 0
q4_2024_orders = sales_2024['Orders'].sum()
q4_2024_aov = q4_2024_revenue / q4_2024_orders if q4_2024_orders > 0 else 0

q4_2025_revenue = sales_2025['Total sales'].sum()
q4_2025_spend = sales_2025['total_spend'].sum()
q4_2025_mer = q4_2025_revenue / q4_2025_spend if q4_2025_spend > 0 else 0
q4_2025_orders = sales_2025['Orders'].sum()
q4_2025_aov = q4_2025_revenue / q4_2025_orders if q4_2025_orders > 0 else 0

# MTD comparison (same number of days)
days_2025 = len(sales_2025)
sales_2024_mtd = sales_2024.head(days_2025)
q4_2024_mtd_revenue = sales_2024_mtd['Total sales'].sum()

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Q4 2025 Revenue (MTD)", 
        f"${q4_2025_revenue:,.0f}",
        delta=f"${q4_2025_revenue - q4_2024_mtd_revenue:,.0f} vs '24 MTD"
    )
    
with col2:
    pacing = (q4_2025_revenue / q4_2024_mtd_revenue * 100) if q4_2024_mtd_revenue > 0 else 0
    st.metric(
        "Pacing vs 2024", 
        f"{pacing:.1f}%",
        delta=f"{pacing - 100:.1f}%",
        delta_color="normal" if pacing >= 100 else "inverse"
    )

with col3:
    st.metric(
        "MER (2025 vs '24)", 
        f"{q4_2025_mer:.2f}x",
        delta=f"{q4_2025_mer - q4_2024_mer:.2f}x"
    )

with col4:
    st.metric(
        "Orders (2025 vs '24)",
        f"{q4_2025_orders:,}",
        delta=f"{q4_2025_orders - q4_2024_orders:,}"
    )

with col5:
    st.metric(
        "AOV (2025 vs '24)",
        f"${q4_2025_aov:.0f}",
        delta=f"${q4_2025_aov - q4_2024_aov:.0f}"
    )

st.markdown("---")

# ===== MONTHLY TRENDS =====
st.header("📅 Monthly Breakdown")

# Add month column
sales_2024['Month'] = sales_2024['Day'].dt.strftime('%B')
sales_2025['Month'] = sales_2025['Day'].dt.strftime('%B')

monthly_2024 = sales_2024.groupby('Month').agg({
    'Total sales': 'sum',
    'Orders': 'sum',
    'total_spend': 'sum'
}).reset_index()
monthly_2024['AOV'] = monthly_2024['Total sales'] / monthly_2024['Orders']
monthly_2024['MER'] = monthly_2024['Total sales'] / monthly_2024['total_spend']

monthly_2025 = sales_2025.groupby('Month').agg({
    'Total sales': 'sum',
    'Orders': 'sum',
    'total_spend': 'sum'
}).reset_index()
monthly_2025['AOV'] = monthly_2025['Total sales'] / monthly_2025['Orders']
monthly_2025['MER'] = monthly_2025['Total sales'] / monthly_2025['total_spend']

# Order months correctly
month_order = ['October', 'November', 'December']
monthly_2024['Month'] = pd.Categorical(monthly_2024['Month'], categories=month_order, ordered=True)
monthly_2025['Month'] = pd.Categorical(monthly_2025['Month'], categories=month_order, ordered=True)
monthly_2024 = monthly_2024.sort_values('Month')
monthly_2025 = monthly_2025.sort_values('Month')

# Display monthly comparison table
st.subheader("Monthly Performance Comparison")
col1, col2 = st.columns(2)

with col1:
    st.markdown("**2024**")
    monthly_2024_display = monthly_2024.copy()
    monthly_2024_display['Total sales'] = monthly_2024_display['Total sales'].apply(lambda x: f"${x:,.0f}")
    monthly_2024_display['total_spend'] = monthly_2024_display['total_spend'].apply(lambda x: f"${x:,.0f}")
    monthly_2024_display['AOV'] = monthly_2024_display['AOV'].apply(lambda x: f"${x:.0f}")
    monthly_2024_display['MER'] = monthly_2024_display['MER'].apply(lambda x: f"{x:.2f}x")
    st.dataframe(monthly_2024_display, hide_index=True, use_container_width=True)

with col2:
    st.markdown("**2025**")
    monthly_2025_display = monthly_2025.copy()
    monthly_2025_display['Total sales'] = monthly_2025_display['Total sales'].apply(lambda x: f"${x:,.0f}")
    monthly_2025_display['total_spend'] = monthly_2025_display['total_spend'].apply(lambda x: f"${x:,.0f}")
    monthly_2025_display['AOV'] = monthly_2025_display['AOV'].apply(lambda x: f"${x:.0f}")
    monthly_2025_display['MER'] = monthly_2025_display['MER'].apply(lambda x: f"{x:.2f}x")
    st.dataframe(monthly_2025_display, hide_index=True, use_container_width=True)

st.markdown("---")

# ===== WEEKLY TRENDS =====
st.header("📊 Weekly Trends")

# Add week column
sales_2024['Week'] = sales_2024['Day'].dt.isocalendar().week
sales_2025['Week'] = sales_2025['Day'].dt.isocalendar().week

weekly_2024 = sales_2024.groupby('Week').agg({
    'Total sales': 'sum',
    'Orders': 'sum',
    'total_spend': 'sum',
    'Day': 'min'
}).reset_index()
weekly_2024['MER'] = weekly_2024['Total sales'] / weekly_2024['total_spend']
weekly_2024['Week_Label'] = weekly_2024['Day'].dt.strftime('Week of %b %d')

weekly_2025 = sales_2025.groupby('Week').agg({
    'Total sales': 'sum',
    'Orders': 'sum',
    'total_spend': 'sum',
    'Day': 'min'
}).reset_index()
weekly_2025['MER'] = weekly_2025['Total sales'] / weekly_2025['total_spend']
weekly_2025['Week_Label'] = weekly_2025['Day'].dt.strftime('Week of %b %d')

# Create weekly chart
fig_weekly = make_subplots(
    rows=2, cols=1,
    subplot_titles=("Weekly Revenue Comparison", "Weekly MER Comparison"),
    specs=[[{"secondary_y": False}], [{"secondary_y": False}]],
    vertical_spacing=0.15,
    row_heights=[0.5, 0.5]
)

# Revenue bars
fig_weekly.add_trace(
    go.Bar(x=weekly_2024['Week_Label'], y=weekly_2024['Total sales'], 
           name="2024 Revenue", marker_color='#1f77b4', opacity=0.7),
    row=1, col=1
)
fig_weekly.add_trace(
    go.Bar(x=weekly_2025['Week_Label'], y=weekly_2025['Total sales'], 
           name="2025 Revenue", marker_color='#ff7f0e', opacity=0.7),
    row=1, col=1
)

# MER lines
fig_weekly.add_trace(
    go.Scatter(x=weekly_2024['Week_Label'], y=weekly_2024['MER'], 
               name="2024 MER", mode='lines+markers', line=dict(color='#1f77b4', width=3)),
    row=2, col=1
)
fig_weekly.add_trace(
    go.Scatter(x=weekly_2025['Week_Label'], y=weekly_2025['MER'], 
               name="2025 MER", mode='lines+markers', line=dict(color='#ff7f0e', width=3)),
    row=2, col=1
)

fig_weekly.update_yaxes(title_text="Revenue ($)", row=1, col=1)
fig_weekly.update_yaxes(title_text="MER", row=2, col=1)
fig_weekly.update_xaxes(title_text="Week", row=2, col=1)

fig_weekly.update_layout(height=800, showlegend=True, hovermode='x unified')
st.plotly_chart(fig_weekly, use_container_width=True)

st.markdown("---")

# ===== DAILY TRENDS =====
st.header("📈 Daily Performance")

# Create daily comparison table for most recent days
n_days_display = 14  # Show last 2 weeks
recent_2024 = sales_2024.tail(n_days_display).copy()
recent_2025 = sales_2025.tail(n_days_display).copy()

col1, col2 = st.columns(2)

with col1:
    st.subheader("2024 - Last 14 Days")
    recent_2024_display = recent_2024[['Day', 'Total sales', 'Orders', 'total_spend', 'MER']].copy()
    recent_2024_display['Date'] = recent_2024_display['Day'].dt.strftime('%b %d, %Y')
    recent_2024_display['Total sales'] = recent_2024_display['Total sales'].apply(lambda x: f"${x:,.0f}")
    recent_2024_display['total_spend'] = recent_2024_display['total_spend'].apply(lambda x: f"${x:,.0f}")
    recent_2024_display['MER'] = recent_2024_display['MER'].apply(lambda x: f"{x:.2f}")
    recent_2024_display = recent_2024_display[['Date', 'Total sales', 'Orders', 'total_spend', 'MER']]
    recent_2024_display = recent_2024_display.sort_values('Date', ascending=False)
    st.dataframe(recent_2024_display, hide_index=True, use_container_width=True)

with col2:
    st.subheader("2025 - Last 14 Days")
    recent_2025_display = recent_2025[['Day', 'Total sales', 'Orders', 'total_spend', 'MER']].copy()
    recent_2025_display['Date'] = recent_2025_display['Day'].dt.strftime('%b %d, %Y')
    recent_2025_display['Total sales'] = recent_2025_display['Total sales'].apply(lambda x: f"${x:,.0f}")
    recent_2025_display['total_spend'] = recent_2025_display['total_spend'].apply(lambda x: f"${x:,.0f}")
    recent_2025_display['MER'] = recent_2025_display['MER'].apply(lambda x: f"{x:.2f}")
    recent_2025_display = recent_2025_display[['Date', 'Total sales', 'Orders', 'total_spend', 'MER']]
    recent_2025_display = recent_2025_display.sort_values('Date', ascending=False)
    st.dataframe(recent_2025_display, hide_index=True, use_container_width=True)

st.markdown("---")

# ===== BFCM DEEP DIVE =====
st.header("🎁 BFCM Deep Dive")

bfcm_2024 = sales_2024[sales_2024['Day'] >= BFCM_START_2024].copy()
bfcm_2025 = sales_2025[sales_2025['Day'] >= BFCM_START_2025].copy()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("BFCM Revenue (2024)", f"${bfcm_2024['Total sales'].sum():,.0f}")
    st.metric("BFCM Revenue (2025)", f"${bfcm_2025['Total sales'].sum():,.0f}")

with col2:
    st.metric("BFCM Orders (2024)", f"{bfcm_2024['Orders'].sum():,}")
    st.metric("BFCM Orders (2025)", f"{bfcm_2025['Orders'].sum():,}")

with col3:
    bfcm_mer_2024 = bfcm_2024['Total sales'].sum() / bfcm_2024['total_spend'].sum() if bfcm_2024['total_spend'].sum() > 0 else 0
    bfcm_mer_2025 = bfcm_2025['Total sales'].sum() / bfcm_2025['total_spend'].sum() if bfcm_2025['total_spend'].sum() > 0 else 0
    st.metric("BFCM MER (2024)", f"{bfcm_mer_2024:.2f}x")
    st.metric("BFCM MER (2025)", f"{bfcm_mer_2025:.2f}x")

with col4:
    bfcm_aov_2024 = bfcm_2024['Total sales'].sum() / bfcm_2024['Orders'].sum() if bfcm_2024['Orders'].sum() > 0 else 0
    bfcm_aov_2025 = bfcm_2025['Total sales'].sum() / bfcm_2025['Orders'].sum() if bfcm_2025['Orders'].sum() > 0 else 0
    st.metric("BFCM AOV (2024)", f"${bfcm_aov_2024:.0f}")
    st.metric("BFCM AOV (2025)", f"${bfcm_aov_2025:.0f}")

st.markdown("---")

# ===== PRODUCT PERFORMANCE =====
st.header("🛍️ Product Performance")

if not products_2024.empty and not products_2025.empty:
    # Aggregate by product
    prod_summary_2024 = products_2024.groupby('Product title').agg({
        'Total sales': 'sum',
        'Net items sold': 'sum'
    }).reset_index()
    prod_summary_2024.columns = ['Product', 'Revenue_2024', 'Units_2024']
    
    prod_summary_2025 = products_2025.groupby('Product title').agg({
        'Total sales': 'sum',
        'Net items sold': 'sum'
    }).reset_index()
    prod_summary_2025.columns = ['Product', 'Revenue_2025', 'Units_2025']
    
    # Merge
    prod_comparison = prod_summary_2024.merge(prod_summary_2025, on='Product', how='outer')
    prod_comparison['Revenue_2024'] = prod_comparison['Revenue_2024'].fillna(0)
    prod_comparison['Revenue_2025'] = prod_comparison['Revenue_2025'].fillna(0)
    prod_comparison['Units_2024'] = prod_comparison['Units_2024'].fillna(0)
    prod_comparison['Units_2025'] = prod_comparison['Units_2025'].fillna(0)
    
    # Calculate growth
    prod_comparison['Revenue_Growth'] = ((prod_comparison['Revenue_2025'] - prod_comparison['Revenue_2024']) / 
                                         prod_comparison['Revenue_2024'] * 100)
    prod_comparison['Revenue_Growth'] = prod_comparison['Revenue_Growth'].replace([np.inf, -np.inf], 0).fillna(0)
    
    # Top products
    top_2025 = prod_comparison.nlargest(10, 'Revenue_2025')[['Product', 'Revenue_2025', 'Units_2025', 'Revenue_Growth']]
    
    # Growing products
    growing = prod_comparison[prod_comparison['Revenue_2024'] > 0].nlargest(10, 'Revenue_Growth')[['Product', 'Revenue_2024', 'Revenue_2025', 'Revenue_Growth']]
    
    # Declining products
    declining = prod_comparison[prod_comparison['Revenue_2024'] > 0].nsmallest(10, 'Revenue_Growth')[['Product', 'Revenue_2024', 'Revenue_2025', 'Revenue_Growth']]
    
    # New products (no 2024 revenue)
    new_products = prod_comparison[(prod_comparison['Revenue_2024'] == 0) & (prod_comparison['Revenue_2025'] > 0)].nlargest(10, 'Revenue_2025')[['Product', 'Revenue_2025', 'Units_2025']]
    
    # Display
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏆 Top 10 Products (2025 Revenue)")
        top_2025_display = top_2025.copy()
        top_2025_display['Revenue_2025'] = top_2025_display['Revenue_2025'].apply(lambda x: f"${x:,.0f}")
        top_2025_display['Revenue_Growth'] = top_2025_display['Revenue_Growth'].apply(lambda x: f"{x:+.1f}%")
        st.dataframe(top_2025_display, hide_index=True, use_container_width=True)
        
        st.subheader("📈 Top 10 Growing Products (YoY %)")
        growing_display = growing.copy()
        growing_display['Revenue_2024'] = growing_display['Revenue_2024'].apply(lambda x: f"${x:,.0f}")
        growing_display['Revenue_2025'] = growing_display['Revenue_2025'].apply(lambda x: f"${x:,.0f}")
        growing_display['Revenue_Growth'] = growing_display['Revenue_Growth'].apply(lambda x: f"{x:+.1f}%")
        st.dataframe(growing_display, hide_index=True, use_container_width=True)
    
    with col2:
        st.subheader("🆕 New Products (No 2024 Sales)")
        if not new_products.empty:
            new_products_display = new_products.copy()
            new_products_display['Revenue_2025'] = new_products_display['Revenue_2025'].apply(lambda x: f"${x:,.0f}")
            st.dataframe(new_products_display, hide_index=True, use_container_width=True)
        else:
            st.write("No new products detected.")
        
        st.subheader("📉 Top 10 Declining Products (YoY %)")
        declining_display = declining.copy()
        declining_display['Revenue_2024'] = declining_display['Revenue_2024'].apply(lambda x: f"${x:,.0f}")
        declining_display['Revenue_2025'] = declining_display['Revenue_2025'].apply(lambda x: f"${x:,.0f}")
        declining_display['Revenue_Growth'] = declining_display['Revenue_Growth'].apply(lambda x: f"{x:+.1f}%")
        st.dataframe(declining_display, hide_index=True, use_container_width=True)

else:
    st.warning("Product data not available for analysis.")

st.markdown("---")

# ===== TRAFFIC BY CHANNEL =====
st.header("🌐 Traffic by Channel (GA4)")

if not traffic_2025.empty:
    # Aggregate by channel
    traffic_summary_2025 = traffic_2025.groupby('Session default channel group').agg({
        'Sessions': 'sum',
        'Total users': 'sum',
        'Ecommerce purchases': 'sum',
        'Purchase revenue': 'sum'
    }).reset_index()
    traffic_summary_2025['Conversion Rate'] = (traffic_summary_2025['Ecommerce purchases'] / 
                                                traffic_summary_2025['Sessions'] * 100)
    traffic_summary_2025['Revenue per Session'] = (traffic_summary_2025['Purchase revenue'] / 
                                                    traffic_summary_2025['Sessions'])
    
    traffic_summary_2025 = traffic_summary_2025.sort_values('Sessions', ascending=False).head(10)
    
    st.subheader("Top 10 Channels by Sessions (2025)")
    traffic_display = traffic_summary_2025.copy()
    traffic_display['Sessions'] = traffic_display['Sessions'].apply(lambda x: f"{x:,}")
    traffic_display['Total users'] = traffic_display['Total users'].apply(lambda x: f"{x:,}")
    traffic_display['Purchase revenue'] = traffic_display['Purchase revenue'].apply(lambda x: f"${x:,.0f}")
    traffic_display['Conversion Rate'] = traffic_display['Conversion Rate'].apply(lambda x: f"{x:.2f}%")
    traffic_display['Revenue per Session'] = traffic_display['Revenue per Session'].apply(lambda x: f"${x:.2f}")
    st.dataframe(traffic_display, hide_index=True, use_container_width=True)
else:
    st.warning("Traffic channel data not available.")

st.markdown("---")

# Footer
st.caption(f"Dashboard auto-refreshes every 30 minutes | Data through {last_complete_day.strftime('%B %d, %Y')}")

