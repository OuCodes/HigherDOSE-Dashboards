"""
HigherDOSE November Performance Dashboard (New)
----------------------------------------------

This Streamlit app visualizes 2024 vs 2025 performance for:
- Shopify revenue
- GA4 traffic
- Meta + Google ads
- SMS (CRM / Attentive summary)

It is intentionally separate from the existing `streamlit_app.py`
so we don't change the original BFCM dashboard.
"""

import streamlit as st
import pandas as pd
from pathlib import Path
from datetime import datetime
import plotly.express as px


st.set_page_config(
    page_title="HigherDOSE November Performance (New)",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).parent
ADS_DIR = BASE_DIR / "data" / "ads"
EXEC_SUM_DIR = ADS_DIR / "exec-sum"
MAIL_DIR = BASE_DIR / "data" / "mail"


def _pct_change(new: float, old: float) -> float:
    if old == 0 or pd.isna(old):
        return 0.0
    return (new - old) / old * 100.0


@st.cache_data(ttl=1800)
def load_core_data():
    """Load all core datasets used in this dashboard."""

    # Shopify daily exec-summary
    sales_2024 = pd.read_csv(
        EXEC_SUM_DIR / "Total sales over time - 2024-01-01 - 2024-12-31-DAILY.csv"
    )
    sales_2025 = pd.read_csv(
        EXEC_SUM_DIR / "Total sales over time - OU - 2025-01-01 - 2025-11-20.csv"
    )
    for df in (sales_2024, sales_2025):
        df["Day"] = pd.to_datetime(df["Day"])
        df["Month"] = df["Day"].dt.to_period("M")

    # GA4 traffic (session default channel group)
    ga4_2024 = pd.read_csv(
        EXEC_SUM_DIR
        / "daily-traffic_acquisition_Session_default_channel_group-2024-01-01-2024-12-31..csv",
        comment="#",
    )
    ga4_2025 = pd.read_csv(
        EXEC_SUM_DIR
        / "daily-traffic_acquisition_Session_default_channel_group-2025-01-01-2025-11-19.csv"
    )
    ga4_2024["Date"] = pd.to_datetime(ga4_2024["Date"].astype(str), format="%Y%m%d")
    ga4_2025["Date"] = pd.to_datetime(ga4_2025["Date"])
    for df in (ga4_2024, ga4_2025):
        df["Month"] = df["Date"].dt.to_period("M")

    # Meta daily exports
    meta_2024 = pd.read_csv(
        ADS_DIR / "weekly-report-2024-ads" / "meta-daily-export-jan-1-2024-to-dec-31-2024.csv"
    )
    meta_2025 = pd.read_csv(
        ADS_DIR / "meta-mtd-export-jan-01-2025-to-nov-19-2025.auto.csv"
    )
    for df in (meta_2024, meta_2025):
        df["Day"] = pd.to_datetime(df["Day"])
        df["Month"] = df["Day"].dt.to_period("M")

    # Google Ads account-level daily (skip first 2 header rows)
    google_2024 = pd.read_csv(
        ADS_DIR / "weekly-report-2024-ads" / "google-2024-account-level-daily report.csv",
        skiprows=2,
    )
    google_2025 = pd.read_csv(
        ADS_DIR / "google-mtd-export-jan-01-to-nov-19-2025-account-level-daily report.csv",
        skiprows=2,
    )
    for df in (google_2024, google_2025):
        df["Day"] = pd.to_datetime(df["Day"])
        df["Month"] = df["Day"].dt.to_period("M")
        # Normalise numeric columns (they often come with commas)
        for col in ["Cost", "Clicks", "Impr.", "Conv. value", "Conversions"]:
            if col in df.columns and df[col].dtype == "O":
                df[col] = df[col].astype(str).str.replace(",", "").astype(float)

    # Northbeam November 2025 cash snapshot (all channels)
    nb_path = ADS_DIR / "northbeam-2025-november.csv"
    try:
        nb = pd.read_csv(nb_path, engine="python", on_bad_lines="skip")
        if "accounting_mode" in nb.columns:
            nb = nb[nb["accounting_mode"] == "Cash snapshot"].copy()
        nb["date"] = pd.to_datetime(nb["date"])
    except Exception:
        nb = pd.DataFrame()

    # SMS CRM monthly summary (YoY)
    sms_path = ADS_DIR / "ytd_statistics" / "HigherDOSE CRM Reporting Data - SMS YoY Monthly.csv"
    sms_raw = pd.read_csv(sms_path, skiprows=1)
    # Expected columns like: Conversion Date, Conversions, Total Revenue, AOV, '', Conversion Date.1, Conversions.1, ...
    sms_tidy_rows = []
    for _, row in sms_raw.iterrows():
        month_2024 = row.get("Conversion Date")
        if isinstance(month_2024, str) and month_2024.strip():
            sms_tidy_rows.append(
                {
                    "year": 2024,
                    "month": month_2024,
                    "conversions": pd.to_numeric(str(row.get("Conversions", "0")).replace(",", ""), errors="coerce") or 0.0,
                    "revenue": pd.to_numeric(
                        str(row.get("Total Revenue", "0")).replace("$", "").replace(",", ""),
                        errors="coerce",
                    )
                    or 0.0,
                }
            )
        month_2025 = row.get("Conversion Date.1")
        if isinstance(month_2025, str) and month_2025.strip():
            sms_tidy_rows.append(
                {
                    "year": 2025,
                    "month": month_2025,
                    "conversions": pd.to_numeric(str(row.get("Conversions.1", "0")).replace(",", ""), errors="coerce")
                    or 0.0,
                    "revenue": pd.to_numeric(
                        str(row.get("Total Revenue.1", "0")).replace("$", "").replace(",", ""),
                        errors="coerce",
                    )
                    or 0.0,
                }
            )
    sms_monthly = pd.DataFrame(sms_tidy_rows)

    return {
        "sales_2024": sales_2024,
        "sales_2025": sales_2025,
        "ga4_2024": ga4_2024,
        "ga4_2025": ga4_2025,
        "meta_2024": meta_2024,
        "meta_2025": meta_2025,
        "google_2024": google_2024,
        "google_2025": google_2025,
        "northbeam_2025": nb,
        "sms_monthly": sms_monthly,
    }


data = load_core_data()
now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

st.title("📈 HigherDOSE November Performance – New Dashboard")
st.caption(f"Data last loaded at **{now_str}**. This app is independent from the original `streamlit_app.py`.")

st.markdown("---")


def november_core_metrics():
    """Compute Nov 1–19 2024 vs 2025 core metrics."""
    s24 = data["sales_2024"]
    s25 = data["sales_2025"]
    g24 = data["ga4_2024"]
    g25 = data["ga4_2025"]

    nov24 = s24[(s24["Day"] >= "2024-11-01") & (s24["Day"] <= "2024-11-19")]
    nov25 = s25[(s25["Day"] >= "2025-11-01") & (s25["Day"] <= "2025-11-19")]

    shop24 = nov24["Total sales"].sum()
    shop25 = nov25["Total sales"].sum()

    ga24 = g24[(g24["Date"] >= "2024-11-01") & (g24["Date"] <= "2024-11-19")]
    ga25 = g25[(g25["Date"] >= "2025-11-01") & (g25["Date"] <= "2025-11-19")]
    sess24 = ga24["Sessions"].sum()
    sess25 = ga25["Sessions"].sum()

    # Meta + Google for the same window
    m24 = data["meta_2024"]
    m25 = data["meta_2025"]
    m24_n = m24[(m24["Day"] >= "2024-11-01") & (m24["Day"] <= "2024-11-19")]
    m25_n = m25[(m25["Day"] >= "2025-11-01") & (m25["Day"] <= "2025-11-19")]
    meta_spend_24 = m24_n["Amount spent (USD)"].sum()
    meta_spend_25 = m25_n["Amount spent (USD)"].sum()
    meta_rev_24 = m24_n["Purchases conversion value"].sum()
    meta_rev_25 = m25_n["Purchases conversion value"].sum()

    g24_n = data["google_2024"][
        (data["google_2024"]["Day"] >= "2024-11-01")
        & (data["google_2024"]["Day"] <= "2024-11-19")
    ]
    g25_n = data["google_2025"][
        (data["google_2025"]["Day"] >= "2025-11-01")
        & (data["google_2025"]["Day"] <= "2025-11-19")
    ]
    goog_spend_24 = g24_n["Cost"].sum()
    goog_spend_25 = g25_n["Cost"].sum()
    goog_rev_24 = g24_n["Conv. value"].sum()
    goog_rev_25 = g25_n["Conv. value"].sum()

    spend24 = meta_spend_24 + goog_spend_24
    spend25 = meta_spend_25 + goog_spend_25
    rev24 = meta_rev_24 + goog_rev_24
    rev25 = meta_rev_25 + goog_rev_25

    sms = data["sms_monthly"]
    # November 2024 SMS revenue from CRM summary
    sms_nov_24 = sms[(sms["year"] == 2024) & (sms["month"] == "November 2024")]["revenue"].sum()
    # No explicit November 2025 row yet; leave as 0 / TBD
    sms_nov_25 = sms[(sms["year"] == 2025) & (sms["month"] == "November 2025")]["revenue"].sum()

    return {
        "shop24": shop24,
        "shop25": shop25,
        "sess24": sess24,
        "sess25": sess25,
        "spend24": spend24,
        "spend25": spend25,
        "rev24": rev24,
        "rev25": rev25,
        "sms24": sms_nov_24,
        "sms25": sms_nov_25,
    }


core = november_core_metrics()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric(
        "Shopify Revenue (Nov 1–19, 2024)",
        f"${core['shop24']:,.0f}",
    )
    st.metric(
        "Shopify Revenue (Nov 1–19, 2025)",
        f"${core['shop25']:,.0f}",
        f"{_pct_change(core['shop25'], core['shop24']):+.1f}% YoY",
    )
with col2:
    st.metric(
        "GA4 Sessions 2024 (Nov 1–19)",
        f"{core['sess24']:,.0f}",
    )
    st.metric(
        "GA4 Sessions 2025 (Nov 1–19)",
        f"{core['sess25']:,.0f}",
        f"{_pct_change(core['sess25'], core['sess24']):+.1f}% YoY",
    )
with col3:
    roas24 = core["rev24"] / core["spend24"] if core["spend24"] else 0
    roas25 = core["rev25"] / core["spend25"] if core["spend25"] else 0
    st.metric(
        "Meta+Google ROAS 2024 (Nov 1–19)",
        f"{roas24:.2f}x",
    )
    st.metric(
        "Meta+Google ROAS 2025 (Nov 1–19)",
        f"{roas25:.2f}x",
        f"{_pct_change(roas25, roas24):+.1f}% YoY",
    )
with col4:
    st.metric(
        "SMS Revenue (Nov 2024, CRM summary)",
        f"${core['sms24']:,.0f}",
    )
    st.metric(
        "SMS Revenue (Nov 2025, CRM summary)",
        "TBD" if core["sms25"] == 0 else f"${core['sms25']:,.0f}",
    )

st.markdown("---")

st.subheader("📅 Monthly Run-up – Shopify Revenue (Aug–Nov)")

shop_rows = []
for year, df in [(2024, data["sales_2024"]), (2025, data["sales_2025"])]:
    month_agg = (
        df[df["Month"].astype(str).isin([f"{year}-08", f"{year}-09", f"{year}-10", f"{year}-11"])]
        .groupby("Month")["Total sales"]
        .sum()
        .reset_index()
    )
    month_agg["year"] = year
    shop_rows.append(month_agg)
shop_monthly = pd.concat(shop_rows, ignore_index=True)
shop_monthly["Month_str"] = shop_monthly["Month"].astype(str)

fig_shop = px.bar(
    shop_monthly,
    x="Month_str",
    y="Total sales",
    color="year",
    barmode="group",
    labels={"Total sales": "Revenue", "Month_str": "Month"},
    title="Shopify Revenue by Month (Aug–Nov, 2024 vs 2025)",
)
st.plotly_chart(fig_shop, use_container_width=True)

st.markdown("---")

left, right = st.columns(2)

with left:
    st.subheader("📲 SMS – CRM Monthly YoY")
    sms = data["sms_monthly"].copy()
    # Focus on months where 2025 data exists (Jan–Sep)
    mask_months = sms["month"].isin(
        [
            "January 2024",
            "February 2024",
            "March 2024",
            "April 2024",
            "May 2024",
            "June 2024",
            "July 2024",
            "August 2024",
            "September 2024",
        ]
    )
    sms_plot = sms[mask_months | sms["month"].str.contains("2025", na=False)].copy()
    # Normalize month label to just the month name for plotting
    sms_plot["month_name"] = sms_plot["month"].str.extract(r"^(\\w+)", expand=False)
    fig_sms = px.bar(
        sms_plot,
        x="month_name",
        y="revenue",
        color="year",
        barmode="group",
        labels={"revenue": "Revenue", "month_name": "Month"},
        title="SMS Revenue by Month (Jan–Sep, CRM summary)",
    )
    st.plotly_chart(fig_sms, use_container_width=True)

with right:
    st.subheader("💰 Meta & Google – Monthly ROAS (Aug–Nov)")
    meta_rows = []
    for year, df in [(2024, data["meta_2024"]), (2025, data["meta_2025"])]:
        sub = df[df["Month"].astype(str).isin([f"{year}-08", f"{year}-09", f"{year}-10", f"{year}-11"])]
        g = (
            sub.groupby("Month")
            .agg(
                spend=("Amount spent (USD)", "sum"),
                rev=("Purchases conversion value", "sum"),
            )
            .reset_index()
        )
        g["roas"] = g["rev"] / g["spend"]
        g["channel"] = "Meta"
        g["year"] = year
        meta_rows.append(g)

    google_rows = []
    for year, df in [(2024, data["google_2024"]), (2025, data["google_2025"])]:
        sub = df[df["Month"].astype(str).isin([f"{year}-08", f"{year}-09", f"{year}-10", f"{year}-11"])]
        g = (
            sub.groupby("Month")
            .agg(spend=("Cost", "sum"), rev=("Conv. value", "sum"))
            .reset_index()
        )
        g["roas"] = g["rev"] / g["spend"]
        g["channel"] = "Google"
        g["year"] = year
        google_rows.append(g)

    ads_monthly = pd.concat(meta_rows + google_rows, ignore_index=True)
    ads_monthly["Month_str"] = ads_monthly["Month"].astype(str)
    fig_ads = px.line(
        ads_monthly,
        x="Month_str",
        y="roas",
        color="channel",
        line_dash="year",
        markers=True,
        labels={"roas": "ROAS", "Month_str": "Month"},
        title="Meta & Google ROAS by Month (Aug–Nov, 2024 vs 2025)",
    )
    st.plotly_chart(fig_ads, use_container_width=True)

st.markdown("---")

st.subheader("🌐 GA4 Traffic – Monthly Sessions (Aug–Nov)")

ga_rows = []
for year, df in [(2024, data["ga4_2024"]), (2025, data["ga4_2025"])]:
    sub = df[df["Month"].astype(str).isin([f"{year}-08", f"{year}-09", f"{year}-10", f"{year}-11"])]
    g = sub.groupby("Month").agg(sessions=("Sessions", "sum")).reset_index()
    g["year"] = year
    ga_rows.append(g)

ga_monthly = pd.concat(ga_rows, ignore_index=True)
ga_monthly["Month_str"] = ga_monthly["Month"].astype(str)

fig_ga = px.bar(
    ga_monthly,
    x="Month_str",
    y="sessions",
    color="year",
    barmode="group",
    labels={"sessions": "Sessions", "Month_str": "Month"},
    title="GA4 Sessions by Month (Aug–Nov, 2024 vs 2025)",
)
st.plotly_chart(fig_ga, use_container_width=True)





