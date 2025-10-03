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
import os

import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
PLANNING_DIR = ROOT / "data" / "ads" / "q4-planning-2025"
SHOPIFY_DIR = PLANNING_DIR / "shopify"
OUTPUT_DIR = ROOT / "data" / "reports" / "goals"


def _latest_shopify_ou_2025() -> Optional[Path]:
	import glob
	candidates = [Path(p) for p in glob.glob(str(SHOPIFY_DIR / "Total sales over time - OU - 2025*.csv"))]
	if not candidates:
		return None
	# Choose by content: parse date column and pick file with max date
	best: tuple[pd.Timestamp, Path] | None = None
	for path in candidates:
		try:
			df = pd.read_csv(path)
			cols = {c.lower().strip(): c for c in df.columns}
			date_col = None
			for k in ["day", "date", "month"]:
				if k in cols:
					date_col = cols[k]
					break
			if date_col is None:
				continue
			df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
			mx = pd.to_datetime(df[date_col]).max()
			if pd.isna(mx):
				continue
			if best is None or mx > best[0]:
				best = (mx, path)
		except Exception:
			continue
	if best:
		return best[1]
	# Fallback to newest by mtime if parsing failed
	candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
	return candidates[0]


def _shopify_cutoff_from(df: Optional[pd.DataFrame], path: Optional[Path]) -> Optional[str]:
	"""Return cutoff date string from Shopify OU file content and filename; prefer the later of the two."""
	content_dt: Optional[pd.Timestamp] = None
	try:
		if df is not None and not df.empty:
			for cand in ["Day", "Date", "Month"]:
				if cand in df.columns:
					ser = pd.to_datetime(df[cand], errors="coerce")
					mx = ser.max()
					if pd.notna(mx):
						content_dt = pd.to_datetime(mx)
						break
	except Exception:
		pass
	file_dt: Optional[pd.Timestamp] = None
	try:
		if path is not None:
			name = path.name
			import re
			dates = re.findall(r"\d{4}-\d{2}-\d{2}", name)
			if dates:
				file_dt = pd.to_datetime(dates[-1], errors="coerce")
	except Exception:
		pass
	# Choose the later valid date
	candidates: list[pd.Timestamp] = []
	if content_dt is not None and pd.notna(content_dt):
		candidates.append(content_dt)
	if file_dt is not None and pd.notna(file_dt):
		candidates.append(file_dt)
	if not candidates:
		return None
	return str(max(candidates).date())


def _latest_northbeam_csv_path() -> Optional[Path]:
	import glob
	candidates: List[str] = []
	candidates.extend(glob.glob(str(PLANNING_DIR / "northbeam" / "**" / "*.csv"), recursive=True))
	candidates.extend(glob.glob(str(ROOT / "data" / "ads" / "**" / "northbeam" / "*.csv"), recursive=True))
	# Also include top-level YTD exports under data/ads: prefer canonical ytd naming, then legacy new_ytd_*
	candidates.extend(glob.glob(str(ROOT / "data" / "ads" / "ytd_sales_data-higher_dose_llc-*.csv")))
	candidates.extend(glob.glob(str(ROOT / "data" / "ads" / "new_ytd_*sales_data*.csv")))
	candidates.extend(glob.glob(str(ROOT / "data" / "ads" / "*sales_data*.csv")))
	if not candidates:
		return None
	candidates.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
	return Path(candidates[0])


def _northbeam_df_filtered(mode_env: Optional[str] = None) -> Optional[pd.DataFrame]:
	"""Load latest Northbeam CSV and return a DataFrame with columns ['date','spend_num'] filtered by accounting_mode."""
	path = _latest_northbeam_csv_path()
	if not path or not path.exists():
		return None
	try:
		df = pd.read_csv(path, low_memory=False)
		if 'date' not in df.columns or 'spend' not in df.columns:
			return None
		df = df.copy()
		df['date'] = pd.to_datetime(df['date'], errors='coerce')
		mode = (mode_env or os.getenv('NORTHBEAM_ACCOUNTING_MODE', 'Cash snapshot')).strip().lower()
		if 'accounting_mode' in df.columns and mode:
			mask = df['accounting_mode'].astype(str).str.lower().str.strip() == mode
			if mask.any():
				df = df[mask]
		df['spend_num'] = pd.to_numeric(df['spend'], errors='coerce').fillna(0.0)
		return df[['date','spend_num']]
	except Exception:
		return None


def _northbeam_ytd_spend(df_nb: pd.DataFrame, year: int, cutoff: pd.Timestamp) -> float:
	"""Sum Northbeam spend for a given year up to cutoff date (inclusive)."""
	if df_nb is None or df_nb.empty:
		return 0.0
	mask = (df_nb['date'].dt.year == year) & (df_nb['date'] <= cutoff)
	return float(df_nb.loc[mask, 'spend_num'].sum())


Q4_MONTHS = ["2024-10", "2024-11", "2024-12"]
Q4_2025_MONTHS = ["2025-10", "2025-11", "2025-12"]


@dataclass
class SalesGoalsRow:
	month: str
	spend_target: float
	revenue_target: float
	roas_target: float
	spend_to_rev_pct: float
	# 2024 actuals
	spend_2024: float = 0.0
	revenue_2024: float = 0.0
	roas_2024: float = 0.0
	spend_to_rev_pct_2024: float = 0.0
	# deltas
	spend_delta_pct: float = 0.0
	revenue_delta_pct: float = 0.0
	roas_delta_pct: float = 0.0
	spend_to_rev_delta_pct: float = 0.0


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
		cols = set(df.columns)
		if "Total sales" not in cols:
			return None
		# Accept Day or Date or Month as a date-like column; prefer Day
		date_col = None
		for c in ["Day", "Date", "Month"]:
			if c in cols:
				date_col = c
				break
		if date_col is None:
			return None
		df = df.copy()
		df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
		df = df.dropna(subset=[date_col])
		# Standardize to Day for downstream when available
		if "Day" not in df.columns:
			df = df.rename(columns={date_col: "Day"})
		return df
	except Exception:
		return None


def _sum_shopify_total_sales(path: Path) -> float:
	"""Sum 'Total sales' from any Shopify export (daily or monthly)."""
	df = _read_shopify_daily(path)
	if df is None or df.empty or "Total sales" not in df.columns:
		try:
			df2 = pd.read_csv(path)
			if "Total sales" in df2.columns:
				return float(pd.to_numeric(df2["Total sales"], errors="coerce").fillna(0).sum())
		except Exception:
			return 0.0
	return float(pd.to_numeric(df["Total sales"], errors="coerce").fillna(0).sum())


def _sum_northbeam_2025_spend() -> float:
	"""Attempt to locate a Northbeam spend export and sum 2025 YTD spend.
	Searches under q4-planning northbeam folder first, then broadly under data/ads.
	"""
	import glob
	candidates: List[str] = []
	# Targeted paths
	candidates.extend(glob.glob(str(PLANNING_DIR / "northbeam" / "**" / "*.csv"), recursive=True))
	# Broader fallback
	candidates.extend(glob.glob(str(ROOT / "data" / "ads" / "**" / "northbeam" / "*.csv"), recursive=True))
	if not candidates:
		return 0.0
	# Prefer newest file
	candidates.sort(key=lambda p: Path(p).stat().st_mtime, reverse=True)
	for p in candidates:
		try:
			df = pd.read_csv(p)
			cols = {c.lower().strip(): c for c in df.columns}
			# Find date column
			date_col = None
			for k in ["date", "day", "day date", "report date"]:
				if k in cols:
					date_col = cols[k]
					break
			if date_col is None:
				# try any column containing 'date'
				for lc, orig in cols.items():
					if "date" in lc:
						date_col = orig
						break
			if date_col is None:
				continue
			# Find spend column
			spend_col = None
			for k in ["spend", "cost", "ad spend", "amount spent", "total spend"]:
				if k in cols:
					spend_col = cols[k]
					break
			if spend_col is None:
				# fuzzy contains
				for lc, orig in cols.items():
					if ("spend" in lc or lc == "cost" or lc.startswith("cost (")) and ("roas" not in lc and "return on ad spend" not in lc):
						spend_col = orig
						break
			if spend_col is None:
				continue
			work = df.copy()
			work[date_col] = pd.to_datetime(work[date_col], errors="coerce")
			work = work.dropna(subset=[date_col])
			# Filter to a single accounting mode if available (default: Cash snapshot)
			desired_mode = os.getenv("NORTHBEAM_ACCOUNTING_MODE", "Cash snapshot").strip().lower()
			if "accounting_mode" in work.columns and desired_mode:
				modes_lower = work["accounting_mode"].astype(str).str.lower().str.strip()
				mask_mode = modes_lower == desired_mode
				if mask_mode.any():
					work = work[mask_mode]
			# Coerce spend (strip $ and commas)
			sp_series = work[spend_col].astype(str).str.replace(r"[^0-9\.-]", "", regex=True)
			work["__spend"] = pd.to_numeric(sp_series, errors="coerce").fillna(0.0)
			mask_2025 = work[date_col].dt.year == 2025
			val = float(work.loc[mask_2025, "__spend"].sum())
			if val > 0:
				return val
		except Exception:
			continue
	return 0.0


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


def project_q4_2025_rows(spend_q4_target: float, rev_q4_target: float, spend_shares: pd.Series, rev_shares: pd.Series,
						 spend_2024_by_month: Dict[str, float], rev_2024_by_month: Dict[str, float],
						 months: List[str]) -> List[SalesGoalsRow]:
	rows: List[SalesGoalsRow] = []
	for ym in months:
		# Map shares by equivalent month from 2024 share indices
		ym_2024 = ym.replace("2025", "2024")
		spend_weight = float(spend_shares.get(ym_2024, 0.0))
		rev_weight = float(rev_shares.get(ym_2024, 0.0))
		spend_m = spend_q4_target * spend_weight
		rev_m = rev_q4_target * rev_weight
		# 2024 actuals for same month
		sp_24 = float(spend_2024_by_month.get(ym_2024, 0.0))
		rv_24 = float(rev_2024_by_month.get(ym_2024, 0.0))
		roas_24 = (rv_24 / sp_24) if sp_24 > 0 else 0.0
		sp_to_rev_24 = (sp_24 / rv_24) if rv_24 > 0 else 0.0
		# deltas vs 2024 (relative %)
		sp_delta = (spend_m / sp_24 - 1.0) if sp_24 > 0 else 0.0
		rv_delta = (rev_m / rv_24 - 1.0) if rv_24 > 0 else 0.0
		roas_m = (rev_m / spend_m) if spend_m > 0 else 0.0
		spend_to_rev = (spend_m / rev_m) if rev_m > 0 else 0.0
		roas_delta = (roas_m / roas_24 - 1.0) if roas_24 > 0 else 0.0
		sp_to_rev_delta = (spend_to_rev / sp_to_rev_24 - 1.0) if sp_to_rev_24 > 0 else 0.0
		rows.append(SalesGoalsRow(
			month=ym,
			spend_target=spend_m,
			revenue_target=rev_m,
			roas_target=roas_m,
			spend_to_rev_pct=spend_to_rev,
			spend_2024=sp_24,
			revenue_2024=rv_24,
			roas_2024=roas_24,
			spend_to_rev_pct_2024=sp_to_rev_24,
			spend_delta_pct=sp_delta,
			revenue_delta_pct=rv_delta,
			roas_delta_pct=roas_delta,
			spend_to_rev_delta_pct=sp_to_rev_delta,
		))
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
		"spend_2024": r.spend_2024,
		"revenue_2024": r.revenue_2024,
		"roas_2024": r.roas_2024,
		"spend_to_rev_pct_2024": r.spend_to_rev_pct_2024,
		"spend_delta_pct": r.spend_delta_pct,
		"revenue_delta_pct": r.revenue_delta_pct,
		"roas_delta_pct": r.roas_delta_pct,
		"spend_to_rev_delta_pct": r.spend_to_rev_delta_pct,
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
	mode = str(context.get("mode", "remainder")).strip().lower()
	lines.append("Assumptions:")
	if mode == "trend":
		lines.append("- Primary plan is trend-based: uses 2025 YTD YoY vs 2024 and 2024 seasonal shares")
		lines.append("- Efficiency bounded by env: EFF_MIN_ROAS/EFF_MAX_ROAS and EFF_SPEND_TO_REV_MIN/MAX")
		lines.append("- FY targets shown for reference")
	else:
		lines.append("- 2025 Spend target: 2024 Spend × 1.05")
		lines.append("- 2025 Revenue target: 2024 Revenue × 1.20")
		lines.append("- Q4 targets = 2025 targets − 2025 YTD actuals; allocated using blended 2023/2024 Q4 monthly shares")
	lines.append("")
	lines.append("Baseline and YTD:")
	lines.append(f"- 2024 Spend (full-year): {usd(context['spend_2024'])}")
	lines.append(f"- 2024 Revenue (full-year): {usd(context['rev_2024'])}")
	lines.append(f"- 2025 YTD Spend: {usd(context['spend_2025_ytd'])}")
	lines.append(f"- 2025 YTD Revenue: {usd(context['rev_2025_ytd'])}")
	# YTD pacing vs 2024
	if 'spend_ytd_2024' in context and 'spend_ytd_2025' in context:
		sp_24 = context['spend_ytd_2024']
		sp_25 = context['spend_ytd_2025']
		sp_yoy = (sp_25 / sp_24 - 1.0) if sp_24 else 0.0
		lines.append(f"- YTD Spend vs 2024: {usd(sp_25)} vs {usd(sp_24)} ({pct(sp_yoy)})")
	if 'rev_ytd_2024' in context and 'rev_ytd_2025' in context:
		rv_24 = context['rev_ytd_2024']
		rv_25 = context['rev_ytd_2025']
		rv_yoy = (rv_25 / rv_24 - 1.0) if rv_24 else 0.0
		lines.append(f"- YTD Revenue vs 2024: {usd(rv_25)} vs {usd(rv_24)} ({pct(rv_yoy)})")
	lines.append("")
	lines.append("Annual Goals vs 2024:")
	lines.append("- Revenue: +20% vs 2024")
	lines.append("- Spend: +5% vs 2024")
	lines.append("")
	# FY target vs Q4 remainder
	fy_roas = (context['rev_2025_target'] / context['spend_2025_target']) if context.get('spend_2025_target') else 0.0
	fy_sr = (context['spend_2025_target'] / context['rev_2025_target']) if context.get('rev_2025_target') else 0.0
	lines.append("FY 2025 Target")
	lines.append(f"- Spend: {usd(context['spend_2025_target'])}")
	lines.append(f"- Revenue: {usd(context['rev_2025_target'])}")
	lines.append(f"- ROAS: {fy_roas:.2f}x")
	lines.append(f"- Spend/Rev %: {pct(fy_sr)}")
	lines.append("")
	section_label = "Sep–Dec 2025 Total (Primary plan)" if mode == "trend" else "Sep–Dec 2025 Remainder"
	lines.append(section_label)
	# Always compute header totals from rows to avoid drift
	sp_tot_header = sum(r.spend_target for r in rows)
	rev_tot_header = sum(r.revenue_target for r in rows)
	q4_roas_hdr = (rev_tot_header / sp_tot_header) if sp_tot_header > 0 else 0.0
	q4_sr_hdr = (sp_tot_header / rev_tot_header) if rev_tot_header > 0 else 0.0
	lines.append(f"- Spend: {usd(sp_tot_header)}")
	lines.append(f"- Revenue: {usd(rev_tot_header)}")
	lines.append(f"- ROAS: {q4_roas_hdr:.2f}x")
	lines.append(f"- Spend/Rev %: {pct(q4_sr_hdr)}")
	lines.append("")
	# Data cutoffs
	if 'cutoff_shopify' in context or 'cutoff_nb' in context:
		lines.append("Data cutoffs:")
		if context.get('cutoff_shopify'):
			lines.append(f"- Shopify YTD through: {context['cutoff_shopify']}")
		if context.get('cutoff_nb'):
			lines.append(f"- Northbeam YTD through: {context['cutoff_nb']}")
		lines.append("")
	# Revenue remaining KPIs
	if 'rev_fy_remaining' in context:
		lines.append("Revenue remaining to FY target")
		lines.append(f"- Amount: {usd(context['rev_fy_remaining'])}")
		# Overall required daily run-rate to reach FY target by Dec 31
		if 'overall_daily_run_rate' in context and context['overall_daily_run_rate'] is not None:
			lines.append(f"- Overall required daily run-rate (to Dec 31): {usd(context['overall_daily_run_rate'])}")
		lines.append("")
	if 'rev_sep_dec_remaining' in context:
		lines.append("Sep–Dec revenue remaining")
		lines.append(f"- Amount: {usd(context['rev_sep_dec_remaining'])}")
		# Monthly run-rate table
		mr = context.get('monthly_run') or []
		if mr:
			lines.append("")
			lines.append("Month | Remaining revenue | Required daily run-rate")
			lines.append("---|---:|---:")
			for d in mr:
				lines.append(f"{d['month']} | {usd(d['remaining'])} | {usd(d['runrate'])}")
			lines.append("")
	lines.append("Monthly projections (Sep–Dec):")
	lines.append("")
	lines.append("Month | Spend | Revenue | ROAS | Spend/Rev % | 2024 Spend | 2024 Revenue | 2024 ROAS | 2024 Spend/Rev % | Δ Spend | Δ Revenue | Δ ROAS | Δ Spend/Rev %")
	lines.append("---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:")
	for r in rows:
		lines.append(
			f"{r.month} | {usd(r.spend_target)} | {usd(r.revenue_target)} | {r.roas_target:.2f}x | {pct(r.spend_to_rev_pct)} | "
			f"{usd(r.spend_2024)} | {usd(r.revenue_2024)} | {r.roas_2024:.2f}x | {pct(r.spend_to_rev_pct_2024)} | "
			f"{pct(r.spend_delta_pct)} | {pct(r.revenue_delta_pct)} | {pct(r.roas_delta_pct)} | {pct(r.spend_to_rev_delta_pct)}"
		)
	lines.append("")
	# Totals and implied efficiency
	sp_tot = sum(r.spend_target for r in rows)
	rev_tot = sum(r.revenue_target for r in rows)
	roas_q4 = (rev_tot / sp_tot) if sp_tot > 0 else 0.0
	lines.append("Sep–Dec 2025 Total")
	lines.append(f"- Spend: {usd(sp_tot)}")
	lines.append(f"- Revenue: {usd(rev_tot)}")
	lines.append(f"- ROAS: {roas_q4:.2f}x")
	lines.append(f"- Spend/Rev %: {pct(sp_tot / rev_tot if rev_tot else 0.0)}")
	lines.append("")
	# 2024 Q4 totals
	sp24_tot = sum(r.spend_2024 for r in rows)
	rev24_tot = sum(r.revenue_2024 for r in rows)
	roas24_q4 = (rev24_tot / sp24_tot) if sp24_tot > 0 else 0.0
	lines.append("Sep–Dec 2024 Total")
	lines.append(f"- Spend: {usd(sp24_tot)}")
	lines.append(f"- Revenue: {usd(rev24_tot)}")
	lines.append(f"- ROAS: {roas24_q4:.2f}x")
	lines.append(f"- Spend/Rev %: {pct(sp24_tot / rev24_tot if rev24_tot else 0.0)}")
	lines.append("")
	md_path.write_text("\n".join(lines))
	return csv_path, md_path


def main() -> Tuple[Path, Path]:
	# Parse historical total spend for all months
	hist_path = PLANNING_DIR / "Historical Spend - Historical Spend.csv"
	hspend_df = parse_historical_total_spend(hist_path)

	# Shopify – load 2024 full-year daily and Q4 daily
	shopify_2024_full_path = SHOPIFY_DIR / "Total sales over time - 01-01-2024-12-31-2024.csv"
	shopify_2024_full = _read_shopify_daily(shopify_2024_full_path)
	if shopify_2024_full is None:
		shopify_2024_full = pd.DataFrame()
	shopify_2024_q4_path = SHOPIFY_DIR / "total-sales-over-time-2024Q4.csv"
	shopify_2024_q4 = _read_shopify_daily(shopify_2024_q4_path)
	if shopify_2024_q4 is None:
		shopify_2024_q4 = pd.DataFrame()

	# Shopify – load 2023 Q4 daily if present
	shopify_2023_q4_path = SHOPIFY_DIR / "total-sales-over-time-2023Q4.csv"
	shopify_2023_q4 = _read_shopify_daily(shopify_2023_q4_path)
	if shopify_2023_q4 is None:
		shopify_2023_q4 = pd.DataFrame()

	# Shopify – 2025 YTD (OU file)
	shopify_2025_ytd_path = _latest_shopify_ou_2025() or (SHOPIFY_DIR / "Total sales over time - OU - 2025-01-01 - 2025-09-02 .csv")
	shopify_2025_ytd = _read_shopify_daily(shopify_2025_ytd_path)
	if shopify_2025_ytd is None:
		shopify_2025_ytd = pd.DataFrame()
	# Shopify cutoff date
	cutoff_shopify = _shopify_cutoff_from(shopify_2025_ytd, shopify_2025_ytd_path)

	# Baselines
	spend_2024, rev_2024 = compute_full_year_baselines(hspend_df, shopify_2024_full)
	# If revenue baseline missing, sum from the 2024 monthly file directly
	if rev_2024 == 0.0:
		rev_2024 = _sum_shopify_total_sales(shopify_2024_full_path)
	spend_2025_ytd_hist, rev_2025_ytd = compute_2025_ytd(hspend_df, shopify_2025_ytd)
	# Override spend with Northbeam if available
	spend_2025_ytd_nb = _sum_northbeam_2025_spend()
	spend_2025_ytd = spend_2025_ytd_nb if spend_2025_ytd_nb > 0 else spend_2025_ytd_hist
	# Northbeam cutoff date
	cutoff_nb = None
	nb_path = _latest_northbeam_csv_path()
	if nb_path and nb_path.exists():
		try:
			dfn = pd.read_csv(nb_path, usecols=["date", "accounting_mode"], low_memory=False)
			dfn["date"] = pd.to_datetime(dfn["date"], errors="coerce")
			mode = os.getenv("NORTHBEAM_ACCOUNTING_MODE", "Cash snapshot").strip().lower()
			if "accounting_mode" in dfn.columns and mode:
				msk = dfn["accounting_mode"].astype(str).str.lower().str.strip() == mode
				dfn = dfn[msk]
			cut = dfn["date"].max()
			if pd.notna(cut):
				cutoff_nb = str(cut.date())
		except Exception:
			pass

	# YTD pacing vs 2024
	# Prefer Northbeam for spend if available; align 2024 to same cutoff day/month
	spend_ytd_2025 = 0.0
	spend_ytd_2024 = 0.0
	df_nb_full = _northbeam_df_filtered()
	if df_nb_full is not None and not df_nb_full.empty and cutoff_nb:
		cut_dt_2025 = pd.to_datetime(cutoff_nb)
		spend_ytd_2025 = _northbeam_ytd_spend(df_nb_full, 2025, cut_dt_2025)
		# 2024 YTD from historical monthly spend up to the same cutoff month
		if not hspend_df.empty:
			last_month_2024 = f"2024-{cut_dt_2025.month:02d}"
			mask_2024 = (hspend_df["month"].str.startswith("2024-")) & (hspend_df["month"] <= last_month_2024)
			spend_ytd_2024 = float(hspend_df.loc[mask_2024, "total_spend"].sum())
	else:
		# Fallback to historical monthly spend
		def _ytd_spend(hdf: pd.DataFrame, year: int, last_month: str) -> float:
			if hdf.empty:
				return 0.0
			m = (hdf["month"].str.startswith(f"{year}-")) & (hdf["month"] <= last_month)
			return float(hdf.loc[m, "total_spend"].sum())
		last_2025_month = ""
		if not hspend_df.empty:
			m25 = hspend_df[hspend_df["month"].str.startswith("2025-")]["month"].tolist()
			last_2025_month = max(m25) if m25 else ""
		spend_ytd_2025 = _ytd_spend(hspend_df, 2025, last_2025_month) if last_2025_month else 0.0
		spend_ytd_2024 = _ytd_spend(hspend_df, 2024, last_2025_month.replace("2025-", "2024-")) if last_2025_month else 0.0

	# Revenue YTD: from 2025 OU file sum 'Total sales' and 'Total sales (previous_year)' across available days
	rev_ytd_2025 = 0.0
	rev_ytd_2024 = 0.0
	if shopify_2025_ytd is not None and not shopify_2025_ytd.empty:
		# Align Shopify YTD to Northbeam cutoff date if available; else use Shopify max Day
		cut_dt = None
		if cutoff_nb:
			try:
				cut_dt = pd.to_datetime(cutoff_nb)
			except Exception:
				cut_dt = None
		if cut_dt is None and 'Day' in shopify_2025_ytd.columns:
			cut_dt = pd.to_datetime(shopify_2025_ytd['Day'], errors='coerce').max()
		mask = pd.Series([True]*len(shopify_2025_ytd))
		if cut_dt is not None and 'Day' in shopify_2025_ytd.columns:
			mask = pd.to_datetime(shopify_2025_ytd['Day'], errors='coerce') <= cut_dt
		if 'Total sales' in shopify_2025_ytd.columns:
			rev_ytd_2025 = float(pd.to_numeric(shopify_2025_ytd.loc[mask, 'Total sales'], errors='coerce').fillna(0).sum())
		py_col = 'Total sales (previous_year)'
		if py_col in shopify_2025_ytd.columns:
			rev_ytd_2024 = float(pd.to_numeric(shopify_2025_ytd.loc[mask, py_col], errors='coerce').fillna(0).sum())

	# Targets
	spend_2025_target = spend_2024 * 1.05
	rev_2025_target = rev_2024 * 1.20
	spend_q4_target = max(spend_2025_target - spend_2025_ytd, 0.0)
	rev_q4_target = max(rev_2025_target - rev_2025_ytd, 0.0)

	# Spend weights (Sep–Dec shares) from historical spend 2024 (fallbacks if missing)
	spend_monthly = hspend_df.copy()
	spend_2024_sd = (
		spend_monthly[spend_monthly["month"].isin(["2024-09","2024-10", "2024-11", "2024-12"])][["month", "total_spend"]]
		.rename(columns={"total_spend": "spend"})
	)
	if not spend_2024_sd.empty:
		tot = float(spend_2024_sd["spend"].sum())
		spend_shares = (spend_2024_sd.set_index("month")["spend"] / tot).reindex(["2024-09","2024-10","2024-11","2024-12"]).fillna(0.0)
	else:
		spend_shares = pd.Series({"2024-09": 0.25, "2024-10": 0.25, "2024-11": 0.25, "2024-12": 0.25})

	# Revenue weights from Shopify 2024 daily totals (Sep–Dec)
	rev_2024_monthly = pd.DataFrame()
	if shopify_2024_full is not None and not shopify_2024_full.empty:
		w = shopify_2024_full.copy()
		if "Day" in w.columns:
			w["month"] = pd.to_datetime(w["Day"], errors="coerce").dt.strftime("%Y-%m")
			rev_2024_monthly = w.groupby("month")["Total sales"].sum().reset_index().rename(columns={"Total sales":"revenue"})
	rev_2024_sd = rev_2024_monthly[rev_2024_monthly["month"].isin(["2024-09","2024-10","2024-11","2024-12"])].copy() if not rev_2024_monthly.empty else pd.DataFrame(columns=["month","revenue"])
	if not rev_2024_sd.empty:
		tot_r = float(rev_2024_sd["revenue"].sum())
		rev_shares = (rev_2024_sd.set_index("month")["revenue"] / tot_r).reindex(["2024-09","2024-10","2024-11","2024-12"]).fillna(0.0)
	else:
		rev_shares = pd.Series({"2024-09": 0.25, "2024-10": 0.25, "2024-11": 0.25, "2024-12": 0.25})

	# Build 2024 monthly actuals for Q4
	spend_2024_q4 = (
		hspend_df[hspend_df["month"].isin(["2024-09","2024-10","2024-11","2024-12"])][["month", "total_spend"]]
		.rename(columns={"total_spend": "spend"})
		.set_index("month")["spend"].to_dict()
	)
	rev_2024_q4_dict = (
		rev_2024_sd.set_index("month")["revenue"].to_dict() if not rev_2024_sd.empty else {}
	)

	# Set Sep–Dec remainder targets: keep revenue remainder; set spend to target Spend/Rev ratio
	rev_fy_remaining = max(rev_2025_target - rev_2025_ytd, 0.0)
	desired_spend_to_rev = float(os.getenv("EFF_SPEND_TO_REV", "0.25"))
	if desired_spend_to_rev < 0:
		desired_spend_to_rev = 0.25
	# Revenue remainder from FY target at cutoff
	rev_sep_dec_target = rev_fy_remaining
	# Build per-month revenue targets from shaped weights (Sep–Dec 2025)
	months_2025 = ["2025-09","2025-10","2025-11","2025-12"]
	months_2024 = [m.replace("2025","2024") for m in months_2025]
	rev_per_month: dict[str, float] = {}

	# 2023 monthly (Oct–Dec) from Q4 file; Sep falls back to 2024
	rev_2023_monthly = pd.DataFrame()
	if shopify_2023_q4 is not None and not shopify_2023_q4.empty:
		w3 = shopify_2023_q4.copy()
		if "Day" in w3.columns:
			w3["month"] = pd.to_datetime(w3["Day"], errors="coerce").dt.strftime("%Y-%m")
			rev_2023_monthly = w3.groupby("month")["Total sales"].sum().reset_index().rename(columns={"Total sales":"revenue"})

	# Growth factors 2023→2024 per month
	gf: dict[str, float] = {}
	for m24 in months_2024:
		if m24 == "2024-09":
			gf[m24] = 1.0
			continue
		r24 = float(rev_2024_q4_dict.get(m24, 0.0))
		m23 = m24.replace("2024","2023")
		r23 = 0.0
		if not rev_2023_monthly.empty:
			row = rev_2023_monthly[rev_2023_monthly["month"] == m23]
			if not row.empty:
				r23 = float(row["revenue"].iloc[0])
		gf[m24] = (r24 / r23) if r23 > 0 else 1.0

	# Holiday bias multipliers
	holiday_bias = {"2024-09": 0.94, "2024-10": 1.10, "2024-11": 1.12, "2024-12": 0.85}

	# 2025 September run-rate bias (relative to 2024 September)
	sep_rr_bias = 1.0
	try:
		if shopify_2025_ytd is not None and not shopify_2025_ytd.empty and not rev_2024_sd.empty:
			w25 = shopify_2025_ytd.copy()
			if "Day" in w25.columns:
				w25["month"] = pd.to_datetime(w25["Day"], errors="coerce").dt.strftime("%Y-%m")
			m25_sep = float(w25[w25["month"] == "2025-09"]["Total sales"].sum())
			m24_sep = float(rev_2024_sd[rev_2024_sd["month"] == "2024-09"]["revenue"].sum())
			if m24_sep > 0:
				sep_rr_bias = max(0.85, min(1.05, m25_sep / m24_sep))
	except Exception:
		pass

	# Compose weights: 2024 share × growth × holiday × rr_bias (Sep only)
	weights: dict[str, float] = {}
	for m24 in months_2024:
		base = float(rev_shares.get(m24, 0.0))
		g = float(gf.get(m24, 1.0))
		b = float(holiday_bias.get(m24, 1.0))
		adj = base * g * b
		if m24 == "2024-09":
			adj *= sep_rr_bias
		weights[m24] = adj
	# Normalize
	tot_w = sum(weights.values()) or 1.0
	for m25, m24 in zip(months_2025, months_2024):
		share = weights[m24] / tot_w
		rev_per_month[m25] = rev_sep_dec_target * share

	# Baseline 2024 monthly spend/revenue ratios (Spend/Rev) for Sep–Dec
	sr_2024: dict[str, float] = {}
	for m24 in months_2024:
		rv24 = float(rev_2024_q4_dict.get(m24, 0.0))
		sp24 = float(spend_2024_q4.get(m24, 0.0))
		sr_2024[m24] = (sp24 / rv24) if rv24 > 0 else desired_spend_to_rev
	# Compute weighted average baseline ratio using 2025 revenue shares
	avg_sr_baseline = 0.0
	for m24 in months_2024:
		avg_sr_baseline += float(rev_shares.get(m24, 0.0)) * float(sr_2024.get(m24, desired_spend_to_rev))
	factor = (desired_spend_to_rev / avg_sr_baseline) if avg_sr_baseline > 0 else 1.0
	# Optional clamp band
	sr_min = float(os.getenv("EFF_SPEND_TO_REV_MIN", "0.25"))
	sr_max = float(os.getenv("EFF_SPEND_TO_REV_MAX", "0.30"))
	# Enforce ROAS cap: sr_min must be at least 1 / max_roas
	max_roas = float(os.getenv("EFF_MAX_ROAS", "4.5"))
	if max_roas > 0:
		sr_min = max(sr_min, 1.0 / max_roas)
	# Project per-month ratios and spends
	spend_per_month: dict[str, float] = {}
	# Spend bias to push more spend earlier (Oct/Nov) and ease December
	spend_bias = {"2024-09": 0.96, "2024-10": 1.12, "2024-11": 1.15, "2024-12": 0.88}
	for m25, m24 in zip(months_2025, months_2024):
		proj_sr = float(sr_2024.get(m24, desired_spend_to_rev)) * factor * float(spend_bias.get(m24, 1.0))
		if sr_min > 0 and sr_max > sr_min:
			proj_sr = max(sr_min, min(sr_max, proj_sr))
		spend_per_month[m25] = rev_per_month[m25] * proj_sr
	# Re-normalize to hit total spend implied by desired average (optional)
	# Intentionally skip renormalization to preserve per-month SR minimum (ROAS cap)
	cur_total_spend = sum(spend_per_month.values())
	# Cap September ROAS by increasing spend if above cap (default 4.0); do not lock if below
	sep_roas_cap = float(os.getenv("EFF_SEP_ROAS_CAP", "4.0"))
	if sep_roas_cap > 0 and rev_per_month.get("2025-09", 0.0) > 0:
		cur_sp = spend_per_month.get("2025-09", 0.0)
		cur_roas = (rev_per_month["2025-09"] / cur_sp) if cur_sp > 0 else float('inf')
		if cur_roas > sep_roas_cap:
			spend_per_month["2025-09"] = rev_per_month["2025-09"] / sep_roas_cap
	# Build spend shares keyed by 2024 months for the projector
	spend_total = sum(spend_per_month.values())
	spend_q4_target = spend_total
	rev_q4_target = rev_sep_dec_target
	spend_shares = pd.Series({m24: (spend_per_month[m25] / spend_total if spend_total else 0.0) for m25, m24 in zip(months_2025, months_2024)})

	# Projections with 2024 baselines
	rows = project_q4_2025_rows(
		spend_q4_target,
		rev_q4_target,
		spend_shares,
		rev_shares,
		spend_2024_by_month=spend_2024_q4,
		rev_2024_by_month=rev_2024_q4_dict,
		months=months_2025,
	)

	# Final enforcement: cap ROAS per month at EFF_MAX_ROAS by increasing spend if needed
	try:
		max_roas = float(os.getenv("EFF_MAX_ROAS", "4.5"))
		for r in rows:
			if r.revenue_target > 0 and max_roas > 0:
				current_roas = r.revenue_target / r.spend_target if r.spend_target > 0 else float('inf')
				if current_roas > max_roas:
					new_spend = r.revenue_target / max_roas
					r.spend_target = new_spend
					r.roas_target = max_roas
					r.spend_to_rev_pct = new_spend / r.revenue_target
					# Recompute deltas vs 2024
					sp_24 = r.spend_2024
					rv_24 = r.revenue_2024
					r.spend_delta_pct = (new_spend / sp_24 - 1.0) if sp_24 > 0 else 0.0
					r.revenue_delta_pct = (r.revenue_target / rv_24 - 1.0) if rv_24 > 0 else 0.0
					# ROAS delta vs 2024
					r.roas_delta_pct = (r.roas_target / r.roas_2024 - 1.0) if r.roas_2024 > 0 else 0.0
					# Spend/Rev delta vs 2024
					r.spend_to_rev_delta_pct = (r.spend_to_rev_pct / r.spend_to_rev_pct_2024 - 1.0) if r.spend_to_rev_pct_2024 > 0 else 0.0
		# Enforce ROAS floor (>= EFF_MIN_ROAS) for Oct and Dec only by decreasing spend if needed
		min_roas = float(os.getenv("EFF_MIN_ROAS", "3.8"))
		for r in rows:
			if r.month in ("2025-10", "2025-12") and r.revenue_target > 0 and min_roas > 0:
				current_roas = r.revenue_target / r.spend_target if r.spend_target > 0 else float('inf')
				if current_roas < min_roas:
					new_spend = r.revenue_target / min_roas
					r.spend_target = new_spend
					r.roas_target = min_roas
					r.spend_to_rev_pct = new_spend / r.revenue_target
					# Recompute deltas vs 2024
					sp_24 = r.spend_2024
					rv_24 = r.revenue_2024
					r.spend_delta_pct = (new_spend / sp_24 - 1.0) if sp_24 > 0 else 0.0
					r.revenue_delta_pct = (r.revenue_target / rv_24 - 1.0) if rv_24 > 0 else 0.0
					# ROAS delta vs 2024
					r.roas_delta_pct = (r.roas_target / r.roas_2024 - 1.0) if r.roas_2024 > 0 else 0.0
					# Spend/Rev delta vs 2024
					r.spend_to_rev_delta_pct = (r.spend_to_rev_pct / r.spend_to_rev_pct_2024 - 1.0) if r.spend_to_rev_pct_2024 > 0 else 0.0
	except Exception:
		pass

	# Trend-based scenario using 2025 YTD YoY
	rows_trend = []
	try:
		yoy_rev = (rev_ytd_2025 / rev_ytd_2024 - 1.0) if rev_ytd_2024 > 0 else 0.0
		yoy_sp = (spend_ytd_2025 / spend_ytd_2024 - 1.0) if spend_ytd_2024 > 0 else 0.0
		base_rev_total = float(rev_2024_sd["revenue"].sum()) if not rev_2024_sd.empty else sum(rev_2024_q4_dict.values())
		base_sp_total = float(sum(spend_2024_q4.values()))
		trend_rev_total = base_rev_total * (1.0 + max(yoy_rev, -0.5))
		trend_sp_total = base_sp_total * (1.0 + max(yoy_sp, -0.5))
		# Optionally match the FY remainder revenue target for Sep–Dec
		try:
			if str(os.getenv("TREND_MATCH_TARGET", "0")).strip().lower() in ("1", "true", "yes", "y"):  # noqa: E714
				trend_rev_total = rev_sep_dec_target
		except Exception:
			pass
		# Desired average SR for trend scenario
		trend_avg_sr = (trend_sp_total / trend_rev_total) if trend_rev_total > 0 else desired_spend_to_rev
		# Use same shaped weights for revenue, with optional share adjustments per month
		base_shares = {m25: (rev_per_month.get(m25, 0.0) / rev_sep_dec_target) if rev_sep_dec_target > 0 else 0.0 for m25 in months_2025}
		def _f(var: str, default: float = 1.0) -> float:
			try:
				return float(os.getenv(var, str(default)))
			except Exception:
				return default
		adj_09 = _f("REV_ADJ_2025_09", 1.0)
		adj_10 = _f("REV_ADJ_2025_10", 1.0)
		adj_11 = _f("REV_ADJ_2025_11", 1.0)
		adj_12 = _f("REV_ADJ_2025_12", 1.0)
		unnorm = {
			"2025-09": base_shares.get("2025-09", 0.0) * adj_09,
			"2025-10": base_shares.get("2025-10", 0.0) * adj_10,
			"2025-11": base_shares.get("2025-11", 0.0) * adj_11,
			"2025-12": base_shares.get("2025-12", 0.0) * adj_12,
		}
		sum_unnorm = sum(unnorm.values()) or 1.0
		adj_shares = {m: (v / sum_unnorm) for m, v in unnorm.items()}
		rev_trend_per_month = {m25: trend_rev_total * adj_shares.get(m25, 0.0) for m25 in months_2025}
		# Optional: cap September spend by limiting September revenue and redistributing the excess to other months
		try:
			sep_max_spend = float(os.getenv("SEP_MAX_SPEND", "0"))
			sep_roas_cap = float(os.getenv("EFF_SEP_ROAS_CAP", "0"))
			if sep_max_spend > 0 and sep_roas_cap > 0:
				max_rev_sep = sep_max_spend * sep_roas_cap
				cur_rev_sep = rev_trend_per_month.get("2025-09", 0.0)
				if cur_rev_sep > max_rev_sep:
					excess = cur_rev_sep - max_rev_sep
					rev_trend_per_month["2025-09"] = max_rev_sep
					# redistribute to Oct–Dec using their adjusted shares
					redis_keys = ["2025-10", "2025-11", "2025-12"]
					redis_weights = [adj_shares.get(k, 0.0) for k in redis_keys]
					sum_w = sum(redis_weights) or 1.0
					for k, w in zip(redis_keys, redis_weights):
						rev_trend_per_month[k] = rev_trend_per_month.get(k, 0.0) + excess * (w / sum_w)
		except Exception:
			pass

		# Optional: ensure September revenue is at least a YoY floor (bounded by spend and ROAS caps) by shifting from later months
		try:
			sep_yoy_mult = float(os.getenv("SEP_YOY_MULT", "1.0"))
			rev_2024_sep = float(rev_2024_q4_dict.get("2024-09", 0.0))
			yoy_floor = rev_2024_sep * sep_yoy_mult
			if yoy_floor > 0:
				# Respect the spend/ROAS cap
				target_sep = yoy_floor
				if sep_max_spend > 0 and sep_roas_cap > 0:
					cap_rev = sep_max_spend * sep_roas_cap
					target_sep = min(yoy_floor, cap_rev)
				cur_sep = rev_trend_per_month.get("2025-09", 0.0)
				if cur_sep < target_sep:
					need = target_sep - cur_sep
					# Pull from October, then November, then December, greedily up to available
					for k in ["2025-10", "2025-11", "2025-12"]:
						if need <= 0:
							break
						avail = rev_trend_per_month.get(k, 0.0)
						if avail <= 0:
							continue
						shift = min(avail, need)
						rev_trend_per_month[k] = avail - shift
						need -= shift
					# Assign collected to September
					moved = target_sep - cur_sep - need
					rev_trend_per_month["2025-09"] = cur_sep + moved
		except Exception:
			pass
		# Build monthly SR using 2024 pattern scaled to average
		avg_sr_baseline = 0.0
		for m24 in months_2024:
			avg_sr_baseline += float(rev_shares.get(m24, 0.0)) * float(sr_2024.get(m24, desired_spend_to_rev))
		trend_factor = (trend_avg_sr / avg_sr_baseline) if avg_sr_baseline > 0 else 1.0
		trend_spend_per_month = {}
		for m25, m24 in zip(months_2025, months_2024):
			proj_sr = float(sr_2024.get(m24, desired_spend_to_rev)) * trend_factor * float(spend_bias.get(m24, 1.0))
			proj_sr = max(1.0/float(os.getenv("EFF_MAX_ROAS", "4.5")), min(float(os.getenv("EFF_SPEND_TO_REV_MAX", "0.35")), proj_sr))
			trend_spend_per_month[m25] = rev_trend_per_month[m25] * proj_sr
		# Enforce per-month ROAS cap and Oct/Dec floor
		spend_shares_trend = pd.Series({m24: (trend_spend_per_month[m25] / max(sum(trend_spend_per_month.values()), 1e-9)) for m25, m24 in zip(months_2025, months_2024)})
		rev_shares_trend = pd.Series({m24: (rev_trend_per_month[m25] / max(trend_rev_total, 1e-9)) for m25, m24 in zip(months_2025, months_2024)})
		trend_rows = project_q4_2025_rows(
			sum(trend_spend_per_month.values()),
			trend_rev_total,
			spend_shares_trend,
			rev_shares_trend,
			spend_2024_by_month=spend_2024_q4,
			rev_2024_by_month=rev_2024_q4_dict,
			months=months_2025,
		)
		# Cap/floor
		max_roas2 = float(os.getenv("EFF_MAX_ROAS", "4.5"))
		min_roas2 = float(os.getenv("EFF_MIN_ROAS", "3.8"))
		for r in trend_rows:
			if r.revenue_target > 0 and max_roas2 > 0:
				curr = r.revenue_target / r.spend_target if r.spend_target > 0 else float('inf')
				if curr > max_roas2:
					new_sp = r.revenue_target / max_roas2
					r.spend_target = new_sp
					r.roas_target = max_roas2
					r.spend_to_rev_pct = new_sp / r.revenue_target
			if r.month in ("2025-10","2025-12") and r.revenue_target > 0 and min_roas2 > 0:
				curr = r.revenue_target / r.spend_target if r.spend_target > 0 else float('inf')
				if curr < min_roas2:
					new_sp = r.revenue_target / min_roas2
					r.spend_target = new_sp
					r.roas_target = min_roas2
					r.spend_to_rev_pct = new_sp / r.revenue_target
		# November-specific ROAS floor to push efficiency
		try:
			nov_min = float(os.getenv("EFF_NOV_MIN_ROAS", "0"))
			if nov_min > 0:
				for r in trend_rows:
					if r.month == "2025-11" and r.revenue_target > 0:
						curr = r.revenue_target / r.spend_target if r.spend_target > 0 else float('inf')
						if curr < nov_min:
							new_sp = r.revenue_target / nov_min
							r.spend_target = new_sp
							r.roas_target = nov_min
							r.spend_to_rev_pct = new_sp / r.revenue_target
		except Exception:
			pass
		# September-specific cap for trend scenario
		try:
			sep_cap2 = float(os.getenv("EFF_SEP_ROAS_CAP", "0"))
			if sep_cap2 > 0:
				for r in trend_rows:
					if r.month == "2025-09" and r.revenue_target > 0:
						curr = r.revenue_target / r.spend_target if r.spend_target > 0 else float('inf')
						if curr > sep_cap2:
							new_sp = r.revenue_target / sep_cap2
							r.spend_target = new_sp
							r.roas_target = sep_cap2
							r.spend_to_rev_pct = new_sp / r.revenue_target
		except Exception:
			pass
		# Recompute deltas for trend rows after adjustments to ensure accurate reporting
		try:
			for r in trend_rows:
				# Recompute derived metrics
				if r.spend_target > 0:
					r.roas_target = r.revenue_target / r.spend_target
				r.spend_to_rev_pct = (r.spend_target / r.revenue_target) if r.revenue_target > 0 else 0.0
				# Recompute deltas vs 2024
				sp_24 = r.spend_2024
				rv_24 = r.revenue_2024
				r.roas_2024 = (rv_24 / sp_24) if sp_24 > 0 else 0.0
				r.spend_to_rev_pct_2024 = (sp_24 / rv_24) if rv_24 > 0 else 0.0
				r.spend_delta_pct = (r.spend_target / sp_24 - 1.0) if sp_24 > 0 else 0.0
				r.revenue_delta_pct = (r.revenue_target / rv_24 - 1.0) if rv_24 > 0 else 0.0
				r.roas_delta_pct = (r.roas_target / r.roas_2024 - 1.0) if r.roas_2024 > 0 else 0.0
				r.spend_to_rev_delta_pct = (r.spend_to_rev_pct / r.spend_to_rev_pct_2024 - 1.0) if r.spend_to_rev_pct_2024 > 0 else 0.0
		except Exception:
			pass
		rows_trend = trend_rows
	except Exception:
		rows_trend = []
	# Ensure monthly_run exists
	if 'monthly_run' not in locals():
		monthly_run = []

	# Choose primary plan mode
	plan_mode = os.getenv("SALES_GOALS_MODE", "remainder").strip().lower()
	primary_rows: List[SalesGoalsRow] = rows
	if plan_mode == "trend" and rows_trend:
		primary_rows = rows_trend

	# Optional rounding of spend upward to get cleaner revenue numbers
	try:
		round_base = int(os.getenv("ROUND_SPEND_TO", "0"))
		preserve_total = str(os.getenv("ROUND_PRESERVE_TOTAL", "1")).strip().lower() in ("1","true","yes","y")
		round_last = str(os.getenv("ROUND_LAST_MONTH", "0")).strip().lower() in ("1","true","yes","y")
		if round_base and round_base > 0 and primary_rows:
			# Compute target total revenue (optionally round total)
			target_total_rev = sum(r.revenue_target for r in primary_rows)
			round_total_base = int(os.getenv("ROUND_TOTAL_REV_TO", "0"))
			if round_total_base and round_total_base > 0:
				import math
				target_total_rev = float(round(target_total_rev / round_total_base) * round_total_base)
			# Round all but last month (to preserve total)
			for r in primary_rows[:-1 if preserve_total and not round_last else len(primary_rows)]:
				if r.spend_target <= 0 or r.roas_target <= 0:
					continue
				import math
				new_sp = float(math.ceil(r.spend_target / round_base) * round_base)
				r.spend_target = new_sp
				r.revenue_target = new_sp * r.roas_target
				r.spend_to_rev_pct = new_sp / r.revenue_target if r.revenue_target > 0 else 0.0
			# Adjust last month to preserve total revenue if requested
			if preserve_total and primary_rows:
				new_sum = sum(r.revenue_target for r in primary_rows[:-1])
				last = primary_rows[-1]
				if round_last:
					# Round last spend up, then set revenue to hit total and back-compute ROAS
					new_sp_last = float(math.ceil(max(0.0, (target_total_rev - new_sum) / max(last.roas_target, 1e-9)) / round_base) * round_base)
					last.spend_target = new_sp_last
					last.revenue_target = max(0.0, target_total_rev - new_sum)
					last.roas_target = (last.revenue_target / last.spend_target) if last.spend_target > 0 else last.roas_target
					last.spend_to_rev_pct = last.spend_target / last.revenue_target if last.revenue_target > 0 else 0.0
				else:
					last.revenue_target = max(0.0, target_total_rev - new_sum)
					last.spend_target = (last.revenue_target / last.roas_target) if last.roas_target > 0 else 0.0
					last.spend_to_rev_pct = last.spend_target / last.revenue_target if last.revenue_target > 0 else 0.0
			# Recompute deltas vs 2024 after rounding
			for r in primary_rows:
				sp_24 = r.spend_2024
				rv_24 = r.revenue_2024
				r.roas_2024 = (rv_24 / sp_24) if sp_24 > 0 else 0.0
				r.spend_to_rev_pct_2024 = (sp_24 / rv_24) if rv_24 > 0 else 0.0
				r.spend_delta_pct = (r.spend_target / sp_24 - 1.0) if sp_24 > 0 else 0.0
				r.revenue_delta_pct = (r.revenue_target / rv_24 - 1.0) if rv_24 > 0 else 0.0
				r.roas_delta_pct = (r.roas_target / r.roas_2024 - 1.0) if r.roas_2024 > 0 else 0.0
				r.spend_to_rev_delta_pct = (r.spend_to_rev_pct / r.spend_to_rev_pct_2024 - 1.0) if r.spend_to_rev_pct_2024 > 0 else 0.0
	except Exception:
		pass

	csv_path, md_path = write_outputs(primary_rows, context={
		"spend_2024": spend_2024,
		"rev_2024": rev_2024,
		"spend_2025_ytd": spend_ytd_2025,
		"rev_2025_ytd": rev_2025_ytd,
		"spend_2025_target": spend_2024 * 1.05,
		"rev_2025_target": rev_2024 * 1.20,
		"spend_q4_target": spend_q4_target,
		"rev_q4_target": rev_q4_target,
		"mode": plan_mode,
		# Overall FY target and required daily run rate (to Dec 31)
		"overall_daily_run_rate": (
			(rev_2024 * 1.20 - rev_2025_ytd) / max((pd.Timestamp(year=2025, month=12, day=31) - pd.to_datetime(cutoff_shopify)).days, 1)
			if cutoff_shopify else None
		),
		# YTD pacing context
		"spend_ytd_2024": spend_ytd_2024,
		"spend_ytd_2025": spend_ytd_2025,
		"rev_ytd_2024": rev_ytd_2024,
		"rev_ytd_2025": rev_ytd_2025,
		# Cutoffs
		"cutoff_shopify": cutoff_shopify,
		"cutoff_nb": cutoff_nb,
		# Remaining KPIs
		"rev_fy_remaining": rev_fy_remaining,
		"rev_sep_dec_remaining": rev_sep_dec_target,
		"monthly_run": monthly_run,
	})
	# Write an appended markdown with the alternative scenario if present
	if rows_trend and plan_mode != "trend":
		try:
			md_append = []
			md_append.append("\nTrend-based plan (2025 YTD YoY)")
			md_append.append("")
			md_append.append("Month | Spend | Revenue | ROAS | Spend/Rev %")
			md_append.append("---|---:|---:|---:|---:")
			def usd(x: float) -> str:
				return f"${x:,.0f}"
			for r in rows_trend:
				md_append.append(f"{r.month} | {usd(r.spend_target)} | {usd(r.revenue_target)} | {r.roas_target:.2f}x | {r.spend_to_rev_pct*100:.1f}%")
			with open(md_path, "a") as f:
				f.write("\n" + "\n".join(md_append) + "\n")
		except Exception:
			pass
	# Append weekly breakdown tables per month using 2024 Shopify daily patterns with weekly ROAS variation
	try:
		with open(md_path, "a") as f:
			f.write("\nWeekly breakdowns (patterned from Shopify 2024 daily)\n\n")
			for r in primary_rows:
				month = r.month
				ref_month = month.replace("2025", "2024")
				# Choose daily source for 2024 weekly revenue shares
				if ref_month == "2024-09":
					# Use 2025 OU previous_year to approximate 2024 September weekly revenue shares
					shares = compute_weekly_shares_from_shopify_prev_year(shopify_2025_ytd, "2025-09")
				else:
					daily_src = shopify_2024_q4
					shares = compute_weekly_shares_from_shopify(daily_src, ref_month)
				# Preserve monthly totals; vary weekly ROAS using 2024 demand shares
				monthly_rev = float(r.revenue_target)
				monthly_sp = float(r.spend_target)
				monthly_roas = float(r.roas_target) if r.roas_target > 0 else (monthly_rev / monthly_sp if monthly_sp > 0 else 0.0)
				w_revs = [monthly_rev * s for s in shares]
				# Demand factor: relative to equal share
				avg_share = (sum(shares) / len(shares)) if shares else 0.0
				factors = [(s / avg_share) if avg_share > 0 else 1.0 for s in shares]
				alpha = 0.5
				try:
					alpha = float(os.getenv("WEEK_ROAS_ALPHA", "0.5"))
				except Exception:
					alpha = 0.5
				base_roas = [monthly_roas * (max(0.1, f) ** alpha) for f in factors]
				# Scale ROAS so that sum(w_rev / roas) == monthly_sp
				req_spend_num = sum((wr / max(br, 1e-9)) for wr, br in zip(w_revs, base_roas))
				scale = (req_spend_num / monthly_sp) if monthly_sp > 0 else 1.0
				adj_roas = [br / max(scale, 1e-9) for br in base_roas]
				w_spends = [wr / max(ar, 1e-9) for wr, ar in zip(w_revs, adj_roas)]
				# If September 2025, override weeks 1-2 with actuals (Shopify revenue, Northbeam spend)
				if month == "2025-09":
					try:
						# Revenue actuals from Shopify 2025 daily
						rev_w = [0.0, 0.0, 0.0, 0.0]
						if shopify_2025_ytd is not None and not shopify_2025_ytd.empty and "Day" in shopify_2025_ytd.columns and "Total sales" in shopify_2025_ytd.columns:
							w25 = shopify_2025_ytd.copy()
							w25["month"] = pd.to_datetime(w25["Day"], errors="coerce").dt.strftime("%Y-%m")
							m = w25["month"] == "2025-09"
							seg = w25.loc[m, ["Day", "Total sales"]].dropna()
							if not seg.empty:
								seg["week_in_month"] = pd.to_datetime(seg["Day"], errors="coerce").apply(_week_in_month_from_day)
								grp = seg.groupby("week_in_month")["Total sales"].sum()
								for i in [1,2]:
									rev_w[i-1] = float(grp.get(i, 0.0))
						# Spend actuals from Northbeam
						sp_w = [0.0, 0.0, 0.0, 0.0]
						if df_nb_full is not None and not df_nb_full.empty:
							seg2 = df_nb_full.copy()
							seg2["month"] = seg2["date"].dt.strftime("%Y-%m")
							m2 = seg2["month"] == "2025-09"
							seg2 = seg2.loc[m2, ["date", "spend_num"]].dropna()
							if not seg2.empty:
								seg2["week_in_month"] = seg2["date"].apply(_week_in_month_from_day)
								grp2 = seg2.groupby("week_in_month")["spend_num"].sum()
								for i in [1,2]:
									sp_w[i-1] = float(grp2.get(i, 0.0))
						# If we have any actuals, apply them and back into remaining weeks 3-4
						if (rev_w[0] > 0 or rev_w[1] > 0) or (sp_w[0] > 0 or sp_w[1] > 0):
							# Apply actuals for weeks 1-2
							w_revs[0] = rev_w[0] if rev_w[0] > 0 else w_revs[0]
							w_revs[1] = rev_w[1] if rev_w[1] > 0 else w_revs[1]
							w_spends[0] = sp_w[0] if sp_w[0] > 0 else w_spends[0]
							w_spends[1] = sp_w[1] if sp_w[1] > 0 else w_spends[1]
							# Compute remainders for weeks 3-4 to preserve monthly totals
							rem_rev = max(0.0, monthly_rev - (w_revs[0] + w_revs[1]))
							rem_sp = max(0.0, monthly_sp - (w_spends[0] + w_spends[1]))
							# Use 2024 shares for weeks 3-4 to split remainder
							s34 = max(1e-9, shares[2] + shares[3])
							w_revs[2] = rem_rev * (shares[2] / s34)
							w_revs[3] = rem_rev * (shares[3] / s34)
							# Allocate spend remainder proportionally to projected ROAS
							roas34 = [adj_roas[2], adj_roas[3]]
							need_sp34 = [w_revs[2] / max(roas34[0], 1e-9), w_revs[3] / max(roas34[1], 1e-9)]
							sum_need = sum(need_sp34) or 1.0
							w_spends[2] = rem_sp * (need_sp34[0] / sum_need)
							w_spends[3] = rem_sp * (need_sp34[1] / sum_need)
							# Adjust week 4 to absorb any rounding drift
							w_sp_correction = monthly_sp - sum(w_spends)
							w_rev_correction = monthly_rev - sum(w_revs)
							w_spends[3] += w_sp_correction
							w_revs[3] += w_rev_correction
							# Update adjusted ROAS
							adj_roas = [(wr / max(ws, 1e-9)) if ws > 0 else 0.0 for ws, wr in zip(w_spends, w_revs)]
					except Exception:
						pass
				# Final guard to correct tiny rounding drift on spend
				sp_correction = monthly_sp - sum(w_spends)
				if len(w_spends) > 0 and abs(sp_correction) > 0.5:
					w_spends[-1] += sp_correction
					adj_roas[-1] = w_revs[-1] / max(w_spends[-1], 1e-9)
				# 2024 weekly revenue (reference) using the same revenue shares
				r24m = float(rev_2024_q4_dict.get(ref_month, 0.0))
				rev24_weeks = [r24m * s for s in shares]
				# Normalize to monthly total in case of drift
				rev_norm = sum(rev24_weeks) or 1.0
				if rev_norm:
					rev24_weeks = [rv * (r24m / rev_norm) for rv in rev24_weeks]
				# Markdown table (2025 plan with 2024 weekly revenue reference)
				f.write(f"{month} – Weekly plan\n\n")
				f.write("Week | Spend | Revenue | ROAS | Spend/Rev % | 2024 Revenue\n")
				f.write("---|---:|---:|---:|---:|---:\n")
				for idx, (ws, wr, ar, r24w) in enumerate(zip(w_spends, w_revs, adj_roas, rev24_weeks), start=1):
					roas = (wr / ws) if ws > 0 else 0.0
					sprev = (ws / wr) if wr > 0 else 0.0
					f.write(f"W{idx} | ${ws:,.0f} | ${wr:,.0f} | {roas:.2f}x | {sprev*100:.1f}% | ${r24w:,.0f}\n")
				f.write("\n")
	except Exception:
		pass
	return csv_path, md_path


def _week_in_month_from_day(day: pd.Timestamp) -> int:
	"""Return 1-based week index within the month using simple 7-day buckets (days 1-7 => 1, 8-14 => 2, ...)."""
	try:
		return int((int(day.day) - 1) // 7) + 1
	except Exception:
		return 1


def compute_weekly_shares_from_shopify(shopify_daily: Optional[pd.DataFrame], month_yyyy_mm: str) -> List[float]:
	"""Compute weekly revenue shares for a given month from Shopify daily data using simple 7-day buckets.

	Returns a list of shares for weeks [1..4] summing to 1.0. Defaults to 4 equal weeks if data missing.
	"""
	if shopify_daily is None or shopify_daily.empty or "Day" not in shopify_daily.columns or "Total sales" not in shopify_daily.columns:
		return [0.25, 0.25, 0.25, 0.25]
	work = shopify_daily.copy()
	work["month"] = pd.to_datetime(work["Day"], errors="coerce").dt.strftime("%Y-%m")
	mask = work["month"] == month_yyyy_mm
	mon = work.loc[mask, ["Day", "Total sales"]].dropna()
	if mon.empty:
		return [0.25, 0.25, 0.25, 0.25]
	mon["week_in_month"] = pd.to_datetime(mon["Day"], errors="coerce").apply(_week_in_month_from_day)
	agg = mon.groupby("week_in_month")["Total sales"].sum().sort_index()
	vals = agg.to_list()
	if not vals:
		return [0.25, 0.25, 0.25, 0.25]
	# Normalize to shares
	total = float(sum(vals)) or 1.0
	shares = [float(v) / total for v in vals]
	# Coerce to exactly 4 weeks to keep reporting consistent
	n = len(shares)
	if n == 1:
		shares = [0.25, 0.25, 0.25, 0.25]
	elif n == 2:
		shares = [shares[0] / 2.0, shares[0] / 2.0, shares[1] / 2.0, shares[1] / 2.0]
	elif n == 3:
		mid = shares[1] / 2.0
		shares = [shares[0], mid, mid, shares[2]]
	elif n >= 5:
		# Keep first 3, merge the rest into the 4th
		merged = sum(shares[3:])
		shares = [shares[0], shares[1], shares[2], merged]
	# Ensure sum to 1.0 by adjusting last element
	if shares:
		resid = 1.0 - sum(shares)
		shares[-1] += resid
	return shares

# Build 2024 weekly revenue shares for September using 2025 OU "previous_year" column
def compute_weekly_shares_from_shopify_prev_year(shopify_2025_daily: Optional[pd.DataFrame], month_yyyy_mm_2025: str) -> List[float]:
	"""From 2025 OU file, use 'Total sales (previous_year)' to infer 2024 weekly revenue shares for a 2025 month.

	Returns [w1..w4] shares summing to 1.0; falls back to equal quarters on missing data.
	"""
	if shopify_2025_daily is None or shopify_2025_daily.empty:
		return [0.25, 0.25, 0.25, 0.25]
	cols = set(shopify_2025_daily.columns)
	if "Day" not in cols:
		return [0.25, 0.25, 0.25, 0.25]
	prev_col = None
	for cand in ["Total sales (previous_year)", "Total sales (previous year)", "Total sales prev year"]:
		if cand in cols:
			prev_col = cand
			break
	if prev_col is None:
		return [0.25, 0.25, 0.25, 0.25]
	try:
		w = shopify_2025_daily.copy()
		w["month"] = pd.to_datetime(w["Day"], errors="coerce").dt.strftime("%Y-%m")
		mask = w["month"] == month_yyyy_mm_2025
		seg = w.loc[mask, ["Day", prev_col]].dropna()
		if seg.empty:
			return [0.25, 0.25, 0.25, 0.25]
		seg["week_in_month"] = pd.to_datetime(seg["Day"], errors="coerce").apply(_week_in_month_from_day)
		agg = seg.groupby("week_in_month")[prev_col].sum().sort_index()
		vals = agg.to_list()
		if not vals:
			return [0.25, 0.25, 0.25, 0.25]
		total = float(sum(vals)) or 1.0
		shares = [float(v) / total for v in vals]
		# Coerce to exactly 4 weeks
		n = len(shares)
		if n == 1:
			shares = [0.25, 0.25, 0.25, 0.25]
		elif n == 2:
			shares = [shares[0] / 2.0, shares[0] / 2.0, shares[1] / 2.0, shares[1] / 2.0]
		elif n == 3:
			mid = shares[1] / 2.0
			shares = [shares[0], mid, mid, shares[2]]
		elif n >= 5:
			merged = sum(shares[3:])
			shares = [shares[0], shares[1], shares[2], merged]
		if shares:
			resid = 1.0 - sum(shares)
			shares[-1] += resid
		return shares
	except Exception:
		return [0.25, 0.25, 0.25, 0.25]

# Spend shares from Northbeam by week (for 2024 reference weekly spend/ROAS)
def compute_weekly_spend_shares_from_nb(df_nb: Optional[pd.DataFrame], month_yyyy_mm: str) -> List[float]:
	"""Compute weekly spend shares for a given month from a Northbeam daily export.

	Returns a list of shares for weeks [1..4] summing to 1.0. Defaults to revenue shares fallback if data missing.
	"""
	try:
		if df_nb is None or df_nb.empty:
			return [0.25, 0.25, 0.25, 0.25]
		work = df_nb.copy()
		work["month"] = work["date"].dt.strftime("%Y-%m")
		mask = work["month"] == month_yyyy_mm
		mon = work.loc[mask, ["date", "spend_num"]].dropna()
		if mon.empty:
			return [0.25, 0.25, 0.25, 0.25]
		mon["week_in_month"] = mon["date"].apply(_week_in_month_from_day)
		agg = mon.groupby("week_in_month")["spend_num"].sum().sort_index()
		vals = agg.to_list()
		if not vals:
			return [0.25, 0.25, 0.25, 0.25]
		total = float(sum(vals)) or 1.0
		shares = [float(v) / total for v in vals]
		# Coerce to exactly 4 weeks like revenue shares
		n = len(shares)
		if n == 1:
			shares = [0.25, 0.25, 0.25, 0.25]
		elif n == 2:
			shares = [shares[0] / 2.0, shares[0] / 2.0, shares[1] / 2.0, shares[1] / 2.0]
		elif n == 3:
			mid = shares[1] / 2.0
			shares = [shares[0], mid, mid, shares[2]]
		elif n >= 5:
			merged = sum(shares[3:])
			shares = [shares[0], shares[1], shares[2], merged]
		# Ensure sum to 1.0 by adjusting last element
		if shares:
			resid = 1.0 - sum(shares)
			shares[-1] += resid
		return shares
	except Exception:
		return [0.25, 0.25, 0.25, 0.25]


if __name__ == "__main__":
	main() 