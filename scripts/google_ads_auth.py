#!/usr/bin/env python3
import sys
from pathlib import Path
import yaml
from google_auth_oauthlib.flow import InstalledAppFlow

CONFIG = Path('config/google_ads/google-ads.yaml')
SCOPES = ['https://www.googleapis.com/auth/adwords']


def main() -> None:
	if not CONFIG.exists():
		raise SystemExit(f"Missing config: {CONFIG}")
	cfg = yaml.safe_load(CONFIG.read_text())
	client_id = cfg.get('client_id')
	client_secret = cfg.get('client_secret')
	if not client_id or not client_secret:
		raise SystemExit('client_id/client_secret missing in config')

	client_config = {
		"installed": {
			"client_id": client_id,
			"client_secret": client_secret,
			"auth_uri": "https://accounts.google.com/o/oauth2/auth",
			"token_uri": "https://oauth2.googleapis.com/token",
			"redirect_uris": ["http://localhost"],
		}
	}

	print('Opening browser for Google Ads OAuth consent...')
	flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
	creds = flow.run_local_server(port=0, prompt='consent')

	refresh_token = getattr(creds, 'refresh_token', None)
	if not refresh_token:
		raise SystemExit('No refresh_token returned. Ensure you approved offline access and try again.')

	cfg['refresh_token'] = refresh_token
	CONFIG.write_text(yaml.safe_dump(cfg, sort_keys=False))
	print(f'Saved refresh_token to {CONFIG}')


if __name__ == '__main__':
	main() 