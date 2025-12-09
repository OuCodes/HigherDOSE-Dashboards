"""
HigherDOSE December Performance Dashboard
------------------------------------------

This Streamlit app visualizes December 2024 vs December 2025 performance for:
- Shopify revenue
- GA4 traffic
- Meta + Google ads
- Email campaigns (Klaviyo)
- MER (Marketing Efficiency Ratio)

This is a separate app from the existing streamlit_app.py (BFCM dashboard).
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


st.set_page_config(
    page_title="HigherDOSE December Performance",
    page_icon="🎄",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).parent
ADS_DIR = BASE_DIR / "data" / "ads"
EXEC_SUM_DIR = ADS_DIR / "exec-sum"
DECEMBER_DIR = ADS_DIR / "december-only"  # Filtered December-only data
MAIL_DIR = BASE_DIR / "data" / "mail"


def _pct_change(new: float, old: float) -> float:
    """Calculate percentage change between two values."""
    if old == 0 or pd.isna(old):
        return 0.0
    return (new - old) / old * 100.0


@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_core_data():
    """Load all core datasets used in this dashboard."""
    
    # Check if data directory exists
    if not EXEC_SUM_DIR.exists():
        st.error(f"❌ Data directory not found: {EXEC_SUM_DIR}")
        st.info("📁 Please add data files to the repository or use the file uploader below.")
        return None
    
    # Shopify daily sales data
    sales_2024_file = EXEC_SUM_DIR / "Total sales over time - 2024-01-01 - 2024-12-31-DAILY.csv"
    if not sales_2024_file.exists():
        st.error(f"❌ Missing file: Total sales over time - 2024-01-01 - 2024-12-31-DAILY.csv")
        st.info("📁 Please add this file to: data/ads/exec-sum/")
        return None
    
    sales_2024 = pd.read_csv(sales_2024_file)
    
    # Find the most recent 2025 sales file (prioritize newer data)
    sales_2025_files = sorted(EXEC_SUM_DIR.glob("Total sales over time - OU - 2025-*.csv"))
    # Filter to only include files with the expected naming pattern
    sales_2025_files = [f for f in sales_2025_files if "DECEMBER-ONLY" not in f.name]
    
    if sales_2025_files:
        # Get the most recent file (latest date in filename)
        sales_2025 = pd.read_csv(sales_2025_files[-1])
        data_file_name = sales_2025_files[-1].name
    else:
        st.warning("⚠️ No 2025 sales data found. Showing 2024 data only.")
        sales_2025 = pd.DataFrame(columns=["Day", "Total sales", "Orders"])
        data_file_name = "No 2025 data available"
    
    for df in (sales_2024, sales_2025):
        if len(df) > 0:
            df["Day"] = pd.to_datetime(df["Day"])
            df["Month"] = df["Day"].dt.to_period("M")
    
    # GA4 traffic data
    ga4_2024_files = sorted(EXEC_SUM_DIR.glob("daily-traffic_acquisition_Session_default_channel_group-2024-*.csv"))
    ga4_2025_files = sorted(EXEC_SUM_DIR.glob("daily-traffic_acquisition_Session_default_channel_group-2025-*.csv"))
    
    if ga4_2024_files:
        ga4_2024 = pd.read_csv(ga4_2024_files[-1], comment="#")
    else:
        ga4_2024 = pd.DataFrame()
    
    if ga4_2025_files:
        ga4_2025 = pd.read_csv(ga4_2025_files[-1])
    else:
        ga4_2025 = pd.DataFrame()
    
    # Parse GA4 dates
    if len(ga4_2024) > 0:
        ga4_2024["Date"] = pd.to_datetime(ga4_2024["Date"].astype(str), format="%Y%m%d", errors='coerce')
        ga4_2024["Month"] = ga4_2024["Date"].dt.to_period("M")
    
    if len(ga4_2025) > 0:
        ga4_2025["Date"] = pd.to_datetime(ga4_2025["Date"], errors='coerce')
        ga4_2025["Month"] = ga4_2025["Date"].dt.to_period("M")
    
    # Meta daily exports
    meta_2024_file = ADS_DIR / "weekly-report-2024-ads" / "meta-daily-export-jan-1-2024-to-dec-31-2024.csv"
    meta_2025_files = sorted(ADS_DIR.glob("meta-mtd-export-*.csv"))
    
    if meta_2024_file.exists():
        meta_2024 = pd.read_csv(meta_2024_file)
    else:
        meta_2024 = pd.DataFrame()
    
    if meta_2025_files:
        meta_2025 = pd.read_csv(meta_2025_files[-1])
    else:
        meta_2025 = pd.DataFrame()
    
    for df in (meta_2024, meta_2025):
        if len(df) > 0:
            df["Day"] = pd.to_datetime(df["Day"])
            df["Month"] = df["Day"].dt.to_period("M")
    
    # Google Ads account-level daily (skip first 2 header rows)
    google_2024_file = ADS_DIR / "weekly-report-2024-ads" / "google-2024-account-level-daily report.csv"
    google_2025_files = sorted(ADS_DIR.glob("google-mtd-export-*.csv"))
    
    if google_2024_file.exists():
        google_2024 = pd.read_csv(google_2024_file, skiprows=2)
    else:
        google_2024 = pd.DataFrame()
    
    if google_2025_files:
        google_2025 = pd.read_csv(google_2025_files[-1], skiprows=2)
    else:
        google_2025 = pd.DataFrame()
    
    for df in (google_2024, google_2025):
        if len(df) > 0:
            df["Day"] = pd.to_datetime(df["Day"])
            df["Month"] = df["Day"].dt.to_period("M")
            # Normalize numeric columns
            for col in ["Cost", "Clicks", "Impr.", "Conv. value", "Conversions"]:
                if col in df.columns and df[col].dtype == "O":
                    df[col] = df[col].astype(str).str.replace(",", "").astype(float)
    
    # Northbeam 2025 spend data
    nb_file = ADS_DIR / "northbeam-2025-november.csv"
    try:
        if nb_file.exists():
            nb_2025 = pd.read_csv(nb_file, engine="python", on_bad_lines="skip")
            if "accounting_mode" in nb_2025.columns:
                nb_2025 = nb_2025[nb_2025["accounting_mode"] == "Cash snapshot"].copy()
            nb_2025["date"] = pd.to_datetime(nb_2025["date"])
            nb_2025["spend"] = pd.to_numeric(nb_2025["spend"], errors='coerce').fillna(0)
        else:
            nb_2025 = pd.DataFrame()
    except Exception:
        nb_2025 = pd.DataFrame()
    
    # Email campaigns (Klaviyo)
    emails_2024_file = MAIL_DIR / "klaviyo_campaigns_november_2024.csv"
    emails_2025_file = MAIL_DIR / "klaviyo_campaigns_november_2025.csv"
    
    try:
        if emails_2024_file.exists():
            emails_2024 = pd.read_csv(emails_2024_file, on_bad_lines='skip')
        else:
            emails_2024 = pd.DataFrame()
    except:
        emails_2024 = pd.DataFrame()
    
    try:
        if emails_2025_file.exists():
            emails_2025 = pd.read_csv(emails_2025_file, on_bad_lines='skip')
        else:
            emails_2025 = pd.DataFrame()
    except:
        emails_2025 = pd.DataFrame()
    
    return {
        "sales_2024": sales_2024,
        "sales_2025": sales_2025,
        "ga4_2024": ga4_2024,
        "ga4_2025": ga4_2025,
        "meta_2024": meta_2024,
        "meta_2025": meta_2025,
        "google_2024": google_2024,
        "google_2025": google_2025,
        "northbeam_2025": nb_2025,
        "emails_2024": emails_2024,
        "emails_2025": emails_2025,
        "data_file_name": data_file_name,
    }


# Load data
with st.spinner("Loading data..."):
    data = load_core_data()
    
    # Check if data loaded successfully
    if data is None:
        st.error("### ❌ Unable to load data")
        st.markdown("---")
        st.markdown("### 📋 Setup Instructions")
        st.markdown("""
        To use this dashboard, you need to add data files to the repository:
        
        1. **Clone the repository locally:**
           ```bash
           git clone https://github.com/OuCodes/HigherDOSE-Dashboards.git
           cd HigherDOSE-Dashboards
           ```
        
        2. **Copy your data files:**
           ```bash
           # From your main HigherDOSE repository
           cp -r /path/to/HigherDOSE/data ./
           ```
        
        3. **Push to GitHub:**
           ```bash
           git add data/
           git commit -m "Add data files"
           git push
           ```
        
        4. **Required files:**
           - `data/ads/exec-sum/Total sales over time - 2024-01-01 - 2024-12-31-DAILY.csv`
           - `data/ads/exec-sum/Total sales over time - OU - 2025-*.csv`
           - GA4, Meta, Google Ads data files (optional)
        
        **Note:** Make sure your data is appropriate for a public repository!
        """)
        st.stop()

now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# Header
st.title("🎄 HigherDOSE December Performance Dashboard")
st.caption(f"**Data last loaded:** {now_str} | **Sales file:** {data['data_file_name']}")

# Sidebar controls
with st.sidebar:
    st.header("🔄 Dashboard Controls")
    
    if st.button("Clear Cache & Refresh", type="primary"):
        st.cache_data.clear()
        st.rerun()
    
    st.caption("Click to reload latest data")
    st.markdown("---")
    
    st.header("📅 Date Range Selection")
    dec_start = st.date_input(
        "December Start Date",
        value=datetime(2024, 12, 1),
        min_value=datetime(2024, 12, 1),
        max_value=datetime(2025, 12, 31)
    )
    
    dec_end = st.date_input(
        "December End Date (2024/2025)",
        value=datetime(2024, 12, 31),
        min_value=datetime(2024, 12, 1),
        max_value=datetime(2025, 12, 31)
    )
    
    st.markdown("---")
    st.info("This dashboard compares December 2024 vs December 2025 performance across all key metrics.")

st.markdown("---")


def december_core_metrics(start_date, end_date):
    """Compute December 2024 vs 2025 core metrics for the selected date range."""
    
    # Determine the year ranges
    # For 2024, use Dec 1-31 (or up to end_date if in December 2024)
    # For 2025, use Dec 1 through the same day-of-month
    
    start_2024 = "2024-12-01"
    end_2024 = min(pd.Timestamp("2024-12-31"), pd.Timestamp(end_date))
    
    start_2025 = "2025-12-01"
    end_2025 = min(pd.Timestamp("2025-12-31"), pd.Timestamp(end_date))
    
    s24 = data["sales_2024"]
    s25 = data["sales_2025"]
    
    dec24 = s24[(s24["Day"] >= start_2024) & (s24["Day"] <= end_2024)]
    dec25 = s25[(s25["Day"] >= start_2025) & (s25["Day"] <= end_2025)]
    
    shop24 = dec24["Total sales"].sum()
    shop25 = dec25["Total sales"].sum()
    orders24 = dec24["Orders"].sum()
    orders25 = dec25["Orders"].sum()
    
    # GA4 Sessions
    g24 = data["ga4_2024"]
    g25 = data["ga4_2025"]
    
    if len(g24) > 0:
        ga24 = g24[(g24["Date"] >= start_2024) & (g24["Date"] <= end_2024)]
        sess24 = ga24["Sessions"].sum() if "Sessions" in ga24.columns else 0
    else:
        sess24 = 0
    
    if len(g25) > 0:
        ga25 = g25[(g25["Date"] >= start_2025) & (g25["Date"] <= end_2025)]
        sess25 = ga25["Sessions"].sum() if "Sessions" in ga25.columns else 0
    else:
        sess25 = 0
    
    # Meta + Google spend and revenue
    m24 = data["meta_2024"]
    m25 = data["meta_2025"]
    
    if len(m24) > 0:
        m24_dec = m24[(m24["Day"] >= start_2024) & (m24["Day"] <= end_2024)]
        meta_spend_24 = m24_dec["Amount spent (USD)"].sum() if "Amount spent (USD)" in m24_dec.columns else 0
        meta_rev_24 = m24_dec["Purchases conversion value"].sum() if "Purchases conversion value" in m24_dec.columns else 0
    else:
        meta_spend_24 = 0
        meta_rev_24 = 0
    
    if len(m25) > 0:
        m25_dec = m25[(m25["Day"] >= start_2025) & (m25["Day"] <= end_2025)]
        meta_spend_25 = m25_dec["Amount spent (USD)"].sum() if "Amount spent (USD)" in m25_dec.columns else 0
        meta_rev_25 = m25_dec["Purchases conversion value"].sum() if "Purchases conversion value" in m25_dec.columns else 0
    else:
        meta_spend_25 = 0
        meta_rev_25 = 0
    
    g24_data = data["google_2024"]
    g25_data = data["google_2025"]
    
    if len(g24_data) > 0:
        g24_dec = g24_data[(g24_data["Day"] >= start_2024) & (g24_data["Day"] <= end_2024)]
        goog_spend_24 = g24_dec["Cost"].sum() if "Cost" in g24_dec.columns else 0
        goog_rev_24 = g24_dec["Conv. value"].sum() if "Conv. value" in g24_dec.columns else 0
    else:
        goog_spend_24 = 0
        goog_rev_24 = 0
    
    if len(g25_data) > 0:
        g25_dec = g25_data[(g25_data["Day"] >= start_2025) & (g25_data["Day"] <= end_2025)]
        goog_spend_25 = g25_dec["Cost"].sum() if "Cost" in g25_dec.columns else 0
        goog_rev_25 = g25_dec["Conv. value"].sum() if "Conv. value" in g25_dec.columns else 0
    else:
        goog_spend_25 = 0
        goog_rev_25 = 0
    
    # Total spend with 15% markup for other channels
    paid_spend_24 = meta_spend_24 + goog_spend_24
    total_spend_24 = paid_spend_24 * 1.15
    
    paid_spend_25 = meta_spend_25 + goog_spend_25
    total_spend_25 = paid_spend_25 * 1.15
    
    # MER calculation
    mer_24 = shop24 / total_spend_24 if total_spend_24 > 0 else 0
    mer_25 = shop25 / total_spend_25 if total_spend_25 > 0 else 0
    
    # ROAS from Meta + Google attributed revenue
    rev24 = meta_rev_24 + goog_rev_24
    rev25 = meta_rev_25 + goog_rev_25
    roas_24 = rev24 / (meta_spend_24 + goog_spend_24) if (meta_spend_24 + goog_spend_24) > 0 else 0
    roas_25 = rev25 / (meta_spend_25 + goog_spend_25) if (meta_spend_25 + goog_spend_25) > 0 else 0
    
    return {
        "shop24": shop24,
        "shop25": shop25,
        "orders24": orders24,
        "orders25": orders25,
        "sess24": sess24,
        "sess25": sess25,
        "spend24": total_spend_24,
        "spend25": total_spend_25,
        "mer24": mer_24,
        "mer25": mer_25,
        "roas24": roas_24,
        "roas25": roas_25,
        "days_2024": len(dec24),
        "days_2025": len(dec25),
    }


core = december_core_metrics(dec_start, dec_end)

# Key Metrics Row
st.subheader("📊 December Performance Overview")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        f"Shopify Revenue 2024 ({core['days_2024']} days)",
        f"${core['shop24']:,.0f}",
    )
    st.metric(
        f"Shopify Revenue 2025 ({core['days_2025']} days)",
        f"${core['shop25']:,.0f}",
        f"{_pct_change(core['shop25'], core['shop24']):+.1f}% YoY" if core['shop24'] > 0 else "N/A",
    )

with col2:
    st.metric(
        "Orders 2024",
        f"{core['orders24']:,.0f}",
    )
    st.metric(
        "Orders 2025",
        f"{core['orders25']:,.0f}",
        f"{_pct_change(core['orders25'], core['orders24']):+.1f}% YoY" if core['orders24'] > 0 else "N/A",
    )

with col3:
    st.metric(
        "MER 2024",
        f"{core['mer24']:.2f}x" if core['mer24'] > 0 else "N/A",
    )
    st.metric(
        "MER 2025",
        f"{core['mer25']:.2f}x" if core['mer25'] > 0 else "N/A",
        f"{_pct_change(core['mer25'], core['mer24']):+.1f}%" if core['mer24'] > 0 and core['mer25'] > 0 else "N/A",
    )

with col4:
    st.metric(
        "GA4 Sessions 2024",
        f"{core['sess24']:,.0f}" if core['sess24'] > 0 else "N/A",
    )
    st.metric(
        "GA4 Sessions 2025",
        f"{core['sess25']:,.0f}" if core['sess25'] > 0 else "N/A",
        f"{_pct_change(core['sess25'], core['sess24']):+.1f}% YoY" if core['sess24'] > 0 and core['sess25'] > 0 else "N/A",
    )

st.markdown("---")

# Daily Revenue Comparison
st.subheader("📈 Daily Revenue Comparison - December 2024 vs 2025")

s24 = data["sales_2024"]
s25 = data["sales_2025"]

dec24_daily = s24[(s24["Day"] >= "2024-12-01") & (s24["Day"] <= "2024-12-31")].copy()
dec25_daily = s25[(s25["Day"] >= "2025-12-01") & (s25["Day"] <= "2025-12-31")].copy()

dec24_daily["day_of_month"] = dec24_daily["Day"].dt.day
dec25_daily["day_of_month"] = dec25_daily["Day"].dt.day

fig_daily = go.Figure()

fig_daily.add_trace(
    go.Bar(
        x=dec24_daily["day_of_month"],
        y=dec24_daily["Total sales"],
        name="2024 Revenue",
        marker_color="#2563EB",
        hovertemplate='<b>Dec %{x}, 2024</b><br>Revenue: $%{y:,.0f}<extra></extra>',
    )
)

if len(dec25_daily) > 0:
    fig_daily.add_trace(
        go.Bar(
            x=dec25_daily["day_of_month"],
            y=dec25_daily["Total sales"],
            name="2025 Revenue",
            marker_color="#10B981",
            hovertemplate='<b>Dec %{x}, 2025</b><br>Revenue: $%{y:,.0f}<extra></extra>',
        )
    )

fig_daily.update_layout(
    barmode='group',
    xaxis_title="Day of Month",
    yaxis_title="Revenue ($)",
    height=450,
    hovermode='x unified',
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    )
)

st.plotly_chart(fig_daily, use_container_width=True)

st.markdown("---")

# MER Trend Comparison
st.subheader("💰 MER (Marketing Efficiency Ratio) Trend")

col1, col2 = st.columns(2)

# Calculate MER for daily data
# For 2024, use Meta + Google spend
m24 = data["meta_2024"]
g24_data = data["google_2024"]

if len(m24) > 0 and len(g24_data) > 0:
    m24_dec = m24[(m24["Day"] >= "2024-12-01") & (m24["Day"] <= "2024-12-31")]
    g24_dec = g24_data[(g24_data["Day"] >= "2024-12-01") & (g24_data["Day"] <= "2024-12-31")]
    
    # Merge spend data
    dec24_daily = dec24_daily.merge(
        m24_dec[["Day", "Amount spent (USD)"]].rename(columns={"Amount spent (USD)": "meta_spend"}),
        on="Day",
        how="left"
    )
    dec24_daily = dec24_daily.merge(
        g24_dec[["Day", "Cost"]].rename(columns={"Cost": "google_spend"}),
        on="Day",
        how="left"
    )
    
    dec24_daily["meta_spend"] = dec24_daily["meta_spend"].fillna(0)
    dec24_daily["google_spend"] = dec24_daily["google_spend"].fillna(0)
    dec24_daily["total_spend"] = (dec24_daily["meta_spend"] + dec24_daily["google_spend"]) * 1.15
    dec24_daily["MER"] = dec24_daily.apply(
        lambda row: row["Total sales"] / row["total_spend"] if row["total_spend"] > 0 else 0,
        axis=1
    )

# For 2025, use Northbeam or Meta+Google
m25 = data["meta_2025"]
g25_data = data["google_2025"]
nb_2025 = data["northbeam_2025"]

if len(nb_2025) > 0:
    # Use Northbeam
    nb_dec = nb_2025[(nb_2025["date"] >= "2025-12-01") & (nb_2025["date"] <= "2025-12-31")]
    nb_spend_daily = nb_dec.groupby("date")["spend"].sum().reset_index()
    nb_spend_daily.columns = ["Day", "total_spend"]
    
    dec25_daily = dec25_daily.merge(nb_spend_daily, on="Day", how="left")
    dec25_daily["total_spend"] = dec25_daily["total_spend"].fillna(0)
elif len(m25) > 0 and len(g25_data) > 0:
    # Use Meta + Google
    m25_dec = m25[(m25["Day"] >= "2025-12-01") & (m25["Day"] <= "2025-12-31")]
    g25_dec = g25_data[(g25_data["Day"] >= "2025-12-01") & (g25_data["Day"] <= "2025-12-31")]
    
    dec25_daily = dec25_daily.merge(
        m25_dec[["Day", "Amount spent (USD)"]].rename(columns={"Amount spent (USD)": "meta_spend"}),
        on="Day",
        how="left"
    )
    dec25_daily = dec25_daily.merge(
        g25_dec[["Day", "Cost"]].rename(columns={"Cost": "google_spend"}),
        on="Day",
        how="left"
    )
    
    dec25_daily["meta_spend"] = dec25_daily["meta_spend"].fillna(0)
    dec25_daily["google_spend"] = dec25_daily["google_spend"].fillna(0)
    dec25_daily["total_spend"] = (dec25_daily["meta_spend"] + dec25_daily["google_spend"]) * 1.15

if "total_spend" in dec25_daily.columns:
    dec25_daily["MER"] = dec25_daily.apply(
        lambda row: row["Total sales"] / row["total_spend"] if row["total_spend"] > 0 else 0,
        axis=1
    )

# Plot MER trends
with col1:
    st.markdown("**2024 MER Trend**")
    
    if "MER" in dec24_daily.columns:
        fig_mer_24 = go.Figure()
        
        fig_mer_24.add_trace(
            go.Scatter(
                x=dec24_daily["day_of_month"],
                y=dec24_daily["MER"],
                mode='lines+markers',
                line=dict(color='#7C3AED', width=3),
                marker=dict(size=8),
                hovertemplate='<b>Dec %{x}, 2024</b><br>MER: %{y:.2f}x<extra></extra>',
            )
        )
        
        fig_mer_24.add_hline(
            y=3.0,
            line_dash="dash",
            line_color="#EF4444",
            annotation_text="Target: 3.0x",
            annotation_position="right"
        )
        
        avg_mer_24 = dec24_daily["MER"].mean()
        fig_mer_24.add_annotation(
            text=f"Average MER: {avg_mer_24:.2f}x",
            xref="paper", yref="paper",
            x=0.5, y=1.1,
            showarrow=False,
            font=dict(size=12, color="#7C3AED"),
            bgcolor="rgba(124, 58, 237, 0.1)",
            borderpad=8
        )
        
        fig_mer_24.update_layout(
            xaxis_title="Day of Month",
            yaxis_title="MER (x)",
            height=350,
            showlegend=False
        )
        
        st.plotly_chart(fig_mer_24, use_container_width=True)
    else:
        st.info("MER data not available for 2024 December")

with col2:
    st.markdown("**2025 MER Trend**")
    
    if "MER" in dec25_daily.columns and len(dec25_daily) > 0:
        # Filter to only show days with MER > 0
        dec25_mer = dec25_daily[dec25_daily["MER"] > 0]
        
        if len(dec25_mer) > 0:
            fig_mer_25 = go.Figure()
            
            fig_mer_25.add_trace(
                go.Scatter(
                    x=dec25_mer["day_of_month"],
                    y=dec25_mer["MER"],
                    mode='lines+markers',
                    line=dict(color='#F59E0B', width=3),
                    marker=dict(size=8),
                    hovertemplate='<b>Dec %{x}, 2025</b><br>MER: %{y:.2f}x<extra></extra>',
                )
            )
            
            fig_mer_25.add_hline(
                y=3.0,
                line_dash="dash",
                line_color="#EF4444",
                annotation_text="Target: 3.0x",
                annotation_position="right"
            )
            
            avg_mer_25 = dec25_mer["MER"].mean()
            fig_mer_25.add_annotation(
                text=f"Average MER: {avg_mer_25:.2f}x",
                xref="paper", yref="paper",
                x=0.5, y=1.1,
                showarrow=False,
                font=dict(size=12, color="#F59E0B"),
                bgcolor="rgba(245, 158, 11, 0.1)",
                borderpad=8
            )
            
            fig_mer_25.update_layout(
                xaxis_title="Day of Month",
                yaxis_title="MER (x)",
                height=350,
                showlegend=False
            )
            
            st.plotly_chart(fig_mer_25, use_container_width=True)
        else:
            st.info("No MER data available yet for December 2025")
    else:
        st.info("MER data not available for 2025 December (spend data needed)")

st.markdown("---")

# Cumulative Revenue Growth
st.subheader("📊 Cumulative Revenue Growth")

dec24_daily_sorted = dec24_daily.sort_values("day_of_month")
dec25_daily_sorted = dec25_daily.sort_values("day_of_month")

dec24_daily_sorted["cumulative_revenue"] = dec24_daily_sorted["Total sales"].cumsum()
dec25_daily_sorted["cumulative_revenue"] = dec25_daily_sorted["Total sales"].cumsum()

fig_cumulative = go.Figure()

fig_cumulative.add_trace(
    go.Scatter(
        x=dec24_daily_sorted["day_of_month"],
        y=dec24_daily_sorted["cumulative_revenue"],
        name="2024 Cumulative",
        mode='lines+markers',
        line=dict(color='#2563EB', width=4),
        marker=dict(size=6),
        fill='tonexty',
        hovertemplate='<b>Through Dec %{x}, 2024</b><br>Total: $%{y:,.0f}<extra></extra>',
    )
)

if len(dec25_daily_sorted) > 0:
    fig_cumulative.add_trace(
        go.Scatter(
            x=dec25_daily_sorted["day_of_month"],
            y=dec25_daily_sorted["cumulative_revenue"],
            name="2025 Cumulative",
            mode='lines+markers',
            line=dict(color='#10B981', width=4),
            marker=dict(size=6),
            fill='tonexty',
            hovertemplate='<b>Through Dec %{x}, 2025</b><br>Total: $%{y:,.0f}<extra></extra>',
        )
    )

fig_cumulative.update_layout(
    xaxis_title="Day of Month",
    yaxis_title="Cumulative Revenue ($)",
    height=400,
    hovermode='x unified',
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1
    )
)

st.plotly_chart(fig_cumulative, use_container_width=True)

st.markdown("---")

# Daily Performance Tables
st.subheader("📋 Daily Performance Details")

col1, col2 = st.columns(2)

with col1:
    st.markdown("**📊 December 2024 Daily Performance**")
    
    dec24_display = dec24_daily.copy()
    dec24_display = dec24_display.sort_values("Day", ascending=False)
    
    display_cols = {
        "Day": dec24_display["Day"].dt.strftime('%b %d, %Y'),
        "Sales": dec24_display["Total sales"].apply(lambda x: f"${x:,.0f}"),
        "Orders": dec24_display["Orders"].apply(lambda x: f"{int(x):,}"),
    }
    
    if "total_spend" in dec24_display.columns:
        display_cols["Spend"] = dec24_display["total_spend"].apply(lambda x: f"${x:,.0f}")
    
    if "MER" in dec24_display.columns:
        display_cols["MER"] = dec24_display["MER"].apply(lambda x: f"{x:.2f}x" if x > 0 else "N/A")
    
    df_24_display = pd.DataFrame(display_cols)
    
    st.dataframe(
        df_24_display,
        use_container_width=True,
        hide_index=True,
        height=500
    )

with col2:
    st.markdown("**📊 December 2025 Daily Performance**")
    
    if len(dec25_daily) > 0:
        dec25_display = dec25_daily.copy()
        dec25_display = dec25_display.sort_values("Day", ascending=False)
        
        display_cols_25 = {
            "Day": dec25_display["Day"].dt.strftime('%b %d, %Y'),
            "Sales": dec25_display["Total sales"].apply(lambda x: f"${x:,.0f}"),
            "Orders": dec25_display["Orders"].apply(lambda x: f"{int(x):,}"),
        }
        
        if "total_spend" in dec25_display.columns:
            display_cols_25["Spend"] = dec25_display["total_spend"].apply(
                lambda x: f"${x:,.0f}" if x > 0 else "TBD"
            )
        
        if "MER" in dec25_display.columns:
            display_cols_25["MER"] = dec25_display["MER"].apply(
                lambda x: f"{x:.2f}x" if x > 0 else "TBD"
            )
        
        df_25_display = pd.DataFrame(display_cols_25)
        
        st.dataframe(
            df_25_display,
            use_container_width=True,
            hide_index=True,
            height=500
        )
    else:
        st.info("No data available yet for December 2025")

st.markdown("---")

# Footer
st.caption(f"🔄 Cache refreshes every 5 minutes • Built with Streamlit • Last updated: {now_str}")
