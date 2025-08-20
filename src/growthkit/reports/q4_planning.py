#!/usr/bin/env python3
"""
Q4 2025 Planning – Monthly Demand and Channel Spend

Reads standardized exports from `data/ads/q4-planning-2025/` and produces:
  - q4-2025-product-forecast.csv
  - q4-2025-channel-spend-plan.csv
  - q4-2025-planning.md (markdown summary)

Design principles:
  - Do not double-count attribution: use platform exports for spend; treat Northbeam only
    as optional mapping/context. Keep accrual vs cash separate – do not sum them.
  - Be resilient to missing Shopify inventory fields; prefer Net items sold if available.
  - Use 2024 Q4 as baseline; apply +25% target for 2025 Q4. Allocate by 2024 share.
  - New product ramp (Filtered Showerhead) can be overlaid using analog launch data.
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd
import numpy as np

from growthkit.reports import product_data


ROOT = Path(__file__).resolve().parents[3]  # repo root
PLANNING_DIR = ROOT / "data" / "ads" / "q4-planning-2025"


@dataclass
class ProductMonthly:
    month: str
    product: str
    revenue_2024: float
    units_2024: float
    aov_2024: float
    ntb_pct_2024: float


@dataclass
class ChannelMonthly:
    month: str
    channel: str
    spend_2024: float
    revenue_2024: float
    roas_2024: float


def _read_csv(path: Path, **read_kwargs) -> Optional[pd.DataFrame]:
    if not path or not path.exists():
        return None
    try:
        df = pd.read_csv(path, **read_kwargs)
        return df
    except Exception:
        return None


# -------------------------------
# Shopify loaders
# -------------------------------

def load_shopify_product_sales(year: int) -> Optional[pd.DataFrame]:
    path = PLANNING_DIR / "shopify" / f"total-sales-by-product-{year}Q4.csv"
    df = _read_csv(path)
    if df is None:
        return None

    cols = {c.lower().strip(): c for c in df.columns}
    day_col = next((cols[k] for k in cols if k in {"day", "date"}), None)
    title_col = next((cols[k] for k in cols if k in {"product title", "title", "product"}), None)
    sales_col = next((cols[k] for k in cols if k in {"total sales", "net sales", "gross sales"}), None)
    units_col = next((cols[k] for k in cols if k in {"net items sold", "units", "quantity"}), None)
    new_c_col = next((cols[k] for k in cols if k in {"new customers", "new", "new revenue"}), None)
    ret_c_col = next((cols[k] for k in cols if k in {"returning customers", "returning", "returning revenue"}), None)

    if title_col is None or sales_col is None:
        return None

    work = df.copy()
    if day_col and day_col in work.columns:
        work["__day"] = pd.to_datetime(work[day_col], errors="coerce")
        work["month"] = work["__day"].dt.strftime("%Y-%m")
    else:
        work["month"] = f"{year}-10"

    work["product"] = work[title_col].astype(str)
    work["revenue"] = pd.to_numeric(work[sales_col], errors="coerce").fillna(0.0)
    work["units"] = pd.to_numeric(work[units_col], errors="coerce").fillna(0.0) if units_col else 0.0

    if new_c_col and ret_c_col:
        new_v = pd.to_numeric(work[new_c_col], errors="coerce").fillna(0.0)
        ret_v = pd.to_numeric(work[ret_c_col], errors="coerce").fillna(0.0)
        denom = (new_v + ret_v).replace(0, np.nan)
        work["ntb_pct"] = (new_v / denom * 100.0).fillna(0.0)
    else:
        work["ntb_pct"] = 0.0

    def to_canonical(name: str) -> str:
        key = str(name).strip().lower()
        return product_data.ALIASES.get(key, name)

    work["product_canonical"] = work["product"].apply(to_canonical)

    agg = (
        work.groupby(["month", "product_canonical"]).agg(
            revenue=("revenue", "sum"),
            units=("units", "sum"),
            ntb_pct=("ntb_pct", "mean"),
        ).reset_index()
    )
    agg["aov"] = agg.apply(lambda r: (r["revenue"] / r["units"]) if r["units"] else 0.0, axis=1)
    agg = agg[agg["month"].isin([f"{year}-10", f"{year}-11", f"{year}-12"])]

    return agg.rename(columns={"product_canonical": "product"})


def load_shopify_totals(year: int) -> Optional[pd.DataFrame]:
    path = PLANNING_DIR / "shopify" / f"total-sales-over-time-{year}Q4.csv"
    df = _read_csv(path)
    if df is None:
        return None
    cols = {c.lower().strip(): c for c in df.columns}
    day_col = next((cols[k] for k in cols if k in {"day", "date"}), None)
    sales_col = next((cols[k] for k in cols if k in {"total sales", "net sales", "gross sales"}), None)
    orders_col = next((cols[k] for k in cols if k in {"orders", "total orders"}), None)
    if sales_col is None:
        return None
    work = df.copy()
    if day_col and day_col in work.columns:
        work["__day"] = pd.to_datetime(work[day_col], errors="coerce")
        work["month"] = work["__day"].dt.strftime("%Y-%m")
    else:
        work["month"] = f"{year}-10"
    work["revenue"] = pd.to_numeric(work[sales_col], errors="coerce").fillna(0.0)
    work["orders"] = pd.to_numeric(work[orders_col], errors="coerce").fillna(0.0) if orders_col else 0.0
    return work.groupby("month")["revenue", "orders"].sum().reset_index()


# -------------------------------
# Ads loaders (channel-level)
# -------------------------------

def _load_ads_generic(path: Path, spend_cols: List[str], value_cols: List[str]) -> Optional[pd.DataFrame]:
    # Flexible CSV read with Google-specific fallback
    df: Optional[pd.DataFrame]
    try:
        df = pd.read_csv(path)
    except Exception:
        df = None
    if df is None and str(path.name).startswith("google-ads-"):
        try:
            df = pd.read_csv(path, skiprows=2)
        except Exception:
            df = None
    if df is None:
        return None
    # Normalize columns
    cols_map = {c.lower().strip(): c for c in df.columns}

    def _find_day_col() -> Optional[str]:
        # allow fuzzy: any column containing 'day' or 'date'
        for lc, orig in cols_map.items():
            if "day" in lc or lc == "date" or "date" in lc:
                return orig
        return None

    def _find_spend_col() -> Optional[str]:
        # exact matches first
        for key in spend_cols:
            if key in cols_map:
                return cols_map[key]
        # fuzzy contains for common patterns (handles parentheses like "amount spent (usd)")
        # Prefer 'amount spent' and 'cost', but EXCLUDE 'return on ad spend' / 'roas'
        for lc, orig in cols_map.items():
            if ("amount spent" in lc or lc == "cost" or lc.startswith("cost (")) and ("return on ad spend" not in lc and "roas" not in lc):
                return orig
        # last resort: a bare 'spend' column that is not ROAS
        for lc, orig in cols_map.items():
            if lc == "spend" and ("return on ad spend" not in lc and "roas" not in lc):
                return orig
        return None

    def _find_value_col() -> Optional[str]:
        # exact matches first
        for key in value_cols:
            if key in cols_map:
                return cols_map[key]
        # fuzzy contains for conversion value columns
        for lc, orig in cols_map.items():
            if any(k in lc for k in ["conv. value", "conversion value", "purchases conversion value", "purchase value"]):
                return orig
        return None

    day_col = _find_day_col()
    spend_col = _find_spend_col()
    value_col = _find_value_col()

    # Google exports often include 1-2 preface rows; retry with skip if day column missing
    if day_col is None and path.name.startswith("google-ads-"):
        try:
            df = pd.read_csv(path, skiprows=2)
            cols_map = {c.lower().strip(): c for c in df.columns}
            day_col = _find_day_col()
            spend_col = _find_spend_col()
            value_col = _find_value_col()
        except Exception:
            pass

    # If still no day or spend, give up
    if spend_col is None or day_col is None:
        return None

    work = df.copy()
    # Parse to datetime then to month YYYY-MM
    work["__day"] = pd.to_datetime(work[day_col], errors="coerce")
    work["month"] = work["__day"].dt.strftime("%Y-%m")

    work["spend"] = pd.to_numeric(work[spend_col], errors="coerce").fillna(0.0)
    if value_col:
        # Remove thousands separators (e.g., "12,735.04") before conversion
        revenue_series = work[value_col].astype(str).str.replace(",", "", regex=False)
        work["revenue"] = pd.to_numeric(revenue_series, errors="coerce").fillna(0.0)
    else:
        work["revenue"] = 0.0
    return work


def load_meta_ads(year: int) -> Optional[pd.DataFrame]:
    path = PLANNING_DIR / "ads" / f"meta-ads-{year}Q4-daily.csv"
    df = _load_ads_generic(
        path,
        spend_cols=["amount spent", "spend", "cost"],
        value_cols=["purchase value", "conv. value", "conversion value", "purchase conversion value"],
    )
    if df is None:
        return None
    df["channel"] = "Facebook Ads"
    return df


def load_google_ads(year: int) -> Optional[pd.DataFrame]:
    path = PLANNING_DIR / "ads" / f"google-ads-{year}Q4-daily.csv"
    df = _load_ads_generic(
        path,
        spend_cols=["cost", "spend", "amount spent"],
        value_cols=["conv. value", "conversion value", "purchase value"],
    )
    if df is None:
        return None
    df["channel"] = "Google Ads"
    return df


def load_optional_ads(filename: str, channel_name: str) -> Optional[pd.DataFrame]:
    path = PLANNING_DIR / "ads" / filename
    df = _load_ads_generic(
        path,
        spend_cols=["cost", "spend", "amount spent"],
        value_cols=["conv. value", "conversion value", "purchase value", "revenue"],
    )
    if df is None:
        return None
    df["channel"] = channel_name
    return df


def monthly_channel_summary(year: int) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for loader in (load_meta_ads, load_google_ads):
        df = loader(year)
        if df is not None:
            frames.append(df)

    opt = [
        (f"twitter-ads-{year}Q4-daily.csv", "Twitter Ads"),
        (f"affiliate-{year}Q4-daily.csv", "Affiliate"),
        (f"pinterest-ads-{year}Q4-daily.csv", "Pinterest Ads"),
        (f"tiktok-ads-{year}Q4-daily.csv", "TikTok Ads"),
        (f"microsoft-ads-{year}Q4-daily.csv", "Microsoft Ads"),
    ]
    for fname, chan in opt:
        df = load_optional_ads(fname, chan)
        if df is not None:
            frames.append(df)

    if not frames:
        return pd.DataFrame(columns=["month", "channel", "spend", "revenue", "roas"])

    full = pd.concat(frames, ignore_index=True)

    agg = (
        full.groupby(["month", "channel"]).agg(
            spend=("spend", "sum"),
            revenue=("revenue", "sum"),
        ).reset_index()
    )
    agg["roas"] = agg.apply(lambda r: (r["revenue"] / r["spend"]) if r["spend"] else 0.0, axis=1)
    agg = agg[agg["month"].isin([f"{year}-10", f"{year}-11", f"{year}-12"])]
    return agg


# -------------------------------
# Launch analogs (new product ramp)
# -------------------------------

def load_launch_analog(name: str = "body-sculptor-launch.csv") -> Optional[pd.DataFrame]:
    path = PLANNING_DIR / "launch-analogs" / name
    df = _read_csv(path)
    if df is None:
        return None
    cols = {c.lower().strip(): c for c in df.columns}
    day_col = next((cols[k] for k in cols if k in {"day", "date"}), None)
    week_col = next((cols[k] for k in cols if k in {"week", "week start", "week_start"}), None)
    units_col = next((cols[k] for k in cols if k in {"units", "net items sold", "quantity"}), None)
    revenue_col = next((cols[k] for k in cols if k in {"revenue", "total sales"}), None)
    work = df.copy()
    if week_col:
        work["__period"] = pd.to_datetime(work[week_col], errors="coerce")
    elif day_col:
        work["__period"] = pd.to_datetime(work[day_col], errors="coerce").dt.to_period("W").apply(lambda p: p.start_time)
    else:
        return None
    if units_col:
        work["units"] = pd.to_numeric(work[units_col], errors="coerce").fillna(0.0)
    else:
        work["units"] = 0.0
    if revenue_col:
        work["revenue"] = pd.to_numeric(work[revenue_col], errors="coerce").fillna(0.0)
    else:
        work["revenue"] = 0.0

    weekly = work.groupby("__period")["units", "revenue"].sum().reset_index().rename(columns={"__period": "week_start"})
    return weekly


# -------------------------------
# Planning calculations
# -------------------------------

def build_2024_product_baseline() -> pd.DataFrame:
    agg = load_shopify_product_sales(2024)
    if agg is None or agg.empty:
        return pd.DataFrame(columns=["month", "product", "revenue_2024", "units_2024", "aov_2024", "ntb_pct_2024"])
    out = agg.rename(columns={"revenue": "revenue_2024", "units": "units_2024", "aov": "aov_2024", "ntb_pct": "ntb_pct_2024"})
    return out[["month", "product", "revenue_2024", "units_2024", "aov_2024", "ntb_pct_2024"]]


def build_2023_product_baseline() -> pd.DataFrame:
    agg = load_shopify_product_sales(2023)
    if agg is None or agg.empty:
        return pd.DataFrame(columns=["month", "product", "revenue_2023", "units_2023"])
    out = agg.rename(columns={"revenue": "revenue_2023", "units": "units_2023"})
    return out[["month", "product", "revenue_2023", "units_2023"]]


def build_2024_channel_baseline() -> pd.DataFrame:
    agg = monthly_channel_summary(2024)
    if agg is None or agg.empty:
        return pd.DataFrame(columns=["month", "channel", "spend_2024", "revenue_2024", "roas_2024"])
    out = agg.rename(columns={"spend": "spend_2024", "revenue": "revenue_2024", "roas": "roas_2024"})
    return out[["month", "channel", "spend_2024", "revenue_2024", "roas_2024"]]


def apply_25pct_target_product(baseline_2024: pd.DataFrame) -> pd.DataFrame:
    if baseline_2024.empty:
        return baseline_2024
    month_totals = baseline_2024.groupby("month")["revenue_2024"].sum().rename("month_total").reset_index()
    work = baseline_2024.merge(month_totals, on="month", how="left")
    work["share"] = work.apply(lambda r: (r["revenue_2024"] / r["month_total"]) if r["month_total"] else 0.0, axis=1)
    work["revenue_2025_target"] = work["share"] * work["month_total"] * 1.25
    work["units_2025_target"] = work.apply(
        lambda r: (r["revenue_2025_target"] / r["aov_2024"]) if r["aov_2024"] else (r["share"] * r["units_2024"] * 1.25),
        axis=1,
    )
    cols = [
        "month",
        "product",
        "revenue_2024",
        "units_2024",
        "aov_2024",
        "ntb_pct_2024",
        "revenue_2025_target",
        "units_2025_target",
    ]
    return work[cols]


def apply_25pct_target_channel(baseline_2024: pd.DataFrame) -> pd.DataFrame:
    if baseline_2024.empty:
        return baseline_2024
    month_totals = baseline_2024.groupby("month")["revenue_2024"].sum().rename("month_total").reset_index()
    work = baseline_2024.merge(month_totals, on="month", how="left")
    work["rev_share"] = work.apply(lambda r: (r["revenue_2024"] / r["month_total"]) if r["month_total"] else 0.0, axis=1)
    work["revenue_2025_target"] = work["rev_share"] * work["month_total"] * 1.25
    work["spend_2025_target"] = work.apply(lambda r: (r["revenue_2025_target"] / r["roas_2024"]) if r["roas_2024"] else 0.0, axis=1)
    cols = [
        "month",
        "channel",
        "spend_2024",
        "revenue_2024",
        "roas_2024",
        "spend_2025_target",
        "revenue_2025_target",
    ]
    return work[cols]


def overlay_new_product_ramp(product_df: pd.DataFrame, analog_weekly: Optional[pd.DataFrame], product_name: str = "Filtered Showerhead", launch_month: str = "2025-11", price: Optional[float] = None) -> pd.DataFrame:
    if analog_weekly is None or analog_weekly.empty:
        return product_df

    wk = analog_weekly.copy().sort_values("week_start").reset_index(drop=True)

    launch = pd.to_datetime(f"{launch_month}-01")
    wk["week_idx"] = np.arange(len(wk))
    wk["date_sim"] = launch + pd.to_timedelta(wk["week_idx"] * 7, unit="D")
    wk["month"] = wk["date_sim"].dt.strftime("%Y-%m")

    monthly = wk.groupby("month")["units", "revenue"].sum().reset_index()
    monthly = monthly[monthly["month"].isin(["2025-10", "2025-11", "2025-12"])]

    add = monthly.copy()
    add["product"] = product_name
    if price is not None:
        add["revenue"] = add["units"] * float(price)

    if product_df is None or product_df.empty:
        base_cols = [
            "month",
            "product",
            "revenue_2024",
            "units_2024",
            "aov_2024",
            "ntb_pct_2024",
            "revenue_2025_target",
            "units_2025_target",
        ]
        product_df = pd.DataFrame(columns=base_cols)

    work = product_df.copy()
    for m in ["2025-10", "2025-11", "2025-12"]:
        if not ((work["month"] == m) & (work["product"] == product_name)).any():
            work = pd.concat([
                work,
                pd.DataFrame([{ "month": m, "product": product_name, "revenue_2024": 0.0, "units_2024": 0.0, "aov_2024": 0.0, "ntb_pct_2024": 0.0, "revenue_2025_target": 0.0, "units_2025_target": 0.0 }]),
            ], ignore_index=True)

    add_map_units = {(r["month"], product_name): r["units"] for _, r in add.iterrows()}
    add_map_rev = {(r["month"], product_name): r["revenue"] for _, r in add.iterrows()}

    work["units_2025_target"] = work.apply(lambda row: row["units_2025_target"] + add_map_units.get((row["month"], row["product"]), 0.0), axis=1)
    work["revenue_2025_target"] = work.apply(lambda row: row["revenue_2025_target"] + add_map_rev.get((row["month"], row["product"]), 0.0), axis=1)

    return work


# -------------------------------
# Northbeam loaders for channel shares
# -------------------------------

def _find_first_csv(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    for p in sorted(path.glob("*.csv")):
        return p
    return None


def load_northbeam_ytd_2025() -> Optional[pd.DataFrame]:
    nb_dir = PLANNING_DIR / "northbeam"
    nb_file = _find_first_csv(nb_dir)
    if not nb_file:
        return None
    try:
        df = pd.read_csv(nb_file)
    except Exception:
        return None
    cols = {c.lower().strip(): c for c in df.columns}
    # Identify date, channel, spend columns
    date_col = None
    for k, v in cols.items():
        if k in {"day", "date"} or "date" in k:
            date_col = v
            break
    chan_col = None
    for k, v in cols.items():
        if "breakdown_platform" in k or "channel" in k or "platform" in k:
            chan_col = v
            break
    spend_col = None
    for k, v in cols.items():
        if k == "spend" or k.startswith("spend (") or "amount spent" in k or k == "cost":
            spend_col = v
            break
    if not chan_col or not spend_col:
        return None
    work = df.copy()
    if date_col and date_col in work.columns:
        work["__day"] = pd.to_datetime(work[date_col], errors="coerce")
        work = work[work["__day"].dt.year == 2025]
    work["channel_raw"] = work[chan_col].astype(str).str.lower()
    work["spend"] = pd.to_numeric(work[spend_col], errors="coerce").fillna(0.0)

    def map_nb_channel(val: str) -> str:
        v = val.lower()
        if any(k in v for k in ["facebook", "meta", "instagram"]):
            return "Facebook Ads"
        if "google" in v:
            return "Google Ads"
        if "tiktok" in v:
            return "TikTok Ads"
        if "pinterest" in v:
            return "Pinterest Ads"
        if any(k in v for k in ["bing", "microsoft"]):
            return "Microsoft Ads"
        if any(k in v for k in ["awin", "affiliate", "shopmyshelf", "shareasale"]):
            return "Affiliate"
        if "applovin" in v:
            return "AppLovin"
        return val.title()

    work["channel"] = work["channel_raw"].apply(map_nb_channel)
    agg = work.groupby("channel")["spend"].sum().reset_index()
    total = agg["spend"].sum()
    if total <= 0:
        return None
    agg["share"] = agg["spend"] / total
    return agg


def load_northbeam_last_30_shares() -> Optional[pd.DataFrame]:
    nb_dir = PLANNING_DIR / "northbeam"
    nb_file = _find_first_csv(nb_dir)
    if not nb_file:
        return None
    try:
        df = pd.read_csv(nb_file)
    except Exception:
        return None
    cols = {c.lower().strip(): c for c in df.columns}
    date_col = None
    for k, v in cols.items():
        if k in {"day", "date"} or "date" in k:
            date_col = v
            break
    chan_col = None
    for k, v in cols.items():
        if "breakdown_platform" in k or "channel" in k or "platform" in k:
            chan_col = v
            break
    spend_col = None
    for k, v in cols.items():
        if k == "spend" or k.startswith("spend (") or "amount spent" in k or k == "cost":
            spend_col = v
            break
    if not chan_col or not spend_col:
        return None
    work = df.copy()
    ref_end = None
    if date_col and date_col in work.columns:
        work["__day"] = pd.to_datetime(work[date_col], errors="coerce")
        ref_end = work["__day"].max()
        if pd.isna(ref_end):
            ref_end = pd.Timestamp.today().normalize()
        ref_start = ref_end - pd.Timedelta(days=30)
        work = work[(work["__day"] >= ref_start) & (work["__day"] <= ref_end)]
    work["channel_raw"] = work[chan_col].astype(str).str.lower()
    work["spend"] = pd.to_numeric(work[spend_col], errors="coerce").fillna(0.0)

    def map_nb_channel(val: str) -> str:
        v = val.lower()
        if any(k in v for k in ["facebook", "meta", "instagram"]):
            return "Facebook Ads"
        if "google" in v:
            return "Google Ads"
        if "tiktok" in v:
            return "TikTok Ads"
        if "pinterest" in v:
            return "Pinterest Ads"
        if any(k in v for k in ["bing", "microsoft"]):
            return "Microsoft Ads"
        if any(k in v for k in ["awin", "affiliate", "shopmyshelf", "shareasale"]):
            return "Affiliate"
        if "applovin" in v:
            return "AppLovin"
        return val.title()

    work["channel"] = work["channel_raw"].apply(map_nb_channel)
    agg = work.groupby("channel")["spend"].sum().reset_index()
    total = agg["spend"].sum()
    if total <= 0:
        return None
    agg["share"] = agg["spend"] / total
    return agg


# -------------------------------
# Markdown output
# -------------------------------

def to_markdown(product_df: pd.DataFrame, channel_df: pd.DataFrame) -> str:
    def _fmt_currency(x: float) -> str:
        try:
            return f"${float(x):,.0f}"
        except Exception:
            return "$0"

    def _fmt_num(x: float) -> str:
        try:
            return f"{float(x):,.0f}"
        except Exception:
            return "0"

    # Safeguard empty inputs
    product_df = product_df.copy() if product_df is not None else pd.DataFrame()
    channel_df = channel_df.copy() if channel_df is not None else pd.DataFrame()

    # Ensure required columns exist on product_df
    for col in [
        "month",
        "product",
        "revenue_2024",
        "units_2024",
        "revenue_2025_target",
        "units_2025_target",
    ]:
        if col not in product_df.columns:
            # Default sensible types
            product_df[col] = "" if col in {"month", "product"} else 0.0

    # Map months to 2025 labels for display
    prod = product_df[[
        "month",
        "product",
        "revenue_2024",
        "units_2024",
        "revenue_2025_target",
        "units_2025_target",
    ]].copy()
    def _to_2025(val: str) -> str:
        s = str(val)
        if len(s) >= 7 and s[4] == "-" and s[5:7] in {"10", "11", "12"}:
            return f"2025-{s[5:7]}"
        return s
    prod["month"] = prod["month"].apply(_to_2025)

    # Load and merge 2023 baseline
    prod_2023 = build_2023_product_baseline()
    if not prod_2023.empty:
        prod_2023 = prod_2023.copy()
        prod_2023["month"] = prod_2023["month"].apply(_to_2025)
        prod = prod.merge(prod_2023, on=["month", "product"], how="left")
    else:
        prod["revenue_2023"] = 0.0
        prod["units_2023"] = 0.0

    # Sort by month then 2025 revenue desc
    prod = prod.sort_values(["month", "revenue_2025_target"], ascending=[True, False])

    # Build product markdown rows
    prod_md = [
        "| Month | Product | 2023 Rev | 2024 Rev | Rev Δ% (24 vs 23) | 2025 Target Rev | Rev Δ% (25 vs 24) | 2023 Units | 2024 Units | Units Δ% (24 vs 23) | 2025 Target Units | Units Δ% (25 vs 24) |",
        "| - | - | -: | -: | -: | -: | -: | -: | -: | -: | -: | -: |",
    ]
    if prod.empty:
        prod_md.append("| — | — | $0 | $0 | 0% | $0 | 0% | 0 | 0 | 0% | 0 | 0% |")
    else:
        # Separate zero-revenue rows
        nz = prod[(pd.to_numeric(prod["revenue_2024"], errors="coerce").fillna(0) > 0) | (pd.to_numeric(prod["revenue_2025_target"], errors="coerce").fillna(0) > 0) | (pd.to_numeric(prod["revenue_2023"], errors="coerce").fillna(0) > 0)]
        z = prod[~prod.index.isin(nz.index)]
        # Emit non-zero rows
        for _, r in nz.iterrows():
            rev23 = float(r.get('revenue_2023', 0) or 0.0)
            rev24 = float(r.get('revenue_2024', 0) or 0.0)
            rev25 = float(r.get('revenue_2025_target', 0) or 0.0)
            u23 = float(r.get('units_2023', 0) or 0.0)
            u24 = float(r.get('units_2024', 0) or 0.0)
            u25 = float(r.get('units_2025_target', 0) or 0.0)
            rev_delta_24_vs_23 = ((rev24 - rev23) / rev23 * 100.0) if rev23 else 0.0
            rev_delta_25_vs_24 = ((rev25 - rev24) / rev24 * 100.0) if rev24 else 0.0
            units_delta_24_vs_23 = ((u24 - u23) / u23 * 100.0) if u23 else 0.0
            units_delta_25_vs_24 = ((u25 - u24) / u24 * 100.0) if u24 else 0.0
            prod_md.append(
                f"| {r['month']} | {r['product']} | {_fmt_currency(rev23)} | {_fmt_currency(rev24)} | {rev_delta_24_vs_23:+.0f}% | {_fmt_currency(rev25)} | {rev_delta_25_vs_24:+.0f}% | {_fmt_num(u23)} | {_fmt_num(u24)} | {units_delta_24_vs_23:+.0f}% | {_fmt_num(u25)} | {units_delta_25_vs_24:+.0f}% |"
            )
        # Emit zero-revenue aggregate per month (units only)
        if not z.empty:
            zagg = z.groupby("month").agg(units23=("units_2023", "sum"), units24=("units_2024", "sum"), units25=("units_2025_target", "sum")).reset_index()
            for _, r in zagg.iterrows():
                u23, u24, u25 = float(r['units23'] or 0), float(r['units24'] or 0), float(r['units25'] or 0)
                units_delta_24_vs_23 = ((u24 - u23) / u23 * 100.0) if u23 else 0.0
                units_delta_25_vs_24 = ((u25 - u24) / u24 * 100.0) if u24 else 0.0
                prod_md.append(
                    f"| {r['month']} | Zero-Revenue (units only) | $0 | $0 | 0% | $0 | 0% | {_fmt_num(u23)} | {_fmt_num(u24)} | {units_delta_24_vs_23:+.0f}% | {_fmt_num(u25)} | {units_delta_25_vs_24:+.0f}% |"
                )
        # Totals across Q4
        tot_row = {
            "revenue_2023": pd.to_numeric(prod["revenue_2023"], errors="coerce").fillna(0).sum(),
            "revenue_2024": pd.to_numeric(prod["revenue_2024"], errors="coerce").fillna(0).sum(),
            "revenue_2025_target": pd.to_numeric(prod["revenue_2025_target"], errors="coerce").fillna(0).sum(),
            "units_2023": pd.to_numeric(prod["units_2023"], errors="coerce").fillna(0).sum(),
            "units_2024": pd.to_numeric(prod["units_2024"], errors="coerce").fillna(0).sum(),
            "units_2025_target": pd.to_numeric(prod["units_2025_target"], errors="coerce").fillna(0).sum(),
        }
        rev_delta_24_vs_23_tot = ((tot_row['revenue_2024'] - tot_row['revenue_2023']) / tot_row['revenue_2023'] * 100.0) if tot_row['revenue_2023'] else 0.0
        rev_delta_25_vs_24_tot = ((tot_row['revenue_2025_target'] - tot_row['revenue_2024']) / tot_row['revenue_2024'] * 100.0) if tot_row['revenue_2024'] else 0.0
        units_delta_24_vs_23_tot = ((tot_row['units_2024'] - tot_row['units_2023']) / tot_row['units_2023'] * 100.0) if tot_row['units_2023'] else 0.0
        units_delta_25_vs_24_tot = ((tot_row['units_2025_target'] - tot_row['units_2024']) / tot_row['units_2024'] * 100.0) if tot_row['units_2024'] else 0.0
        prod_md.append(
            f"| **All Products (Q4)** | — | {_fmt_currency(tot_row['revenue_2023'])} | {_fmt_currency(tot_row['revenue_2024'])} | {rev_delta_24_vs_23_tot:+.0f}% | {_fmt_currency(tot_row['revenue_2025_target'])} | {rev_delta_25_vs_24_tot:+.0f}% | {_fmt_num(tot_row['units_2023'])} | {_fmt_num(tot_row['units_2024'])} | {units_delta_24_vs_23_tot:+.0f}% | {_fmt_num(tot_row['units_2025_target'])} | {units_delta_25_vs_24_tot:+.0f}% |"
        )

    # Channels: ensure required columns and compute targets if missing
    for col in [
        "month",
        "channel",
        "spend_2024",
        "revenue_2024",
        "roas_2024",
    ]:
        if col not in channel_df.columns:
            channel_df[col] = 0.0 if col not in {"month", "channel"} else ""

    if "revenue_2025_target" not in channel_df.columns:
        if set(["revenue_2024"]).issubset(channel_df.columns):
            channel_df["revenue_2025_target"] = pd.to_numeric(channel_df["revenue_2024"], errors="coerce").fillna(0.0) * 1.25
        else:
            channel_df["revenue_2025_target"] = 0.0
    if "spend_2025_target" not in channel_df.columns:
        if set(["revenue_2025_target", "roas_2024"]).issubset(channel_df.columns):
            numer = pd.to_numeric(channel_df["revenue_2025_target"], errors="coerce").fillna(0.0)
            roas = pd.to_numeric(channel_df["roas_2024"], errors="coerce").replace(0, np.nan)
            channel_df["spend_2025_target"] = (numer / roas).fillna(0.0)
        else:
            channel_df["spend_2025_target"] = 0.0

    # Summarise 2023 and 2024 (for display) alongside 2025 targets
    try:
        chan23 = monthly_channel_summary(2023)
    except Exception:
        chan23 = pd.DataFrame(columns=["month", "channel", "spend", "revenue", "roas"])
    try:
        chan24 = monthly_channel_summary(2024)
    except Exception:
        chan24 = pd.DataFrame(columns=["month", "channel", "spend", "revenue", "roas"])

    def _by_channel_tot(df: pd.DataFrame, spend_col: str = "spend", rev_col: str = "revenue") -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=["channel", spend_col, rev_col])
        out = df.groupby("channel").agg({spend_col: "sum", rev_col: "sum"}).reset_index()
        return out

    ch23 = _by_channel_tot(chan23)
    ch24 = _by_channel_tot(chan24)

    ch25 = (
        channel_df.groupby("channel").agg(
            spend_2025_target=("spend_2025_target", "sum"),
            revenue_2025_target=("revenue_2025_target", "sum"),
        ).reset_index()
    )

    ch_merge = pd.merge(ch23.rename(columns={"spend": "spend23", "revenue": "rev23"}),
                        ch24.rename(columns={"spend": "spend24", "revenue": "rev24"}),
                        on="channel", how="outer")
    ch_merge = pd.merge(ch_merge, ch25.rename(columns={"spend_2025_target": "spend25", "revenue_2025_target": "rev25"}), on="channel", how="outer")
    for c in ["spend23", "rev23", "spend24", "rev24", "spend25", "rev25"]:
        if c not in ch_merge.columns:
            ch_merge[c] = 0.0
    ch_merge = ch_merge.fillna(0.0)

    # Precompute 2024 monthly spend weights per channel for month-splitting
    # weights[(channel, '2024-10')] = fraction of that channel's Q4 2024 spend in October
    weights: dict[tuple[str, str], float] = {}
    if not chan24.empty:
        c24_spend = chan24.groupby(["channel", "month"]).agg(spend=("spend", "sum")).reset_index()
        c24_tot = c24_spend.groupby("channel")["spend"].sum().rename("tot").reset_index()
        c24m = c24_spend.merge(c24_tot, on="channel", how="left")
        c24m["w"] = c24m.apply(lambda r: (r["spend"] / r["tot"]) if r["tot"] else 0.0, axis=1)
        for _, r in c24m.iterrows():
            weights[(str(r["channel"]), str(r["month"]))] = float(r["w"])

    # Reweight ALL channels' Q4 2025 target spend using NB last-30-day (fallback YTD) shares
    nb_30 = load_northbeam_last_30_shares()
    nb_ytd = load_northbeam_ytd_2025()
    nb_shares = nb_30 if (nb_30 is not None and not nb_30.empty) else nb_ytd
    reweighted_targets: list[tuple[str, float]] = []
    if nb_shares is not None and not nb_shares.empty:
        total_target_spend = float(ch_merge["spend25"].sum())
        # Build new spend25 per channel
        nb_shares = nb_shares.copy()
        nb_shares["spend25_new"] = nb_shares["share"].astype(float) * total_target_spend
        reweighted_targets = [(str(r["channel"]), float(r["spend25_new"])) for _, r in nb_shares.iterrows()]
        # Merge into ch_merge, overriding spend25 where NB share exists
        ch_merge = ch_merge.merge(nb_shares[["channel", "spend25_new"]], on="channel", how="left")
        ch_merge["spend25"] = ch_merge.apply(lambda r: r["spend25_new"] if pd.notna(r.get("spend25_new")) else r["spend25"], axis=1)
        ch_merge = ch_merge.drop(columns=["spend25_new"]) if "spend25_new" in ch_merge.columns else ch_merge

    # Enforce Q4 constraints: cap Affiliate; ensure Google > Meta
    if not ch_merge.empty:
        total_q4 = float(ch_merge["spend25"].sum())
        # Cap Affiliate at 15% of total
        cap_share = 0.15
        cap_amt = total_q4 * cap_share
        aff_idx = ch_merge["channel"].str.lower() == "affiliate"
        if aff_idx.any():
            cur_aff = float(ch_merge.loc[aff_idx, "spend25"].sum())
            if cur_aff > cap_amt:
                delta = cur_aff - cap_amt
                ch_merge.loc[aff_idx, "spend25"] = cap_amt
                # Reallocate delta to Google and Meta (60% Google, 40% Meta)
                g_idx = ch_merge["channel"].str.lower() == "google ads"
                m_idx = ch_merge["channel"].str.lower() == "facebook ads"
                if g_idx.any():
                    ch_merge.loc[g_idx, "spend25"] = ch_merge.loc[g_idx, "spend25"] + 0.6 * delta
                if m_idx.any():
                    ch_merge.loc[m_idx, "spend25"] = ch_merge.loc[m_idx, "spend25"] + 0.4 * delta
        # Ensure Google > Meta
        g_sp = float(ch_merge.loc[ch_merge["channel"].str.lower()=="google ads", "spend25"].sum())
        m_sp = float(ch_merge.loc[ch_merge["channel"].str.lower()=="facebook ads", "spend25"].sum())
        if g_sp <= m_sp and (g_sp+m_sp)>0:
            move = (m_sp - g_sp) / 2.0 + 1.0  # nudge
            # Reduce from Meta if possible
            if (m_sp - move) > 0:
                ch_merge.loc[ch_merge["channel"].str.lower()=="facebook ads", "spend25"] = m_sp - move
                ch_merge.loc[ch_merge["channel"].str.lower()=="google ads", "spend25"] = g_sp + move

    chan_md = [
        "| Channel | 2023 Q4 Spend | 2023 Q4 Revenue | 2024 Q4 Spend | 2024 Q4 Revenue | 2025 Target Spend | 2025 Target Revenue | Spend Δ% | Rev Δ% |",
        "| - | -: | -: | -: | -: | -: | -: | -: | -: |",
    ]
    if ch_merge.empty:
        chan_md.append("| — | $0 | $0 | $0 | $0 | $0 | $0 | 0% | 0% |")
    else:
        for _, r in ch_merge.sort_values(["spend25", "spend24", "spend23"], ascending=False).iterrows():
            s24 = float(r['spend24']) if pd.notna(r['spend24']) else 0.0
            s25 = float(r['spend25']) if pd.notna(r['spend25']) else 0.0
            v24 = float(r['rev24']) if pd.notna(r['rev24']) else 0.0
            v25 = float(r['rev25']) if pd.notna(r['rev25']) else 0.0
            sdelta = ((s25 - s24) / s24 * 100.0) if s24 else 0.0
            vdelta = ((v25 - v24) / v24 * 100.0) if v24 else 0.0
            chan_md.append(
                f"| {r['channel']} | {_fmt_currency(r['spend23'])} | {_fmt_currency(r['rev23'])} | {_fmt_currency(s24)} | {_fmt_currency(v24)} | {_fmt_currency(s25)} | {_fmt_currency(v25)} | {sdelta:+.0f}% | {vdelta:+.0f}% |"
            )

    # Build markdown doc
    md = []
    md.append("# Q4 2025 Planning")
    md.append("")
    md.append("## Product Forecast (Oct–Dec)")
    md.append("\n".join(prod_md))
    md.append("")
    md.append("## Channel Spend Plan (Q4)")
    md.append("\n".join(chan_md))
    md.append("")
    md.append("_Notes: 2025 targets are +25% over 2024 monthly actuals; new product ramp included if analog provided. No double counting between accrual/cash._")
    return "\n".join(md)


def write_markdown(product_df: pd.DataFrame, channel_df: pd.DataFrame, out_dir: Optional[Path] = None) -> Path:
    out_dir = out_dir or PLANNING_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "q4-2025-planning.md"
    md = to_markdown(product_df, channel_df)
    md_path.write_text(md, encoding="utf-8")
    return md_path


def write_combined_report(product_df: pd.DataFrame, channel_df: pd.DataFrame, reports_dir: Optional[Path] = None, consolidate: str = "threshold", threshold_usd: float = 100_000.0) -> Path:
    from datetime import datetime

    def _to_2025(val: str) -> str:
        s = str(val)
        if len(s) >= 7 and s[4] == "-" and s[5:7] in {"10", "11", "12"}:
            return f"2025-{s[5:7]}"
        return s

    # Write combined report into the planning folder by default
    reports_dir = reports_dir or PLANNING_DIR
    reports_dir.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    fname = f"q4-2025-planning-{today}-combined.md"
    path = reports_dir / fname

    # Totals and highlights
    prod = product_df.copy()
    chan = channel_df.copy()

    def _sum(df: pd.DataFrame, col: str) -> float:
        return float(pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).sum())

    # Monthly totals
    prod_tot_month = (
        prod.groupby("month").agg(
            rev24=("revenue_2024", "sum"),
            units24=("units_2024", "sum"),
            rev25=("revenue_2025_target", "sum"),
            units25=("units_2025_target", "sum"),
        ).reset_index()
    )

    # Q4 totals
    q4_rev24 = _sum(prod_tot_month, "rev24")
    q4_units24 = _sum(prod_tot_month, "units24")
    q4_rev25 = _sum(prod_tot_month, "rev25")
    q4_units25 = _sum(prod_tot_month, "units25")

    # Channel totals 2025 target
    # Ensure 2025 target columns exist on channel_df
    if "revenue_2025_target" not in chan.columns:
        if "revenue_2024" in chan.columns:
            chan["revenue_2025_target"] = pd.to_numeric(chan["revenue_2024"], errors="coerce").fillna(0.0) * 1.25
        else:
            chan["revenue_2025_target"] = 0.0
    if "spend_2025_target" not in chan.columns:
        if "roas_2024" in chan.columns:
            numer = pd.to_numeric(chan["revenue_2025_target"], errors="coerce").fillna(0.0)
            roas = pd.to_numeric(chan["roas_2024"], errors="coerce").replace(0, np.nan)
            chan["spend_2025_target"] = (numer / roas).fillna(0.0)
        else:
            chan["spend_2025_target"] = 0.0

    chan_tot = (
        chan.groupby("channel")
        .agg(spend25=("spend_2025_target", "sum"), rev25=("revenue_2025_target", "sum"))
        .reset_index()
        .sort_values("spend25", ascending=False)
    )

    # Build 2023 and 2024 channel totals for comparison (and monthly views)
    try:
        chan23 = monthly_channel_summary(2023)
    except Exception:
        chan23 = pd.DataFrame(columns=["month", "channel", "spend", "revenue", "roas"])
    try:
        chan24 = monthly_channel_summary(2024)
    except Exception:
        chan24 = pd.DataFrame(columns=["month", "channel", "spend", "revenue", "roas"])

    def _by_channel_tot(df: pd.DataFrame, spend_col: str = "spend", rev_col: str = "revenue") -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame(columns=["channel", spend_col, rev_col])
        out = df.groupby("channel").agg({spend_col: "sum", rev_col: "sum"}).reset_index()
        return out

    ch23 = _by_channel_tot(chan23)
    ch24 = _by_channel_tot(chan24)

    # Merge into a 2023/2024/2025 table
    ch_merge = pd.merge(ch23.rename(columns={"spend": "spend23", "revenue": "rev23"}),
                        ch24.rename(columns={"spend": "spend24", "revenue": "rev24"}),
                        on="channel", how="outer")
    ch_merge = pd.merge(ch_merge, chan_tot.rename(columns={"spend25": "spend25", "rev25": "rev25"}), on="channel", how="outer")
    for c in ["spend23", "rev23", "spend24", "rev24", "spend25", "rev25"]:
        if c not in ch_merge.columns:
            ch_merge[c] = 0.0
    ch_merge = ch_merge.fillna(0.0)

    # Precompute 2024 monthly spend weights per channel for month-splitting
    # weights[(channel, '2024-10')] = fraction of that channel's Q4 2024 spend in October
    weights: dict[tuple[str, str], float] = {}
    if not chan24.empty:
        c24_spend = chan24.groupby(["channel", "month"]).agg(spend=("spend", "sum")).reset_index()
        c24_tot = c24_spend.groupby("channel")["spend"].sum().rename("tot").reset_index()
        c24m = c24_spend.merge(c24_tot, on="channel", how="left")
        c24m["w"] = c24m.apply(lambda r: (r["spend"] / r["tot"]) if r["tot"] else 0.0, axis=1)
        for _, r in c24m.iterrows():
            weights[(str(r["channel"]), str(r["month"]))] = float(r["w"])

    # Reweight ALL channels' Q4 2025 target spend using NB last-30-day (fallback YTD) shares
    nb_30 = load_northbeam_last_30_shares()
    nb_ytd = load_northbeam_ytd_2025()
    nb_shares = nb_30 if (nb_30 is not None and not nb_30.empty) else nb_ytd
    reweighted_targets: list[tuple[str, float]] = []
    if nb_shares is not None and not nb_shares.empty:
        total_target_spend = float(ch_merge["spend25"].sum())
        # Build new spend25 per channel
        nb_shares = nb_shares.copy()
        nb_shares["spend25_new"] = nb_shares["share"].astype(float) * total_target_spend
        reweighted_targets = [(str(r["channel"]), float(r["spend25_new"])) for _, r in nb_shares.iterrows()]
        # Merge into ch_merge, overriding spend25 where NB share exists
        ch_merge = ch_merge.merge(nb_shares[["channel", "spend25_new"]], on="channel", how="left")
        ch_merge["spend25"] = ch_merge.apply(lambda r: r["spend25_new"] if pd.notna(r.get("spend25_new")) else r["spend25"], axis=1)
        ch_merge = ch_merge.drop(columns=["spend25_new"]) if "spend25_new" in ch_merge.columns else ch_merge

    # Enforce Q4 constraints: cap Affiliate; ensure Google > Meta
    if not ch_merge.empty:
        total_q4 = float(ch_merge["spend25"].sum())
        # Cap Affiliate at 15% of total
        cap_share = 0.15
        cap_amt = total_q4 * cap_share
        aff_idx = ch_merge["channel"].str.lower() == "affiliate"
        if aff_idx.any():
            cur_aff = float(ch_merge.loc[aff_idx, "spend25"].sum())
            if cur_aff > cap_amt:
                delta = cur_aff - cap_amt
                ch_merge.loc[aff_idx, "spend25"] = cap_amt
                # Reallocate delta to Google and Meta (60% Google, 40% Meta)
                g_idx = ch_merge["channel"].str.lower() == "google ads"
                m_idx = ch_merge["channel"].str.lower() == "facebook ads"
                if g_idx.any():
                    ch_merge.loc[g_idx, "spend25"] = ch_merge.loc[g_idx, "spend25"] + 0.6 * delta
                if m_idx.any():
                    ch_merge.loc[m_idx, "spend25"] = ch_merge.loc[m_idx, "spend25"] + 0.4 * delta
        # Ensure Google > Meta
        g_sp = float(ch_merge.loc[ch_merge["channel"].str.lower()=="google ads", "spend25"].sum())
        m_sp = float(ch_merge.loc[ch_merge["channel"].str.lower()=="facebook ads", "spend25"].sum())
        if g_sp <= m_sp and (g_sp+m_sp)>0:
            move = (m_sp - g_sp) / 2.0 + 1.0  # nudge
            # Reduce from Meta if possible
            if (m_sp - move) > 0:
                ch_merge.loc[ch_merge["channel"].str.lower()=="facebook ads", "spend25"] = m_sp - move
                ch_merge.loc[ch_merge["channel"].str.lower()=="google ads", "spend25"] = g_sp + move

    chan_md = [
        "| Channel | 2023 Q4 Spend | 2023 Q4 Revenue | 2024 Q4 Spend | 2024 Q4 Revenue | 2025 Target Spend | 2025 Target Revenue | Spend Δ% | Rev Δ% |",
        "| - | -: | -: | -: | -: | -: | -: | -: | -: |",
    ]
    if ch_merge.empty:
        chan_md.append("| — | $0 | $0 | $0 | $0 | $0 | $0 | 0% | 0% |")
    else:
        for _, r in ch_merge.sort_values(["spend25", "spend24", "spend23"], ascending=False).iterrows():
            s24 = float(r['spend24']) if pd.notna(r['spend24']) else 0.0
            s25 = float(r['spend25']) if pd.notna(r['spend25']) else 0.0
            v24 = float(r['rev24']) if pd.notna(r['rev24']) else 0.0
            v25 = float(r['rev25']) if pd.notna(r['rev25']) else 0.0
            sdelta = ((s25 - s24) / s24 * 100.0) if s24 else 0.0
            vdelta = ((v25 - v24) / v24 * 100.0) if v24 else 0.0
            chan_md.append(
                f"| {r['channel']} | {_fmt_currency(r['spend23'])} | {_fmt_currency(r['rev23'])} | {_fmt_currency(s24)} | {_fmt_currency(v24)} | {_fmt_currency(s25)} | {_fmt_currency(v25)} | {sdelta:+.0f}% | {vdelta:+.0f}% |"
            )

    # Build markdown doc
    lines: list[str] = []
    lines += [
        "---",
        "title: \"Q4 2025 Planning Report\"",
        "description: \"Monthly demand and channel spend plan for Oct–Dec 2025 (+25% target over 2024)\"",
        "recipient: \"Ingrid\"",
        "report_type: \"Q4 Planning Report\"",
        f"date: \"{today}\"",
        "period: \"2025-10-01 – 2025-12-31\"",
        f"version: \"{today}\"",
        "---",
        "",
        "# Q4 2025 Planning — October 2025 ‑ December 2025",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        f"• 2024 Q4 Actuals: { _fmt_currency(q4_rev24) } revenue, { _fmt_num(q4_units24) } units",
        f"• 2025 Q4 Targets (+25%): { _fmt_currency(q4_rev25) } revenue, { _fmt_num(q4_units25) } units",
    ]

    for _, r in prod_tot_month.sort_values("month").iterrows():
        lines.append(
            f"• {r['month'].replace('2024-','2025-')}: 2024 { _fmt_currency(r['rev24']) } → 2025 target { _fmt_currency(r['rev25']) } | Units: 2024 { _fmt_num(r['units24']) } → 2025 { _fmt_num(r['units25']) }"
        )

    if _sum(prod, "revenue_2025_target") > 0 or _sum(prod, "units_2025_target") > 0:
        lines.append(f"• New Product (Filtered Showerhead) included: { _fmt_num(_sum(prod, "units_2025_target")) } units, { _fmt_currency(_sum(prod, "revenue_2025_target")) } revenue across Q4")

    # Q4 channel totals
    lines += [
        "",
        "---",
        "",
        "## 2. Channel Spend Plan (Q4 Totals)",
        "",
        "| Channel | 2023 Q4 Spend | 2023 Q4 Revenue | 2024 Q4 Spend | 2024 Q4 Revenue | 2025 Target Spend | 2025 Target Revenue |",
        "| - | -: | -: | -: | -: | -: | -: |",
    ]
    for _, r in ch_merge.sort_values(["spend25", "spend24", "spend23"], ascending=False).iterrows():
        lines.append(
            f"| {r['channel']} | {_fmt_currency(r['spend23'])} | {_fmt_currency(r['rev23'])} | {_fmt_currency(r['spend24'])} | {_fmt_currency(r['rev24'])} | {_fmt_currency(r['spend25'])} | {_fmt_currency(r['rev25'])} |"
        )

    # Per-month channel breakdown
    lines += [
        "",
        "---",
        "",
        "## 3. Channel Spend Plan by Month",
        "",
        "### October 2025",
        *_chan_month_table("2025-10"),
        "",
        "### November 2025",
        *_chan_month_table("2025-11"),
        "",
        "### December 2025",
        *_chan_month_table("2025-12"),
    ]

    # Consolidated product tables by month
    def _prod_month_table(mon: str) -> list[str]:
        df = prod_by_month.get(mon, pd.DataFrame())
        tbl = [
            "| Product Group | 2023 Rev | 2024 Rev | Rev Δ% (24 vs 23) | 2025 Target Rev | Rev Δ% (25 vs 24) | 2023 Units | 2024 Units | Units Δ% (24 vs 23) | 2025 Target Units | Units Δ% (25 vs 24) |",
            "| - | -: | -: | -: | -: | -: | -: | -: | -: | -: | -: |",
        ]
        if df is None or df.empty:
            tbl.append("| — | $0 | $0 | 0% | $0 | 0% | 0 | 0 | 0% | 0 | 0% |")
            return tbl
        # Totals at top
        tot = {
            "revenue_2023": pd.to_numeric(df.get("revenue_2023", 0), errors="coerce").fillna(0).sum(),
            "revenue_2024": pd.to_numeric(df.get("revenue_2024", 0), errors="coerce").fillna(0).sum(),
            "revenue_2025_target": pd.to_numeric(df.get("revenue_2025_target", 0), errors="coerce").fillna(0).sum(),
            "units_2023": pd.to_numeric(df.get("units_2023", 0), errors="coerce").fillna(0).sum(),
            "units_2024": pd.to_numeric(df.get("units_2024", 0), errors="coerce").fillna(0).sum(),
            "units_2025_target": pd.to_numeric(df.get("units_2025_target", 0), errors="coerce").fillna(0).sum(),
        }
        sdelta_24_vs_23 = ((tot['revenue_2024'] - tot['revenue_2023']) / tot['revenue_2023'] * 100.0) if tot['revenue_2023'] else 0.0
        sdelta_25_vs_24 = ((tot['revenue_2025_target'] - tot['revenue_2024']) / tot['revenue_2024'] * 100.0) if tot['revenue_2024'] else 0.0
        udelta_24_vs_23 = ((tot['units_2024'] - tot['units_2023']) / tot['units_2023'] * 100.0) if tot['units_2023'] else 0.0
        udelta_25_vs_24 = ((tot['units_2025_target'] - tot['units_2024']) / tot['units_2024'] * 100.0) if tot['units_2024'] else 0.0
        tbl.append(
            f"| **All Products** | {_fmt_currency(tot['revenue_2023'])} | {_fmt_currency(tot['revenue_2024'])} | {sdelta_24_vs_23:+.0f}% | {_fmt_currency(tot['revenue_2025_target'])} | {sdelta_25_vs_24:+.0f}% | {_fmt_num(tot['units_2023'])} | {_fmt_num(tot['units_2024'])} | {udelta_24_vs_23:+.0f}% | {_fmt_num(tot['units_2025_target'])} | {udelta_25_vs_24:+.0f}% |"
        )
        # Rows
        for _, r in df.iterrows():
            grp = r.get("group", "Other")
            rev23 = float(r.get('revenue_2023', 0) or 0.0)
            rev24 = float(r.get('revenue_2024', 0) or 0.0)
            rev25 = float(r.get('revenue_2025_target', 0) or 0.0)
            u23 = float(r.get('units_2023', 0) or 0.0)
            u24 = float(r.get('units_2024', 0) or 0.0)
            u25 = float(r.get('units_2025_target', 0) or 0.0)
            sdelta_24_vs_23 = ((rev24 - rev23) / rev23 * 100.0) if rev23 else 0.0
            sdelta_25_vs_24 = ((rev25 - rev24) / rev24 * 100.0) if rev24 else 0.0
            udelta_24_vs_23 = ((u24 - u23) / u23 * 100.0) if u23 else 0.0
            udelta_25_vs_24 = ((u25 - u24) / u24 * 100.0) if u24 else 0.0
            tbl.append(
                f"| {grp} | {_fmt_currency(rev23)} | {_fmt_currency(rev24)} | {sdelta_24_vs_23:+.0f}% | {_fmt_currency(rev25)} | {sdelta_25_vs_24:+.0f}% | {_fmt_num(u23)} | {_fmt_num(u24)} | {udelta_24_vs_23:+.0f}% | {_fmt_num(u25)} | {udelta_25_vs_24:+.0f}% |"
            )
        return tbl

    lines += [
        "",
        "---",
        "",
        "## 4. Product Forecast by Month (Consolidated)",
        f"Consolidation mode: {consolidate}; Threshold: ${threshold_usd:,.0f}",
        "",
        "### October 2025",
        *_prod_month_table("2025-10"),
        "",
        "### November 2025",
        *_prod_month_table("2025-11"),
        "",
        "### December 2025",
        *_prod_month_table("2025-12"),
    ]

    # Assumptions & Next steps
    lines += [
        "",
        "---",
        "",
        "## 5. Assumptions & Notes",
        "- +25% uplift over 2024 monthly actuals used to derive 2025 targets",
        "- Spend derived using 2024 channel ROAS (constant-ROAS assumption)",
        "- Shopify is used as cash anchor; Northbeam used only for context (no accrual/cash mixing)",
        "- Showerhead ramp based on Body Sculptor analog if provided",
        "",
        "## 6. Next Steps",
        "1. Confirm hero SKU focus and any promo depth (BFCM) that may re-shape mix",
        "2. Provide lead-times/MOQs to translate monthly units into PO dates/qty",
        "3. Lock channel caps/targets by month; adjust for any platform changes",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def write_outputs(product_df: pd.DataFrame, channel_df: pd.DataFrame, out_dir: Optional[Path] = None) -> Tuple[Path, Path]:
    out_dir = out_dir or PLANNING_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    prod_path = out_dir / "q4-2025-product-forecast.csv"
    chan_path = out_dir / "q4-2025-channel-spend-plan.csv"
    product_df.to_csv(prod_path, index=False)
    channel_df.to_csv(chan_path, index=False)
    # Also write markdowns
    write_markdown(product_df, channel_df, out_dir=out_dir)
    write_combined_report(product_df, channel_df, reports_dir=out_dir, consolidate="threshold", threshold_usd=100_000.0)
    return prod_path, chan_path


def run(overlay_showerhead: bool = True, showerhead_price: Optional[float] = None, launch_month: str = "2025-11") -> Tuple[Path, Path]:
    prod_base_2024 = build_2024_product_baseline()
    chan_base_2024 = build_2024_channel_baseline()

    prod_target = apply_25pct_target_product(prod_base_2024)
    chan_target = apply_25pct_target_channel(chan_base_2024)

    if overlay_showerhead:
        analog = load_launch_analog("body-sculptor-launch.csv")
        prod_target = overlay_new_product_ramp(
            prod_target, analog, product_name="Filtered Showerhead", launch_month=launch_month, price=showerhead_price
        )

    return write_outputs(prod_target, chan_target, out_dir=PLANNING_DIR)


def main():
    run()


if __name__ == "__main__":
    main() 