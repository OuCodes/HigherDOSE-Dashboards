#!/usr/bin/env python3
"""Quick utility to inspect which permissions a Facebook access token has.

Run directly:
    python tests/test_me_permissions.py --token EAA...  # explicit token

If --token is omitted, the script will try to load the newest token file
created by `growthkit.connectors.facebook.tokens` and use the long-lived **user** token
found there.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from typing import Dict, Any, Optional

from growthkit.utils.style import ansi
from growthkit.utils.logs import report
from growthkit.connectors.facebook.engine import TokenManager

logger = report.settings(__file__)

GRAPH_VERSION = "v23.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"


def graph_get(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{BASE_URL}/{endpoint}?{query}"
    logger.info("GET %s", url)
    try:
        with urllib.request.urlopen(url) as resp:
            body = resp.read().decode()
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="ignore") if hasattr(e, "read") else ""
        print(f"{ansi.red}HTTP {e.code}: {e.reason}{ansi.reset}\n{body}")
        sys.exit(1)


def load_latest_user_token() -> Optional[str]:
    tm = TokenManager()
    latest = tm.get_latest_run_file()
    if not latest:
        return None
    tm.load_run_data(latest)
    if tm.user_config.long_lived_token and tm.user_config.long_lived_token.access_token:
        return tm.user_config.long_lived_token.access_token
    return None


def main(argv: Optional[list[str]] = None):
    parser = argparse.ArgumentParser(description="Show granted / declined permissions for an access token")
    parser.add_argument("--token", help="Access token to inspect (falls back to latest token file if omitted)")
    args = parser.parse_args(argv)

    token = args.token or load_latest_user_token()
    if not token:
        print(f"{ansi.red}No token supplied and no token file found.{ansi.reset}")
        print("Run growthkit.connectors.facebook.tokens first or pass --token.")
        sys.exit(1)

    print(f"🔍 Inspecting permissions for token: {ansi.yellow}{token[:20]}...{ansi.reset}\n")

    data = graph_get("me/permissions", {"access_token": token})
    perms = data.get("data", [])
    if not perms:
        print("No permission entries returned.")
        sys.exit(0)

    granted = [p for p in perms if p.get("status") == "granted"]
    declined = [p for p in perms if p.get("status") == "declined"]

    print(f"{ansi.green}GRANTED{ansi.reset} permissions ({len(granted)}):")
    for p in granted:
        print("  •", p["permission"])

    if declined:
        print(f"\n{ansi.red}DECLINED{ansi.reset} / missing permissions ({len(declined)}):")
        for p in declined:
            print("  •", p["permission"])

    needed = {"pages_show_list", "pages_read_user_content", "ads_read"}
    missing = [perm for perm in needed if perm not in {p["permission"] for p in granted}]
    if missing:
        print(f"\n{ansi.yellow}⚠️  Missing required permission(s):{ansi.reset}")
        for m in missing:
            print("  →", m)
    else:
        print(f"\n{ansi.green}✅ Token has all required permissions for comment extractor.{ansi.reset}")


if __name__ == "__main__":
    main()
