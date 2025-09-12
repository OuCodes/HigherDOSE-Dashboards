#!/usr/bin/env python3
"""
Q4 2025 Sales Goals – Monthly Projections

Computes monthly projections for Spend, Revenue, Efficiency (ROAS), and Spend vs Revenue %
for Oct–Dec 2025, using:
- Spend: Historical all-channel spend CSV (for 2023/2024 Q4 weighting and 2024 full-year baseline)
- Revenue: Shopify Total sales (for 2023/2024 Q4 weighting, 2024 full-year baseline, and 2025 YTD actuals)

Targets:
- 2025 Spend target = 2024 full-year Spend * 1.05
- 2025 Revenue target = 2024 full-year Revenue * 1.25

Q4 targets = 2025 targets - 2025 YTD actuals (clamped at >= 0). Allocate across Oct/Nov/Dec
using a 50/50 blend of 2023 and 2024 Q4 monthly shares (fallback to 2024-only if 2023 missing).

Outputs:
- data/reports/goals/q4-2025-sales-goals.csv
- data/reports/goals/q4-2025-sales-goals.md
"""

from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import csv

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
PLANNING_DIR = ROOT / "data" / "ads" / "q4-planning-2025"
SHOPIFY_DIR = PLANNING_DIR / "shopify"
OUTPUT_DIR = ROOT / "data" / "reports" / "goals"


Q4_MONTHS = ["2024-10", "2024-11", "2024-12"]
Q4_2025_MONTHS = ["2025-10", "2025-11", "2025-12"]


@dataclass
class SalesGoalsRow:
	month: str
	spend_target: float
	revenue_target: float
	roas_target: float
	spend_to_rev_pct: float


def _coerce_currency(val: str | float | int) -> float:
	if isinstance(val, (int, float)):
		return float(val)
	s = str(val)
	if s.strip() == "–":
		return 0.0
	s = s.replace("$", "").replace(",", "").strip()
	try:
		return float(s)
	except Exception:
		return 0.0


def _month_to_yyyy_mm(token: str) -> Optional[str]:
	"""Convert values like 'Oct-24' -> '2024-10'. Fallback to pandas if needed."""
	try:
		dt = pd.to_datetime(token, format="%b-%y", errors="coerce")
		if pd.isna(dt):
			dt = pd.to_datetime(token, errors="coerce")
		if pd.isna(dt):
			return None
		return f"{dt.year}-{dt.month:02d}"
	except Exception:
		return None


def parse_historical_total_spend(csv_path: Path) -> pd.DataFrame:
	"""Robustly parse 'Historical Spend - Historical Spend.csv' picking the first field as Month and the last field as Total Spend.
	Handles unusual multi-line header by using csv.reader over all lines and selecting rows matching month tokens like 'Oct-23'.
	Returns dataframe with columns: month (YYYY-MM), total_spend.
	"""
	rows: List[Dict[str, str | float]] = []
	if not csv_path.exists():
		return pd.DataFrame(columns=["month", "total_spend"])  # empty
	with csv_path.open("r", newline="") as f:
		reader = csv.reader(f)
		for parts in reader:
			if not parts:
				continue
			first = parts[0].strip() if parts else ""
			# Month rows look like 'Oct-24' etc
			if len(first) >= 6 and first[3] == "-":
				mon = _month_to_yyyy_mm(first)
				if not mon:
					continue
				val = parts[-1] if parts else "0"
				rows.append({"month": mon, "total_spend": _coerce_currency(val)})
	return pd.DataFrame(rows)


def _read_shopify_daily(path: Path) -> Optional[pd.DataFrame]:
	if not path.exists():
		return None
	try:
		df = pd.read_csv(path)
		# Normalize
		if "Day" not in df.columns or "Total sales" not in df.columns:
			return None
		df = df.copy()
		df["Day"] = pd.to_datetime(df["Day"], errors="coerce")
		df = df.dropna(subset=["Day"])  # keep valid days
		return df
	except Exception:
		return None


def monthly_sum_from_daily(df: pd.DataFrame) -> pd.DataFrame:
	work = df.copy()
	work["month"] = work["Day"].dt.strftime("%Y-%m")
	agg = work.groupby("month")["Total sales"].sum().reset_index().rename(columns={"Total sales": "revenue"})
	return agg


def q4_monthly_shares(series_df: pd.DataFrame, value_col: str = "revenue", year: int = 2024) -> pd.Series:
	"""Compute Oct/Nov/Dec shares for the given year from a dataframe with columns ['month', value_col]."""
	want = [f"{year}-10", f"{year}-11", f"{year}-12"]
	q4 = series_df[series_df["month"].isin(want)] if not series_df.empty else pd.DataFrame(columns=["month", value_col])
	if q4.empty:
		return pd.Series({f"{year}-10": 0.0, f"{year}-11": 0.0, f"{year}-12": 0.0})
	total = float(q4[value_col].sum())
	if total <= 0:
		return pd.Series({f"{year}-10": 0.0, f"{year}-11": 0.0, f"{year}-12": 0.0})
	shares = q4.set_index("month")[value_col] / total
	return shares.reindex(want).fillna(0.0)


def blend_shares(sh_2023: pd.Series, sh_2024: pd.Series) -> pd.Series:
	if sh_2023 is None or sh_2023.sum() == 0:
		return sh_2024
	if sh_2024 is None or sh_2024.sum() == 0:
		return sh_2023
	out = (sh_2023.fillna(0.0) + sh_2024.fillna(0.0)) / 2.0
	# Normalize to 1.0 in case of rounding
	return out / max(out.sum(), 1e-9)


def compute_full_year_baselines(hspend_df: pd.DataFrame, shopify_2024_full: pd.DataFrame) -> Tuple[float, float]:
	"""Return (spend_2024_total, revenue_2024_total)."""
	spend_2024 = float(hspend_df[hspend_df["month"].str.startswith("2024-")]["total_spend"].sum()) if not hspend_df.empty else 0.0
	rev_2024 = float(shopify_2024_full["Total sales"].sum()) if not shopify_2024_full.empty else 0.0
	return spend_2024, rev_2024


def compute_2025_ytd(hspend_df: pd.DataFrame, shopify_2025_daily: pd.DataFrame) -> Tuple[float, float]:
	"""Return (spend_2025_ytd, revenue_2025_ytd)."""
	spend_2025 = float(hspend_df[hspend_df["month"].str.startswith("2025-")]["total_spend"].sum()) if not hspend_df.empty else 0.0
	rev_2025 = float(shopify_2025_daily["Total sales"].sum()) if shopify_2025_daily is not None and not shopify_2025_daily.empty else 0.0
	return spend_2025, rev_2025


def project_q4_2025_rows(spend_q4_target: float, rev_q4_target: float, spend_shares: pd.Series, rev_shares: pd.Series) -> List[SalesGoalsRow]:
	rows: List[SalesGoalsRow] = []
	for ym, next_month in zip(["2025-10", "2025-11", "2025-12"], ["2025-11", "2025-12", None]):
		# Map shares by equivalent month from 2023/2024 share indices
		ym_2024 = ym.replace("2025", "2024")
		spend_weight = float(spend_shares.get(ym_2024, 0.0))
		rev_weight = float(rev_shares.get(ym_2024, 0.0))
		spend_m = spend_q4_target * spend_weight
		rev_m = rev_q4_target * rev_weight
		roas_m = (rev_m / spend_m) if spend_m > 0 else 0.0
		spend_to_rev = (spend_m / rev_m) if rev_m > 0 else 0.0
		rows.append(SalesGoalsRow(month=ym, spend_target=spend_m, revenue_target=rev_m, roas_target=roas_m, spend_to_rev_pct=spend_to_rev))
	return rows


def write_outputs(rows: List[SalesGoalsRow], context: Dict[str, float]) -> Tuple[Path, Path]:
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
	csv_path = OUTPUT_DIR / "q4-2025-sales-goals.csv"
	md_path = OUTPUT_DIR / "q4-2025-sales-goals.md"

	# CSV
	df = pd.DataFrame([{
		"month": r.month,
		"spend_target": r.spend_target,
		"revenue_target": r.revenue_target,
		"roas_target": r.roas_target,
		"spend_to_rev_pct": r.spend_to_rev_pct,
	} for r in rows])
	df.to_csv(csv_path, index=False)

	# Markdown
	def usd(x: float) -> str:
		return f"${x:,.0f}"
	def pct(x: float) -> str:
		return f"{x*100:.1f}%"

	lines: List[str] = []
	lines.append("## Q4 2025 Sales Goals – Monthly Projections")
	lines.append("")
	lines.append("Assumptions:")
	lines.append("- 2025 Spend target: 2024 Spend × 1.05")
	lines.append("- 2025 Revenue target: 2024 Revenue × 1.25")
	lines.append("- Q4 targets = 2025 targets − 2025 YTD actuals; allocated using blended 2023/2024 Q4 monthly shares")
	lines.append("")
	lines.append("Baseline and YTD:")
	lines.append(f"- 2024 Spend (full-year): {usd(context['spend_2024'])}")
	lines.append(f"- 2024 Revenue (full-year): {usd(context['rev_2024'])}")
	lines.append(f"- 2025 YTD Spend: {usd(context['spend_2025_ytd'])}")
	lines.append(f"- 2025 YTD Revenue: {usd(context['rev_2025_ytd'])}")
	lines.append("")
	lines.append("Targets:")
	lines.append(f"- 2025 Spend target (full-year): {usd(context['spend_2025_target'])}")
	lines.append(f"- 2025 Revenue target (full-year): {usd(context['rev_2025_target'])}")
	lines.append(f"- Q4 Spend to allocate: {usd(context['spend_q4_target'])}")
	lines.append(f"- Q4 Revenue to allocate: {usd(context['rev_q4_target'])}")
	lines.append("")
	lines.append("Monthly projections:")
	lines.append("")
	lines.append("Month | Spend | Revenue | ROAS | Spend/Rev %")
	lines.append("---|---:|---:|---:|---:")
	for r in rows:
		lines.append(f"{r.month} | {usd(r.spend_target)} | {usd(r.revenue_target)} | {r.roas_target:.2f}x | {pct(r.spend_to_rev_pct)}")
	lines.append("")
	# Totals and implied efficiency
	sp_tot = sum(r.spend_target for r in rows)
	rev_tot = sum(r.revenue_target for r in rows)
	roas_q4 = (rev_tot / sp_tot) if sp_tot > 0 else 0.0
	lines.append(f"Q4 Total | {usd(sp_tot)} | {usd(rev_tot)} | {roas_q4:.2f}x | {pct(sp_tot / rev_tot if rev_tot else 0.0)}")
	lines.append("")
	md_path.write_text("\n".join(lines))
	return csv_path, md_path


def main() -> Tuple[Path, Path]:
	# Parse historical total spend for all months
	hist_path = PLANNING_DIR / "Historical Spend - Historical Spend.csv"
	hspend_df = parse_historical_total_spend(hist_path)

	# Shopify – load 2024 full-year daily and Q4 daily
	shopify_2024_full_path = SHOPIFY_DIR / "Total sales over time - 01-01-2024-12-31-2024.csv"
	shopify_2024_full = _read_shopify_daily(shopify_2024_full_path) or pd.DataFrame()
	shopify_2024_q4_path = SHOPIFY_DIR / "total-sales-over-time-2024Q4.csv"
	shopify_2024_q4 = _read_shopify_daily(shopify_2024_q4_path) or pd.DataFrame()

	# Shopify – load 2023 Q4 daily if present
	shopify_2023_q4_path = SHOPIFY_DIR / "total-sales-over-time-2023Q4.csv"
	shopify_2023_q4 = _read_shopify_daily(shopify_2023_q4_path) or pd.DataFrame()

	# Shopify – 2025 YTD (OU file)
	shopify_2025_ytd_path = SHOPIFY_DIR / "Total sales over time - OU - 2025-01-01 - 2025-09-02 .csv"
	shopify_2025_ytd = _read_shopify_daily(shopify_2025_ytd_path) or pd.DataFrame()

	# Baselines
	spend_2024, rev_2024 = compute_full_year_baselines(hspend_df, shopify_2024_full)
	spend_2025_ytd, rev_2025_ytd = compute_2025_ytd(hspend_df, shopify_2025_ytd)

	# Targets
	spend_2025_target = spend_2024 * 1.05
	rev_2025_target = rev_2024 * 1.25
	spend_q4_target = max(spend_2025_target - spend_2025_ytd, 0.0)
	rev_q4_target = max(rev_2025_target - rev_2025_ytd, 0.0)

	# Spend weights (Q4 shares) from historical spend 2023/2024
	spend_monthly = hspend_df.copy()
	spend_2023_shares = (
		spend_monthly[spend_monthly["month"].isin(["2023-10", "2023-11", "2023-12"])][["month", "total_spend"]]
		.rename(columns={"total_spend": "spend"})
	)
	spend_2024_shares = (
		spend_monthly[spend_monthly["month"].isin(["2024-10", "2024-11", "2024-12"])][["month", "total_spend"]]
		.rename(columns={"total_spend": "spend"})
	)
	sp_sh_2023 = q4_monthly_shares(spend_2023_shares, value_col="spend", year=2023)
	sp_sh_2024 = q4_monthly_shares(spend_2024_shares, value_col="spend", year=2024)
	spend_shares = blend_shares(sp_sh_2023, sp_sh_2024)

	# Revenue weights from Shopify 2023/2024 Q4 daily
	rev_2023_q4_m = monthly_sum_from_daily(shopify_2023_q4) if not shopify_2023_q4.empty else pd.DataFrame(columns=["month", "revenue"])
	rev_2024_q4_m = monthly_sum_from_daily(shopify_2024_q4) if not shopify_2024_q4.empty else pd.DataFrame(columns=["month", "revenue"])
	rev_sh_2023 = q4_monthly_shares(rev_2023_q4_m, value_col="revenue", year=2023)
	rev_sh_2024 = q4_monthly_shares(rev_2024_q4_m, value_col="revenue", year=2024)
	rev_shares = blend_shares(rev_sh_2023, rev_sh_2024)

	# Projections
	rows = project_q4_2025_rows(spend_q4_target, rev_q4_target, spend_shares, rev_shares)

	csv_path, md_path = write_outputs(rows, context={
		"spend_2024": spend_2024,
		"rev_2024": rev_2024,
		"spend_2025_ytd": spend_2025_ytd,
		"rev_2025_ytd": rev_2025_ytd,
		"spend_2025_target": spend_2025_target,
		"rev_2025_target": rev_2025_target,
		"spend_q4_target": spend_q4_target,
		"rev_q4_target": rev_q4_target,
	})
	return csv_path, md_path


if __name__ == "__main__":
	main() 