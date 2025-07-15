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
import ast
import re
from datetime import datetime

import numpy as np
import pandas as pd

import report_analysis_weekly as base

# Pathlib for file-friendly names
from pathlib import Path


# -------------------------------------------------------------
# 🔎  Product & Category Mapping Helpers
# -------------------------------------------------------------

def load_product_mappings(md_path: str = "product-list.md"):
    """Parse the product-list markdown to build mappings without importing it as a module.

    We look for literal `categories = {...}` and optional `aliases = {...}` blocks and
    evaluate them safely with `ast.literal_eval` so we avoid executing any other code
    (like the file-writing section).
    """
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    def _extract_dict(name: str):
        pattern = rf"{name}\s*=\s*(\{{.*?\}})"  # greedy balanced with simple heuristic
        match = re.search(pattern, content, re.S)
        if match:
            try:
                return ast.literal_eval(match.group(1))
            except Exception:
                pass
        return {}

    categories_dict = _extract_dict("categories")
    aliases_dict = _extract_dict("aliases")

    # Build product → category mapping
    product_to_category: dict[str, str] = {}
    for cat, prods in categories_dict.items():
        for prod in prods:
            product_to_category[prod] = cat

    # Ensure a default bucket for unmatched rows
    product_to_category.setdefault("Unattributed", "Unattributed")

    # Normalize helper
    def _norm(s: str):
        # insert spaces before CamelCase transitions first
        s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
        s = s.replace("_", " ").replace("-", " ")
        s = s.lower()
        s = re.sub(r"[^a-z0-9 ]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    alias_map = {_norm(k): v for k, v in aliases_dict.items()}
    # Ensure canonical names map to themselves
    for prod in product_to_category:
        alias_map.setdefault(_norm(prod), prod)

    # Precompute variants with spaces removed for camel-case matches
    expanded_alias = {}
    for key, val in alias_map.items():
        expanded_alias[key] = val
        nospace = key.replace(" ", "")
        if nospace != key:
            expanded_alias.setdefault(nospace, val)

    # sort longest->shortest for deterministic greedy matching
    alias_sorted = sorted(expanded_alias.items(), key=lambda kv: len(kv[0]), reverse=True)
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


def markdown_table(summary: pd.DataFrame, index_label: str, extra_col: str | None = None):
    """Return a markdown table string for a given summary dataframe.

    Parameters
    ----------
    summary : pd.DataFrame
        DataFrame with metrics already computed. The index is expected to be
        the primary label (e.g., product name or category).
    index_label : str
        Header text to use for the index column (e.g., "Product").
    extra_col : str | None
        Optional column in `summary` to display immediately after the index
        column (e.g., "Category" when the index is Product).
    """

    headers = [index_label]
    if extra_col:
        headers.append(extra_col)
    headers.extend(["Spend", "Revenue", "ROAS", "CAC", "AOV", "Transactions"])

    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("-" * len(h) for h in headers) + "|"]

    for idx, row in summary.iterrows():
        cells = [idx]
        if extra_col:
            cells.append(row[extra_col])  # type: ignore[index]
        cells.extend([
            f"${row['spend']:,.0f}",
            f"${row['attributed_rev']:,.0f}",
            f"{row['roas']:.2f}",
            f"${row['cac']:.2f}",
            f"${row['aov']:.2f}",
            f"{row.get('transactions_display', row['transactions']):.0f}",
        ])
        lines.append("| " + " | ".join(map(str, cells)) + " |")

    return "\n".join(lines)


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

    total_series = {
        "spend": spend,
        "attributed_rev": revenue,
        "roas": revenue / spend if spend else 0,
        "cac": spend / txns_display if txns_display else 0,
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

        export_name = (
            f"unattributed_lines_{datetime.now().strftime('%Y-%m-%d')}.csv"
        )
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

    # Insert product/category tables *after* the DTC 7-Day Snapshot section.
    # We look for the header that starts that section, then locate the first
    # divider ("\n---\n") that follows it and inject our markdown right there.

    dtc_header = "## 2. DTC Performance"
    header_pos = base_report.find(dtc_header)

    if header_pos != -1:
        # Find the divider that closes the DTC section
        divider_pos = base_report.find("\n---\n", header_pos)
        if divider_pos != -1:
            insert_at = divider_pos  # insert *before* this divider
            final_report = base_report[:insert_at] + product_section_md + base_report[insert_at:]
        else:
            # Fallback – divider not found after header; append at end
            final_report = base_report + product_section_md
    else:
        # Fallback – header not found; keep previous behaviour (second divider)
        front_matter, remainder = base_report.split("\n---\n", 1)
        remainder_with_section = remainder.replace("\n---\n", product_section_md, 1)
        final_report = "\n---\n".join([front_matter, remainder_with_section])

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

    out_file = f"weekly-growth-report-with-products-{datetime.now().strftime('%Y-%m-%d')}.md"
    with open(out_file, "w") as f:
        f.write(final_report)

    print(f"📝 Markdown report saved to {out_file}")


if __name__ == "__main__":
    main() 