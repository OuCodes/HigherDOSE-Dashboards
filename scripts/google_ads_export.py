#!/usr/bin/env python3
import sys
import csv
from pathlib import Path
from datetime import date, timedelta
from typing import List
import yaml
from google.ads.googleads.client import GoogleAdsClient

CONFIG = Path('config/google_ads/google-ads.yaml')
OUT_DIR = Path('data/ads')

HEADER = [
	"Account Level - Daily Report",
	"Period",
	"Account name,Customer ID,Day,Currency code,Cost,Clicks,Impr.,CTR,Avg. CPC (Converted currency),Cost (Converted currency),Conv. value,Conv. value / cost (current model),Conversions,Cost / conv.,Converted currency code",
]

ROW_HEADER = [
	"Account name","Customer ID","Day","Currency code","Cost","Clicks","Impr.","CTR",
	"Avg. CPC (Converted currency)","Cost (Converted currency)","Conv. value",
	"Conv. value / cost (current model)","Conversions","Cost / conv.","Converted currency code",
]

# GAQL mirrors sample: account-level by day
GAQL = (
	"SELECT customer.descriptive_name, customer.id, segments.date, "
	"customer.currency_code, metrics.cost_micros, metrics.clicks, metrics.impressions, metrics.ctr, "
	"metrics.average_cpc, metrics.conversions_value, metrics.conversions, metrics.cost_per_conversion "
	"FROM customer "
	"WHERE segments.date BETWEEN %s AND %s "
	"ORDER BY segments.date"
)


def format_money_micros(micros: int) -> str:
	return f"{micros/1_000_000:.2f}"


def percent(val: float) -> str:
	return f"{val*100:.2f}%" if val is not None else ""


def build_filename(start: date, end: date) -> Path:
	name = (
		f"google-mtd-export-{start.strftime('%b').lower()}-{start.strftime('%d')}-"
		f"to-{end.strftime('%b').lower()}-{end.strftime('%d')}-{end.strftime('%Y')}-"
		f"account-level-daily report.csv"
	)
	return OUT_DIR / name


def main() -> None:
	OUT_DIR.mkdir(parents=True, exist_ok=True)
	cfg = yaml.safe_load(CONFIG.read_text())
	client = GoogleAdsClient.load_from_dict(cfg)
	# Ensure login-customer-id header is set (required when accessing a client under an MCC)
	login_cid = (cfg.get('login_customer_id') or cfg.get('login-customer-id') or '').replace('-', '')
	if login_cid:
		client.login_customer_id = login_cid

	end = date.today()
	start = end - timedelta(days=29)
	period_str = f"{start.strftime('%B %d, %Y')} - {end.strftime('%B %d, %Y')}"
	outfile = build_filename(start, end)

	gaql = GAQL % (f"'{start}'", f"'{end}'")
	service = client.get_service("GoogleAdsService")
	linked_cid = (cfg.get('linked_customer_id') or cfg.get('customer_id') or '').replace('-', '')
	stream = service.search_stream(customer_id=linked_cid, query=gaql)

	with outfile.open('w', newline='', encoding='utf-8') as f:
		w = csv.writer(f)
		w.writerow([HEADER[0]])
		w.writerow([period_str])
		w.writerow(["Account name,Customer ID,Day,Currency code,Cost,Clicks,Impr.,CTR,Avg. CPC (Converted currency),Cost (Converted currency),Conv. value,Conv. value / cost (current model),Conversions,Cost / conv.,Converted currency code"])  # keep exact header row as in sample

		for batch in stream:
			for row in batch.results:
				cust = row.customer
				metrics = row.metrics
				segments = row.segments
				name = cust.descriptive_name
				cid = str(cust.id)
				cid_fmt = f"{cid[:3]}-{cid[3:6]}-{cid[6:]}"
				day = str(segments.date)
				ccy = cust.currency_code
				cost = format_money_micros(metrics.cost_micros)
				clicks = f"{metrics.clicks:,}"
				impr = f"{metrics.impressions:,}"
				ctr = percent(metrics.ctr)
				avg_cpc = format_money_micros(metrics.average_cpc.micros) if getattr(metrics, 'average_cpc', None) else ""
				# Converted currency == account currency in your sample (no cross-currency); mirror values
				cost_converted = cost
				conv_value = f"{metrics.conversions_value:,.2f}" if metrics.conversions_value is not None else ""
				cv_per_cost = f"{(metrics.conversions_value/ (metrics.cost_micros/1_000_000)):.2f}" if metrics.conversions_value and metrics.cost_micros else ""
				conversions = f"{metrics.conversions:,.2f}" if metrics.conversions is not None else ""
				cost_per_conv = f"{(metrics.cost_micros/1_000_000/metrics.conversions):.2f}" if metrics.conversions else ""
				w.writerow([
					name,
					cid_fmt,
					day,
					ccy,
					cost,
					clicks,
					impr,
					ctr,
					avg_cpc,
					cost_converted,
					conv_value,
					cv_per_cost,
					conversions,
					cost_per_conv,
					ccy,
				])

	print(f"Wrote {outfile}")


if __name__ == '__main__':
	main() 