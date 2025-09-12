#!/usr/bin/env python3
"""Generate LDW YoY report (2025 vs 2024) with channel deltas."""

from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime
import pandas as pd

from growthkit.reports.executive import MTDReportGenerator
import glob


def _run_exec_for_range(start: str, end: str):
	gen = MTDReportGenerator(start_date=start, end_date=end, output_dir="data/reports/weekly", choose_files=False, interactive=False)
	# Internals mirror run(), but we want to capture metrics rather than save the standard report directly
	gen._set_date_ranges()
	selected = gen._find_and_select_files()
	ga4_cur, shop_cur = gen.load_data_for_period(selected.get('current', {}), gen.mtd_date_range_current)
	ga4_prev, shop_prev = gen.load_data_for_period(selected.get('previous', {}), gen.mtd_date_range_previous)
	gen.ga4_data_current, gen.shopify_data_current = ga4_cur, shop_cur
	gen.ga4_data_previous, gen.shopify_data_previous = ga4_prev, shop_prev
	metrics_current = {
		'ga4': gen.calculate_ga4_metrics(ga4_cur),
		'shopify': gen.calculate_shopify_metrics(shop_cur, gen.mtd_date_range_current),
	}
	return gen, metrics_current


def _find_latest_l30_file() -> str | None:
	# Broaden match: include l30d, ytd, new_ytd; search recursively
	cands: list[str] = []
	for patt in [
		"data/ads/**/*sales_data-higher_dose_llc-*.csv",
		"data/ads/**/l30d-sales_data-higher_dose_llc-*.csv",
		"data/ads/**/ytd-sales_data-higher_dose_llc-*.csv",
		"data/ads/**/new_ytd_sales_data-higher_dose_llc-*.csv",
	]:
		cands.extend(glob.glob(patt, recursive=True))
	if not cands:
		return None
	cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
	return cands[0]


def _load_nb_df(gen: MTDReportGenerator) -> pd.DataFrame | None:
	# Prefer the NB DataFrame already loaded by the generator
	try:
		if isinstance(gen.ga4_data_current, dict) and 'northbeam' in gen.ga4_data_current:
			nb_df = gen.ga4_data_current['northbeam']
			if isinstance(nb_df, pd.DataFrame) and not nb_df.empty:
				return nb_df.copy()
	except Exception:
		pass
	# Fallback: read latest NB CSV on disk
	path = _find_latest_l30_file()
	if not path:
		return None
	try:
		return pd.read_csv(path, thousands=',')
	except Exception:
		return None


def _current_channel_table_from_l30(gen_cur: MTDReportGenerator) -> pd.DataFrame:
	"""Build 2025 channel table from latest L30 Northbeam export (spend + NB revenue)."""
	df = _load_nb_df(gen_cur)
	if df is None or df.empty:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	# Normalize date
	date_col = None
	for c in ['date','Date','day','Day']:
		if c in df.columns:
			date_col = c
			break
	# Remove duplicate columns which can cause df[col] to be a DataFrame
	df = df.loc[:, ~df.columns.duplicated()]
	if date_col is None:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	df = df.rename(columns={date_col: 'date'})
	df['date'] = pd.to_datetime(df['date'], errors='coerce')
	start_dt = gen_cur.mtd_date_range_current['start_dt']
	end_dt = gen_cur.mtd_date_range_current['end_dt']
	df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)].copy()
	# Map columns with strict preference to avoid picking unrelated 'revenue_per_visit' or 'ltv_' fields
	orig_cols = list(df.columns)
	lowered = {str(c).lower().strip(): c for c in orig_cols}
	# Spend
	if 'spend' in lowered:
		df = df.rename(columns={lowered['spend']: 'spend'})
	# Revenue: prefer attributed_rev, then web_revenue, then rev
	if 'attributed_rev' in lowered:
		df = df.rename(columns={lowered['attributed_rev']: 'attributed_rev'})
	elif 'web_revenue' in lowered:
		df = df.rename(columns={lowered['web_revenue']: 'attributed_rev'})
	elif 'rev' in lowered:
		df = df.rename(columns={lowered['rev']: 'attributed_rev'})
	# Transactions: prefer exact 'transactions', then 'web_transactions'
	if 'transactions' in lowered:
		df = df.rename(columns={lowered['transactions']: 'transactions'})
	elif 'web_transactions' in lowered:
		df = df.rename(columns={lowered['web_transactions']: 'transactions'})
	# Platform
	plat_key = None
	for k in ['breakdown_platform_northbeam','platform']:
		if k in lowered:
			plat_key = lowered[k]
			break
	if plat_key is not None:
		df = df.rename(columns={plat_key: 'breakdown_platform_northbeam'})
	# Deduplicate again after renaming
	df = df.loc[:, ~df.columns.duplicated()]
	# Filter accrual and positive spend when present
	if 'accounting_mode' in df.columns:
		df = df[df['accounting_mode'].str.contains('Accrual', case=False, na=False)]
	# Coerce numeric
	for c in ['spend','attributed_rev','transactions']:
		if c in df.columns:
			df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
	# We will compute 1D click revenue from attributed_rev filtered by attribution_model/window below
	# Keep rows that have either positive spend OR positive revenue/transactions
	if {'spend','attributed_rev','transactions'}.issubset(df.columns):
		mask_keep = (df['spend'] > 0) | (df['attributed_rev'] > 0) | (df['transactions'] > 0)
		df = df[mask_keep]
	# Channel mapping
	def _plat_to_channel(name: str) -> str | None:
		val = str(name).lower()
		if 'google' in val:
			return 'Paid Search'
		if 'bing' in val or 'microsoft' in val:
			return 'Bing Ads'
		if 'meta' in val or 'facebook' in val or 'instagram' in val:
			return 'Paid Social'
		if 'tiktok' in val:
			return 'TikTok Ads'
		if 'pinterest' in val:
			return 'Pinterest Ads'
		if 'applovin' in val:
			return 'AppLovin'
		if 'awin' in val:
			return 'Awin (Paid Affiliate)'
		if 'shopmy' in val:
			return 'ShopMyShelf (Influencer)'
		return None
	if 'breakdown_platform_northbeam' not in df.columns:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	df['__custom_channel__'] = df['breakdown_platform_northbeam'].apply(_plat_to_channel)
	grp = df.dropna(subset=['__custom_channel__']).groupby('__custom_channel__')
	agg_cols = [c for c in ['spend','attributed_rev','transactions'] if c in df.columns]
	if not agg_cols:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	agg = grp[agg_cols].sum().fillna(0)
	agg['ROAS'] = agg.apply(lambda r: (r.get('attributed_rev', 0) / r.get('spend', 0)) if r.get('spend', 0) else 0, axis=1)
	# CAC per channel when transactions present (Spend/Transactions)
	if 'transactions' in agg.columns:
		agg['CAC'] = agg.apply(lambda r: (r.get('spend', 0) / r.get('transactions', 0)) if r.get('transactions', 0) else 0, axis=1)
	else:
		agg['CAC'] = 0
	# 1D ROAS: derive from attributed_rev filtered by attribution_model/window
	if {'attribution_model','attribution_window'}.issubset(df.columns):
		mask_click = df['attribution_model'].astype(str).str.lower().str.contains('click', na=False) | df['attribution_window'].astype(str).str.lower().str.contains('click', na=False)
		mask_1d = df['attribution_window'].astype(str).str.lower().str.contains('1d', na=False) | df['attribution_window'].astype(str).str.lower().str.contains('1 day', na=False)
		df_1d = df[mask_click & mask_1d].copy()
	else:
		df_1d = df.iloc[0:0].copy()
	rev1d_by_ch = None
	if not df_1d.empty and 'attributed_rev' in df_1d.columns:
		rev1d_by_ch = (df_1d.dropna(subset=['__custom_channel__'])
					.groupby('__custom_channel__')['attributed_rev']
					.sum())
	# Default 0s, then fill available 1D rev / spend
	agg['ROAS_1D'] = 0
	if rev1d_by_ch is not None:
		for ch, rev1d in rev1d_by_ch.items():
			sp = float(agg.loc[ch, 'spend']) if 'spend' in agg.columns and ch in agg.index else float(agg.loc[ch, 'Spend']) if 'Spend' in agg.columns and ch in agg.index else 0.0
			if sp > 0:
				agg.loc[ch, 'ROAS_1D'] = rev1d / sp
	# Rename for consistency
	if 'spend' in agg.columns:
		agg = agg.rename(columns={'spend':'Spend'})
	if 'attributed_rev' in agg.columns:
		agg = agg.rename(columns={'attributed_rev':'Revenue'})
	if 'transactions' in agg.columns:
		agg = agg.rename(columns={'transactions':'Transactions'})
	# Keep known channels order if present
	desired = ['Paid Search','Paid Social','AppLovin','Bing Ads','Pinterest Ads','TikTok Ads','Awin (Paid Affiliate)','ShopMyShelf (Influencer)']
	agg = agg.reindex(desired, fill_value=0).combine_first(agg)
	agg.index.name = 'Channel'
	# Ensure expected columns exist
	for col in ['Revenue','Spend','ROAS','CAC','ROAS_1D','Transactions']:
		if col not in agg.columns:
			agg[col] = 0
	return agg[['Revenue','Spend','ROAS','CAC','ROAS_1D','Transactions']]


def _current_channel_table_from_l30_for_range(gen_cur: MTDReportGenerator, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> pd.DataFrame:
	"""Build 2025 channel table from latest L30 Northbeam export limited to [start_dt, end_dt]."""
	df = _load_nb_df(gen_cur)
	if df is None or df.empty:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	# Normalize date
	date_col = None
	for c in ['date','Date','day','Day']:
		if c in df.columns:
			date_col = c
			break
	df = df.loc[:, ~df.columns.duplicated()]
	if date_col is None:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	df = df.rename(columns={date_col: 'date'})
	df['date'] = pd.to_datetime(df['date'], errors='coerce')
	df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)].copy()
	# Accrual filter and positive-signal keep
	if 'accounting_mode' in df.columns:
		df = df[df['accounting_mode'].str.contains('Accrual', case=False, na=False)]
	# Map columns with strict preference to avoid unrelated 'revenue_per_visit' or 'ltv_' fields
	orig_cols = list(df.columns)
	lowered = {str(c).lower().strip(): c for c in orig_cols}
	# Spend
	if 'spend' in lowered:
		df = df.rename(columns={lowered['spend']: 'spend'})
	# Revenue: prefer attributed_rev, then web_revenue, then rev
	if 'attributed_rev' in lowered:
		df = df.rename(columns={lowered['attributed_rev']: 'attributed_rev'})
	elif 'web_revenue' in lowered:
		df = df.rename(columns={lowered['web_revenue']: 'attributed_rev'})
	elif 'rev' in lowered:
		df = df.rename(columns={lowered['rev']: 'attributed_rev'})
	# Transactions: prefer exact 'transactions', then 'web_transactions'
	if 'transactions' in lowered:
		df = df.rename(columns={lowered['transactions']: 'transactions'})
	elif 'web_transactions' in lowered:
		df = df.rename(columns={lowered['web_transactions']: 'transactions'})
	# Platform
	plat_key = None
	for k in ['breakdown_platform_northbeam','platform']:
		if k in lowered:
			plat_key = lowered[k]
			break
	if plat_key is not None:
		df = df.rename(columns={plat_key: 'breakdown_platform_northbeam'})
	df = df.loc[:, ~df.columns.duplicated()]
	for c in ['spend','attributed_rev','transactions']:
		if c in df.columns:
			df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
	if {'spend','attributed_rev','transactions'}.intersection(df.columns):
		mask_any = False
		if 'spend' in df.columns:
			mask_any = (df['spend'] > 0)
		if 'attributed_rev' in df.columns:
			mask_any = mask_any | (df['attributed_rev'] > 0) if isinstance(mask_any, pd.Series) else (df['attributed_rev'] > 0)
		if 'transactions' in df.columns:
			mask_any = mask_any | (df['transactions'] > 0) if isinstance(mask_any, pd.Series) else (df['transactions'] > 0)
		df = df[mask_any]
	# Channel mapping
	def _plat_to_channel(name: str) -> str | None:
		val = str(name).lower()
		if 'google' in val: return 'Paid Search'
		if 'bing' in val or 'microsoft' in val: return 'Bing Ads'
		if 'meta' in val or 'facebook' in val or 'instagram' in val: return 'Paid Social'
		if 'tiktok' in val: return 'TikTok Ads'
		if 'pinterest' in val: return 'Pinterest Ads'
		if 'applovin' in val: return 'AppLovin'
		if 'awin' in val: return 'Awin (Paid Affiliate)'
		if 'shopmy' in val: return 'ShopMyShelf (Influencer)'
		return None
	if 'breakdown_platform_northbeam' not in df.columns:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	df['__custom_channel__'] = df['breakdown_platform_northbeam'].apply(_plat_to_channel)
	grp = df.dropna(subset=['__custom_channel__']).groupby('__custom_channel__')
	agg_cols = [c for c in ['spend','attributed_rev','transactions'] if c in df.columns]
	if not agg_cols:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	agg = grp[agg_cols].sum().fillna(0)
	agg['ROAS'] = agg.apply(lambda r: (r.get('attributed_rev', 0) / r.get('spend', 0)) if r.get('spend', 0) else 0, axis=1)
	# 1D ROAS aggregation
	if {'attribution_model','attribution_window'}.issubset(df.columns):
		mask_click = df['attribution_model'].astype(str).str.lower().str.contains('click', na=False) | df['attribution_window'].astype(str).str.lower().str.contains('click', na=False)
		mask_1d = df['attribution_window'].astype(str).str.lower().str.contains('1d', na=False) | df['attribution_window'].astype(str).str.lower().str.contains('1 day', na=False)
		df_1d = df[mask_click & mask_1d].copy()
		rev1d_by_ch = None
		if not df_1d.empty and 'attributed_rev' in df_1d.columns:
			rev1d_by_ch = (df_1d.dropna(subset=['__custom_channel__'])
					.groupby('__custom_channel__')['attributed_rev']
					.sum())
		agg['ROAS_1D'] = 0
		if rev1d_by_ch is not None:
			for ch, rev1d in rev1d_by_ch.items():
				sp = float(agg.loc[ch, 'spend']) if 'spend' in agg.columns and ch in agg.index else float(agg.loc[ch, 'Spend']) if 'Spend' in agg.columns and ch in agg.index else 0.0
				if sp > 0:
					agg.loc[ch, 'ROAS_1D'] = rev1d / sp
	# Rename
	if 'spend' in agg.columns:
		agg = agg.rename(columns={'spend':'Spend'})
	if 'attributed_rev' in agg.columns:
		agg = agg.rename(columns={'attributed_rev':'Revenue'})
	if 'transactions' in agg.columns:
		agg = agg.rename(columns={'transactions':'Transactions'})
	# Ensure expected columns
	for col in ['Revenue','Spend','ROAS','Transactions','ROAS_1D']:
		if col not in agg.columns:
			agg[col] = 0
	return agg[['Revenue','Spend','ROAS','Transactions','ROAS_1D']]


def _current_channel_table_from_l30_cash(gen_cur: MTDReportGenerator) -> pd.DataFrame:
	"""Build 2025 channel table from Northbeam using Cash accounting for the current window."""
	df = _load_nb_df(gen_cur)
	if df is None or df.empty:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	# Normalize date
	date_col = None
	for c in ['date','Date','day','Day']:
		if c in df.columns:
			date_col = c
			break
	df = df.loc[:, ~df.columns.duplicated()]
	if date_col is None:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	df = df.rename(columns={date_col: 'date'})
	df['date'] = pd.to_datetime(df['date'], errors='coerce')
	start_dt = gen_cur.mtd_date_range_current['start_dt']
	end_dt = gen_cur.mtd_date_range_current['end_dt']
	df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)].copy()
	# Cash accounting filter
	if 'accounting_mode' in df.columns:
		df = df[df['accounting_mode'].astype(str).str.contains('Cash', case=False, na=False)]
	# Map columns with strict preference
	orig_cols = list(df.columns)
	lowered = {str(c).lower().strip(): c for c in orig_cols}
	if 'spend' in lowered:
		df = df.rename(columns={lowered['spend']: 'spend'})
	# Choose revenue source: prefer web_revenue, then rev, then attributed_rev
	rev_candidates = []
	if 'web_revenue' in lowered:
		rev_candidates.append(lowered['web_revenue'])
	if 'rev' in lowered:
		rev_candidates.append(lowered['rev'])
	if 'attributed_rev' in lowered:
		rev_candidates.append(lowered['attributed_rev'])
	chosen_rev = None
	for rc in rev_candidates:
		try:
			if pd.to_numeric(df[rc], errors='coerce').fillna(0).sum() > 0:
				chosen_rev = rc
				break
		except Exception:
			continue
	if chosen_rev is not None:
		df = df.rename(columns={chosen_rev: 'revenue_cash'})
	if 'transactions' in lowered:
		df = df.rename(columns={lowered['transactions']: 'transactions'})
	elif 'web_transactions' in lowered:
		df = df.rename(columns={lowered['web_transactions']: 'transactions'})
	plat_key = None
	for k in ['breakdown_platform_northbeam','platform']:
		if k in lowered:
			plat_key = lowered[k]
			break
	if plat_key is not None:
		df = df.rename(columns={plat_key: 'breakdown_platform_northbeam'})
	df = df.loc[:, ~df.columns.duplicated()]
	for c in ['spend','revenue_cash','transactions']:
		if c in df.columns:
			df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
	if {'spend','revenue_cash','transactions'}.intersection(df.columns):
		mask_any = False
		if 'spend' in df.columns:
			mask_any = (df['spend'] > 0)
		if 'revenue_cash' in df.columns:
			mask_any = mask_any | (df['revenue_cash'] > 0) if isinstance(mask_any, pd.Series) else (df['revenue_cash'] > 0)
		if 'transactions' in df.columns:
			mask_any = mask_any | (df['transactions'] > 0) if isinstance(mask_any, pd.Series) else (df['transactions'] > 0)
		df = df[mask_any]
	def _plat_to_channel(name: str) -> str | None:
		val = str(name).lower()
		if 'google' in val: return 'Paid Search'
		if 'bing' in val or 'microsoft' in val: return 'Bing Ads'
		if 'meta' in val or 'facebook' in val or 'instagram' in val: return 'Paid Social'
		if 'tiktok' in val: return 'TikTok Ads'
		if 'pinterest' in val: return 'Pinterest Ads'
		if 'applovin' in val: return 'AppLovin'
		if 'awin' in val: return 'Awin (Paid Affiliate)'
		if 'shopmy' in val: return 'ShopMyShelf (Influencer)'
		return None
	if 'breakdown_platform_northbeam' not in df.columns:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	df['__custom_channel__'] = df['breakdown_platform_northbeam'].apply(_plat_to_channel)
	agg_cols = [c for c in ['spend','revenue_cash','transactions'] if c in df.columns]
	if not agg_cols:
		return pd.DataFrame(columns=['Revenue', 'Spend', 'ROAS']).set_index(pd.Index([], name='Channel'))
	agg = df.dropna(subset=['__custom_channel__']).groupby('__custom_channel__')[agg_cols].sum().fillna(0)
	if 'transactions' in agg.columns:
		agg = agg.rename(columns={'transactions':'Transactions'})
	agg['ROAS'] = agg.apply(lambda r: (r.get('revenue_cash', 0) / r.get('spend', 0)) if r.get('spend', 0) else 0, axis=1)
	if 'spend' in agg.columns:
		agg = agg.rename(columns={'spend':'Spend'})
	if 'revenue_cash' in agg.columns:
		agg = agg.rename(columns={'revenue_cash':'Revenue'})
	# Keep known channels order if present
	desired = ['Paid Search','Paid Social','AppLovin','Bing Ads','Pinterest Ads','TikTok Ads','Awin (Paid Affiliate)','ShopMyShelf (Influencer)']
	agg = agg.reindex(desired, fill_value=0).combine_first(agg)
	# Ensure expected columns
	for col in ['Revenue','Spend','ROAS','Transactions']:
		if col not in agg.columns:
			agg[col] = 0
	return agg[['Revenue','Spend','ROAS','Transactions']]


def _shopify_orders_in_range(shopify_dict: dict, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> float:
	"""Sum Shopify Orders within [start_dt, end_dt]. Prefer Total sales over time; fallback to New vs returning or on-disk OU CSV."""
	# Prefer Total sales over time daily if available
	ts = shopify_dict.get('total_sales')
	if isinstance(ts, pd.DataFrame) and 'Day' in ts.columns and 'Orders' in ts.columns:
		_df = ts.copy()
		_df['Day'] = pd.to_datetime(_df['Day'], errors='coerce')
		m = (_df['Day'] >= start_dt) & (_df['Day'] <= end_dt)
		_sub = _df[m]
		if not _sub.empty:
			return float(pd.to_numeric(_sub['Orders'], errors='coerce').fillna(0).sum())
	# Fallback: New vs returning daily
	nr = shopify_dict.get('new_returning')
	if isinstance(nr, pd.DataFrame) and 'Day' in nr.columns and 'Orders' in nr.columns:
		_df = nr.copy()
		_df['Day'] = pd.to_datetime(_df['Day'], errors='coerce')
		m = (_df['Day'] >= start_dt) & (_df['Day'] <= end_dt)
		_sub = _df[m]
		if not _sub.empty:
			return float(pd.to_numeric(_sub['Orders'], errors='coerce').fillna(0).sum())
	# Final fallback: on-disk OU CSV for the year
	year = start_dt.year
	candidates = []
	for patt in [
		f"data/ads/**/Total sales over time - OU - {year}*.csv",
		f"data/ads/**/Total sales over time - OU - {year}.csv",
		f"data/ads/weekly-report-{year}-ads/Total sales over time - OU - {year}.csv",
	]:
		candidates.extend(glob.glob(patt, recursive=True))
	if candidates:
		candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
		try:
			_df = pd.read_csv(candidates[0])
			if 'Day' in _df.columns and 'Orders' in _df.columns:
				_df['Day'] = pd.to_datetime(_df['Day'], errors='coerce')
				m = (_df['Day'] >= start_dt) & (_df['Day'] <= end_dt)
				_sub = _df[m]
				if not _sub.empty:
					return float(pd.to_numeric(_sub['Orders'], errors='coerce').fillna(0).sum())
		except Exception:
			pass
	return 0.0


def _l30_1d_transactions(gen_cur: MTDReportGenerator) -> float:
	"""Sum 1-day click transactions in latest L30 within gen_cur window (accrual)."""
	l30 = _find_latest_l30_file()
	if not l30:
		return 0.0
	df = pd.read_csv(l30, thousands=',')
	# Normalize
	date_col = None
	for c in ['date','Date','day','Day']:
		if c in df.columns:
			date_col = c
			break
	df = df.loc[:, ~df.columns.duplicated()]
	if date_col is None:
		return 0.0
	df = df.rename(columns={date_col: 'date'})
	df['date'] = pd.to_datetime(df['date'], errors='coerce')
	start_dt = gen_cur.mtd_date_range_current['start_dt']
	end_dt = gen_cur.mtd_date_range_current['end_dt']
	df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)].copy()
	# Accrual filter
	if 'accounting_mode' in df.columns:
		df = df[df['accounting_mode'].str.contains('Accrual', case=False, na=False)]
	# Map transactions column if present
	trans_col = None
	for c in df.columns:
		low = str(c).lower().strip()
		if low in {'transactions','orders'}:
			trans_col = c
			break
	if trans_col is None:
		return 0.0
	df[trans_col] = pd.to_numeric(df[trans_col], errors='coerce').fillna(0)
	# 1D click filters
	if {'attribution_model','attribution_window'}.issubset(df.columns):
		mask_click = df['attribution_model'].astype(str).str.lower().str.contains('click', na=False) | df['attribution_window'].astype(str).str.lower().str.contains('click', na=False)
		mask_1d = df['attribution_window'].astype(str).str.lower().str.contains('1d', na=False) | df['attribution_window'].astype(str).str.lower().str.contains('1 day', na=False)
		df = df[mask_click & mask_1d]
	else:
		return 0.0
	return float(df[trans_col].sum())


def _products_revenue_series(shopify_dict: dict, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> pd.Series:
	"""Return a Series of product -> revenue within [start_dt, end_dt]. Tries loaded Shopify products, then falls back to on-disk CSVs."""
	# Try loaded products in dict under common keys
	candidates = []
	for key in ['products','shopify_products','total_sales_by_product','products_by_month']:
		obj = shopify_dict.get(key)
		if isinstance(obj, pd.DataFrame):
			candidates.append(obj)
	if not candidates:
		# Try to find OU product files on disk for the year
		year = start_dt.year
		paths = []
		for patt in [
			f"data/**/Total sales by product - OU - {year}*.csv",
			f"data/**/Total sales by product - {year}-01-01 - {year}-12-31*.csv",
			f"data/**/Total sales by product - {year}-01-01 - {year}-12-31.csv",
		]:
			paths.extend(glob.glob(patt, recursive=True))
		if paths:
			paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
			try:
				df = pd.read_csv(paths[0])
				candidates.append(df)
			except Exception:
				pass
	if not candidates:
		return pd.Series(dtype=float)
	# Use the first viable candidate
	df = candidates[0].copy()
	# Normalize date column
	date_col = None
	for c in ['Month','Day','Date']:
		if c in df.columns:
			date_col = c
			break
	if date_col is None:
		return pd.Series(dtype=float)
	df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
	msk = (df[date_col] >= start_dt) & (df[date_col] <= end_dt)
	sub = df[msk]
	if sub.empty:
		return pd.Series(dtype=float)
	# Columns
	name_col = 'Product title' if 'Product title' in sub.columns else None
	val_col = 'Total sales' if 'Total sales' in sub.columns else None
	if not name_col or not val_col:
		return pd.Series(dtype=float)
	sub[val_col] = pd.to_numeric(sub[val_col], errors='coerce').fillna(0)
	series = sub.groupby(name_col)[val_col].sum().sort_values(ascending=False)
	return series


def _find_2024_platform_files() -> tuple[str | None, str | None]:
	meta = None
	google = None
	candidates = glob.glob("data/ads/weekly-report-2024-ads/*.csv")
	for p in candidates:
		name = os.path.basename(p).lower()
		if 'meta' in name or 'facebook' in name:
			meta = p
		if 'google' in name:
			google = p
	return meta, google


def _load_meta_spend(meta_csv: str, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> float:
	df = pd.read_csv(meta_csv)
	# Expect columns: Day, Amount spent (USD)
	if 'Day' not in df.columns:
		return 0.0
	df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
	mask = (df['Day'] >= start_dt) & (df['Day'] <= end_dt)
	sub = df[mask]
	col = next((c for c in df.columns if 'amount spent' in c.lower()), None)
	if not col:
		return 0.0
	return pd.to_numeric(sub[col], errors='coerce').fillna(0).sum()


def _load_google_spend(google_csv: str, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> float:
	df = pd.read_csv(google_csv, skiprows=2)
	# Expect columns: Day, Cost
	if 'Day' not in df.columns or 'Cost' not in df.columns:
		return 0.0
	df['Day'] = pd.to_datetime(df['Day'], errors='coerce')
	mask = (df['Day'] >= start_dt) & (df['Day'] <= end_dt)
	sub = df[mask]
	return pd.to_numeric(sub['Cost'], errors='coerce').fillna(0).sum()


def _prev_channel_table_with_platform(gen_prev: MTDReportGenerator) -> pd.DataFrame:
	"""Build a 2024 channel table using GA4 revenue and platform spend (Meta/Google)."""
	start_dt = gen_prev.mtd_date_range_current['start_dt']
	end_dt = gen_prev.mtd_date_range_current['end_dt']
	# Revenue by channel from GA4 channel group
	rev_by_ch = {}
	cg = gen_prev.ga4_data_current.get('channel_group')
	if isinstance(cg, pd.DataFrame) and not cg.empty:
		df = cg.copy()
		if not pd.api.types.is_datetime64_any_dtype(df['Date']):
			df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
		mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt)
		sub = df[mask]
		col = 'Default channel group' if 'Default channel group' in sub.columns else None
		if col and 'Total revenue' in sub.columns:
			grp = sub.groupby(col)['Total revenue'].sum()
			rev_by_ch = grp.to_dict()
	# Spend from platform files
	meta_csv, google_csv = _find_2024_platform_files()
	meta_spend = _load_meta_spend(meta_csv, start_dt, end_dt) if meta_csv else 0.0
	goog_spend = _load_google_spend(google_csv, start_dt, end_dt) if google_csv else 0.0
	# Assemble DataFrame for Paid Social and Paid Search
	rows = []
	for ch, spend in [('Paid Social', meta_spend), ('Paid Search', goog_spend)]:
		rev = float(rev_by_ch.get(ch, 0.0))
		roas = (rev / spend) if spend else 0.0
		rows.append({'Channel': ch, 'Spend': spend, 'Revenue': rev, 'ROAS': roas})
	return pd.DataFrame(rows).set_index('Channel')

def _prev_channel_table_for_range(gen_prev: MTDReportGenerator, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> pd.DataFrame:
	"""Same as _prev_channel_table_with_platform but for an explicit custom date range using channel_group_full."""
	# Revenue by channel from GA4 channel group FULL
	rev_by_ch = {}
	cg_full = gen_prev.ga4_data_current.get('channel_group_full')
	if cg_full is None or (hasattr(cg_full, 'empty') and cg_full.empty):
		cg_full = gen_prev.ga4_data_current.get('channel_group')
	if isinstance(cg_full, pd.DataFrame) and not cg_full.empty:
		df = cg_full.copy()
		if not pd.api.types.is_datetime64_any_dtype(df['Date']):
			df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
		mask = (df['Date'] >= start_dt) & (df['Date'] <= end_dt)
		sub = df[mask]
		col = None
		for candidate in ['Default channel group', 'Session default channel group']:
			if candidate in sub.columns:
				col = candidate
				break
		if col and 'Total revenue' in sub.columns:
			grp = sub.groupby(col)['Total revenue'].sum()
			rev_by_ch = grp.to_dict()
	# Spend from platform files in same window
	meta_csv, google_csv = _find_2024_platform_files()
	meta_spend = _load_meta_spend(meta_csv, start_dt, end_dt) if meta_csv else 0.0
	goog_spend = _load_google_spend(google_csv, start_dt, end_dt) if google_csv else 0.0
	rows = []
	for ch, spend in [('Paid Social', meta_spend), ('Paid Search', goog_spend)]:
		rev = float(rev_by_ch.get(ch, 0.0))
		roas = (rev / spend) if spend else 0.0
		rows.append({'Channel': ch, 'Spend': spend, 'Revenue': rev, 'ROAS': roas})
	return pd.DataFrame(rows).set_index('Channel')


def _channel_table_from_metrics(gen: MTDReportGenerator, metrics: dict) -> pd.DataFrame:
	# Prefer precomputed custom-channel table from metrics
	ga_metrics = metrics.get('ga4', {})
	df_curr = ga_metrics.get('custom_channel_performance')
	if isinstance(df_curr, pd.DataFrame) and not df_curr.empty:
		# Ensure expected columns and derive ROAS if spend available
		df = df_curr.copy()
		if 'Total revenue' in df.columns:
			df.rename(columns={'Total revenue': 'Revenue'}, inplace=True)
		if 'spend' not in df.columns:
			df['spend'] = 0
		df['ROAS'] = df.apply(lambda r: (r['Revenue'] / r['spend']) if r.get('spend', 0) else 0, axis=1)
		df.rename(columns={'spend': 'Spend'}, inplace=True)
		df.index.name = 'Channel'
		return df[['Revenue', 'Spend', 'ROAS']]

	# Fallback: recompute from raw GA4 data on the generator instance
	ga4_curr = getattr(gen, 'ga4_data_current', {}) or {}
	src_df = ga4_curr.get('source_medium')
	if src_df is None or src_df.empty:
		return pd.DataFrame(columns=['Channel', 'Spend', 'Revenue', 'ROAS']).set_index('Channel')
	# Find source column
	src_col = None
	for col in src_df.columns:
		if str(col).lower().startswith('session source'):
			src_col = col
			break
	if src_col is None or 'Total revenue' not in src_df.columns:
		return pd.DataFrame(columns=['Channel', 'Spend', 'Revenue', 'ROAS']).set_index('Channel')
	def _map_src(val: str) -> str | None:
		s = str(val).lower()
		if 'awin' in s:
			return 'Awin (Paid Affiliate)'
		if 'shopmy' in s:
			return 'ShopMyShelf (Influencer)'
		if 'applovin' in s:
			return 'AppLovin'
		if 'bing / cpc' in s or 'bing ads' in s or 'microsoft' in s:
			return 'Bing Ads'
		if 'pinterest' in s:
			return 'Pinterest Ads'
		if 'tiktok' in s:
			return 'TikTok Ads'
		if 'google / cpc' in s or 'google ads' in s:
			return 'Paid Search'
		if 'facebook' in s or 'instagram' in s or 'meta' in s:
			return 'Paid Social'
		return None
	df = src_df.copy()
	df['__custom_channel__'] = df[src_col].apply(_map_src)
	revenue_df = (
		df.dropna(subset=['__custom_channel__'])
			.groupby('__custom_channel__')
			.agg({'Total revenue': 'sum'})
	)
	# Attach spend from Northbeam if present
	spend_df = None
	nb = ga4_curr.get('northbeam')
	if nb is not None and not nb.empty:
		platform_col = 'breakdown_platform_northbeam' if 'breakdown_platform_northbeam' in nb.columns else (
			'platform' if 'platform' in nb.columns else None
		)
		if platform_col is not None:
			def _plat_map(val: str) -> str | None:
				s = str(val).lower()
				if 'google' in s:
					return 'Paid Search'
				if 'bing' in s or 'microsoft' in s:
					return 'Bing Ads'
				if 'meta' in s or 'facebook' in s or 'instagram' in s:
					return 'Paid Social'
				if 'tiktok' in s:
					return 'TikTok Ads'
				if 'pinterest' in s:
					return 'Pinterest Ads'
				if 'applovin' in s:
					return 'AppLovin'
				if 'awin' in s:
					return 'Awin (Paid Affiliate)'
				if 'shopmy' in s:
					return 'ShopMyShelf (Influencer)'
				return None
			nb2 = nb.copy()
			if 'date' in nb2.columns:
				m = (nb2['date'] >= gen.mtd_date_range_current['start_dt']) & (nb2['date'] <= gen.mtd_date_range_current['end_dt'])
				nb2 = nb2[m]
			if 'accounting_mode' in nb2.columns:
				nb2 = nb2[nb2['accounting_mode'].str.contains('Accrual', case=False, na=False)]
			if 'spend' in nb2.columns:
				nb2['spend'] = pd.to_numeric(nb2['spend'], errors='coerce').fillna(0)
				nb2 = nb2[nb2['spend'] > 0]
			nb2['__custom_channel__'] = nb2[platform_col].apply(_plat_map)
			spend_df = (
				nb2.dropna(subset=['__custom_channel__'])
					.groupby('__custom_channel__')
					.agg({'spend': 'sum'})
			)
	merged = revenue_df.join(spend_df, how='left') if spend_df is not None else revenue_df
	merged = merged.fillna(0)
	merged['ROAS'] = merged.apply(lambda r: r['Total revenue'] / r['spend'] if r.get('spend', 0) else 0, axis=1)
	merged.rename(columns={'Total revenue': 'Revenue', 'spend': 'Spend'}, inplace=True)
	merged.index.name = 'Channel'
	return merged


def main():
	# Conservative assumption: 2025 VIP 8/27 through 9/02; LY match 8/26 through 9/02
	cur_start = os.environ.get('LDW_2025_START', '2025-08-27')
	cur_end = os.environ.get('LDW_2025_END', '2025-09-03')
	ly_start = os.environ.get('LDW_2024_START', '2024-08-23')
	ly_end = os.environ.get('LDW_2024_END', '2024-09-04')

	# Run current period
	gen_cur, metrics_cur = _run_exec_for_range(cur_start, cur_end)
	# Override the date range explicitly for title context
	gen_cur.mtd_date_range_current['start'] = cur_start
	gen_cur.mtd_date_range_current['end'] = cur_end
	gen_cur.mtd_date_range_current['start_dt'] = pd.to_datetime(cur_start)
	gen_cur.mtd_date_range_current['end_dt'] = pd.to_datetime(cur_end)

	# Run previous period (LY)
	gen_prev, metrics_prev = _run_exec_for_range(ly_start, ly_end)
	gen_prev.mtd_date_range_current['start'] = ly_start
	gen_prev.mtd_date_range_current['end'] = ly_end
	gen_prev.mtd_date_range_current['start_dt'] = pd.to_datetime(ly_start)
	gen_prev.mtd_date_range_current['end_dt'] = pd.to_datetime(ly_end)

	# Build channel tables and deltas
	t_cur = _current_channel_table_from_l30(gen_cur)
	# For previous year, construct using GA4 revenue and platform spend (Meta + Google)
	t_prev = _prev_channel_table_with_platform(gen_prev)
	all_channels = sorted(set(t_cur.index.tolist()) | set(t_prev.index.tolist()))

	rows = []
	for ch in all_channels:
		spend_cur = float(t_cur.loc[ch, 'Spend']) if ch in t_cur.index else 0.0
		rev_cur = float(t_cur.loc[ch, 'Revenue']) if ch in t_cur.index else 0.0
		roas_cur = float(t_cur.loc[ch, 'ROAS']) if ch in t_cur.index else (rev_cur / spend_cur if spend_cur else 0.0)
		cac_cur = float(t_cur.loc[ch, 'CAC']) if ('CAC' in t_cur.columns and ch in t_cur.index) else None
		roas1d_cur = float(t_cur.loc[ch, 'ROAS_1D']) if ('ROAS_1D' in t_cur.columns and ch in t_cur.index) else None
		spend_prev = float(t_prev.loc[ch, 'Spend']) if ch in t_prev.index else 0.0
		rev_prev = float(t_prev.loc[ch, 'Revenue']) if ch in t_prev.index else 0.0
		roas_prev = float(t_prev.loc[ch, 'ROAS']) if ch in t_prev.index else (rev_prev / spend_prev if spend_prev else 0.0)
		cac_prev = float(t_prev.loc[ch, 'CAC']) if ('CAC' in t_prev.columns and ch in t_prev.index) else None
		rows.append({
			'Channel': ch,
			'Spend (2025)': spend_cur,
			'Spend (2024)': spend_prev,
			'Spend Δ%': ((spend_cur - spend_prev) / spend_prev * 100) if spend_prev else None,
			'Revenue (2025)': rev_cur,
			'Revenue (2024)': rev_prev,
			'Revenue Δ%': ((rev_cur - rev_prev) / rev_prev * 100) if rev_prev else None,
			'ROAS (2025)': roas_cur,
			'ROAS (2024)': roas_prev,
			'1D ROAS (2025)': roas1d_cur,
			'CAC (2025)': cac_cur,
			'CAC (2024)': cac_prev,
			'ROAS Δ': (roas_cur - roas_prev),
		})
	delta_df = pd.DataFrame(rows)
	if delta_df.empty:
		# Write a minimal report noting missing data and exit gracefully
		out_dir = Path('data/reports/weekly')
		out_dir.mkdir(parents=True, exist_ok=True)
		fname = f"ldw-yoy-report-{datetime.now().strftime('%Y-%m-%d')}.md"
		out_path = out_dir / fname
		with open(out_path, 'w', encoding='utf-8') as f:
			f.write("# Labor Day Weekend YoY Report (2025 vs 2024)\n\nData unavailable to compute channel-level deltas. Please ensure GA4 source/medium and Northbeam files are present for both periods.\n")
		print(f"⚠️ Wrote placeholder report due to missing channel data: {out_path}")
		return

	delta_df = delta_df.set_index('Channel').sort_values('Revenue (2025)', ascending=False)

	# Compose markdown report
	out_dir = Path('data/reports/weekly')
	out_dir.mkdir(parents=True, exist_ok=True)
	fname = f"ldw-yoy-report-{datetime.now().strftime('%Y-%m-%d')}.md"
	out_path = out_dir / fname

	def _fmt_money(v: float | None) -> str:
		if v is None:
			return 'N/A'
		return f"${v:,.0f}"
	def _fmt_pct(v: float | None) -> str:
		if v is None:
			return 'N/A'
		return f"{v:+.1f}%"
	def _fmt_roas(v: float | None) -> str:
		if v is None:
			return 'N/A'
		return f"{v:.2f}"
	def _fmt_ratio(v: float | None) -> str:
		# Generic ratio formatter, 2 decimals
		if v is None:
			return 'N/A'
		return f"{v:.2f}"

	def _fmt_money2(v: float | None) -> str:
		# like _fmt_money but accepts None
		return _fmt_money(v if v is not None else None)

	head = (
		f"# Labor Day Weekend YoY Report (2025 vs 2024)\n\n"
		f"**2025 Period:** {cur_start} → {cur_end}  \n"
		f"**2024 Period:** {ly_start} → {ly_end}  \n\n---\n\n"
	)

	# Clarify channel taxonomy
	md_note = (
		"> Note: 'Paid Social' aggregates Meta (Facebook/Instagram). TikTok, Pinterest, etc. are shown separately when present. 1D ROAS is computed from 1‑day revenue in the 2025 L30 export when available.\n\n"
	)
	head += md_note

	# Executive bullets from Shopify totals when available
	total_2025 = metrics_cur.get('shopify', {}).get('total_revenue', 0) or 0
	total_2024 = 0  # We don't have a Shopify daily 2024 file here; leave as 0 unless GA4 total is desired
	orders_2025 = metrics_cur.get('shopify', {}).get('total_orders', 0) or 0
	blended_roas_2025 = 0.0
	if 'northbeam' in gen_cur.ga4_data_current:
		nb = gen_cur.ga4_data_current['northbeam']
		if 'date' in nb.columns and 'spend' in nb.columns:
			nb2 = nb.copy()
			nb2 = nb2[(nb2['date'] >= gen_cur.mtd_date_range_current['start_dt']) & (nb2['date'] <= gen_cur.mtd_date_range_current['end_dt'])]
			if 'accounting_mode' in nb2.columns:
				nb2 = nb2[nb2['accounting_mode'].str.contains('Accrual', case=False, na=False)]
			nb2['spend'] = pd.to_numeric(nb2['spend'], errors='coerce').fillna(0)
			spend_2025 = float(nb2['spend'].sum())
			blended_roas_2025 = (total_2025 / spend_2025) if spend_2025 else 0.0

	# Build channel delta markdown table
	md = head

	# ------------------------------
	# YoY Summary (2025 vs 2024)
	# ------------------------------
	# Totals needed for summary
	tot_spend_2025 = t_cur['Spend'].sum() if not t_cur.empty else 0.0
	tot_spend_2024 = t_prev['Spend'].sum() if not t_prev.empty else 0.0
	# Shopify revenue helper (Total sales over time daily preferred; fallback to New vs Returning)
	def _shopify_rev_in_range(shopify_dict: dict, start_dt: pd.Timestamp, end_dt: pd.Timestamp) -> float:
		# Prefer Total sales over time daily if available
		ts = shopify_dict.get('total_sales')
		if isinstance(ts, pd.DataFrame) and 'Day' in ts.columns and 'Total sales' in ts.columns:
			_df = ts.copy()
			_df['Day'] = pd.to_datetime(_df['Day'], errors='coerce')
			m = (_df['Day'] >= start_dt) & (_df['Day'] <= end_dt)
			_sub = _df[m]
			if not _sub.empty:
				return float(pd.to_numeric(_sub['Total sales'], errors='coerce').fillna(0).sum())
		# Fallback: sum New vs Returning daily
		nr = shopify_dict.get('new_returning')
		if isinstance(nr, pd.DataFrame) and 'Day' in nr.columns and 'Total sales' in nr.columns:
			_df = nr.copy()
			_df['Day'] = pd.to_datetime(_df['Day'], errors='coerce')
			m = (_df['Day'] >= start_dt) & (_df['Day'] <= end_dt)
			_sub = _df[m]
			if not _sub.empty:
				return float(pd.to_numeric(_sub['Total sales'], errors='coerce').fillna(0).sum())
		# Final fallback: try to locate a daily 'OU' Shopify file on disk for the given year
		year = start_dt.year
		candidates = []
		for patt in [
			f"data/ads/**/Total sales over time - OU - {year}*.csv",
			f"data/ads/**/Total sales over time - OU - {year}.csv",
			f"data/ads/weekly-report-{year}-ads/Total sales over time - OU - {year}.csv",
		]:
			candidates.extend(glob.glob(patt, recursive=True))
		if candidates:
			candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
			try:
				_df = pd.read_csv(candidates[0])
				if 'Day' in _df.columns and 'Total sales' in _df.columns:
					_df['Day'] = pd.to_datetime(_df['Day'], errors='coerce')
					m = (_df['Day'] >= start_dt) & (_df['Day'] <= end_dt)
					_sub = _df[m]
					if not _sub.empty:
						return float(pd.to_numeric(_sub['Total sales'], errors='coerce').fillna(0).sum())
			except Exception:
				pass
		return 0.0
	# 2025 total revenue from Shopify (current period)
	cur_start_dt = gen_cur.mtd_date_range_current['start_dt']
	cur_end_dt = gen_cur.mtd_date_range_current['end_dt']
	total_rev_2025 = _shopify_rev_in_range(gen_cur.shopify_data_current, cur_start_dt, cur_end_dt)
	# 2024 total revenue from Shopify (filter to LY window)
	start_prev = gen_prev.mtd_date_range_current['start_dt']
	end_prev = gen_prev.mtd_date_range_current['end_dt']
	total_rev_2024 = _shopify_rev_in_range(gen_prev.shopify_data_current, start_prev, end_prev)
	# ROAS calculations
	roas_2025 = (total_rev_2025 / tot_spend_2025) if tot_spend_2025 else 0.0
	roas_2024 = (total_rev_2024 / tot_spend_2024) if tot_spend_2024 else 0.0
	# 1D ROAS 2025 (spend-weighted): sum(ROAS_1D * Spend)/sum(Spend)
	total_rev1d_2025 = 0.0
	if 'ROAS_1D' in t_cur.columns:
		for ch, row in t_cur.iterrows():
			sp = float(row.get('Spend', 0) or 0)
			roas1d = float(row.get('ROAS_1D', 0) or 0)
			total_rev1d_2025 += sp * roas1d
	roas1d_2025 = (total_rev1d_2025 / tot_spend_2025) if tot_spend_2025 else 0.0
	# True Blended CAC (Spend/Orders) using Shopify Orders
	orders_2025_true = _shopify_orders_in_range(gen_cur.shopify_data_current, cur_start_dt, cur_end_dt)
	orders_2024_true = _shopify_orders_in_range(gen_prev.shopify_data_current, start_prev, end_prev)
	blended_cac_true_2025 = (tot_spend_2025 / orders_2025_true) if orders_2025_true else None
	blended_cac_true_2024 = (tot_spend_2024 / orders_2024_true) if orders_2024_true else None

	def _fmt_delta(pct: float | None) -> str:
		return _fmt_pct(pct) if pct is not None else 'N/A'

	spend_yoy = ((tot_spend_2025 - tot_spend_2024) / tot_spend_2024 * 100) if tot_spend_2024 else None
	rev_yoy = ((total_rev_2025 - total_rev_2024) / total_rev_2024 * 100) if total_rev_2024 else None
	roas_yoy = ((roas_2025 - roas_2024) / roas_2024 * 100) if roas_2024 else None
	cac_yoy = ((blended_cac_true_2025 - blended_cac_true_2024) / blended_cac_true_2024 * 100) if (blended_cac_true_2025 is not None and blended_cac_true_2024) else None

	md += "## YoY Summary (2025 vs 2024)\n\n"
	md += f"- **Spend:** {_fmt_money(tot_spend_2025)} ( {_fmt_money(tot_spend_2024)} | {_fmt_delta(spend_yoy)} )\n"
	md += f"- **Revenue:** {_fmt_money(total_rev_2025)} ( {_fmt_money(total_rev_2024)} | {_fmt_delta(rev_yoy)} )\n"
	md += f"- **ROAS:** {_fmt_roas(roas_2025)} ( {_fmt_roas(roas_2024)} | {_fmt_delta(roas_yoy)} )\n"
	md += f"- **Blended CAC:** {_fmt_money(blended_cac_true_2025)} ( {_fmt_money(blended_cac_true_2024)} | {_fmt_delta(cac_yoy)} )\n\n"

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
	# Total row for main channel table
	total_rev_2025_channels = float(t_cur['Revenue'].sum()) if not t_cur.empty else 0.0
	total_rev_2024_channels = float(t_prev['Revenue'].sum()) if not t_prev.empty else 0.0
	total_spend_delta = ((tot_spend_2025 - tot_spend_2024) / tot_spend_2024 * 100) if tot_spend_2024 else None
	total_rev_delta = ((total_rev_2025_channels - total_rev_2024_channels) / total_rev_2024_channels * 100) if total_rev_2024_channels else None
	total_roas_2025 = (total_rev_2025_channels / tot_spend_2025) if tot_spend_2025 else 0.0
	total_roas_2024 = (total_rev_2024_channels / tot_spend_2024) if tot_spend_2024 else 0.0
	total_cac_2025 = None
	if 'Transactions' in t_cur.columns and t_cur['Transactions'].sum() > 0:
		total_cac_2025 = tot_spend_2025 / t_cur['Transactions'].sum()
	total_cac_2024 = None
	md += (
		f"| Total | {_fmt_money(tot_spend_2025)} | {_fmt_money(tot_spend_2024)} | {_fmt_pct(total_spend_delta)} | "
		f"{_fmt_money(total_rev_2025_channels)} | {_fmt_money(total_rev_2024_channels)} | {_fmt_pct(total_rev_delta)} | "
		f"{_fmt_roas(total_roas_2025)} | {_fmt_roas(total_roas_2024)} | "
		f"{_fmt_money2(total_cac_2025)} | {_fmt_money2(total_cac_2024)} |\n"
	)

	# Totals line
	spend_delta = ((tot_spend_2025 - tot_spend_2024) / tot_spend_2024 * 100) if tot_spend_2024 else None
	md += "\n**Totals:** "
	md += f"Spend {_fmt_money(tot_spend_2025)} ( {_fmt_money(tot_spend_2024)} | {_fmt_delta(spend_delta)} ), "
	md += f"Revenue {_fmt_money(total_rev_2025)} ( {_fmt_money(total_rev_2024)} | {_fmt_delta(rev_yoy)} ), "
	md += f"ROAS {_fmt_roas(roas_2025)} ( {_fmt_roas(roas_2024)} | {_fmt_delta(roas_yoy)} )"
	md += f" | Blended CAC {_fmt_money(blended_cac_true_2025)} ( {_fmt_money(blended_cac_true_2024)} | {_fmt_delta(cac_yoy)} )\n\n"

	# ---------------------------------------
	# Northbeam Channel Performance (Cash accounting, 2025)
	# ---------------------------------------
	t_cash = _current_channel_table_from_l30_cash(gen_cur)
	if not t_cash.empty:
		md += "## Northbeam Channel Performance (Cash Accounting, 2025)\n\n"
		md += "| Channel | Spend (Cash) | Revenue (Cash) | ROAS (Cash) | CAC (Cash) |\n"
		md += "|---|---:|---:|---:|---:|\n"
		for ch, r in t_cash.iterrows():
			cac_val = (r['Spend'] / r['Transactions']) if r.get('Transactions', 0) else None
			md += (
				f"| {ch} | {_fmt_money(r['Spend'])} | {_fmt_money(r['Revenue'])} | {_fmt_roas(r['ROAS'])} | {_fmt_money2(cac_val)} |\n"
			)
		# Total row
		tc_spend = float(t_cash['Spend'].sum())
		tc_rev = float(t_cash['Revenue'].sum())
		tc_roas = (tc_rev / tc_spend) if tc_spend else 0.0
		tc_orders = float(t_cash['Transactions'].sum()) if 'Transactions' in t_cash.columns else 0.0
		tc_cac = (tc_spend / tc_orders) if tc_orders else None
		md += (
			f"| Total | {_fmt_money(tc_spend)} | {_fmt_money(tc_rev)} | {_fmt_roas(tc_roas)} | {_fmt_money2(tc_cac)} |\n\n"
		)

	# ---------------------------------------
	# Same-window 2024 (2024-08-27 → 2024-09-02)
	# ---------------------------------------
	sw24_start = pd.to_datetime('2024-08-27')
	sw24_end = pd.to_datetime('2024-09-03')
	sw25_start = pd.to_datetime('2025-08-27')
	sw25_end = pd.to_datetime('2025-09-03')
	sw_prev = _prev_channel_table_for_range(gen_prev, sw24_start, sw24_end)
	# 2025 range-specific NB aggregation for the same window
	sw_cur = _current_channel_table_from_l30_for_range(gen_cur, sw25_start, sw25_end)
	# Shopify revenue and Orders for same window (2024)
	sw_rev_2024 = _shopify_rev_in_range(gen_prev.shopify_data_current, sw24_start, sw24_end)
	sw_spend_2024 = float(sw_prev['Spend'].sum()) if not sw_prev.empty else 0.0
	sw_roas_2024 = (sw_rev_2024 / sw_spend_2024) if sw_spend_2024 else 0.0
	sw_orders_2024 = _shopify_orders_in_range(gen_prev.shopify_data_current, sw24_start, sw24_end)
	sw_cac_2024 = (sw_spend_2024 / sw_orders_2024) if sw_orders_2024 else None
	# 2025 metrics for the same window (current window already matches, but compute explicitly)
	sw_rev_2025 = _shopify_rev_in_range(gen_cur.shopify_data_current, sw25_start, sw25_end)
	# Spend from range-specific NB aggregation (sw_cur)
	sw_spend_2025 = float(sw_cur['Spend'].sum()) if not sw_cur.empty else 0.0
	sw_roas_2025 = (sw_rev_2025 / sw_spend_2025) if sw_spend_2025 else 0.0
	sw_orders_2025 = _shopify_orders_in_range(gen_cur.shopify_data_current, sw25_start, sw25_end)
	sw_cac_2025 = (sw_spend_2025 / sw_orders_2025) if sw_orders_2025 else None
	# Deltas
	sw_spend_yoy = ((sw_spend_2025 - sw_spend_2024) / sw_spend_2024 * 100) if sw_spend_2024 else None
	sw_rev_yoy = ((sw_rev_2025 - sw_rev_2024) / sw_rev_2024 * 100) if sw_rev_2024 else None
	sw_roas_yoy = ((sw_roas_2025 - sw_roas_2024) / sw_roas_2024 * 100) if sw_roas_2024 else None
	sw_cac_yoy = ((sw_cac_2025 - sw_cac_2024) / sw_cac_2024 * 100) if (sw_cac_2025 is not None and sw_cac_2024) else None

	# Build same-window comparison table (channels)
	sw_all_channels = sorted(set(t_cur.index.tolist()) | set(sw_prev.index.tolist()))
	sw_rows = []
	for ch in sw_all_channels:
		spend_25 = float(t_cur.loc[ch, 'Spend']) if ch in t_cur.index else 0.0
		rev_25 = float(t_cur.loc[ch, 'Revenue']) if ch in t_cur.index else 0.0
		roas_25 = float(t_cur.loc[ch, 'ROAS']) if ch in t_cur.index else (rev_25 / spend_25 if spend_25 else 0.0)
		spend_24 = float(sw_prev.loc[ch, 'Spend']) if ch in sw_prev.index else 0.0
		rev_24 = float(sw_prev.loc[ch, 'Revenue']) if ch in sw_prev.index else 0.0
		roas_24 = float(sw_prev.loc[ch, 'ROAS']) if ch in sw_prev.index else (rev_24 / spend_24 if spend_24 else 0.0)
		sw_rows.append({
			'Channel': ch,
			'Spend (2025)': spend_25,
			'Spend (2024)': spend_24,
			'Spend Δ%': ((spend_25 - spend_24) / spend_24 * 100) if spend_24 else None,
			'Revenue (2025)': rev_25,
			'Revenue (2024)': rev_24,
			'Revenue Δ%': ((rev_25 - rev_24) / rev_24 * 100) if rev_24 else None,
			'ROAS (2025)': roas_25,
			'ROAS (2024)': roas_24,
		})
	sw_delta_df = pd.DataFrame(sw_rows).set_index('Channel') if sw_rows else pd.DataFrame()
	if not sw_delta_df.empty:
		sw_delta_df = sw_delta_df.sort_values('Revenue (2025)', ascending=False)

	md += "## Same-Window Comparison (Aug 27 – Sep 03)\n\n"
	md += f"- **Spend:** {_fmt_money(sw_spend_2025)} ( {_fmt_money(sw_spend_2024)} | {_fmt_delta(sw_spend_yoy)} )\n"
	md += f"- **Revenue (Shopify):** {_fmt_money(sw_rev_2025)} ( {_fmt_money(sw_rev_2024)} | {_fmt_delta(sw_rev_yoy)} )\n"
	md += f"- **ROAS:** {_fmt_roas(sw_roas_2025)} ( {_fmt_roas(sw_roas_2024)} | {_fmt_delta(sw_roas_yoy)} )\n"
	md += f"- **Blended CAC:** {_fmt_money(sw_cac_2025)} ( {_fmt_money(sw_cac_2024)} | {_fmt_delta(sw_cac_yoy)} )\n\n"
	# Channel table
	md += "| Channel | Spend 2025 | Spend 2024 | Δ Spend | Revenue 2025 (NB) | Revenue 2024 (GA4) | Δ Revenue | ROAS 2025 | ROAS 2024 |\n"
	md += "|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
	for ch in sorted(set(sw_cur.index.tolist()) | set(sw_prev.index.tolist())):
		r25 = sw_cur.loc[ch] if ch in sw_cur.index else None
		r24 = sw_prev.loc[ch] if ch in sw_prev.index else None
		sp25 = float(r25['Spend']) if r25 is not None else 0.0
		sp24 = float(r24['Spend']) if r24 is not None else 0.0
		d_sp = ((sp25 - sp24) / sp24 * 100) if sp24 else None
		rev25 = float(r25['Revenue']) if r25 is not None else 0.0
		rev24 = float(r24['Revenue']) if r24 is not None else 0.0
		d_rev = ((rev25 - rev24) / rev24 * 100) if rev24 else None
		roas25 = float(r25['ROAS']) if r25 is not None else (rev25 / sp25 if sp25 else 0.0)
		roas24 = float(r24['ROAS']) if r24 is not None else (rev24 / sp24 if sp24 else 0.0)
		md += (
			f"| {ch} | {_fmt_money(sp25)} | {_fmt_money(sp24)} | {_fmt_pct(d_sp)} | "
			f"{_fmt_money(rev25)} | {_fmt_money(rev24)} | {_fmt_pct(d_rev)} | "
			f"{_fmt_roas(roas25)} | {_fmt_roas(roas24)} |\n"
		)
	# Total row for same-window table (NB/GA4)
	sw_tot_sp25 = float(sw_cur['Spend'].sum()) if not sw_cur.empty else 0.0
	sw_tot_sp24 = float(sw_prev['Spend'].sum()) if not sw_prev.empty else 0.0
	sw_tot_rev25 = float(sw_cur['Revenue'].sum()) if not sw_cur.empty else 0.0
	sw_tot_rev24 = float(sw_prev['Revenue'].sum()) if not sw_prev.empty else 0.0
	sw_d_sp = ((sw_tot_sp25 - sw_tot_sp24) / sw_tot_sp24 * 100) if sw_tot_sp24 else None
	sw_d_rev = ((sw_tot_rev25 - sw_tot_rev24) / sw_tot_rev24 * 100) if sw_tot_rev24 else None
	sw_roas25 = (sw_tot_rev25 / sw_tot_sp25) if sw_tot_sp25 else 0.0
	sw_roas24 = (sw_tot_rev24 / sw_tot_sp24) if sw_tot_sp24 else 0.0
	md += (
		f"| Total | {_fmt_money(sw_tot_sp25)} | {_fmt_money(sw_tot_sp24)} | {_fmt_pct(sw_d_sp)} | "
		f"{_fmt_money(sw_tot_rev25)} | {_fmt_money(sw_tot_rev24)} | {_fmt_pct(sw_d_rev)} | "
		f"{_fmt_roas(sw_roas25)} | {_fmt_roas(sw_roas24)} |\n"
	)
	md += "\n"

	# Optional: Product-level performance from provided Shopify file within 2025 window
	cur_start_dt = gen_cur.mtd_date_range_current['start_dt']
	cur_end_dt = gen_cur.mtd_date_range_current['end_dt']
	# 2025 products series
	s25 = _products_revenue_series(gen_cur.shopify_data_current, cur_start_dt, cur_end_dt)
	if not s25.empty:
		md += "## Top Products (2025 LDW window)\n\n"
		md += "| Product | 2025 Revenue |\n|---|---:|\n"
		for prod, v25 in s25.head(15).items():
			md += f"| {prod} | {_fmt_money(float(v25))} |\n"

	with open(out_path, 'w', encoding='utf-8') as f:
		f.write(md)
	print(f"✅ LDW YoY report saved to: {out_path}")


if __name__ == "__main__":
	main() 