#!/usr/bin/env python3
"""
Daily Budget Tracker

Generates a daily plan vs actuals tracker for a given month:
- Inputs: total monthly revenue target, total monthly spend budget, channel mix %, Shopify daily (for historical day-of-week/day-of-month shares), Northbeam daily (for actuals spend and attributed revenue)
- Outputs: CSV with per-day planned revenue, planned spend, planned MER; actual spend/revenue; variances; channel daily budgets from mix

Usage:
  python -m growthkit.reports.budget_tracker --month 2025-11 \
      --rev-target 3000000 --spend-budget 1200000 \
      --mix "Meta=0.45,Google=0.40,Affiliates=0.05,Amazon=0.10"

Data discovery:
- Shopify daily CSVs typically under data/ads/q4-planning-2025/shopify or data/ads
- Northbeam daily exports under data/ads (new_ytd_sales_data-*.csv or similar)

This module is intentionally light-weight and file-driven; no API calls required.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple
import argparse
import calendar
import csv
from datetime import date, datetime

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
ADS_DIR = ROOT / "data" / "ads"
REPORTS_DIR = ROOT / "data" / "reports" / "weekly"


@dataclass
class Inputs:
    month: str                 # YYYY-MM
    rev_target: float          # total revenue target for the month
    spend_budget: float        # total spend budget for the month
    mix: Dict[str, float]      # channel -> share (0..1, should sum ~1)
    shopify_daily: Optional[pd.DataFrame]
    northbeam_daily: Optional[pd.DataFrame]


def parse_mix(mix_arg: str | None) -> Dict[str, float]:
    if not mix_arg:
        return {}
    parts = [p.strip() for p in mix_arg.split(',') if p.strip()]
    res: Dict[str, float] = {}
    for p in parts:
        if '=' not in p:
            continue
        k, v = p.split('=', 1)
        try:
            res[k.strip()] = float(v)
        except Exception:
            continue
    # Normalize to sum=1 when possible
    s = sum(res.values())
    if s > 0:
        res = {k: v / s for k, v in res.items()}
    return res


def read_shopify_daily_default() -> Optional[pd.DataFrame]:
    # Try common locations used in sales_goals.py
    candidates = [
        ROOT / "data" / "ads" / "q4-planning-2025" / "shopify" / "Total sales over time - 01-01-2024-12-31-2024.csv",
        ROOT / "data" / "ads" / "q4-planning-2025" / "shopify" / "Total sales over time - OU - 2025-01-01 - 2025-09-02 .csv",
    ]
    for p in candidates:
        if p.exists():
            try:
                df = pd.read_csv(p)
                return df
            except Exception:
                continue
    # Fallback: any Shopify-like export in data/ads
    for p in sorted((ADS_DIR).glob("*.csv")):
        if "Total sales" in (p.name or ""):
            try:
                return pd.read_csv(p)
            except Exception:
                pass
    return None


def read_northbeam_daily_default() -> Optional[pd.DataFrame]:
    # Prefer YTD export with a date column (scripts/northbeam_sync_ytd.py --daily)
    cands = sorted(ADS_DIR.glob("new_ytd_sales_data-higher_dose_llc-*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        cands = sorted(ADS_DIR.glob("*ytd*sales_data*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cands:
        cands = sorted(ADS_DIR.glob("*ad+platform*date*breakdown*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in cands:
        try:
            return pd.read_csv(p)
        except Exception:
            continue
    return None


def month_dates(yyyy_mm: str) -> list[date]:
    y, m = [int(x) for x in yyyy_mm.split('-')]
    _, ndays = calendar.monthrange(y, m)
    return [date(y, m, d) for d in range(1, ndays + 1)]


def compute_day_of_month_shares(shopify_df: Optional[pd.DataFrame], yyyy_mm: str) -> Dict[date, float]:
    # If Shopify daily provided and contains 'Day' and 'Total sales', compute distribution for that month
    try:
        if shopify_df is not None and not shopify_df.empty and 'Day' in shopify_df.columns:
            df = shopify_df.copy()
            df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
            df = df.dropna(subset=['Day'])
            df['yyyy_mm'] = df['Day'].dt.strftime('%Y-%m')
            df['day'] = df['Day'].dt.date
            if 'Total sales' in df.columns:
                mdf = df[df['yyyy_mm'] == yyyy_mm]
                sub = pd.to_numeric(mdf['Total sales'], errors='coerce').fillna(0.0)
                tot = float(sub.sum())
                if tot > 0:
                    shares: Dict[date, float] = {}
                    for _, r in mdf[['day', 'Total sales']].iterrows():
                        shares[r['day']] = float(pd.to_numeric(pd.Series([r['Total sales']]), errors='coerce').fillna(0.0).iloc[0]) / tot
                    # Normalize exactly to 1.0
                    s = sum(shares.values()) or 1.0
                    return {k: v / s for k, v in shares.items()}
    except Exception:
        pass
    # Fallback: equal shares across the month
    days = month_dates(yyyy_mm)
    w = 1.0 / max(1, len(days))
    return {d: w for d in days}


def build_planned_daily(inputs: Inputs) -> pd.DataFrame:
    days = month_dates(inputs.month)
    shares = compute_day_of_month_shares(inputs.shopify_daily, inputs.month)
    # Align shares to all days (fill missing with 0, then renormalize)
    shares_vec = [float(shares.get(d, 0.0)) for d in days]
    s = sum(shares_vec)
    if s <= 0:
        shares_vec = [1.0 / len(days)] * len(days)
    else:
        shares_vec = [v / s for v in shares_vec]
    plan_rev = [inputs.rev_target * v for v in shares_vec]
    plan_sp = [inputs.spend_budget * v for v in shares_vec]
    plan_mer = [ (r / s) if s > 0 else 0.0 for r, s in zip(plan_rev, plan_sp) ]

    # Channel daily budgets from mix
    channels = list(inputs.mix.keys())
    ch_cols = [f"plan_spend_{c}" for c in channels]
    ch_daily = [[sv * inputs.mix[c] for c in channels] for sv in plan_sp]

    df = pd.DataFrame({
        'date': days,
        'plan_revenue': plan_rev,
        'plan_spend': plan_sp,
        'plan_mer': plan_mer,
    })
    for i, col in enumerate(ch_cols):
        df[col] = [row[i] for row in ch_daily]
    return df


def attach_actuals(df: pd.DataFrame, nb_df: Optional[pd.DataFrame]) -> pd.DataFrame:
    if nb_df is None or nb_df.empty:
        df['actual_spend'] = 0.0
        df['actual_revenue'] = 0.0
        df['actual_mer'] = 0.0
        return df
    # Try to detect columns: either there is a 'date' column prefixed from scripts/northbeam_sync_ytd.py --daily, or a 'Day'
    nbd = nb_df.copy()
    date_col: Optional[str] = None
    for c in ['date', 'Day', 'day', 'Date']:
        if c in nbd.columns:
            date_col = c
            break
    if date_col is None:
        df['actual_spend'] = 0.0
        df['actual_revenue'] = 0.0
        df['actual_mer'] = 0.0
        return df
    # Normalize date
    nbd['_d'] = pd.to_datetime(nbd[date_col], errors='coerce').dt.date
    # Spend / revenue columns vary; reuse mapping logic similar to weekly report
    col_map = {}
    for col in nbd.columns:
        low = str(col).strip().lower()
        if low in {"spend", "cost"}:
            col_map[col] = "spend"
        elif low in {"attributed_rev", "attributed_revenue", "revenue", "total_revenue"}:
            col_map[col] = "revenue"
    if col_map:
        nbd = nbd.rename(columns=col_map)
    spend_col = 'spend' if 'spend' in nbd.columns else None
    rev_col = 'revenue' if 'revenue' in nbd.columns else None
    if spend_col is None and rev_col is None:
        df['actual_spend'] = 0.0
        df['actual_revenue'] = 0.0
        df['actual_mer'] = 0.0
        return df
    grp = nbd.groupby('_d').agg({spend_col or 'spend': 'sum', rev_col or 'revenue': 'sum'})
    grp = grp.rename(columns={spend_col or 'spend': 'actual_spend', rev_col or 'revenue': 'actual_revenue'})
    df = df.merge(grp, how='left', left_on='date', right_index=True)
    df['actual_spend'] = df['actual_spend'].fillna(0.0)
    df['actual_revenue'] = df['actual_revenue'].fillna(0.0)
    df['actual_mer'] = df.apply(lambda r: (r['actual_revenue'] / r['actual_spend']) if r['actual_spend'] > 0 else 0.0, axis=1)
    return df


def add_variances(df: pd.DataFrame) -> pd.DataFrame:
    df['var_revenue'] = df['actual_revenue'] - df['plan_revenue']
    df['var_spend'] = df['actual_spend'] - df['plan_spend']
    df['var_mer'] = df['actual_mer'] - df['plan_mer']
    # Cumulative pacing
    df['cum_plan_rev'] = df['plan_revenue'].cumsum()
    df['cum_plan_spend'] = df['plan_spend'].cumsum()
    df['cum_act_rev'] = df['actual_revenue'].cumsum()
    df['cum_act_spend'] = df['actual_spend'].cumsum()
    df['cum_plan_mer'] = df.apply(lambda r: (r['cum_plan_rev'] / r['cum_plan_spend']) if r['cum_plan_spend'] > 0 else 0.0, axis=1)
    df['cum_act_mer'] = df.apply(lambda r: (r['cum_act_rev'] / r['cum_act_spend']) if r['cum_act_spend'] > 0 else 0.0, axis=1)
    df['cum_var_rev'] = df['cum_act_rev'] - df['cum_plan_rev']
    df['cum_var_spend'] = df['cum_act_spend'] - df['cum_plan_spend']
    return df


def write_csv(df: pd.DataFrame, month: str) -> Path:
    out_dir = REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"budget-tracker-{month}.csv"
    # Format for Excel friendliness
    df2 = df.copy()
    df2['date'] = df2['date'].astype(str)
    df2.to_csv(out_path, index=False)
    return out_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Daily Budget Tracker')
    p.add_argument('--month', required=True, help='Month in YYYY-MM')
    p.add_argument('--rev-target', type=float, required=True, help='Total monthly revenue target')
    p.add_argument('--spend-budget', type=float, required=True, help='Total monthly spend budget')
    p.add_argument('--mix', default='', help='Channel mix like "Meta=0.45,Google=0.40,Affiliates=0.05,Amazon=0.10"')
    p.add_argument('--shopify-csv', default='', help='Optional explicit Shopify daily CSV path')
    p.add_argument('--northbeam-csv', default='', help='Optional explicit Northbeam daily CSV path')
    return p.parse_args(argv)


def load_inputs(ns: argparse.Namespace) -> Inputs:
    shopify_df = None
    if ns.shopify_csv:
        p = Path(ns.shopify_csv)
        if p.exists():
            try:
                shopify_df = pd.read_csv(p)
            except Exception:
                shopify_df = None
    if shopify_df is None:
        shopify_df = read_shopify_daily_default()

    nb_df = None
    if ns.northbeam_csv:
        p = Path(ns.northbeam_csv)
        if p.exists():
            try:
                nb_df = pd.read_csv(p)
            except Exception:
                nb_df = None
    if nb_df is None:
        nb_df = read_northbeam_daily_default()

    return Inputs(
        month=str(ns.month),
        rev_target=float(ns.rev_target or 0.0),
        spend_budget=float(ns.spend_budget or 0.0),
        mix=parse_mix(ns.mix),
        shopify_daily=shopify_df,
        northbeam_daily=nb_df,
    )


def main(argv: list[str] | None = None) -> int:
    ns = parse_args(argv)
    inp = load_inputs(ns)
    if inp.rev_target <= 0 or inp.spend_budget <= 0:
        raise SystemExit('--rev-target and --spend-budget must be > 0')
    if not inp.mix:
        # Provide a sensible default mix if not supplied
        inp.mix = {'Meta': 0.5, 'Google': 0.4, 'Other': 0.1}

    plan = build_planned_daily(inp)
    with_actuals = attach_actuals(plan, inp.northbeam_daily)
    final = add_variances(with_actuals)
    out_path = write_csv(final, inp.month)
    print(f"Wrote {out_path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())



