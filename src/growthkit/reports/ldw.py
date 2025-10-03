#!/usr/bin/env python3
"""Labor Day Weekend YoY Report (2025 vs 2024).

Refactored from `scripts/report_ldw.py` into the library so the script can be a
thin wrapper. Provides `main()` for CLI entrypoints.
"""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
import glob
import pandas as pd

from growthkit.reports.executive import MTDReportGenerator


def _run_exec_for_range(start: str, end: str):
    gen = MTDReportGenerator(
        start_date=start,
        end_date=end,
        output_dir="data/reports/weekly",
        choose_files=False,
        interactive=False,
    )
    # Internals mirror run(), but we want to capture metrics rather than save the standard report directly
    gen._set_date_ranges()
    selected = gen._find_and_select_files()
    ga4_cur, shop_cur = gen.load_data_for_period(selected.get("current", {}), gen.mtd_date_range_current)
    ga4_prev, shop_prev = gen.load_data_for_period(selected.get("previous", {}), gen.mtd_date_range_previous)
    gen.ga4_data_current, gen.shopify_data_current = ga4_cur, shop_cur
    gen.ga4_data_previous, gen.shopify_data_previous = ga4_prev, shop_prev
    metrics_current = {
        "ga4": gen.calculate_ga4_metrics(ga4_cur),
        "shopify": gen.calculate_shopify_metrics(shop_cur, gen.mtd_date_range_current),
    }
    return gen, metrics_current


def _find_latest_l30_file() -> str | None:
    # Broaden match: include l30d, ytd, new_ytd; search recursively
    cands: list[str] = []
    for patt in [
        "data/ads/**/ytd_sales_data-higher_dose_llc-*.csv",  # prefer canonical YTD
        "data/ads/**/new_ytd_sales_data-higher_dose_llc-*.csv",  # legacy
        "data/ads/**/ytd-sales_data-higher_dose_llc-*.csv",  # alternate hyphenation
        "data/ads/**/l30d-sales_data-higher_dose_llc-*.csv",
        "data/ads/**/*sales_data-higher_dose_llc-*.csv",
    ]:
        cands.extend(glob.glob(patt, recursive=True))
    if not cands:
        return None
    cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return cands[0]


def _load_nb_df(gen: MTDReportGenerator) -> pd.DataFrame | None:
    # Prefer the NB DataFrame already loaded by the generator
    try:
        if isinstance(gen.ga4_data_current, dict) and "northbeam" in gen.ga4_data_current:
            nb_df = gen.ga4_data_current["northbeam"]
            if isinstance(nb_df, pd.DataFrame) and not nb_df.empty:
                return nb_df.copy()
    except Exception:
        pass
    # Fallback: read latest NB CSV on disk
    path = _find_latest_l30_file()
    if not path:
        return None
    try:
        return pd.read_csv(path, thousands=",")
    except Exception:
        return None


def _current_channel_table_from_l30(gen_cur: MTDReportGenerator) -> pd.DataFrame:
    """Build 2025 channel table from latest L30 Northbeam export (spend + NB revenue)."""
    df = _load_nb_df(gen_cur)
    if df is None or df.empty:
        return pd.DataFrame(columns=["Revenue", "Spend", "ROAS"]).set_index(pd.Index([], name="Channel"))
    # Normalize date
    date_col = None
    for c in ["date", "Date", "day", "Day"]:
        if c in df.columns:
            date_col = c
            break
    # Remove duplicate columns which can cause df[col] to be a DataFrame
    df = df.loc[:, ~df.columns.duplicated()]
    if date_col is None:
        return pd.DataFrame(columns=["Revenue", "Spend", "ROAS"]).set_index(pd.Index([], name="Channel"))
    df = df.rename(columns={date_col: "date"})
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    start_dt = gen_cur.mtd_date_range_current["start_dt"]
    end_dt = gen_cur.mtd_date_range_current["end_dt"]
    df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)].copy()
    # Map columns with strict preference
    orig_cols = list(df.columns)
    lowered = {str(c).lower().strip(): c for c in orig_cols}
    # Spend
    if "spend" in lowered:
        df = df.rename(columns={lowered["spend"]: "spend"})
    # Revenue
    if "attributed_rev" in lowered:
        df = df.rename(columns={lowered["attributed_rev"]: "attributed_rev"})
    elif "web_revenue" in lowered:
        df = df.rename(columns={lowered["web_revenue"]: "attributed_rev"})
    elif "rev" in lowered:
        df = df.rename(columns={lowered["rev"]: "attributed_rev"})
    # Transactions
    if "transactions" in lowered:
        df = df.rename(columns={lowered["transactions"]: "transactions"})
    elif "web_transactions" in lowered:
        df = df.rename(columns={lowered["web_transactions"]: "transactions"})
    # Platform
    plat_key = None
    for k in ["breakdown_platform_northbeam", "platform"]:
        if k in lowered:
            plat_key = lowered[k]
            break
    if plat_key is not None:
        df = df.rename(columns={plat_key: "breakdown_platform_northbeam"})
    # Deduplicate again after renaming
    df = df.loc[:, ~df.columns.duplicated()]
    # Filter accrual and positive spend when present
    if "accounting_mode" in df.columns:
        df = df[df["accounting_mode"].str.contains("Accrual", case=False, na=False)]
    # Coerce numeric
    for c in ["spend", "attributed_rev", "transactions"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)
    # Keep rows with signal
    if {"spend", "attributed_rev", "transactions"}.issubset(df.columns):
        mask_keep = (df["spend"] > 0) | (df["attributed_rev"] > 0) | (df["transactions"] > 0)
        df = df[mask_keep]
    # Channel mapping
    def _plat_to_channel(name: str) -> str | None:
        val = str(name).lower()
        if "google" in val:
            return "Paid Search"
        if "bing" in val or "microsoft" in val:
            return "Bing Ads"
        if "meta" in val or "facebook" in val or "instagram" in val:
            return "Paid Social"
        if "tiktok" in val:
            return "TikTok Ads"
        if "pinterest" in val:
            return "Pinterest Ads"
        if "applovin" in val:
            return "AppLovin"
        if "awin" in val:
            return "Awin (Paid Affiliate)"
        if "shopmy" in val:
            return "ShopMyShelf (Influencer)"
        return None
    if "breakdown_platform_northbeam" not in df.columns:
        return pd.DataFrame(columns=["Revenue", "Spend", "ROAS"]).set_index(pd.Index([], name="Channel"))
    df["__custom_channel__"] = df["breakdown_platform_northbeam"].apply(_plat_to_channel)
    grp = df.dropna(subset=["__custom_channel__"]).groupby("__custom_channel__")
    agg_cols = [c for c in ["spend", "attributed_rev", "transactions"] if c in df.columns]
    if not agg_cols:
        return pd.DataFrame(columns=["Revenue", "Spend", "ROAS"]).set_index(pd.Index([], name="Channel"))
    agg = grp[agg_cols].sum().fillna(0)
    agg["ROAS"] = agg.apply(lambda r: (r.get("attributed_rev", 0) / r.get("spend", 0)) if r.get("spend", 0) else 0, axis=1)
    # CAC per channel when transactions present (Spend/Transactions)
    if "transactions" in agg.columns:
        agg["CAC"] = agg.apply(lambda r: (r.get("spend", 0) / r.get("transactions", 0)) if r.get("transactions", 0) else 0, axis=1)
    else:
        agg["CAC"] = 0
    # 1D ROAS: derive from attributed_rev filtered by attribution_model/window
    if {"attribution_model", "attribution_window"}.issubset(df.columns):
        mask_click = df["attribution_model"].astype(str).str.lower().str.contains("click", na=False) | df["attribution_window"].astype(str).str.lower().str.contains("click", na=False)
        mask_1d = df["attribution_window"].astype(str).str.lower().str.contains("1d", na=False) | df["attribution_window"].astype(str).str.lower().str.contains("1 day", na=False)
        df_1d = df[mask_click & mask_1d].copy()
    else:
        df_1d = df.iloc[0:0].copy()
    rev1d_by_ch = None
    if not df_1d.empty and "attributed_rev" in df_1d.columns:
        rev1d_by_ch = (
            df_1d.dropna(subset=["__custom_channel__"]).groupby("__custom_channel__")["attributed_rev"].sum()
        )
    agg["ROAS_1D"] = 0
    if rev1d_by_ch is not None:
        for ch, rev1d in rev1d_by_ch.items():
            sp = float(agg.loc[ch, "spend"]) if "spend" in agg.columns and ch in agg.index else float(agg.loc[ch, "Spend"]) if "Spend" in agg.columns and ch in agg.index else 0.0
            if sp > 0:
                agg.loc[ch, "ROAS_1D"] = rev1d / sp
    if "spend" in agg.columns:
        agg = agg.rename(columns={"spend": "Spend"})
    if "attributed_rev" in agg.columns:
        agg = agg.rename(columns={"attributed_rev": "Revenue"})
    if "transactions" in agg.columns:
        agg = agg.rename(columns={"transactions": "Transactions"})
    desired = [
        "Paid Search",
        "Paid Social",
        "AppLovin",
        "Bing Ads",
        "Pinterest Ads",
        "TikTok Ads",
        "Awin (Paid Affiliate)",
        "ShopMyShelf (Influencer)",
    ]
    agg = agg.reindex(desired, fill_value=0).combine_first(agg)
    agg.index.name = "Channel"
    for col in ["Revenue", "Spend", "ROAS", "CAC", "ROAS_1D", "Transactions"]:
        if col not in agg.columns:
            agg[col] = 0
    return agg[["Revenue", "Spend", "ROAS", "CAC", "ROAS_1D", "Transactions"]]


def main():
    # Conservative assumption: 2025 VIP 8/27 through 9/02; LY match 8/26 through 9/02
    cur_start = os.environ.get("LDW_2025_START", "2025-08-27")
    cur_end = os.environ.get("LDW_2025_END", "2025-09-03")
    ly_start = os.environ.get("LDW_2024_START", "2024-08-23")
    ly_end = os.environ.get("LDW_2024_END", "2024-09-04")

    # Run current period
    gen_cur, metrics_cur = _run_exec_for_range(cur_start, cur_end)
    # Override the date range explicitly for title context
    gen_cur.mtd_date_range_current["start"] = cur_start
    gen_cur.mtd_date_range_current["end"] = cur_end
    gen_cur.mtd_date_range_current["start_dt"] = pd.to_datetime(cur_start)
    gen_cur.mtd_date_range_current["end_dt"] = pd.to_datetime(cur_end)

    # Run previous period (LY)
    gen_prev, metrics_prev = _run_exec_for_range(ly_start, ly_end)
    gen_prev.mtd_date_range_current["start"] = ly_start
    gen_prev.mtd_date_range_current["end"] = ly_end
    gen_prev.mtd_date_range_current["start_dt"] = pd.to_datetime(ly_start)
    gen_prev.mtd_date_range_current["end_dt"] = pd.to_datetime(ly_end)

    # Build channel tables and deltas
    t_cur = _current_channel_table_from_l30(gen_cur)
    # For previous year, construct using GA4 revenue and platform spend (Meta + Google)
    from .report_ldw_prev_helpers import _prev_channel_table_with_platform as _prev_tbl  # type: ignore  # optional helper if exists
    try:
        t_prev = _prev_tbl(gen_prev)
    except Exception:
        # Inline fallback: minimal previous table from GA4 and platform CSVs
        t_prev = pd.DataFrame(columns=["Revenue", "Spend", "ROAS"]).set_index(pd.Index([], name="Channel"))

    all_channels = sorted(set(t_cur.index.tolist()) | set(t_prev.index.tolist()))

    rows = []
    for ch in all_channels:
        spend_cur = float(t_cur.loc[ch, "Spend"]) if ch in t_cur.index else 0.0
        rev_cur = float(t_cur.loc[ch, "Revenue"]) if ch in t_cur.index else 0.0
        roas_cur = float(t_cur.loc[ch, "ROAS"]) if ch in t_cur.index else (rev_cur / spend_cur if spend_cur else 0.0)
        cac_cur = float(t_cur.loc[ch, "CAC"]) if ("CAC" in t_cur.columns and ch in t_cur.index) else None
        roas1d_cur = float(t_cur.loc[ch, "ROAS_1D"]) if ("ROAS_1D" in t_cur.columns and ch in t_cur.index) else None
        spend_prev = float(t_prev.loc[ch, "Spend"]) if ch in t_prev.index else 0.0
        rev_prev = float(t_prev.loc[ch, "Revenue"]) if ch in t_prev.index else 0.0
        roas_prev = float(t_prev.loc[ch, "ROAS"]) if ch in t_prev.index else (rev_prev / spend_prev if spend_prev else 0.0)
        cac_prev = float(t_prev.loc[ch, "CAC"]) if ("CAC" in t_prev.columns and ch in t_prev.index) else None
        rows.append(
            {
                "Channel": ch,
                "Spend (2025)": spend_cur,
                "Spend (2024)": spend_prev,
                "Spend Δ%": ((spend_cur - spend_prev) / spend_prev * 100) if spend_prev else None,
                "Revenue (2025)": rev_cur,
                "Revenue (2024)": rev_prev,
                "Revenue Δ%": ((rev_cur - rev_prev) / rev_prev * 100) if rev_prev else None,
                "ROAS (2025)": roas_cur,
                "ROAS (2024)": roas_prev,
                "1D ROAS (2025)": roas1d_cur,
                "CAC (2025)": cac_cur,
                "CAC (2024)": cac_prev,
                "ROAS Δ": (roas_cur - roas_prev),
            }
        )
    delta_df = pd.DataFrame(rows)
    out_dir = Path("data/reports/weekly")
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"ldw-yoy-report-{datetime.now().strftime('%Y-%m-%d')}.md"
    out_path = out_dir / fname

    if delta_df.empty:
        out_path.write_text(
            "# Labor Day Weekend YoY Report (2025 vs 2024)\n\n"
            "Data unavailable to compute channel-level deltas. Please ensure GA4 source/medium and Northbeam files are present for both periods.\n"
        )
        print(f"⚠️ Wrote placeholder report due to missing channel data: {out_path}")
        return

    delta_df = delta_df.set_index("Channel").sort_values("Revenue (2025)", ascending=False)

    def _fmt_money(v: float | None) -> str:
        if v is None:
            return "N/A"
        return f"${v:,.0f}"

    def _fmt_pct(v: float | None) -> str:
        if v is None:
            return "N/A"
        return f"{v:+.1f}%"

    def _fmt_roas(v: float | None) -> str:
        if v is None:
            return "N/A"
        return f"{v:.2f}"

    def _fmt_money2(v: float | None) -> str:
        return _fmt_money(v if v is not None else None)

    # Compose markdown report
    head = (
        f"# Labor Day Weekend YoY Report (2025 vs 2024)\n\n"
        f"**2025 Period:** {cur_start} → {cur_end}  \n"
        f"**2024 Period:** {ly_start} → {ly_end}  \n\n---\n\n"
    )
    md_note = (
        "> Note: 'Paid Social' aggregates Meta (Facebook/Instagram). TikTok, Pinterest, etc. are shown separately when present. 1D ROAS is computed from 1‑day revenue in the 2025 L30 export when available.\n\n"
    )
    md = head + md_note

    # Totals for summary
    tot_spend_2025 = float(t_cur["Spend"].sum()) if not t_cur.empty else 0.0
    tot_spend_2024 = float(t_prev["Spend"].sum()) if not t_prev.empty else 0.0

    def _shopify_rev_in_range(shopify_dict: dict, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> float:
        ts = shopify_dict.get("total_sales")
        if isinstance(ts, pd.DataFrame) and "Day" in ts.columns and "Total sales" in ts.columns:
            _df = ts.copy()
            _df["Day"] = pd.to_datetime(_df["Day"], errors="coerce")
            m = (_df["Day"] >= start_dt) & (_df["Day"] <= end_dt)
            _sub = _df[m]
            if not _sub.empty:
                return float(pd.to_numeric(_sub["Total sales"], errors="coerce").fillna(0).sum())
        nr = shopify_dict.get("new_returning")
        if isinstance(nr, pd.DataFrame) and "Day" in nr.columns and "Total sales" in nr.columns:
            _df = nr.copy()
            _df["Day"] = pd.to_datetime(_df["Day"], errors="coerce")
            m = (_df["Day"] >= start_dt) & (_df["Day"] <= end_dt)
            _sub = _df[m]
            if not _sub.empty:
                return float(pd.to_numeric(_sub["Total sales"], errors="coerce").fillna(0).sum())
        return 0.0

    cur_start_dt = gen_cur.mtd_date_range_current["start_dt"]
    cur_end_dt = gen_cur.mtd_date_range_current["end_dt"]
    total_rev_2025 = _shopify_rev_in_range(gen_cur.shopify_data_current, cur_start_dt, cur_end_dt)
    start_prev = gen_prev.mtd_date_range_current["start_dt"]
    end_prev = gen_prev.mtd_date_range_current["end_dt"]
    total_rev_2024 = _shopify_rev_in_range(gen_prev.shopify_data_current, start_prev, end_prev)
    roas_2025 = (total_rev_2025 / tot_spend_2025) if tot_spend_2025 else 0.0
    roas_2024 = (total_rev_2024 / tot_spend_2024) if tot_spend_2024 else 0.0

    total_rev1d_2025 = 0.0
    if "ROAS_1D" in t_cur.columns:
        for _, row in t_cur.iterrows():
            sp = float(row.get("Spend", 0) or 0)
            roas1d = float(row.get("ROAS_1D", 0) or 0)
            total_rev1d_2025 += sp * roas1d
    roas1d_2025 = (total_rev1d_2025 / tot_spend_2025) if tot_spend_2025 else 0.0

    # Build YoY summary
    def _fmt_delta(pct: float | None) -> str:
        return _fmt_pct(pct) if pct is not None else "N/A"

    spend_yoy = ((tot_spend_2025 - tot_spend_2024) / tot_spend_2024 * 100) if tot_spend_2024 else None
    rev_yoy = ((total_rev_2025 - total_rev_2024) / total_rev_2024 * 100) if total_rev_2024 else None
    roas_yoy = ((roas_2025 - roas_2024) / roas_2024 * 100) if roas_2024 else None

    md += "## YoY Summary (2025 vs 2024)\n\n"
    md += f"- **Spend:** {_fmt_money(tot_spend_2025)} ( {_fmt_money(tot_spend_2024)} | {_fmt_delta(spend_yoy)} )\n"
    md += f"- **Revenue:** {_fmt_money(total_rev_2025)} ( {_fmt_money(total_rev_2024)} | {_fmt_delta(rev_yoy)} )\n"
    md += f"- **ROAS:** {_fmt_roas(roas_2025)} ( {_fmt_roas(roas_2024)} | {_fmt_delta(roas_yoy)} )\n"
    md += f"- **Blended CAC:** N/A ( Shopify orders not computed )\n\n"

    md += "## Channel Performance (YoY Deltas)\n\n"
    md += "| Channel | Spend 2025 | Spend 2024 | Δ Spend | Revenue 2025 | Revenue 2024 | Δ Revenue | ROAS 2025 | ROAS 2024 | CAC 2025 | CAC 2024 |\n"
    md += "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for ch, r in delta_df.iterrows():
        md += (
            f"| {ch} | {_fmt_money(r['Spend (2025)'])} | {_fmt_money(r['Spend (2024)'])} | {_fmt_pct(r['Spend Δ%'])} | "
            f"{_fmt_money(r['Revenue (2025)'])} | {_fmt_money(r['Revenue (2024)'])} | {_fmt_pct(r['Revenue Δ%'])} | "
            f"{_fmt_roas(r['ROAS (2025)'])} | {_fmt_roas(r['ROAS (2024)'])} | "
            f"{_fmt_money2(r['CAC (2025)'])} | {_fmt_money2(r['CAC (2024)'])} |\n"
        )

    # Totals line
    total_rev_2025_channels = float(t_cur["Revenue"].sum()) if not t_cur.empty else 0.0
    total_rev_2024_channels = float(t_prev["Revenue"].sum()) if not t_prev.empty else 0.0
    total_spend_delta = ((tot_spend_2025 - tot_spend_2024) / tot_spend_2024 * 100) if tot_spend_2024 else None
    total_rev_delta = ((total_rev_2025_channels - total_rev_2024_channels) / total_rev_2024_channels * 100) if total_rev_2024_channels else None
    total_roas_2025 = (total_rev_2025_channels / tot_spend_2025) if tot_spend_2025 else 0.0
    total_roas_2024 = (total_rev_2024_channels / tot_spend_2024) if tot_spend_2024 else 0.0
    total_cac_2025 = None
    if "Transactions" in t_cur.columns and t_cur["Transactions"].sum() > 0:
        total_cac_2025 = tot_spend_2025 / t_cur["Transactions"].sum()
    total_cac_2024 = None
    md += (
        f"| Total | {_fmt_money(tot_spend_2025)} | {_fmt_money(tot_spend_2024)} | {_fmt_pct(total_spend_delta)} | "
        f"{_fmt_money(total_rev_2025_channels)} | {_fmt_money(total_rev_2024_channels)} | {_fmt_pct(total_rev_delta)} | "
        f"{_fmt_roas(total_roas_2025)} | {_fmt_roas(total_roas_2024)} | "
        f"{_fmt_money2(total_cac_2025)} | {_fmt_money2(total_cac_2024)} |\n"
    )

    # Write report
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"✅ LDW YoY report saved to: {out_path}")


if __name__ == "__main__":
    main()


