#!/usr/bin/env python3
"""
Update Paid Search vs Organic Report (multi-window KPIs) from Northbeam API

- Windows: L30, L60, L90, L6M (ending yesterday, inclusive)
- Accounting: default cash unless overridden
- Model/window: default northbeam_custom, window=1 unless overridden
- Breakdowns: Platform (Northbeam) only
- Metrics computed:
  - Revenue (rev)
  - Spend (spend)
  - MER (rev / spend)
  - % New Visits (new_visits / visits)
  - Cost / New Visit (spend / new_visits)
  - CPA (spend / transactions)
  - nCAC (spend / transactions_1st_time)
  - Revenue share, Revenue per visit (RPV), Conversion rate (CVR)
  - Paid Brand vs Non‑Brand split (Search-only vs Shopping/PMAX)
  - L30 campaign classification tables (Brand vs Non‑Brand)

Writes to: data/reports/weekly/paid-search-vs-organic-multiwindow-2025-09-13.md
"""

import sys
import csv
import io
import urllib.request
from pathlib import Path
from dataclasses import dataclass
from datetime import date, timedelta, datetime

# Ensure src on path
if str(Path('src')) not in sys.path:
	sys.path.append('src')

from growthkit.connectors.northbeam.client import NorthbeamClient
try:
	from growthkit.connectors.ga4 import GA4Client  # type: ignore
except Exception:
	GA4Client = None  # type: ignore

REPORT_PATH = Path('data/reports/weekly/paid-search-vs-organic-multiwindow-2025-09-13.md')
PAID_PLATFORMS = {'Google Ads', 'Microsoft Ads'}
# API breakdown key and CSV column name differ
API_PLATFORM_KEY = 'Platform (Northbeam)'
CSV_PLATFORM_COL = 'breakdown_platform_northbeam'

# API metric ids
METRIC_IDS = ['rev', 'spend', 'visits', 'newVisits', 'txns', 'txnsFt']


@dataclass
class Totals:
	rev: float = 0.0
	spend: float = 0.0
	visits: float = 0.0
	new_visits: float = 0.0
	transactions: float = 0.0
	transactions_1st_time: float = 0.0

	def merge(self, other: 'Totals') -> None:
		self.rev += other.rev
		self.spend += other.spend
		self.visits += other.visits
		self.new_visits += other.new_visits
		self.transactions += other.transactions
		self.transactions_1st_time += other.transactions_1st_time

	def add_row(self, r: dict) -> None:
		self.rev += to_float(r.get('rev'))
		self.spend += to_float(r.get('spend'))
		self.visits += to_float(r.get('visits'))
		self.new_visits += to_float(r.get('new_visits'))
		self.transactions += to_float(r.get('transactions'))
		self.transactions_1st_time += to_float(r.get('transactions_1st_time'))

	def kpis(self) -> dict:
		pct_new = (self.new_visits / self.visits) if self.visits > 0 else None
		cpnv = (self.spend / self.new_visits) if self.new_visits > 0 else None
		cpa = (self.spend / self.transactions) if self.transactions > 0 else None
		ncac = (self.spend / self.transactions_1st_time) if self.transactions_1st_time > 0 else None
		mer = (self.rev / self.spend) if self.spend > 0 else None
		return {
			'rev': self.rev,
			'spend': self.spend,
			'mer': mer,
			'visits': self.visits,
			'new_visits': self.new_visits,
			'transactions': self.transactions,
			'pct_new': pct_new,
			'cpnv': cpnv,
			'cpa': cpa,
			'ncac': ncac,
		}


def fmt_money(x: float | None) -> str:
	if x is None:
		return '—'
	return f"${x:,.0f}" if x >= 1000 else f"${x:,.2f}"


def fmt_rate(x: float | None) -> str:
	if x is None:
		return '—'
	return f"{x*100:,.2f}%"


def fmt_money_2(x: float | None) -> str:
	if x is None:
		return '—'
	return f"${x:,.2f}"


def fmt_ratio(x: float | None) -> str:
	if x is None:
		return '—'
	return f"{x:.2f}x"


def delta_fmt(curr: float | None, prev: float | None, is_pct: bool = False) -> str:
	if curr is None or prev is None:
		return '—'
	d = curr - prev
	if is_pct:
		return f"{d*100:+.2f} pp"
	return f"{d:+,.2f}"


def download_csv(url: str) -> list[dict[str, str]]:
	with urllib.request.urlopen(url) as resp:
		data = resp.read().decode('utf-8')
	reader = csv.DictReader(io.StringIO(data))
	return list(reader)


def to_float(v: str) -> float:
	try:
		if v is None or v == '':
			return 0.0
		return float(v)
	except Exception:
		return 0.0

# Helper: classification

def _is_brand_campaign(name: str) -> bool:
	if not name:
		return False
	n = name.strip().lower()
	if 'nonbrand' in n or 'non-brand' in n or ' nb' in n or ' nbr' in n:
		return False
	return 'brand' in n or n.startswith('br_') or (' pmax' in n and 'brand' in n)


def _is_shopping_or_pmax(name: str, platform: str) -> bool:
	if platform == 'Google Shopping':
		return True
	if not name:
		return False
	n = name.strip().lower()
	return any(k in n for k in ['shopping', 'pmax', 'pmx', 'smart shopping', 'performance max'])

# Aggregate by platform only

def aggregate(rows: list[dict[str, str]]) -> dict:
	res: dict[str, Totals] = {}
	for r in rows:
		plat = r.get(CSV_PLATFORM_COL, '').strip()
		t = res.get(plat)
		if t is None:
			res[plat] = t = Totals()
		t.add_row(r)
	return res

# Aggregate brand vs nonbrand within Paid Search

def aggregate_brand(rows: list[dict[str, str]]) -> dict:
	paid_brand = Totals()
	paid_nonbrand = Totals()
	search_brand = Totals()
	search_nonbrand = Totals()
	shop_brand = Totals()
	shop_nonbrand = Totals()

	for r in rows:
		plat = r.get(CSV_PLATFORM_COL, '').strip()
		if plat not in PAID_PLATFORMS and plat != 'Google Shopping':
			continue
		camp = (r.get('campaign_name') or '').strip()
		is_shop = _is_shopping_or_pmax(camp, plat)
		is_brand = _is_brand_campaign(camp)
		if is_brand:
			paid_brand.add_row(r)
			(search_brand if not is_shop else shop_brand).add_row(r)
		else:
			paid_nonbrand.add_row(r)
			(search_nonbrand if not is_shop else shop_nonbrand).add_row(r)

	return {
		'paid_brand': paid_brand.kpis(),
		'paid_nonbrand': paid_nonbrand.kpis(),
		'search_brand': search_brand.kpis(),
		'search_nonbrand': search_nonbrand.kpis(),
		'shopping_brand': shop_brand.kpis(),
		'shopping_nonbrand': shop_nonbrand.kpis(),
	}

# Collect campaign lists with spend (Brand vs Non‑Brand) for transparency

def collect_campaigns(rows: list[dict[str, str]]) -> dict:
	brand_spend: dict[str, float] = {}
	nonbrand_spend: dict[str, float] = {}
	for r in rows:
		plat = r.get(CSV_PLATFORM_COL, '').strip()
		if plat not in PAID_PLATFORMS and plat != 'Google Shopping':
			continue
		name = (r.get('campaign_name') or '').strip()
		is_brand = _is_brand_campaign(name)
		sp = to_float(r.get('spend'))
		if is_brand:
			brand_spend[name] = brand_spend.get(name, 0.0) + sp
		else:
			nonbrand_spend[name] = nonbrand_spend.get(name, 0.0) + sp
	# Sort by spend desc
	brand_list = sorted(brand_spend.items(), key=lambda x: x[1], reverse=True)
	nonbrand_list = sorted(nonbrand_spend.items(), key=lambda x: x[1], reverse=True)
	return {'brand_campaigns': brand_list, 'nonbrand_campaigns': nonbrand_list}

# Export with Platform-only breakdown

def run_export(c: NorthbeamClient, start: date, end: date, *, mode: str, model: str, window: str) -> list[dict[str, str]]:
	start_s = start.isoformat()
	end_s = end.isoformat()
	# Fetch all platform values to ensure full-channel coverage
	platform_values: list[str] = []
	try:
		for b in c.list_breakdowns():
			if b.get('key') == API_PLATFORM_KEY and isinstance(b.get('values'), list):
				platform_values = [str(v) for v in b['values'] if v]
				break
	except Exception:
		platform_values = []
	breakdowns = [
		{'key': API_PLATFORM_KEY, 'values': platform_values} if platform_values else {'key': API_PLATFORM_KEY},
	]
	export_id = c.create_export(
		start_date=start_s,
		end_date=end_s,
		accounting_mode=mode,
		attribution_model=model,
		attribution_window=window,
		metrics=METRIC_IDS,
		breakdowns=breakdowns,
	)
	res = c.wait_for_export(export_id, interval=1.0, timeout=600.0)
	if not res.location:
		raise SystemExit('No export location returned')
	return download_csv(res.location)

# Build KPIs for Paid (platform in PAID_PLATFORMS) and Organic Search only

def build_kpis(agg: dict) -> dict:
	roll = {
		'paid_all': Totals(),
		'organic': Totals(),
		'all_channels': Totals(),
	}
	for plat, t in agg.items():
		roll['all_channels'].merge(t)
		if plat in PAID_PLATFORMS:
			roll['paid_all'].merge(t)
		elif plat == 'Organic Search':
			roll['organic'].merge(t)
	k = {k: v.kpis() for k, v in roll.items()}
	return k

# GA4 CSV fallback helpers

def _parse_number(s: str | None) -> float:
	if not s:
		return 0.0
	s = s.replace(',', '').replace('$', '').strip()
	try:
		return float(s)
	except Exception:
		return 0.0


def _find_latest_ga4_csv() -> Path | None:
	ads = Path('data/ads')
	if not ads.exists():
		return None
	candidates = sorted([p for p in ads.glob('*.csv') if 'traffic' in p.name.lower() or 'channel_group' in p.name.lower()], key=lambda p: p.stat().st_mtime, reverse=True)
	return candidates[0] if candidates else None


def ga4_from_csv(start: date, end: date) -> dict:
	csv_path = _find_latest_ga4_csv()
	if not csv_path or not csv_path.exists():
		return {}
	with csv_path.open('r', encoding='utf-8') as f:
		reader = csv.DictReader(f)
		rows = list(reader)
	# header keys we may see
	k_channel = None
	for cand in ('Session default channel group', 'Default channel group', 'session default channel group'):
		if cand in reader.fieldnames:
			k_channel = cand
			break
	# also support source/medium variants
	k_srcmed = None
	for cand in ('Source / Medium', 'source / medium', 'Source/Medium', 'sourceMedium'):
		if cand in reader.fieldnames:
			k_srcmed = cand
			break
	k_source = None
	for cand in ('Source', 'source'):
		if cand in reader.fieldnames:
			k_source = cand
			break
	k_medium = None
	for cand in ('Medium', 'medium'):
		if cand in reader.fieldnames:
			k_medium = cand
			break
	k_sessions = 'Sessions' if 'Sessions' in reader.fieldnames else ('sessions' if 'sessions' in reader.fieldnames else None)
	k_users = 'Total users' if 'Total users' in reader.fieldnames else ('Users' if 'Users' in reader.fieldnames else None)
	k_purchases = None
	for cand in ('Purchases', 'Transactions', 'Ecommerce purchases'):
		if cand in reader.fieldnames:
			k_purchases = cand
			break
	k_revenue = None
	for cand in ('Purchase revenue', 'Total revenue', 'Ecommerce revenue'):
		if cand in reader.fieldnames:
			k_revenue = cand
			break
	k_date = None
	for cand in ('Date', 'date'):
		if cand in reader.fieldnames:
			k_date = cand
			break
	by_ch: dict[str, dict] = {}
	for r in rows:
		if k_date and r.get(k_date):
			try:
				dt = datetime.strptime(r[k_date], '%Y-%m-%d').date()
			except Exception:
				# Try alternative formats
				try:
					dt = datetime.strptime(r[k_date], '%m/%d/%Y').date()
				except Exception:
					dt = None
			if dt and not (start <= dt <= end):
				continue
		# Determine channel
		ch = None
		if k_channel:
			ch = (r.get(k_channel) or '').strip()
		else:
			med_val = None
			if k_srcmed and r.get(k_srcmed):
				parts = r.get(k_srcmed).split('/')
				med_val = parts[1].strip().lower() if len(parts) > 1 else r.get(k_srcmed).strip().lower()
			elif k_medium and r.get(k_medium):
				med_val = r.get(k_medium).strip().lower()
			if med_val:
				if 'organic' in med_val:
					ch = 'Organic Search'
				elif (med_val in ('cpc','ppc','paidsearch','paid search')) or ('cpc' in med_val) or ('ppc' in med_val):
					ch = 'Paid Search'
		if ch not in ('Paid Search', 'Organic Search'):
			continue
		acc = by_ch.get(ch) or {'sessions': 0.0, 'users': 0.0, 'purchases': 0.0, 'revenue': 0.0}
		if k_sessions:
			acc['sessions'] += _parse_number(r.get(k_sessions))
		if k_users:
			acc['users'] += _parse_number(r.get(k_users))
		if k_purchases:
			acc['purchases'] += _parse_number(r.get(k_purchases))
		if k_revenue:
			acc['revenue'] += _parse_number(r.get(k_revenue))
		by_ch[ch] = acc
	return by_ch


def md_tables(current: dict, deltas: dict, campaigns: dict, ga4: dict | None = None) -> str:
	# L30 snapshot from current['L30']
	c30 = current['L30']
	lines = []
	lines.append('## Paid Search vs Organic Search — Multi-Window KPIs (Northbeam)')
	lines.append('')
	lines.append('### L30 snapshot (most recent 30 days)')
	lines.append('| Category | Revenue | Spend | MER | % New Visits | Cost / New Visit | CPA | nCAC |')
	lines.append('|---|---:|---:|---:|---:|---:|---:|---:|')
	# Paid All
	lines.append(f"| Paid Search (All) | {fmt_money(c30['paid_all']['rev'])} | {fmt_money(c30['paid_all']['spend'])} | {fmt_ratio(c30['paid_all']['mer'])} | {fmt_rate(c30['paid_all']['pct_new'])} | {fmt_money_2(c30['paid_all']['cpnv'])} | {fmt_money_2(c30['paid_all']['cpa'])} | {fmt_money_2(c30['paid_all']['ncac'])} |")
	# Brand / Non-Brand
	b30 = c30.get('paid_brand', {})
	n30 = c30.get('paid_nonbrand', {})
	lines.append(f"| Paid Search — Brand | {fmt_money(b30.get('rev'))} | {fmt_money(b30.get('spend'))} | {fmt_ratio(b30.get('mer'))} | {fmt_rate(b30.get('pct_new'))} | {fmt_money_2(b30.get('cpnv'))} | {fmt_money_2(b30.get('cpa'))} | {fmt_money_2(b30.get('ncac'))} |")
	lines.append(f"| Paid Search — Non‑Brand | {fmt_money(n30.get('rev'))} | {fmt_money(n30.get('spend'))} | {fmt_ratio(n30.get('mer'))} | {fmt_rate(n30.get('pct_new'))} | {fmt_money_2(n30.get('cpnv'))} | {fmt_money_2(n30.get('cpa'))} | {fmt_money_2(n30.get('ncac'))} |")
	# Organic (keep CPA/nCAC as em-dash for clarity)
	lines.append(f"| Organic Search | {fmt_money(c30['organic']['rev'])} | {fmt_money(c30['organic']['spend'])} | {fmt_ratio(c30['organic'].get('mer'))} | {fmt_rate(c30['organic']['pct_new'])} | {fmt_money_2(c30['organic']['cpnv'])} | — | — |")
	lines.append('')
	lines.append('### KPIs by window — Brand, Non‑Brand, Organic')
	lines.append('| Window | Category | Revenue | Spend | MER | RPV | CVR | % New | CPNV | CPA | nCAC |')
	lines.append('|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
	for w in ('L30','L60','L90','L6M'):
		b = current[w].get('paid_brand', {})
		nb = current[w].get('paid_nonbrand', {})
		org = current[w]['organic']
		def rpv(k):
			vis = k.get('visits') or 0
			return (k.get('rev') or 0)/vis if vis>0 else None
		def cvr(k):
			vis = k.get('visits') or 0
			tx = k.get('transactions') or 0
			return (tx/vis) if vis>0 else None
		lines.append(f"| {w} | Brand | {fmt_money(b.get('rev'))} | {fmt_money(b.get('spend'))} | {fmt_ratio(b.get('mer'))} | {fmt_money_2(rpv(b))} | {fmt_rate(cvr(b))} | {fmt_rate(b.get('pct_new'))} | {fmt_money_2(b.get('cpnv'))} | {fmt_money_2(b.get('cpa'))} | {fmt_money_2(b.get('ncac'))} |")
		lines.append(f"| {w} | Non‑Brand | {fmt_money(nb.get('rev'))} | {fmt_money(nb.get('spend'))} | {fmt_ratio(nb.get('mer'))} | {fmt_money_2(rpv(nb))} | {fmt_rate(cvr(nb))} | {fmt_rate(nb.get('pct_new'))} | {fmt_money_2(nb.get('cpnv'))} | {fmt_money_2(nb.get('cpa'))} | {fmt_money_2(nb.get('ncac'))} |")
		lines.append(f"| {w} | Organic | {fmt_money(org['rev'])} | {fmt_money(org['spend'])} | {fmt_ratio(org.get('mer'))} | {fmt_money_2(rpv(org))} | {fmt_rate(cvr(org))} | {fmt_rate(org.get('pct_new'))} | {fmt_money_2(org['cpnv'])} | — | — |")
	lines.append('')
	lines.append('### Revenue share by window — Brand, Non‑Brand, Organic')
	lines.append('| Window | Brand Rev | Non‑Brand Rev | Organic Rev | Total Revenue | Brand Share | Non‑Brand Share | Organic Share |')
	lines.append('|---|---:|---:|---:|---:|---:|---:|---:|')
	for w in ('L30','L60','L90','L6M'):
		b = current[w].get('paid_brand', {})
		nb = current[w].get('paid_nonbrand', {})
		org = current[w]['organic']
		allc = current[w]['all_channels']
		br = b.get('rev') or 0.0
		nr = nb.get('rev') or 0.0
		orv = org.get('rev') or 0.0
		tot = allc.get('rev') or (br + nr + orv)
		bs = (br/tot) if tot>0 else None
		ns = (nr/tot) if tot>0 else None
		os = (orv/tot) if tot>0 else None
		lines.append(f"| {w} | {fmt_money(br)} | {fmt_money(nr)} | {fmt_money(orv)} | {fmt_money(tot)} | {fmt_rate(bs)} | {fmt_rate(ns)} | {fmt_rate(os)} |")
	lines.append('')
	# Cannibalization Signal: Brand up while Organic down vs previous period
	lines.append('### Cannibalization signal (Brand up, Organic down vs previous)')
	for w in ('L30','L60','L90','L6M'):
		c_b = current[w].get('paid_brand', {})
		c_o = current[w]['organic']
		p_b = deltas[w].get('paid_brand', {}) if isinstance(deltas.get(w), dict) else {}
		p_o = deltas[w]['organic'] if isinstance(deltas.get(w), dict) else {}
		brand_up = (c_b.get('rev') or 0) > (p_b.get('rev') or 0)
		org_down = (c_o.get('rev') or 0) < (p_o.get('rev') or 0)
		signal = 'YES' if brand_up and org_down else 'no'
		lines.append(f"- {w}: {signal}")
	lines.append('')
	lines.append('### Paid Search — Brand vs Non‑Brand (spend share and KPIs)')
	lines.append('| Window | Brand Spend | Non‑Brand Spend | Brand Spend Share |')
	lines.append('|---|---:|---:|---:|')
	for w in ('L30','L60','L90','L6M'):
		b = current[w].get('paid_brand', {})
		n = current[w].get('paid_nonbrand', {})
		bs = (b.get('spend') or 0.0)
		ns = (n.get('spend') or 0.0)
		share_b = (bs / (bs + ns)) if (bs + ns) > 0 else None
		lines.append(f"| {w} | {fmt_money(bs)} | {fmt_money(ns)} | {fmt_rate(share_b)} |")
	lines.append('')
	lines.append('#### By type: Search‑only vs Shopping/PMAX')
	lines.append('| Window | Search Brand Spend | Search Non‑Brand Spend | Search Brand Spend Share | Shopping Brand Spend | Shopping Non‑Brand Spend | Shopping Brand Spend Share |')
	lines.append('|---|---:|---:|---:|---:|---:|---:|')
	for w in ('L30','L60','L90','L6M'):
		sb = current[w].get('search_brand', {})
		sn = current[w].get('search_nonbrand', {})
		shb = current[w].get('shopping_brand', {})
		shn = current[w].get('shopping_nonbrand', {})
		s_bs = (sb.get('spend') or 0.0); s_ns = (sn.get('spend') or 0.0)
		sh_bs = (shb.get('spend') or 0.0); sh_ns = (shn.get('spend') or 0.0)
		s_share = (s_bs/(s_bs+s_ns)) if (s_bs+s_ns)>0 else None
		sh_share = (sh_bs/(sh_bs+sh_ns)) if (sh_bs+sh_ns)>0 else None
		lines.append(f"| {w} | {fmt_money(s_bs)} | {fmt_money(s_ns)} | {fmt_rate(s_share)} | {fmt_money(sh_bs)} | {fmt_money(sh_ns)} | {fmt_rate(sh_share)} |")
	lines.append('')
	# Optional GA4 section
	if ga4:
		lines.append('### GA4 website behavior (sessions, users, purchases, revenue)')
		lines.append('| Window | Channel | Sessions | Users | Purchases | Revenue | CVR | RPV |')
		lines.append('|---|---|---:|---:|---:|---:|---:|---:|')
		for w in ('L30','L60','L90','L6M'):
			for channel in ('Paid Search','Organic Search'):
				row = ga4.get(w, {}).get(channel, {})
				sessions = row.get('sessions') or 0
				purchases = row.get('purchases') or 0
				revenue = row.get('revenue') or 0
				cvr = (purchases/sessions) if sessions>0 else None
				rpv = (revenue/sessions) if sessions>0 else None
				lines.append(f"| {w} | {channel} | {sessions:,.0f} | {(row.get('users') or 0):,.0f} | {purchases:,.0f} | {fmt_money(revenue)} | {fmt_rate(cvr)} | {fmt_money_2(rpv)} |")
		lines.append('')
		# Engagement metrics
		lines.append('### GA4 engagement metrics')
		lines.append('| Window | Channel | Engaged sessions | Engagement rate | Avg session duration (s) | Events per session | Session key event rate |')
		lines.append('|---|---|---:|---:|---:|---:|---:|')
		for w in ('L30','L60','L90','L6M'):
			for channel in ('Paid Search','Organic Search'):
				row = ga4.get(w, {}).get(channel, {})
				lines.append(f"| {w} | {channel} | {(row.get('engaged_sessions') or 0):,.0f} | {fmt_rate(row.get('engagement_rate'))} | {(row.get('avg_session_duration') or 0):,.0f} | {row.get('events_per_session') or 0:.2f} | {fmt_rate(row.get('session_key_event_rate'))} |")
		lines.append('')
		# Engagement quality signal
		lines.append('### Engagement quality signal (Paid share >50% and lower engagement rate vs Organic)')
		for w in ('L30','L60','L90','L6M'):
			p = ga4.get(w, {}).get('Paid Search', {})
			o = ga4.get(w, {}).get('Organic Search', {})
			s_paid = p.get('sessions') or 0.0
			s_org = o.get('sessions') or 0.0
			share = s_paid / (s_paid + s_org) if (s_paid + s_org) > 0 else 0.0
			eng_p = p.get('engagement_rate') or 0.0
			eng_o = o.get('engagement_rate') or 0.0
			signal = 'YES' if (share > 0.5 and eng_p < eng_o) else 'no'
			lines.append(f"- {w}: Paid share {fmt_rate(share)}; Paid ER {fmt_rate(eng_p)} vs Organic {fmt_rate(eng_o)} ⇒ {signal}")
		lines.append('')
	# Campaign tables for L30
	cl30 = campaigns['L30']
	lines.append('### L30 Campaign classification')
	lines.append('#### Brand campaigns (with spend)')
	lines.append('| Campaign | Spend |')
	lines.append('|---|---:|')
	for name, sp in cl30['brand_campaigns']:
		lines.append(f"| {name} | {fmt_money(sp)} |")
	lines.append('')
	lines.append('#### Non‑Brand campaigns (with spend)')
	lines.append('| Campaign | Spend |')
	lines.append('|---|---:|')
	for name, sp in cl30['nonbrand_campaigns']:
		lines.append(f"| {name} | {fmt_money(sp)} |")
	lines.append('')
	return "\n".join(lines) + "\n"


def main() -> None:
	mode = 'cash'
	model = 'northbeam_custom'
	window = '1'
	c = NorthbeamClient()
	# GA4 API may be unavailable; we will try it, else fallback to CSV
	try:
		ga4c: GA4Client | None = GA4Client() if GA4Client is not None else None
	except Exception:
		ga4c = None
	end = date.today() - timedelta(days=1)
	windows = {
		'L30': 30,
		'L60': 60,
		'L90': 90,
		'L6M': 180,
	}
	current: dict[str, dict] = {}
	previous: dict[str, dict] = {}
	campaigns: dict[str, dict] = {}
	ga4_rollup: dict[str, dict] = {}
	for key, days in windows.items():
		start_curr = end - timedelta(days=days-1)
		rows_curr = run_export(c, start_curr, end, mode=mode, model=model, window=window)
		agg_curr = aggregate(rows_curr)
		cur = build_kpis(agg_curr)
		cur.update(aggregate_brand(rows_curr))
		current[key] = cur
		if key == 'L30':
			campaigns[key] = collect_campaigns(rows_curr)
		# previous not rendered currently
		end_prev = start_curr - timedelta(days=1)
		start_prev = end_prev - timedelta(days=days-1)
		rows_prev = run_export(c, start_prev, end_prev, mode=mode, model=model, window=window)
		agg_prev = aggregate(rows_prev)
		previous[key] = build_kpis(agg_prev)
		# GA4 data for this window
		by_ch: dict[str, dict] = {}
		if ga4c is not None:
			try:
				# Base traffic & revenue metrics
				ga4_rows = ga4c.run_channels_report(start_curr, end)
				# Engagement metrics
				ga4_eng = {e['channel']: e for e in ga4c.run_channels_engagement(start_curr, end)}
				for r in ga4_rows:
					ch = r.get('channel') or ''
					if ch in ('Paid Search','Organic Search'):
						eng = ga4_eng.get(ch, {})
						by_ch[ch] = {
							'sessions': r.get('sessions') or 0.0,
							'users': r.get('users') or 0.0,
							'purchases': r.get('purchases') or 0.0,
							'revenue': r.get('revenue') or 0.0,
							'engaged_sessions': eng.get('engaged_sessions') or 0.0,
							'engagement_rate': eng.get('engagement_rate') or 0.0,
							'avg_session_duration': eng.get('avg_session_duration') or 0.0,
							'events_per_session': eng.get('events_per_session') or 0.0,
							'event_count': eng.get('event_count') or 0.0,
							'key_events': eng.get('key_events') or 0.0,
							'session_key_event_rate': eng.get('session_key_event_rate') or 0.0,
						}
			except Exception:
				by_ch = {}
		if not by_ch:
			by_ch = ga4_from_csv(start_curr, end)
		if by_ch:
			ga4_rollup[key] = by_ch

	content = md_tables(current, previous, campaigns, ga4_rollup if ga4_rollup else None)
	REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
	REPORT_PATH.write_text(content, encoding='utf-8')
	print('Updated report:', REPORT_PATH)


if __name__ == '__main__':
	main() 