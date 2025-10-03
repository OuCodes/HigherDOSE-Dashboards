import os
import re
from datetime import datetime, date
from typing import Tuple

import pandas as pd


def parse_datetime(value: str) -> datetime:
    if pd.isna(value):
        return pd.NaT
    # Try multiple common Shopify/CSV formats
    for fmt in (
        "%m/%d/%Y",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except Exception:
            continue
    # Fallback: let pandas try
    try:
        return pd.to_datetime(value, errors="coerce")
    except Exception:
        return pd.NaT


def coerce_money(value) -> float:
    if pd.isna(value):
        return 0.0
    s = str(value)
    # Replace en-dash and other non-numeric
    s = s.replace("–", "").replace(",", "").replace("$", "").strip()
    if s == "" or s.lower() in ("nan", "none"):
        return 0.0
    try:
        return float(s)
    except Exception:
        # Some values like 6.35989E+12 are not money, those are IDs; treat as 0
        return 0.0


def load_a8(filepath: str, since: date) -> pd.DataFrame:
    df = pd.read_csv(filepath, dtype=str, keep_default_na=False)
    # Normalize columns
    df.columns = [c.strip() for c in df.columns]
    if "Created at" not in df.columns:
        raise ValueError("Expected 'Created at' column in A8 CSV")
    if "Lineitem name" not in df.columns or "Lineitem price" not in df.columns:
        raise ValueError("Expected 'Lineitem name' and 'Lineitem price' columns in A8 CSV")

    df["created_dt"] = df["Created at"].apply(parse_datetime)
    df = df[df["created_dt"].notna()].copy()
    df = df[df["created_dt"] >= pd.Timestamp(since)]

    # Best estimate of gift value: use Lineitem price when total is $0 and there is a discount code
    df["line_price"] = df["Lineitem price"].apply(coerce_money)
    total_col = df.get("Total")
    discount_col = df.get("Discount Amount")
    discount_code_col = df.get("Discount Code")

    df["total_amount"] = total_col.apply(coerce_money) if total_col is not None else 0.0
    df["discount_amount"] = discount_col.apply(coerce_money) if discount_col is not None else 0.0
    df["has_discount"] = discount_code_col.fillna("").str.len() > 0 if discount_code_col is not None else False

    # Heuristic: if total is 0 and a discount exists, take gift value as line price; else min(line price, discount)
    def compute_gift_value(row) -> float:
        if row["has_discount"] and row["total_amount"] == 0.0:
            return row["line_price"]
        if row["discount_amount"] > 0:
            # Some rows show discount including tax/shipping; guard by taking at least line price
            return max(min(row["discount_amount"], row["line_price"] if row["line_price"] > 0 else row["discount_amount"]), 0.0)
        return row["line_price"]

    df["gift_value"] = df.apply(compute_gift_value, axis=1)

    # Derive channel flags (ShopMy vs Direct), but default to ShopMy as per user note
    email_col = df.get("Email", pd.Series([""] * len(df)))
    tags_col = df.get("Tags", pd.Series([""] * len(df)))
    source_col = df.get("Source", pd.Series([""] * len(df)))

    def is_shopmy(row) -> bool:
        email = str(row.get("Email", ""))
        tags = str(row.get("Tags", ""))
        source = str(row.get("Source", ""))
        return (
            "shopmy" in email.lower()
            or "shopmy" in tags.lower()
            or "shopmy" in source.lower()
            or "lookbook" in tags.lower()
        )

    df["channel"] = df.apply(lambda r: "ShopMy" if is_shopmy(r) else "Direct", axis=1)
    return df


def summarize_a8(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    by_product = (
        df.groupby("Lineitem name", dropna=False)[["gift_value"]]
        .sum()
        .rename(columns={"gift_value": "gift_value_total"})
        .sort_values("gift_value_total", ascending=False)
    )
    by_product["orders"] = df.groupby("Lineitem name").size()

    by_channel = (
        df.groupby("channel")[["gift_value"]]
        .sum()
        .rename(columns={"gift_value": "gift_value_total"})
        .sort_values("gift_value_total", ascending=False)
    )
    by_channel["orders"] = df.groupby("channel").size()

    by_week = (
        df.assign(week=df["created_dt"].dt.to_period("W-SUN").dt.start_time)
        .groupby("week")[["gift_value"]]
        .sum()
        .rename(columns={"gift_value": "gift_value_total"})
        .sort_values("week")
    )

    return by_product, by_channel, by_week


def load_ga4(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    df.columns = [c.strip() for c in df.columns]
    required = [
        "Date",
        "Source / Medium",
        "Sessions",
        "Ecommerce purchases",
        "Purchase revenue",
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing GA4 columns: {missing}")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df[df["Date"].notna()].copy()
    return df


def summarize_ga4_shopmy_window(
    df: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> Tuple[pd.Series, int]:
    """Summarize GA4 ShopMy metrics within an inclusive [start, end] window.

    Returns (aggregates, a8_hits) where aggregates contains sessions, purchases,
    purchase_revenue, days, last_date.
    """
    # Include ShopMy and referral variants like ShareASale
    pattern_aff = re.compile(r"(shopmy|shareasale)", re.IGNORECASE)
    shopmy = df[df["Source / Medium"].astype(str).str.contains(pattern_aff)]
    a8_pattern = re.compile(r"\ba8\b", re.IGNORECASE)
    a8_hits = int(shopmy["Source / Medium"].astype(str).str.contains(a8_pattern).sum())

    mask = (shopmy["Date"] >= start) & (shopmy["Date"] <= end)
    sub = shopmy[mask]
    agg = pd.Series(
        {
            "sessions": float(sub["Sessions"].sum()),
            "purchases": float(sub["Ecommerce purchases"].sum()),
            "purchase_revenue": float(sub["Purchase revenue"].sum()),
            "days": int(sub["Date"].nunique()),
            "last_date": sub["Date"].max() if not sub.empty else pd.NaT,
        }
    )
    return agg, a8_hits


def load_shopify_total_sales(
    filepath: str, since: date, end: pd.Timestamp | None
) -> Tuple[float, pd.Timestamp, pd.Timestamp]:
    df = pd.read_csv(filepath)
    # Columns: Day, Total sales
    if "Day" not in df.columns or "Total sales" not in df.columns:
        raise ValueError("Shopify Total sales over time CSV must include 'Day' and 'Total sales'")
    df["Day"] = pd.to_datetime(df["Day"], errors="coerce")
    df = df[df["Day"].notna()].copy()
    df["Total sales"] = df["Total sales"].apply(coerce_money)
    df = df[df["Day"] >= pd.Timestamp(since)]
    if end is not None and pd.notna(end):
        df = df[df["Day"] <= end]
    if df.empty:
        return 0.0, pd.NaT, pd.NaT
    total = float(df["Total sales"].sum())
    start = df["Day"].min()
    end = df["Day"].max()
    return total, start, end


def load_shopify_sales_by_product(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    # Expected columns: Product title, Month, Net sales (or Total sales)
    for col in ("Month", "Product title"):
        if col not in df.columns:
            raise ValueError("Shopify product sales CSV missing column: %s" % col)
    # Prefer Net sales if available; otherwise, Total sales
    value_col = "Net sales" if "Net sales" in df.columns else "Total sales"
    df[value_col] = df[value_col].apply(coerce_money)
    df["Month"] = pd.to_datetime(df["Month"], errors="coerce")
    df = df[df["Month"].notna()].copy()
    return df[["Product title", "Month", value_col]].rename(columns={value_col: "sales"})


def compute_seeded_product_lift(
    a8_df: pd.DataFrame,
    product_sales: pd.DataFrame,
    since: date,
    shopify_end: pd.Timestamp,
) -> pd.DataFrame:
    # Identify seeded products from A8 CSV (gift names)
    seeded_gift_names = (
        a8_df["Lineitem name"].dropna().astype(str).str.strip().unique().tolist()
    )
    if shopify_end is not None and pd.notna(shopify_end):
        end_dt = shopify_end
    else:
        end_dt = pd.Timestamp.today().normalize()

    # Define equal-length pre and post windows
    post_start = pd.Timestamp(since)
    post_end = end_dt
    post_days = int((post_end.normalize() - post_start.normalize()).days) + 1 if pd.notna(post_end) else 0
    pre_end = post_start - pd.Timedelta(days=1)
    pre_start = pre_end - pd.Timedelta(days=post_days - 1) if post_days > 0 else pre_end

    pre_mask = (product_sales["Month"] >= pre_start) & (product_sales["Month"] <= pre_end)
    post_mask = (product_sales["Month"] >= post_start) & (product_sales["Month"] <= post_end)

    site_pre = float(product_sales.loc[pre_mask, "sales"].sum()) or 0.0
    site_post = float(product_sales.loc[post_mask, "sales"].sum()) or 0.0
    site_growth = (site_post - site_pre) / site_pre if site_pre > 0 else float("nan")

    # Build a best-match map from A8 gift name -> Shopify product title using token overlap
    def tokenize(name: str) -> set:
        s = re.sub(r"[^a-zA-Z0-9 ]+", " ", name.lower())
        tokens = {t for t in s.split() if len(t) > 1}
        stop = {
            "higherdose",
            "with",
            "without",
            "and",
            "the",
            "set",
            "kit",
            "ritual",
            "v1",
            "full",
            "size",
            "sample",
            "lookbook",
        }
        return {t for t in tokens if t not in stop}

    titles = product_sales["Product title"].astype(str).unique().tolist()
    title_tokens = {title: tokenize(title) for title in titles}

    mapping: dict[str, str | None] = {}
    for gift in seeded_gift_names:
        gtok = tokenize(gift)
        best_title = None
        best_score = 0.0
        for title, ttok in title_tokens.items():
            if not ttok:
                continue
            inter = len(gtok & ttok)
            union = len(gtok | ttok) if (gtok or ttok) else 1
            score = inter / union if union > 0 else 0.0
            # Slight bonus if raw substring present
            if score == 0.0 and gift.lower().split(" ")[0] in title.lower():
                score = 0.2
            if score > best_score:
                best_score = score
                best_title = title
        mapping[gift] = best_title if best_score >= 0.2 else None

    # Aggregate per gift-name using mapped product title sales
    rows = []
    for gift in seeded_gift_names:
        title = mapping.get(gift)
        if title is None:
            pre_sum = 0.0
            post_sum = 0.0
        else:
            pre_sum = float(
                product_sales.loc[pre_mask & (product_sales["Product title"] == title), "sales"].sum()
            )
            post_sum = float(
                product_sales.loc[post_mask & (product_sales["Product title"] == title), "sales"].sum()
            )
        abs_change = post_sum - pre_sum
        pct_change = (abs_change / pre_sum) if pre_sum > 0 else float("nan")
        norm_vs_site = (pct_change - site_growth) if pd.notna(pct_change) and pd.notna(site_growth) else float("nan")
        rows.append(
            {
                "gift_name": gift,
                "mapped_title": title or "(no match)",
                "pre_sales": pre_sum,
                "post_sales": post_sum,
                "abs_change": abs_change,
                "pct_change": pct_change,
                "norm_vs_site": norm_vs_site,
            }
        )
    lift = pd.DataFrame(rows).set_index("gift_name").sort_values("abs_change", ascending=False)

    # Normalize vs site change (relative lift over site trend)
    lift.attrs["site_pre"] = site_pre
    lift.attrs["site_post"] = site_post
    lift.attrs["site_growth"] = site_growth
    lift.attrs["pre_start"] = pre_start
    lift.attrs["pre_end"] = pre_end
    lift.attrs["post_start"] = post_start
    lift.attrs["post_end"] = post_end
    lift.attrs["window_days"] = post_days
    return lift


def write_report(
    out_path: str,
    since: date,
    a8_last: pd.Timestamp,
    a8_totals: float,
    a8_orders: int,
    by_product: pd.DataFrame,
    by_channel: pd.DataFrame,
    by_week: pd.DataFrame,
    ga4_pre: pd.Series,
    ga4_post: pd.Series,
    ga4_shopmy_a8_hits_post: int,
    ga4_pre_start: pd.Timestamp,
    ga4_pre_end: pd.Timestamp,
    ga4_post_start: pd.Timestamp,
    ga4_post_end: pd.Timestamp,
    shopify_total_sales: float,
    shopify_start: pd.Timestamp,
    shopify_end: pd.Timestamp,
    seeded_lift: pd.DataFrame,
):
    lines = []
    lines.append(f"# A8 Impact Assessment (since {since.isoformat()})\n")
    lines.append("")
    # Date ranges
    a8_last_str = a8_last.date().isoformat() if pd.notna(a8_last) else "—"
    ga4_last_str = (
        ga4_post.get("last_date").date().isoformat() if pd.notna(ga4_post.get("last_date")) else "—"
    )
    shopify_start_str = shopify_start.date().isoformat() if pd.notna(shopify_start) else "—"
    shopify_end_str = shopify_end.date().isoformat() if pd.notna(shopify_end) else "—"
    lines.append("## Date Ranges Used")
    lines.append(f"- A8 CSV: {since.isoformat()} to {a8_last_str}")
    lines.append(f"- GA4 ShopMy: {since.isoformat()} to {ga4_last_str}")
    lines.append(f"- Shopify Total Sales: {shopify_start_str} to {shopify_end_str}")
    lines.append("")
    lines.append("## Summary")
    lines.append(
        f"- Gifts total value (ShopMy + Direct heuristic): ${a8_totals:,.0f} across {a8_orders} orders"
    )
    # GA4 summary with explicit windows
    lines.append(
        f"- GA4 ShopMy {ga4_post_start.date().isoformat()} → {ga4_post_end.date().isoformat()}: {ga4_post['sessions']:,.0f} sessions, {ga4_post['purchases']:,.0f} purchases, ${ga4_post['purchase_revenue']:,.0f} revenue (A8 token hits: {ga4_shopmy_a8_hits_post})"
    )
    if ga4_pre["days"] > 0:
        lines.append(
            f"- GA4 ShopMy baseline (prev window {ga4_pre_start.date().isoformat()} → {ga4_pre_end.date().isoformat()}): {ga4_pre['sessions']:,.0f} sessions, {ga4_pre['purchases']:,.0f} purchases, ${ga4_pre['purchase_revenue']:,.0f} revenue"
        )
    lines.append("")

    lines.append("## Gifts by Product")
    top_products = by_product.head(20).copy()
    if not top_products.empty:
        lines.append("\n| Product | Orders | Gift Value |\n|---|---:|---:|")
        for name, row in top_products.iterrows():
            lines.append(f"| {name} | {int(row['orders'])} | ${row['gift_value_total']:,.0f} |")
    else:
        lines.append("(No gift data)")
    lines.append("")

    lines.append("## Gifts by Channel (with % of Shopify Total Sales)")
    if not by_channel.empty:
        lines.append("\n| Channel | Orders | Gift Value | % of Sales |\n|---|---:|---:|---:|")
        for ch, row in by_channel.iterrows():
            pct = (row['gift_value_total'] / shopify_total_sales * 100.0) if shopify_total_sales > 0 else 0.0
            lines.append(f"| {ch} | {int(row['orders'])} | ${row['gift_value_total']:,.0f} | {pct:.2f}% |")
    else:
        lines.append("(No channel data)")
    lines.append("")

    lines.append("## Gifts by Week (with % of Shopify Total Sales)")
    if not by_week.empty:
        lines.append("\n| Week starting | Gift Value | % of Sales |\n|---|---:|---:|")
        for wk, row in by_week.iterrows():
            pct = (row['gift_value_total'] / shopify_total_sales * 100.0) if shopify_total_sales > 0 else 0.0
            lines.append(f"| {wk.date().isoformat()} | ${row['gift_value_total']:,.0f} | {pct:.2f}% |")
    else:
        lines.append("(No weekly data)")
    lines.append("")

    lines.append("## GA4 ShopMy Traffic Only")
    lines.append("\n| Window | Sessions | Purchases | Revenue | Days |\n|---|---:|---:|---:|---:|")
    lines.append(
        f"| Prev {ga4_pre_start.date().isoformat()} → {ga4_pre_end.date().isoformat()} | {ga4_pre['sessions']:,.0f} | {ga4_pre['purchases']:,.0f} | ${ga4_pre['purchase_revenue']:,.0f} | {int(ga4_pre['days'])} |"
    )
    lines.append(
        f"| Current {ga4_post_start.date().isoformat()} → {ga4_post_end.date().isoformat()} | {ga4_post['sessions']:,.0f} | {ga4_post['purchases']:,.0f} | ${ga4_post['purchase_revenue']:,.0f} | {int(ga4_post['days'])} |"
    )
    lines.append("")
    if shopify_total_sales > 0:
        gifts_pct = a8_totals / shopify_total_sales * 100.0
        lines.append(f"- Gifts as % of Shopify total sales: {gifts_pct:.2f}%")

    # Seeded vs baseline lift section
    lines.append("")
    lines.append("## Seeded Product Revenue Change (Post vs Pre, normalized vs site)")
    if not seeded_lift.empty:
        pre_start = seeded_lift.attrs.get("pre_start")
        pre_end = seeded_lift.attrs.get("pre_end")
        post_start = seeded_lift.attrs.get("post_start")
        post_end = seeded_lift.attrs.get("post_end")
        window_days = seeded_lift.attrs.get("window_days")
        if pd.notna(pre_start) and pd.notna(pre_end) and pd.notna(post_start) and pd.notna(post_end):
            lines.append(
                f"- Windows: Pre {pre_start.date().isoformat()} → {pre_end.date().isoformat()} ({window_days} days) | Post {post_start.date().isoformat()} → {post_end.date().isoformat()} ({window_days} days)"
            )
        # Table header after any notes, with a blank line before
        lines.append("")
        lines.append("| Gift (A8 Lineitem name) | Pre Sales | Post Sales | Abs Change | % Change | vs Site Δ |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for gift_name, row in seeded_lift.iterrows():
            pre = row["pre_sales"]
            post = row["post_sales"]
            abs_ch = row["abs_change"]
            pct = row["pct_change"] * 100.0 if pd.notna(row["pct_change"]) else float("nan")
            norm = row["norm_vs_site"] * 100.0 if pd.notna(row["norm_vs_site"]) else float("nan")
            lines.append(
                f"| {gift_name} | ${pre:,.0f} | ${post:,.0f} | ${abs_ch:,.0f} | {pct:.1f}% | {norm:.1f}% |"
            )
        # Site context footer
        site_pre = seeded_lift.attrs.get("site_pre", float("nan"))
        site_post = seeded_lift.attrs.get("site_post", float("nan"))
        site_growth = seeded_lift.attrs.get("site_growth", float("nan"))
        lines.append("")
        lines.append(
            f"- Site revenue change (Jan–Jun vs since {since.isoformat()}): ${site_pre:,.0f} → ${site_post:,.0f} ({site_growth*100.0:.1f}%)"
        )
        # Footnote / interpretation
        lines.append("")
        lines.append("- Note: 'vs Site Δ' = product % change − site % change over the same window.")
        lines.append("  - Positive = product outperformed overall site trend")
        lines.append("  - Negative = product underperformed vs site")
        lines.append("  - N/A = product had zero pre-window sales (no % change defined)")
    else:
        lines.append("(No seeded product revenue found in Shopify data)")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    a8_path = os.path.join(repo_root, "data/ads/A8 Comps.csv")
    ga4_path = os.path.join(
        repo_root,
        "data/ads/exec-sum/daily-traffic_acquisition_Session_source_medium-2025-01-01-2025-09-27.csv",
    )
    shopify_sales_path = os.path.join(
        repo_root,
        "data/ads/exec-sum/Total sales over time - OU - 2025-01-01 - 2025-09-27.csv",
    )
    shopify_by_product_path = os.path.join(
        repo_root,
        "data/ads/exec-sum/Total sales by product - OU - 2025-01-01 - 2025-09-27.csv",
    )
    out_path = os.path.join(
        repo_root, "data/reports/executive/a8-impact-2025-09-27.md"
    )

    since = date(2025, 7, 1)
    before = date(2025, 1, 1)

    a8_df = load_a8(a8_path, since)
    a8_last = a8_df["created_dt"].max() if not a8_df.empty else pd.NaT

    # For percentage calculations, align gifts to Shopify date range end
    # Use A8 end date as the global cap for all windows
    a8_end = a8_last

    shopify_total_sales, shopify_start, shopify_end = load_shopify_total_sales(
        shopify_sales_path, since, end=a8_end
    )
    if pd.notna(a8_end):
        a8_df_for_pct = a8_df[a8_df["created_dt"] <= a8_end]
    else:
        a8_df_for_pct = a8_df

    by_product, by_channel, by_week = summarize_a8(a8_df_for_pct)
    a8_totals = float(by_product["gift_value_total"].sum()) if not by_product.empty else 0.0
    a8_orders = int(a8_df.shape[0])

    ga4_df = load_ga4(ga4_path)
    # GA4 windows aligned to Shopify sales window
    post_start = pd.Timestamp(since)
    post_end = a8_end if pd.notna(a8_end) else ga4_df["Date"].max()
    window_days = int((post_end.normalize() - post_start.normalize()).days) + 1
    pre_end = post_start - pd.Timedelta(days=1)
    pre_start = pre_end - pd.Timedelta(days=window_days - 1)

    ga4_post, ga4_a8_hits_post = summarize_ga4_shopmy_window(ga4_df, start=post_start, end=post_end)
    ga4_pre, _ = summarize_ga4_shopmy_window(ga4_df, start=pre_start, end=pre_end)

    # Seeded product lift
    shopify_product_sales = load_shopify_sales_by_product(shopify_by_product_path)
    seeded_lift = compute_seeded_product_lift(
        a8_df=a8_df,
        product_sales=shopify_product_sales,
        since=since,
        shopify_end=shopify_end,
    )

    write_report(
        out_path=out_path,
        since=since,
        a8_last=a8_last,
        a8_totals=a8_totals,
        a8_orders=a8_orders,
        by_product=by_product,
        by_channel=by_channel,
        by_week=by_week,
        ga4_pre=ga4_pre,
        ga4_post=ga4_post,
        ga4_shopmy_a8_hits_post=ga4_a8_hits_post,
        ga4_pre_start=pre_start,
        ga4_pre_end=pre_end,
        ga4_post_start=post_start,
        ga4_post_end=post_end,
        shopify_total_sales=shopify_total_sales,
        shopify_start=shopify_start,
        shopify_end=shopify_end,
        seeded_lift=seeded_lift,
    )
    print(f"Wrote report: {out_path}")


if __name__ == "__main__":
    main()


