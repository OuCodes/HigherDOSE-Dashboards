#!/usr/bin/env python3
"""
HigherDOSE Weekly Product & Category Growth Report

This script extends the channel-level weekly report by mapping each campaign/ad
row to a specific product (and its category) based on the naming found in the
Ad Name → Ad Set Name → Campaign Name cascade.  It then outputs additional
markdown tables summarising performance by product and by product category.

The original channel-level analytics remain intact via re-use of
`report_analysis_weekly` helper functions.
"""
import re, ast
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from . import weekly as base
import glob, os
import argparse
from pathlib import Path


# -------------------------------------------------------------
# 📅  Previous Week Utilities
# -------------------------------------------------------------

# Helper to pick newest file matching a pattern (used as fallback)
def _latest(pattern: str) -> str | None:
    matches = glob.glob(pattern)
    return max(matches, key=os.path.getmtime) if matches else None


def _find_previous_csv(stats_dir: str = "data/raw/stats") -> str | None:
    """Return path to the previous-week CSV.

    Priority:
    1. Any file whose basename starts with ``prev-`` (Northbeam export you drop in).
    2. Otherwise, the *second* most-recent CSV in the directory.
    """
    csvs = sorted(glob.glob(os.path.join(stats_dir, "*.csv")), key=os.path.getmtime, reverse=True)
    for p in csvs:
        if os.path.basename(p).startswith("prev-"):
            return p
    if len(csvs) >= 2:
        return csvs[1]
    return None


def _load_csv_clean(path: str) -> pd.DataFrame | None:
    """Lightweight clone of base.load_and_clean_data() but non-interactive."""
    if not path or not os.path.exists(path):
        print("⚠️  Previous-week CSV not found – skipping deltas")
        return None
    df = pd.read_csv(path)

    # Minimal numeric cast
    numeric_cols = [
        "spend",
        "attributed_rev",
        "attributed_rev_1st_time",
        "transactions",
        "transactions_1st_time",
        "visits",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.fillna(0)
    # Ensure required platform col present
    if "breakdown_platform_northbeam" not in df.columns:
        df["breakdown_platform_northbeam"] = df.get("platform", "Unknown")
    return df


# -------------------------------------------------------------
# Δ  Delta Formatting Helpers
# -------------------------------------------------------------


def _pct_delta(cur: float, prev: float) -> float:
    if prev == 0:
        return 0.0
    return (cur - prev) / prev * 100.0


def _fmt_delta(cur: float, prev: float, prefix: str = "$", digits: int = 0) -> str:
    """Return a formatted cell showing cur, prev and %Δ."""
    pct = _pct_delta(cur, prev)
    sign = "+" if pct > 0 else ("-" if pct < 0 else "")
    pct_str = f"{sign}{abs(pct):.0f}%"
    if prefix:
        cur_str = f"{prefix}{cur:,.{digits}f}"
        prev_str = f"{prefix}{prev:,.{digits}f}"
    else:
        cur_str = f"{cur:,.{digits}f}"
        prev_str = f"{prev:,.{digits}f}"
    return f"{cur_str} ( {prev_str} | {pct_str} )"


# -------------------------------------------------------------
# 🔎  Product & Category Mapping Helpers
# -------------------------------------------------------------

def load_product_mappings():
    """Return mapping structures from higherdose.product_data."""
    product_to_category = pd.PRODUCT_TO_CATEGORY
    alias_sorted = pd.ALIAS_SORTED

    def _norm(s: str):
        return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()

    return product_to_category, alias_sorted, _norm


def detect_product(row, alias_sorted, norm_fn):
    """Return canonical product found in Ad Name, Ad Set, then Campaign."""
    search_fields = ("ad_name", "adset_name", "campaign_name")
    for field in search_fields:
        original = str(row.get(field, ""))
        text_norm = norm_fn(original)
        text_nospace = text_norm.replace(" ", "")
        for alias, canonical in alias_sorted:
            if alias in text_norm or alias in text_nospace:
                return canonical
    return None


def assign_products(df: pd.DataFrame, alias_sorted, norm_fn):
    df = df.copy()
    df["product"] = df.apply(lambda r: detect_product(r, alias_sorted, norm_fn), axis=1)
    return df


def build_summary(df: pd.DataFrame, group_col: str):
    numeric_cols = [
        "spend",
        "attributed_rev",
        "attributed_rev_1st_time",
        "transactions",
        "transactions_1st_time",
    ]
    present = [c for c in numeric_cols if c in df.columns]
    summary = df.groupby(group_col)[present].sum().astype(float)

    # Metric calculations
    summary["roas"] = (summary["attributed_rev"] / summary["spend"]).replace([np.inf], 0)
    summary["roas_1st_time"] = (
        summary["attributed_rev_1st_time"] / summary["spend"]
    ).replace([np.inf], 0)
    # Use *rounded* transactions for CAC / AOV to avoid confusing fractional counts
    txns_rounded = summary["transactions"].round().replace(0, np.nan)
    summary["cac"] = (summary["spend"] / txns_rounded).replace([np.inf], 0).fillna(0)
    summary["cac_1st_time"] = (
        summary["spend"] / summary["transactions_1st_time"].round().replace(0, np.nan)
    ).replace([np.inf], 0).fillna(0)
    summary["aov"] = (
        summary["attributed_rev"] / txns_rounded
    ).replace([np.inf], 0).fillna(0)

    # Store the rounded value for display purposes
    summary["transactions_display"] = txns_rounded.fillna(0)

    summary = summary.replace([np.inf, -np.inf], 0).round(2)
    summary = summary.sort_values("spend", ascending=False)
    return summary


def markdown_table(
    summary: pd.DataFrame,
    index_label: str,
    extra_col: str | None = None,
    prev_summary: pd.DataFrame | None = None,
):
    """Return a markdown table with optional Prev and Δ% columns for each metric."""

    headers: list[str] = [index_label]
    if extra_col:
        headers.append(extra_col)

    metrics = [
        ("spend", "$", 0, "Spend"),
        ("attributed_rev", "$", 0, "Revenue"),
        ("roas", "", 2, "ROAS"),
        ("roas_1st_time", "", 2, "ROAS 1st"),
        ("cac", "$", 2, "CAC"),
        ("cac_1st_time", "$", 2, "CAC 1st"),
        ("aov", "$", 2, "AOV"),
        ("transactions_display", "", 0, "Transactions"),
    ]

    for m, _, _, title in metrics:
        headers.append(title)
        if prev_summary is not None:
            headers.extend([f"{title} Prev", f"{title} Δ%"])

    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["-"] * len(headers)) + "|"]

    for idx, row in summary.iterrows():
        cells: list[str] = [idx]
        if extra_col:
            cells.append(str(row[extra_col]))

        for metric, prefix, dec, _ in metrics:
            cur_val = row[metric] if metric in row else 0
            # Current value
            cur_fmt = f"{prefix}{cur_val:,.{dec}f}" if prefix else f"{cur_val:,.{dec}f}" if dec else f"{int(cur_val)}"
            cells.append(cur_fmt)

            if prev_summary is not None:
                prev_val = prev_summary.loc[idx][metric] if idx in prev_summary.index and metric in prev_summary.columns else 0
                prev_fmt = f"{prefix}{prev_val:,.{dec}f}" if prefix else f"{prev_val:,.{dec}f}" if dec else f"{int(prev_val)}"
                pct = _pct_delta(cur_val, prev_val)
                sign = "+" if pct > 0 else ("-" if pct < 0 else "")
                delta_fmt = f"{sign}{abs(pct):.0f}%"
                cells.extend([prev_fmt, delta_fmt])

        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


# -------------------------------------------------------------
# Σ  Totals row helper specifically for CHANNEL table so that
#   WoW Prev and Δ columns can be displayed.
# -------------------------------------------------------------


def channel_totals_df(summary: pd.DataFrame, label: str = "**All Channels**") -> pd.DataFrame:
    """Return 1-row DataFrame with totals and rounded txns_display."""
    spend = summary["spend"].sum()
    revenue = summary["attributed_rev"].sum()
    txns = summary["transactions"].sum()

    txns_display = round(txns)
    rev_1st_sum = summary["attributed_rev_1st_time"].sum() if "attributed_rev_1st_time" in summary.columns else 0
    txns_1st_sum = summary["transactions_1st_time"].sum() if "transactions_1st_time" in summary.columns else 0
    row = {
        "spend": spend,
        "attributed_rev": revenue,
        "roas": revenue / spend if spend else 0,
        "roas_1st_time": rev_1st_sum / spend if spend else 0,
        "cac": spend / txns_display if txns_display else 0,
        "cac_1st_time": spend / txns_1st_sum if txns_1st_sum else 0,
        "aov": revenue / txns_display if txns_display else 0,
        "transactions": txns_display,
        "transactions_display": txns_display,
    }
    return pd.DataFrame(row, index=[label])


# -------------------------------------------------------------
# Σ  Helper to add totals row
# -------------------------------------------------------------

def totals_row(summary: pd.DataFrame, label: str):
    """Return a one-row DataFrame with totals across the provided summary."""
    numeric_base = [
        "spend",
        "attributed_rev",
        "transactions",
    ]

    agg = summary[numeric_base].sum()
    spend = agg["spend"]
    revenue = agg["attributed_rev"]
    txns = agg["transactions"]

    txns_display = round(txns)

    rev_1st_sum = summary["attributed_rev_1st_time"].sum() if "attributed_rev_1st_time" in summary.columns else 0
    txns_1st_sum = summary["transactions_1st_time"].sum() if "transactions_1st_time" in summary.columns else 0
    total_series = {
        "spend": spend,
        "attributed_rev": revenue,
        "roas": revenue / spend if spend else 0,
        "roas_1st_time": rev_1st_sum / spend if spend else 0,
        "cac": spend / txns_display if txns_display else 0,
        "cac_1st_time": spend / txns_1st_sum if txns_1st_sum else 0,
        "aov": revenue / txns_display if txns_display else 0,
        "transactions": txns_display,
        "transactions_display": txns_display,
    }

    return pd.DataFrame(total_series, index=[label])


# -------------------------------------------------------------
# 🏁  Main Routine
# -------------------------------------------------------------

def main():
    print("HigherDOSE Weekly Product/Category Report")
    print("========================================\n")

    # -------------------------------------------------------------
    # 🔧  CLI arguments (paths to current-year MTD CSVs)
    # -------------------------------------------------------------

    parser = argparse.ArgumentParser(description="Generate weekly growth report with YoY comparisons")
    parser.add_argument("--google_csv", help="Path to current Google Ads MTD CSV", default=None)
    parser.add_argument("--meta_csv", help="Path to current Meta Ads MTD CSV", default=None)
    args, _unknown = parser.parse_known_args()

    # Determine current-year MTD files (CLI arg if supplied, otherwise prompt)
    google_cur_path = args.google_csv
    if not google_cur_path:
        google_cur_path = input("Path to current-year Google Ads MTD CSV (blank to skip YoY): ").strip() or None

    meta_cur_path = args.meta_csv
    if not meta_cur_path:
        meta_cur_path = input("Path to current-year Meta Ads MTD CSV (blank to skip YoY): ").strip() or None

    # 1. Load channel-level cleaned data from the base module
    df = base.load_and_clean_data()
    if df is None:
        return

    # 2. Product mapping & assignment
    product_to_category, alias_sorted, norm_fn = load_product_mappings()
    df_prod = assign_products(df, alias_sorted, norm_fn)

    # Label rows with no matched product as 'Unattributed'
    df_prod["product"] = df_prod["product"].fillna("Unattributed")

    # 3. Build product & category summaries using Accrual performance rows only (to mirror channel-level logic)
    accrual_df_prod = df_prod[df_prod["accounting_mode"] == "Accrual performance"].copy()

    # -------------------------------------------------------------
    # 🧹 Remove *campaign summary* rows to avoid double-counting.
    # These are rows whose adset_name and ad_name are empty or "(no name)".
    # If a campaign has ONLY such a row (i.e., no ad-level lines), we keep it.
    # But if both summary + detailed rows exist, we drop the summary row.
    # -------------------------------------------------------------

    def _is_blank(val):
        return pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == "(no name)"

    accrual_df_prod["_is_summary"] = accrual_df_prod.apply(
        lambda r: _is_blank(r["adset_name"]) and _is_blank(r["ad_name"]), axis=1
    )

    # Identify campaigns that also have detailed rows (non-summary)
    has_detail = (
        accrual_df_prod.groupby("campaign_name")["_is_summary"].transform(lambda s: (~s).any())
    )

    accrual_filtered = accrual_df_prod[~(accrual_df_prod["_is_summary"] & has_detail)].copy()

    # -------------------------------------------------------------
    # 🔄  Build Product & Category summaries using *Cash snapshot*
    #     to avoid fractional-transaction confusion in CAC/AOV.
    # -------------------------------------------------------------

    cash_df_prod = df_prod[df_prod["accounting_mode"] == "Cash snapshot"].copy()

    # Re-use the same summary-row removal logic for cash rows
    cash_df_prod["_is_summary"] = cash_df_prod.apply(
        lambda r: _is_blank(r["adset_name"]) and _is_blank(r["ad_name"]), axis=1
    )
    cash_has_detail = (
        cash_df_prod.groupby("campaign_name")["_is_summary"].transform(lambda s: (~s).any())
    )
    cash_filtered = cash_df_prod[~(cash_df_prod["_is_summary"] & cash_has_detail)].copy()

    product_summary = build_summary(cash_filtered[cash_filtered["product"].notna()], "product")

    cash_filtered["category"] = cash_filtered["product"].map(product_to_category).fillna("Unattributed")
    category_summary = build_summary(cash_filtered[cash_filtered["category"].notna()], "category")

    # -------------------------------------------------------------
    # 📅  Previous-week summaries for deltas
    # -------------------------------------------------------------
    prev_csv = _find_previous_csv()
    prev_df = _load_csv_clean(prev_csv) if prev_csv else None

    prev_product_summary = prev_category_summary = None
    if prev_df is not None:
        prev_df_prod = assign_products(prev_df, alias_sorted, norm_fn)
        prev_cash_df = prev_df_prod[prev_df_prod["accounting_mode"] == "Cash snapshot"].copy()
        prev_cash_df["category"] = prev_cash_df["product"].map(product_to_category).fillna("Unattributed")

        prev_product_summary = build_summary(prev_cash_df[prev_cash_df["product"].notna()], "product")
        prev_category_summary = build_summary(prev_cash_df[prev_cash_df["category"].notna()], "category")

    # -------------------------------------------------------------
    # 🚩 Capture Unattributed rows for alias discovery
    # -------------------------------------------------------------
    unattributed_df = accrual_filtered[accrual_filtered["product"] == "Unattributed"].copy()

    if not unattributed_df.empty:
        cols_to_keep = [
            "breakdown_platform_northbeam",
            "campaign_name",
            "adset_name",
            "ad_name",
            "spend",
            "attributed_rev",
        ]
        unattributed_export = unattributed_df[cols_to_keep].sort_values("spend", ascending=False)

        out_dir = Path("data/processed/unattributed_products")
        out_dir.mkdir(parents=True, exist_ok=True)
        export_name = out_dir / f"unattributed_lines_{datetime.now().strftime('%Y-%m-%d')}.csv"
        unattributed_export.to_csv(export_name, index=False)
        print(f"📤 Exported {len(unattributed_export)} unattributed rows to {export_name}")

    # 4. Run existing channel-level analyses (for executive summary etc.)
    channel_summary = base.analyze_channel_performance(df)
    if channel_summary.empty:
        print("No channel data – exiting")
        return

    executive_metrics = base.generate_executive_summary(channel_summary)
    campaign_analysis, revenue_only_df = base.analyze_campaign_performance(df)
    first_time_metrics = base.analyze_first_time_metrics(df)
    base.analyze_attribution_modes(df)
    base.identify_opportunities(channel_summary)

    # 5. Assemble markdown report
    base_report = base.export_markdown_report(
        executive_metrics,
        channel_summary,
        campaign_analysis,
        revenue_only_df,
        first_time_metrics,
    )

    # Prepare product summary with Category column for display
    # Product display with totals row
    prod_display = product_summary.copy()
    prod_display["Category"] = prod_display.index.map(product_to_category)

    prod_tot = totals_row(prod_display, label="**All Products**")
    prod_tot["Category"] = "—"

    prod_table_df = pd.concat([prod_tot, prod_display])

    # Category display with totals row
    cat_tot = totals_row(category_summary, label="**All Categories**")
    category_table_df = pd.concat([cat_tot, category_summary])

    product_section_md = (
        "\n## 2a. Performance by Product (Cash Snapshot)\n" +
        markdown_table(prod_table_df, index_label="Product", extra_col="Category") +
        "\n\n## 2b. Performance by Category (Cash Snapshot)\n" +
        markdown_table(category_table_df, index_label="Category") +
        "\n---\n"
    )

    # -------------------------------------------------------------
    # 🚀 Meta Product Group Performance (Accrual Performance)
    # -------------------------------------------------------------
    meta_base = df[(df["accounting_mode"] == "Accrual performance") &
                   (df["breakdown_platform_northbeam"].astype(str).str.contains(r"meta|facebook|fb|instagram", case=False, na=False))].copy()

    # Remove campaign summary rows to avoid double-counting (same logic as above)
    def _is_blank(val):
        return pd.isna(val) or str(val).strip() == "" or str(val).strip().lower() == "(no name)"

    meta_base["_is_summary"] = meta_base.apply(
        lambda r: _is_blank(r["adset_name"]) and _is_blank(r["ad_name"]), axis=1
    )
    has_meta_detail = meta_base.groupby("campaign_name")["_is_summary"].transform(lambda s: (~s).any())
    meta_accrual = meta_base[~(meta_base["_is_summary"] & has_meta_detail)].copy()

    if not meta_accrual.empty:
        # Use campaign-name keywords for grouping to align with user’s totals
        def _keyword_group(row):
            text = str(row.get("campaign_name", "")).lower()
            # Explicit keywords checked in priority order to avoid mis-classification
            if "bundle" in text:
                return "Bundle"
            if "blanket" in text:
                return "Sauna Blanket"
            if "pemf" in text:
                return "PEMF Mat"
            if "hat" in text:
                return "Red Light Hat"
            if "mask" in text:
                return "Red Light Mask"
            return "Body Care & Supplements"

        meta_accrual["product_group"] = meta_accrual.apply(_keyword_group, axis=1)

        # Ensure groups exactly match the desired order for table output
        desired_order = [
            "Body Care & Supplements",
            "Sauna Blanket",
            "Red Light Hat",
            "PEMF Mat",
            "Red Light Mask",
            "Bundle",
        ]

        meta_group_df = meta_accrual.copy()

        meta_summary = build_summary(meta_group_df, "product_group")

        # Re-index to ensure all groups appear (missing groups will be 0)
        meta_summary = meta_summary.reindex(desired_order).fillna(0)

        # Build markdown table mirroring DTC metrics
        headers = [
            "Product Group",
            "Spend",
            "% of Total",
            "CAC",
            "CAC 1st",
            "ROAS",
            "ROAS 1st",
            "AOV",
            "Transactions",
            "Revenue",
        ]
        meta_lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["-"] * len(headers)) + "|"]

        total_spend_meta = meta_summary["spend"].sum() if not meta_summary.empty else 0

        for idx, row in meta_summary.iterrows():
            spend = row["spend"]
            pct_total = (spend / total_spend_meta * 100) if total_spend_meta else 0
            meta_lines.append(
                f"| {idx} | ${spend:,.0f} | {pct_total:.1f}% | "
                f"${row['cac']:,.2f} | ${row['cac_1st_time']:,.2f} | "
                f"{row['roas']:.2f} | {row['roas_1st_time']:.2f} | "
                f"${row['aov']:,.0f} | {int(row['transactions_display'])} | "
                f"${row['attributed_rev']:,.0f} |"
            )

        meta_section_md = (
            "\n## 2c. Meta Product Group Performance (Accrual Performance)\n" +
            "\n".join(meta_lines) +
            "\n---\n"
        )
    else:
        meta_section_md = ""

    # -------------------------------------------------------------
    # 🔄 Build DTC channel table with WoW columns
    # -------------------------------------------------------------
    # Only keep channels with spend > 0 for display, but compute the
    # totals row using the full data so revenue-only rows are still
    # included in the aggregate metrics.

    channel_summary["transactions_display"] = channel_summary["transactions"].round()

    # Build display DF: totals row + channels with spend > 0
    chan_tot = channel_totals_df(channel_summary)
    channel_nonzero = channel_summary[channel_summary["spend"] > 0].copy()
    # Insert a consolidated **Paid Media** row (all channels with spend)
    paid_tot = totals_row(channel_nonzero, label="**Paid Media**")
    channel_summary_display = pd.concat([chan_tot, paid_tot, channel_nonzero])

    prev_channel_summary = None
    if prev_df is not None:
        prev_channel_summary_full = base.analyze_channel_performance(prev_df)
        if isinstance(prev_channel_summary_full, pd.DataFrame) and not prev_channel_summary_full.empty:
            prev_channel_summary_full["transactions_display"] = prev_channel_summary_full["transactions"].round()
            prev_tot = channel_totals_df(prev_channel_summary_full)
            prev_nonzero = prev_channel_summary_full[prev_channel_summary_full["spend"] > 0].copy()
            prev_paid_tot = totals_row(prev_nonzero, label="**Paid Media**")
            prev_channel_summary = pd.concat([prev_tot, prev_paid_tot, prev_nonzero])

    dtc_table_md = "## 2. DTC Breakdown (Accrual Performance) - 7 Days (Northbeam)\n" + \
        markdown_table(channel_summary_display, index_label="Channel", prev_summary=prev_channel_summary) + "\n"

    # ----------------------------------------------
    # 📝  Build the final markdown by starting from
    #     the base report, renaming the DTC header,
    #     and inserting the Product & Category tables
    #     directly beneath that section (as 2a/2b).
    # ----------------------------------------------

    final_report = base_report  # start fresh from base

    # 1) Rename key section headers so we can reliably locate them
    header_map = {
        "## 2. DTC Performance — 7-Day Snapshot (Northbeam)": "## 2. DTC Breakdown (Accrual Performance) - 7 Days (Northbeam)",
        "## 3. Top Campaign Performance Analysis": "## 3. Top Campaign Performance Analysis (Accrual Performance)",
        "## 4. Channel Performance Metrics": "## 4. Channel Performance Metrics (Accrual Performance)",
    }
    for old, new in header_map.items():
        final_report = final_report.replace(old, new)

    # 2) Replace the existing DTC table with the enhanced version that
    #    includes WoW deltas, then append the Product (2a) & Category (2b)
    #    tables directly afterwards.
    dtc_header = "## 2. DTC Breakdown (Accrual Performance) - 7 Days (Northbeam)"
    hdr_pos = final_report.find(dtc_header)
    if hdr_pos != -1:
        divider_pos = final_report.find("\n---\n", hdr_pos)
        if divider_pos != -1:
            final_report = (
                final_report[:hdr_pos] +
                dtc_table_md + "\n" + product_section_md + meta_section_md +
                final_report[divider_pos:]
            )
        else:
            # Fallback – no divider found; replace from header line to next blank line
            next_break = final_report.find("\n\n", hdr_pos)
            replace_end = next_break if next_break != -1 else hdr_pos
            final_report = (
                final_report[:hdr_pos] +
                dtc_table_md + "\n" + product_section_md + meta_section_md +
                final_report[replace_end:]
            )
    else:
        # If header somehow missing, append both sections to ensure they appear.
        final_report += "\n" + dtc_table_md + "\n" + product_section_md + meta_section_md

    # -------------------------------------------------------------
    # 📈 Week-over-Week Executive Delta Overview (re-injected)
    # -------------------------------------------------------------
    if prev_df is not None:
        cur_acc = df[df["accounting_mode"] == "Accrual performance"].copy()
        prev_acc = prev_df[prev_df["accounting_mode"] == "Accrual performance"].copy()

        def _totals(d):
            return {
                "spend": d["spend"].sum(),
                "rev": d["attributed_rev"].sum(),
                "txns": d["transactions"].sum(),
                # First-time metrics (may be absent in some exports)
                "rev_1st": d["attributed_rev_1st_time"].sum() if "attributed_rev_1st_time" in d.columns else 0,
                "txns_1st": d["transactions_1st_time"].sum() if "transactions_1st_time" in d.columns else 0,
            }

        tot_cur = _totals(cur_acc)
        tot_prev = _totals(prev_acc)
        # Derived metrics
        tot_cur["roas"] = tot_cur["rev"] / tot_cur["spend"] if tot_cur["spend"] else 0
        tot_prev["roas"] = tot_prev["rev"] / tot_prev["spend"] if tot_prev["spend"] else 0
        # First-time ROAS & CAC
        tot_cur["roas_1st"] = (
            tot_cur["rev_1st"] / tot_cur["spend"] if tot_cur["spend"] else 0
        )
        tot_prev["roas_1st"] = (
            tot_prev["rev_1st"] / tot_prev["spend"] if tot_prev["spend"] else 0
        )
        tot_cur["cac_1st"] = (
            tot_cur["spend"] / tot_cur["txns_1st"] if tot_cur["txns_1st"] else 0
        )
        tot_prev["cac_1st"] = (
            tot_prev["spend"] / tot_prev["txns_1st"] if tot_prev["txns_1st"] else 0
        )

        wow_lines = [
            "\n### Week-over-Week Overview\n",
            f"* **Spend:** {_fmt_delta(tot_cur['spend'], tot_prev['spend'])}",
            f"* **Revenue:** {_fmt_delta(tot_cur['rev'], tot_prev['rev'])}",
            f"* **ROAS:** {_fmt_delta(tot_cur['roas'], tot_prev['roas'], prefix='', digits=2)}",
            f"* **ROAS 1st:** {_fmt_delta(tot_cur['roas_1st'], tot_prev['roas_1st'], prefix='', digits=2)}",
            f"* **CAC 1st:** {_fmt_delta(tot_cur['cac_1st'], tot_prev['cac_1st'], prefix='$', digits=2)}",
            f"* **Transactions:** {_fmt_delta(tot_cur['txns'], tot_prev['txns'], prefix='', digits=0)}",
            "\n",
        ]

        exec_hdr = "## 1. Executive Summary"
        pos_exec = final_report.find(exec_hdr)
        if pos_exec != -1:
            insert_pos = final_report.find("\n", pos_exec + len(exec_hdr)) + 1
            final_report = final_report[:insert_pos] + "\n".join(wow_lines) + final_report[insert_pos:]

    # -------------------------------------------------------------
    # 📊  Year-over-Year Growth Comparison (Google & Meta Ads)
    # -------------------------------------------------------------

    try:
        # Previous-year daily exports (static for now)
        google_prev_path = os.path.join("stats", "google-2024-account-level-daily report.csv")
        meta_prev_path   = os.path.join("stats", "meta-daily-export-jan-1-2024-to-dec-31-2024.csv")

        def _summarize_google(cur_path: str | None, prev_path: str):
            """Return dict with spend, revenue, conversions, roas for current & previous year MTD."""
            if not cur_path or not os.path.exists(cur_path) or not os.path.exists(prev_path):
                return None

            cur_df = pd.read_csv(cur_path, skiprows=2, thousands=",")
            prev_df = pd.read_csv(prev_path, skiprows=2, thousands=",")

            cur_df["Day"] = pd.to_datetime(cur_df["Day"], errors="coerce")
            prev_df["Day"] = pd.to_datetime(prev_df["Day"], errors="coerce")

            if cur_df["Day"].isna().all() or prev_df["Day"].isna().all():
                return None

            end_cur = cur_df["Day"].max()
            start_cur = end_cur - timedelta(days=6)  # Last 7 days inclusive
            end_prev = datetime(end_cur.year - 1, end_cur.month, end_cur.day)
            start_prev = end_prev - timedelta(days=6)

            cur_mtd = cur_df[(cur_df["Day"] >= start_cur) & (cur_df["Day"] <= end_cur)].copy()
            prev_mtd = prev_df[(prev_df["Day"] >= start_prev) & (prev_df["Day"] <= end_prev)].copy()

            for col in ["Cost", "Conv. value", "Conversions"]:
                cur_mtd[col] = pd.to_numeric(cur_mtd[col], errors="coerce")
                prev_mtd[col] = pd.to_numeric(prev_mtd[col], errors="coerce")

            def _tot(df):
                return (
                    df["Cost"].sum(),
                    df["Conv. value"].sum(),
                    df["Conversions"].sum(),
                )

            spend_cur, rev_cur, conv_cur = _tot(cur_mtd)
            spend_prev, rev_prev, conv_prev = _tot(prev_mtd)

            roas_cur = rev_cur / spend_cur if spend_cur else 0
            roas_prev = rev_prev / spend_prev if spend_prev else 0

            cpa_cur = spend_cur / conv_cur if conv_cur else 0
            cpa_prev = spend_prev / conv_prev if conv_prev else 0

            return {
                "spend_cur": spend_cur,
                "spend_prev": spend_prev,
                "rev_cur": rev_cur,
                "rev_prev": rev_prev,
                "conv_cur": conv_cur,
                "conv_prev": conv_prev,
                "roas_cur": roas_cur,
                "roas_prev": roas_prev,
                "cpa_cur": cpa_cur,
                "cpa_prev": cpa_prev,
                "start_date": start_cur.strftime("%B %d"),
                "end_date": end_cur.strftime("%B %d"),
            }

        def _summarize_meta(cur_path: str | None, prev_path: str):
            if not cur_path or not os.path.exists(cur_path) or not os.path.exists(prev_path):
                return None

            cur_df = pd.read_csv(cur_path, thousands=",")
            prev_df = pd.read_csv(prev_path, thousands=",")

            cur_df["Day"] = pd.to_datetime(cur_df["Day"], errors="coerce")
            prev_df["Day"] = pd.to_datetime(prev_df["Day"], errors="coerce")

            if cur_df["Day"].isna().all() or prev_df["Day"].isna().all():
                return None

            end_cur = cur_df["Day"].max()
            start_cur = end_cur - timedelta(days=6)
            end_prev = datetime(end_cur.year - 1, end_cur.month, end_cur.day)
            start_prev = end_prev - timedelta(days=6)

            cur_mtd = cur_df[(cur_df["Day"] >= start_cur) & (cur_df["Day"] <= end_cur)].copy()
            prev_mtd = prev_df[(prev_df["Day"] >= start_prev) & (prev_df["Day"] <= end_prev)].copy()

            for col in ["Amount spent (USD)", "Purchases conversion value", "Purchases"]:
                cur_mtd[col] = pd.to_numeric(cur_mtd[col], errors="coerce")
                prev_mtd[col] = pd.to_numeric(prev_mtd[col], errors="coerce")

            def _tot(df):
                return (
                    df["Amount spent (USD)"].sum(),
                    df["Purchases conversion value"].sum(),
                    df["Purchases"].sum(),
                )

            spend_cur, rev_cur, conv_cur = _tot(cur_mtd)
            spend_prev, rev_prev, conv_prev = _tot(prev_mtd)

            roas_cur = rev_cur / spend_cur if spend_cur else 0
            roas_prev = rev_prev / spend_prev if spend_prev else 0

            cpa_cur = spend_cur / conv_cur if conv_cur else 0
            cpa_prev = spend_prev / conv_prev if conv_prev else 0

            return {
                "spend_cur": spend_cur,
                "spend_prev": spend_prev,
                "rev_cur": rev_cur,
                "rev_prev": rev_prev,
                "conv_cur": conv_cur,
                "conv_prev": conv_prev,
                "roas_cur": roas_cur,
                "roas_prev": roas_prev,
                "cpa_cur": cpa_cur,
                "cpa_prev": cpa_prev,
                "start_date": start_cur.strftime("%B %d"),
                "end_date": end_cur.strftime("%B %d"),
            }

        google_yoy = _summarize_google(google_cur_path, google_prev_path)
        meta_yoy = _summarize_meta(meta_cur_path, meta_prev_path)

        def _fmt(val: float, prefix: str = "$", digits: int = 0):
            if prefix:
                return f"{prefix}{val:,.{digits}f}"
            return f"{val:,.{digits}f}"

        if google_yoy and meta_yoy:
            end_label = google_yoy["end_date"]
            yoy_lines: list[str] = [
                f"\n## 5. Year-over-Year Growth (Week {google_yoy['start_date']}–{end_label})\n",
            ]

            def _yoy_rows(platform: str, data: dict[str, float]):
                rows: list[str] = []
                metrics = [
                    ("spend", "$", 0, "Spend"),
                    ("rev", "$", 0, "Revenue"),
                    ("conv", "", 0, "Conversions"),
                    ("roas", "", 2, "ROAS"),
                    ("cpa", "$", 2, "CPA"),
                ]
                rows.append(f"\n### {platform}\n")
                rows.append("| Metric | 2025 | 2024 | YoY Δ% |")
                rows.append("|-|-|-|-|")
                for key, prefix, digits, title in metrics:
                    cur_val = data[f"{key}_cur"]
                    prev_val = data[f"{key}_prev"]
                    pct = _pct_delta(cur_val, prev_val)
                    sign = "+" if pct > 0 else ("-" if pct < 0 else "")
                    delta_fmt = f"{sign}{abs(pct):.0f}%"
                    rows.append(
                        f"| {title} | {_fmt(cur_val, prefix, digits)} | {_fmt(prev_val, prefix, digits)} | {delta_fmt} |")
                return "\n".join(rows)

            yoy_lines.append(_yoy_rows("Google Ads", google_yoy))
            yoy_lines.append(_yoy_rows("Meta Ads", meta_yoy))

            yoy_section_md = "\n".join(yoy_lines) + "\n"

            final_report += yoy_section_md
    except Exception as e:
        print(f"⚠️  YoY section failed: {e}")

    # -------------------------------------------------------------
    # 📝  Initialize the working markdown document
    #       Start with the base report produced by the core script and
    #       immediately append the Product & Category section we built
    #       above.  Subsequent steps will mutate this `final_report`
    #       string in-place (e.g., replace the old DTC table, inject
    #       WoW overview, add appendix).
    # -------------------------------------------------------------

    # Replace existing DTC section with new one
    # final_report = base_report + product_section_md

    # Label major base-report tables as Accrual Performance to distinguish from cash snapshot
    header_map = {
        "## 2. DTC Performance — 7-Day Snapshot (Northbeam)": "## 2. DTC Breakdown (Accrual Performance) - 7 Days (Northbeam)",
        "## 3. Top Campaign Performance Analysis": "## 3. Top Campaign Performance Analysis (Accrual Performance)",
        "## 4. Channel Performance Metrics": "## 4. Channel Performance Metrics (Accrual Performance)",
        "### 💰 Highest Spend Campaigns": "### 💰 Highest Spend Campaigns",
    }
    for old, new in header_map.items():
        final_report = final_report.replace(old, new)

    # Append an appendix listing top unattributed campaigns for quick reference
    if not unattributed_df.empty:
        # Include all unattributed rows *with spend > 0*, sorted by spend descending
        top_unattributed = (
            unattributed_df[unattributed_df["spend"] > 0]
            .sort_values("spend", ascending=False)
        )
        appendix_lines = [
            "\n## Appendix: Top Unattributed Spend (Review for New Aliases)\n",
            "| Platform | Campaign | Ad Set | Ad | Spend | Revenue |",
            "|-|-|-|-|-|-|",
        ]

        # Helper to escape pipe characters that would break Markdown tables
        def _escape_pipes(text: str) -> str:
            """Return text safe for Markdown table cells by escaping pipe characters."""
            return str(text).replace("|", "\\|")

        for _, row in top_unattributed.iterrows():
            appendix_lines.append(
                f"| {row['breakdown_platform_northbeam']} | "
                f"{_escape_pipes(row['campaign_name'])[:40]} | "
                f"{_escape_pipes(row['adset_name'])[:30]} | "
                f"{_escape_pipes(row['ad_name'])[:30]} | "
                f"${row['spend']:,.0f} | ${row['attributed_rev']:,.0f} |")

        # Add totals row
        # Totals should reflect only the rows shown in the table
        tot_spend_un = top_unattributed['spend'].sum()
        tot_rev_un = top_unattributed['attributed_rev'].sum()
        appendix_lines.append(
            f"| **Totals** | — | — | — | **${tot_spend_un:,.0f}** | **${tot_rev_un:,.0f}** |")

        final_report += "\n".join(appendix_lines)

    # ------------------------------------------------------------------
    # 🗄️  Save report to dedicated output directory (reports/weekly)
    # ------------------------------------------------------------------
    REPORT_DIR = Path("reports/weekly")
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    out_file = REPORT_DIR / f"weekly-growth-report-with-products-{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(final_report)

    print(f"📝 Markdown report saved to {out_file}")


if __name__ == "__main__":
    main()