#!/usr/bin/env python3
import sys
from pathlib import Path
from datetime import date

# Ensure src on path
if str(Path('src')) not in sys.path:
	sys.path.append('src')

from growthkit.connectors.ga4 import GA4Client

OUT_DIR = Path('data/ads/exec-sum')


def write_csv_with_headers(path: Path, headers: list[str], rows: list[dict]) -> None:
	with path.open('w', encoding='utf-8') as f:
		f.write(','.join(headers) + '\n')
		for r in rows:
			vals = []
			for h in headers:
				v = r.get(h, '')
				if isinstance(v, str):
					vals.append(v.replace(',', ''))
				else:
					vals.append(str(v))
			f.write(','.join(vals) + '\n')


def yyyymmdd_to_yyyy_mm_dd(s: str) -> str:
	# GA4 API returns YYYYMMDD; convert to YYYY-MM-DD if matches
	if s and len(s) == 8 and s.isdigit():
		return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
	return s


def pick_existing_or_default(prefix: str, default: Path) -> Path:
	cands = sorted(OUT_DIR.glob(f"{prefix}-*.csv"), key=lambda p: p.stat().st_mtime, reverse=True)
	return cands[0] if cands else default


def main() -> None:
	OUT_DIR.mkdir(parents=True, exist_ok=True)
	ga = GA4Client()
	today = date.today()
	start = date(today.year, 1, 1)
	end = today
	# Channel group daily (UI-aligned columns)
	chan_rows_api = ga.run_daily(start, end, ["sessionDefaultChannelGroup"])
	chan_rows = []
	for r in chan_rows_api:
		chan_rows.append({
			'Date': yyyymmdd_to_yyyy_mm_dd(str(r.get('date') or '')),
			'Session default channel group': r.get('sessionDefaultChannelGroup') or '',
			'Sessions': int(r.get('sessions') or 0),
			'Total users': int(r.get('users') or 0),
			'Ecommerce purchases': int(r.get('purchases') or 0),
			'Purchase revenue': float(r.get('revenue') or 0.0),
		})
	chan_headers = ['Date', 'Session default channel group', 'Sessions', 'Total users', 'Ecommerce purchases', 'Purchase revenue']
	chan_default = OUT_DIR / f"daily-traffic_acquisition_Session_default_channel_group-{start}-{end}.csv"
	chan_path = chan_default
	write_csv_with_headers(chan_path, chan_headers, chan_rows)
	print('Saved:', chan_path)
	# Source/Medium daily simple (UI-aligned columns)
	sm_rows_api = ga.run_daily(start, end, ["sessionSourceMedium"])
	sm_rows = []
	for r in sm_rows_api:
		sm_rows.append({
			'Date': yyyymmdd_to_yyyy_mm_dd(str(r.get('date') or '')),
			'Source / Medium': r.get('sessionSourceMedium') or '',
			'Sessions': int(r.get('sessions') or 0),
			'Total users': int(r.get('users') or 0),
			'Ecommerce purchases': int(r.get('purchases') or 0),
			'Purchase revenue': float(r.get('revenue') or 0.0),
		})
	sm_headers = ['Date', 'Source / Medium', 'Sessions', 'Total users', 'Ecommerce purchases', 'Purchase revenue']
	sm_default = OUT_DIR / f"daily-traffic_acquisition_Session_source_medium-{start}-{end}.csv"
	sm_path = sm_default
	write_csv_with_headers(sm_path, sm_headers, sm_rows)
	print('Saved:', sm_path)
	# Channel group daily with engagement/event metrics (user-requested headers)
	metric_names = [
		"sessions",
		"engagedSessions",
		"engagementRate",
		"averageSessionDuration",
		"eventsPerSession",
		"eventCount",
		"keyEvents",
		"sessionKeyEventRate",
		"totalRevenue",
	]
	chan_eng = ga.run_daily_custom(start, end, ["sessionDefaultChannelGroup"], metric_names)
	chan_eng_rows = []
	for r in chan_eng:
		chan_eng_rows.append({
			'Session default channel group': r.get('sessionDefaultChannelGroup') or '',
			'Date': yyyymmdd_to_yyyy_mm_dd(str(r.get('date') or '')),
			'Sessions': int(float(r.get('sessions') or 0)),
			'Engaged sessions': int(float(r.get('engagedSessions') or 0)),
			'Engagement rate': float(r.get('engagementRate') or 0.0),
			'Average engagement time per session': float(r.get('averageSessionDuration') or 0.0),
			'Events per session': float(r.get('eventsPerSession') or 0.0),
			'Event count': int(float(r.get('eventCount') or 0)),
			'Key events': int(float(r.get('keyEvents') or 0)),
			'Session key event rate': float(r.get('sessionKeyEventRate') or 0.0),
			'Total revenue': float(r.get('totalRevenue') or 0.0),
		})
	chan_eng_headers = ['Session default channel group', 'Date', 'Sessions', 'Engaged sessions', 'Engagement rate', 'Average engagement time per session', 'Events per session', 'Event count', 'Key events', 'Session key event rate', 'Total revenue']
	chan_eng_default = OUT_DIR / f"daily-traffic_acquisition_Session_default_channel_group_engagement-{start}-{end}.csv"
	chan_eng_path = chan_eng_default
	write_csv_with_headers(chan_eng_path, chan_eng_headers, chan_eng_rows)
	print('Saved:', chan_eng_path)
	# Source/Medium daily with engagement/event metrics (user-requested headers)
	sm_eng = ga.run_daily_custom(start, end, ["sessionSourceMedium"], metric_names)
	sm_eng_rows = []
	for r in sm_eng:
		sm_eng_rows.append({
			'Session source / medium': r.get('sessionSourceMedium') or '',
			'Date': yyyymmdd_to_yyyy_mm_dd(str(r.get('date') or '')),
			'Sessions': int(float(r.get('sessions') or 0)),
			'Engaged sessions': int(float(r.get('engagedSessions') or 0)),
			'Engagement rate': float(r.get('engagementRate') or 0.0),
			'Average engagement time per session': float(r.get('averageSessionDuration') or 0.0),
			'Events per session': float(r.get('eventsPerSession') or 0.0),
			'Event count': int(float(r.get('eventCount') or 0)),
			'Key events': int(float(r.get('keyEvents') or 0)),
			'Session key event rate': float(r.get('sessionKeyEventRate') or 0.0),
			'Total revenue': float(r.get('totalRevenue') or 0.0),
		})
	sm_eng_headers = ['Session source / medium', 'Date', 'Sessions', 'Engaged sessions', 'Engagement rate', 'Average engagement time per session', 'Events per session', 'Event count', 'Key events', 'Session key event rate', 'Total revenue']
	sm_eng_default = OUT_DIR / f"daily-traffic_acquisition_Session_source_medium_engagement-{start}-{end}.csv"
	sm_eng_path = sm_eng_default
	write_csv_with_headers(sm_eng_path, sm_eng_headers, sm_eng_rows)
	print('Saved:', sm_eng_path)


if __name__ == '__main__':
	main() 