#!/usr/bin/env python3
import sys
import json
import csv
import argparse
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

CONFIG_DIR = Path("config", "facebook")
TOKENS_DIR = CONFIG_DIR / "tokens"
AD_ACCOUNT_FILE = CONFIG_DIR / "ad-account-id.json"
GRAPH_VERSION = "v23.0"
BASE_URL = f"https://graph.facebook.com/{GRAPH_VERSION}"

SAMPLE_HEADER = [
    "Day",
    "Delivery status",
    "Delivery level",
    "Ad Set Name",
    "Ad name",
    "Impressions",
    "CPM (cost per 1,000 impressions)",
    "Reach",
    "Cost per 1,000 Accounts Center accounts reached",
    "Frequency",
    "CTR (all)",
    "Unique outbound clicks",
    "Unique outbound CTR (click-through rate)",
    "Cost per unique outbound click",
    "Landing page views",
    "Cost per landing page view",
    "Content views",
    "Cost per content view",
    "Adds to cart",
    "Cost per add to cart",
    "Checkouts Initiated",
    "Cost per checkout initiated",
    "Adds of payment info",
    "Cost per add of payment info",
    "Purchases",
    "Cost per purchase",
    "Purchases conversion value",
    "Average purchases conversion value",
    "Purchase ROAS (return on ad spend)",
    "Amount spent (USD)",
    "Link (ad settings)",
    "Attribution setting",
    "Campaign ID",
    "Ad set ID",
    "Ad ID",
    "Result type",
    "Results",
    "Cost per result",
    "Link clicks",
    "CPC (cost per link click)",
    "Campaign Delivery",
    "Ad Set Delivery",
    "Ad Delivery",
    "Reporting starts",
    "Reporting ends",
]


def _read_latest_token() -> Optional[str]:
    token_files = sorted(TOKENS_DIR.glob("tokens-*.json"))
    if not token_files:
        return None
    latest = token_files[-1]
    try:
        data = json.loads(latest.read_text())
        return data.get("user_config", {}).get("long_lived_token", {}).get("access_token")
    except Exception:
        return None


def _read_config_token() -> Optional[str]:
    ini = CONFIG_DIR / "facebook.ini"
    if not ini.exists():
        return None
    token: Optional[str] = None
    for line in ini.read_text().splitlines():
        if line.strip().startswith("access_token"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                token = parts[1].strip()
                break
    return token


def _read_account_id() -> str:
    if not AD_ACCOUNT_FILE.exists():
        raise FileNotFoundError(f"Missing {AD_ACCOUNT_FILE}")
    data = json.loads(AD_ACCOUNT_FILE.read_text())
    if not isinstance(data, dict) or not data:
        raise ValueError("ad-account-id.json must be an object with at least one key/value")
    account_value = next(iter(data.values()))
    return str(account_value)


def _api_get(url: str) -> Dict[str, Any]:
    with urllib.request.urlopen(url) as resp:
        body = resp.read().decode()
        return json.loads(body)


def _fetch_all_pages(url: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    next_url = url
    while next_url:
        data = _api_get(next_url)
        rows.extend(data.get("data", []))
        paging = data.get("paging", {})
        next_url = paging.get("next")
    return rows


def _float(val: Any) -> Optional[float]:
    try:
        if val is None:
            return None
        return float(val)
    except Exception:
        return None


def _int(val: Any) -> Optional[int]:
    try:
        if val is None:
            return None
        return int(float(val))
    except Exception:
        return None


def _get_action_value(container: Dict[str, Any], key: str, action_type: str) -> Optional[float]:
    items = container.get(key)
    if not isinstance(items, list):
        return None
    for item in items:
        if item.get("action_type") == action_type:
            return _float(item.get("value"))
    return None


def _get_cost_per_action(container: Dict[str, Any], action_type: str) -> Optional[float]:
    items = container.get("cost_per_action_type")
    if not isinstance(items, list):
        return None
    for item in items:
        if item.get("action_type") == action_type:
            return _float(item.get("value"))
    return None


def _safe_div(n: Optional[float], d: Optional[float]) -> Optional[float]:
    if n is None or d in (None, 0, 0.0):
        return None
    return n / d


def _format_month(dt: date) -> str:
    return dt.strftime('%b').lower()


def _compute_last_30() -> Tuple[str, str, date, date]:
    end = date.today()
    start = end - timedelta(days=29)
    return start.isoformat(), end.isoformat(), start, end


def _default_output_path(output_dir: Path, start_dt: date, end_dt: date) -> Path:
    name = (
        f"meta-mtd-export-{_format_month(start_dt)}-{start_dt.strftime('%d')}-{start_dt.strftime('%Y')}"
        f"-to-{_format_month(end_dt)}-{end_dt.strftime('%d')}-{end_dt.strftime('%Y')}.auto.csv"
    )
    return output_dir / name


def build_row(ins: Dict[str, Any]) -> List[Any]:
    date_start = ins.get("date_start")
    date_stop = ins.get("date_stop")

    impressions = _int(ins.get("impressions")) or 0
    reach = _int(ins.get("reach")) or 0
    spend = _float(ins.get("spend")) or 0.0

    cpm = _float(ins.get("cpm"))
    frequency = _float(ins.get("frequency"))
    ctr = _float(ins.get("ctr"))

    # unique outbound clicks (best effort)
    uniq_outbound = ins.get("unique_outbound_clicks")
    if isinstance(uniq_outbound, list) and uniq_outbound:
        # some versions return list of dicts with value
        uniq_outbound_val = _float(uniq_outbound[0].get("value"))
    else:
        uniq_outbound_val = _float(uniq_outbound)

    # landing page views can be number or list
    lpv = _float(ins.get("landing_page_views"))
    if lpv is None:
        lpv = _get_action_value(ins, "actions", "landing_page_view")  # fallback action name variant

    # action metrics
    view_content = _get_action_value(ins, "actions", "view_content")
    add_to_cart = _get_action_value(ins, "actions", "add_to_cart")
    initiate_checkout = _get_action_value(ins, "actions", "initiate_checkout")
    add_payment_info = _get_action_value(ins, "actions", "add_payment_info")
    purchases = _get_action_value(ins, "actions", "purchase")

    purchase_value = _get_action_value(ins, "action_values", "purchase")

    # costs per action (if provided); otherwise compute
    cpp_unique_outbound = _float(ins.get("cost_per_unique_outbound_click"))
    if cpp_unique_outbound is None:
        cpp_unique_outbound = _safe_div(spend, uniq_outbound_val)

    cplpv = _float(ins.get("cost_per_landing_page_view"))
    if cplpv is None:
        cplpv = _safe_div(spend, lpv)

    cpvc = _get_cost_per_action(ins, "view_content")
    if cpvc is None:
        cpvc = _safe_div(spend, view_content)

    cpatc = _get_cost_per_action(ins, "add_to_cart")
    if cpatc is None:
        cpatc = _safe_div(spend, add_to_cart)

    cpco = _get_cost_per_action(ins, "initiate_checkout")
    if cpco is None:
        cpco = _safe_div(spend, initiate_checkout)

    cpapi = _get_cost_per_action(ins, "add_payment_info")
    if cpapi is None:
        cpapi = _safe_div(spend, add_payment_info)

    cpp = _get_cost_per_action(ins, "purchase") or _safe_div(spend, purchases)

    avg_purchase_value = _safe_div(purchase_value, purchases)
    roas = _safe_div(purchase_value, spend)

    link_clicks = _int(ins.get("inline_link_clicks"))
    cpc = _float(ins.get("cpc"))

    uniq_outbound_ctr = _safe_div(uniq_outbound_val, float(reach) if reach else None)

    attribution_setting = ins.get("attribution_setting")

    row = [
        date_start,
        "",
        "",
        "",
        "",
        impressions,
        cpm,
        reach,
        _safe_div(spend * 1000.0, float(reach) if reach else None),
        frequency,
        ctr,
        uniq_outbound_val,
        uniq_outbound_ctr,
        cpp_unique_outbound,
        _int(lpv) if lpv is not None else None,
        cplpv,
        _int(view_content) if view_content is not None else None,
        cpvc,
        _int(add_to_cart) if add_to_cart is not None else None,
        cpatc,
        _int(initiate_checkout) if initiate_checkout is not None else None,
        cpco,
        _int(add_payment_info) if add_payment_info is not None else None,
        cpapi,
        _int(purchases) if purchases is not None else None,
        cpp,
        purchase_value,
        avg_purchase_value,
        roas,
        spend,
        "",
        attribution_setting,
        "",
        "",
        "",
        "Website purchases",
        _int(purchases) if purchases is not None else None,
        cpp,
        link_clicks,
        cpc,
        "",
        "",
        "",
        date_start,
        date_stop,
    ]
    return row


def main():
    parser = argparse.ArgumentParser(description="Export Facebook Ads Insights CSV matching sample columns")
    parser.add_argument("--start", help="Start date YYYY-MM-DD")
    parser.add_argument("--end", help="End date YYYY-MM-DD")
    parser.add_argument("--output", help="Output CSV path")
    parser.add_argument("--output-dir", default=str(Path("data", "ads")), help="Directory to write CSV when auto-naming")
    parser.add_argument("--auto-last-30", action="store_true", help="Compute last 30 days and auto-name the file")
    args = parser.parse_args()

    if args.auto_last_30:
        start_str, end_str, start_dt, end_dt = _compute_last_30()
        args.start = start_str
        args.end = end_str
        if not args.output:
            args.output = str(_default_output_path(Path(args.output_dir), start_dt, end_dt))
    else:
        if not (args.start and args.end):
            print("Error: Provide --start and --end or use --auto-last-30", file=sys.stderr)
            sys.exit(1)
        if not args.output:
            print("Error: --output is required when not using --auto-last-30", file=sys.stderr)
            sys.exit(1)

    token = _read_latest_token() or _read_config_token()
    if not token:
        print("Error: No access token found. Run the token generator first.", file=sys.stderr)
        sys.exit(1)

    account_id = _read_account_id()

    # Request fields
    fields = [
        "date_start,date_stop,impressions,cpm,reach,frequency,ctr,spend,cpc,",
        # link clicks (valid metric) and outbound clicks
        "inline_link_clicks,unique_outbound_clicks,",
        # actions and values for event metrics
        "actions,action_values,cost_per_action_type,",
        # attribution
        "attribution_setting",
    ]
    fields_param = "".join(fields)

    params = {
        "level": "account",
        "time_range": json.dumps({"since": args.start, "until": args.end}),
        "time_increment": 1,
        "fields": fields_param,
        "access_token": token,
    }

    url = f"{BASE_URL}/act_{account_id}/insights?{urllib.parse.urlencode(params)}"
    rows = _fetch_all_pages(url)

    rows.sort(key=lambda r: (r.get("date_start", ""), r.get("date_stop", "")))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(SAMPLE_HEADER)
        for r in rows:
            writer.writerow(build_row(r))

    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main() 