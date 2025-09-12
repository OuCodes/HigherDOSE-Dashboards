#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

# Local imports
from growthkit.reports import product_data


DEFAULT_INPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "ads"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "ads" / "q4-planning-2025" / "ads"


@dataclass
class Inputs:
    northbeam_csv: Path
    output_dir: Path


def _normalize_text(s: str) -> str:
    import re

    # Insert spaces before CamelCase transitions
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    s = s.replace("_", " ").replace("-", " ")
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _build_alias_map() -> list[tuple[str, str]]:
    # Base alias map from product_data
    alias_map = {_normalize_text(k): v for k, v in product_data.ALIASES.items()}
    # Ensure canonical names map to themselves
    for prod in product_data.PRODUCT_TO_CATEGORY.keys():
        alias_map.setdefault(_normalize_text(prod), prod)
    # Expand nospace variants
    expanded: dict[str, str] = {}
    for key, val in alias_map.items():
        expanded[key] = val
        nospace = key.replace(" ", "")
        if nospace != key:
            expanded.setdefault(nospace, val)
    # Sort longest-first for greedy matching
    return sorted(expanded.items(), key=lambda kv: len(kv[0]), reverse=True)


def _detect_product(row: pd.Series, alias_sorted: list[tuple[str, str]]) -> Optional[str]:
    fields = ("ad_name", "adset_name", "campaign_name")
    text_norm_joined = []
    for field in fields:
        text = str(row.get(field, ""))
        if not text:
            continue
        norm = _normalize_text(text)
        text_norm_joined.append(norm)
        text_norm_joined.append(norm.replace(" ", ""))
    if not text_norm_joined:
        return None
    for alias, canonical in alias_sorted:
        for t in text_norm_joined:
            if alias and alias in t:
                return canonical
    return None


def _load_northbeam(path: Path) -> pd.DataFrame:
    # Avoid memory blowups
    df = pd.read_csv(path, low_memory=False)

    # Minimal numeric cast best-effort
    numeric_cols = [
        "spend",
        "attributed_rev",
        "attributed_rev_1st_time",
        "transactions",
        "transactions_1st_time",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.fillna(0)

    # Ensure platform col exists for compatibility
    if "breakdown_platform_northbeam" not in df.columns:
        df["breakdown_platform_northbeam"] = df.get("platform", "Unknown")

    return df


def _assign_products(df: pd.DataFrame, alias_sorted: list[tuple[str, str]]) -> pd.DataFrame:
    df = df.copy()
    df["product"] = df.apply(lambda r: _detect_product(r, alias_sorted), axis=1)
    # Bucket unmatched
    df["product"] = df["product"].fillna("Unattributed")
    return df


def _summarize(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    present = [
        c
        for c in [
            "spend",
            "attributed_rev",
            "attributed_rev_1st_time",
            "transactions",
            "transactions_1st_time",
        ]
        if c in df.columns
    ]
    if not present:
        return pd.DataFrame()
    summary = df.groupby(group_col)[present].sum().astype(float)
    # Derived metrics
    txns = summary.get("transactions", pd.Series(dtype=float)).round()
    with pd.option_context("mode.use_inf_as_na", True):
        if "spend" in summary.columns and "attributed_rev" in summary.columns:
            summary["roas"] = (summary["attributed_rev"] / summary["spend"]).fillna(0)
        if "spend" in summary.columns and "transactions" in summary.columns:
            summary["cac"] = (summary["spend"] / txns.replace(0, pd.NA)).fillna(0)
        if "attributed_rev" in summary.columns and "transactions" in summary.columns:
            summary["aov"] = (summary["attributed_rev"] / txns.replace(0, pd.NA)).fillna(0)
    summary = summary.round(2).sort_values("spend", ascending=False)
    return summary


def _save_outputs(df_prod: pd.DataFrame, df_cat: pd.DataFrame, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_prod = out_dir / "northbeam_spend_by_product.csv"
    csv_cat = out_dir / "northbeam_spend_by_category.csv"
    df_prod.to_csv(csv_prod)
    df_cat.to_csv(csv_cat)

    # Minimal Markdown summary
    md_path = out_dir / "northbeam_spend_summary.md"
    lines = ["# Northbeam Spend Summary by Product\n"]
    lines.append("\n## Top Products by Spend\n")
    top_prod = df_prod.head(20).reset_index()
    for _, r in top_prod.iterrows():
        lines.append(
            f"- {r['product']}: ${r.get('spend', 0):,.0f} | ROAS {r.get('roas', 0):.2f} | CAC ${r.get('cac', 0):,.0f}"
        )
    lines.append("\n## Categories by Spend\n")
    top_cat = df_cat.reset_index()
    for _, r in top_cat.iterrows():
        lines.append(
            f"- {r['category']}: ${r.get('spend', 0):,.0f} | ROAS {r.get('roas', 0):.2f} | CAC ${r.get('cac', 0):,.0f}"
        )
    md_path.write_text("\n".join(lines))

    return csv_prod, csv_cat


def _attach_categories(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["category"] = df["product"].map(product_data.PRODUCT_TO_CATEGORY).fillna("Unattributed")
    return df


def _find_latest_ytd_csv(base_dir: Path) -> Optional[Path]:
    # Prefer YTD Northbeam exports
    candidates = sorted(
        base_dir.glob("ytd-sales_data-*.csv*"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    return candidates[0] if candidates else None


def parse_args(argv: list[str]) -> Inputs:
    parser = argparse.ArgumentParser(description="Aggregate Northbeam spend by product")
    parser.add_argument("--northbeam_csv", type=str, default=None, help="Path to Northbeam YTD CSV")
    parser.add_argument(
        "--output_dir",
        type=str,
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory to write outputs",
    )
    args = parser.parse_args(argv)

    nb_path: Optional[Path]
    if args.northbeam_csv:
        nb_path = Path(args.northbeam_csv)
    else:
        nb_path = _find_latest_ytd_csv(DEFAULT_INPUT_DIR)
    if not nb_path or not nb_path.exists():
        raise FileNotFoundError("Could not find Northbeam YTD CSV. Pass --northbeam_csv explicitly.")

    return Inputs(northbeam_csv=nb_path, output_dir=Path(args.output_dir))


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    inputs = parse_args(argv)

    alias_sorted = _build_alias_map()
    df = _load_northbeam(inputs.northbeam_csv)
    df = _assign_products(df, alias_sorted)
    df_prod = _summarize(df, "product").reset_index()
    df_with_cat = _attach_categories(df_prod)
    df_cat = _summarize(_attach_categories(df), "category").reset_index()

    prod_csv, cat_csv = _save_outputs(df_with_cat, df_cat, inputs.output_dir)

    print(f"Wrote product summary: {prod_csv}")
    print(f"Wrote category summary: {cat_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main()) 