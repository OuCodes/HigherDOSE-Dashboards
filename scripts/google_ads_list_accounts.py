#!/usr/bin/env python3
from pathlib import Path
import yaml
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

CONFIG = Path('config/google_ads/google-ads.yaml')

def main() -> None:
	cfg = yaml.safe_load(CONFIG.read_text())
	client = GoogleAdsClient.load_from_dict(cfg)
	login_cid = (cfg.get('login_customer_id') or cfg.get('login-customer-id') or '').replace('-', '')
	if not login_cid:
		raise SystemExit('login_customer_id is required in config to enumerate hierarchy')
	client.login_customer_id = login_cid
	print(f"Using login_customer_id: {login_cid}")

	cust_service = client.get_service('CustomerService')
	accessible = []
	try:
		customers = cust_service.list_accessible_customers()
		print('Accessible resource names:')
		for rn in customers.resource_names:
			print(rn)
			accessible.append(rn.split('/')[-1])
	except GoogleAdsException as e:
		print(f"CustomerService.list_accessible_customers failed: {e}")
		for err in e.failure.errors:
			print(f"  {err.error_code}: {err.message}")
		raise

	ga_service = client.get_service('GoogleAdsService')

	# Probe each accessible customer to see GAQL access and manager flag
	print("\nProbing accessible customers with GAQL:")
	probe_query = (
		"SELECT customer.id, customer.descriptive_name, customer.manager, customer.time_zone, customer.currency_code "
		"FROM customer"
	)
	for cid in accessible:
		try:
			for batch in ga_service.search_stream(customer_id=cid, query=probe_query):
				for row in batch.results:
					print(f"OK customer_id={cid}: {row.customer.descriptive_name} manager={row.customer.manager} currency={row.customer.currency_code}")
		except GoogleAdsException as e:
			print(f"DENIED customer_id={cid}: {e.failure.errors[0].error_code} - {e.failure.errors[0].message}")

	# Describe the login customer
	query_self = (
		"SELECT customer.id, customer.descriptive_name, customer.manager, customer.time_zone, customer.currency_code "
		"FROM customer"
	)
	try:
		for batch in ga_service.search_stream(customer_id=login_cid, query=query_self):
			for row in batch.results:
				print(f"\nLogin customer: {row.customer.id}\t{row.customer.descriptive_name}\tmanager={row.customer.manager}\t{row.customer.currency_code}")
	except GoogleAdsException as e:
		print(f"GoogleAdsService.search_stream (self) failed for customer_id={login_cid}: {e}")
		for err in e.failure.errors:
			print(f"  {err.error_code}: {err.message}")
		print("Hint: Ensure the OAuth user has access to the login MCC and that the login_customer_id header is set to an MCC, not a leaf account.")
		# continue; do not raise so we can attempt hierarchy query too

	# List hierarchy under login
	query_h = (
		"SELECT customer_client.id, customer_client.client_customer, customer_client.descriptive_name, "
		"customer_client.level, customer_client.manager, customer_client.status "
		"FROM customer_client "
		"ORDER BY customer_client.level, customer_client.id"
	)
	print('\nManaged hierarchy:')
	try:
		for batch in ga_service.search_stream(customer_id=login_cid, query=query_h):
			for row in batch.results:
				cc = row.customer_client
				print(f"{cc.id}\t{cc.client_customer}\t{cc.descriptive_name}\tlevel={cc.level}\tmanager={cc.manager}\tstatus={cc.status}")
	except GoogleAdsException as e:
		print(f"GoogleAdsService.search_stream (hierarchy) failed for customer_id={login_cid}: {e}")
		for err in e.failure.errors:
			print(f"  {err.error_code}: {err.message}")
		print("Hint: If you are accessing a client account, set the MCC id in login_customer_id and pass the client id as the customer_id parameter to queries.")

if __name__ == '__main__':
	main() 