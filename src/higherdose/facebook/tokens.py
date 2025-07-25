#!/usr/bin/env python3
"""
Facebook Graph API Token Generator

This script exchanges short-lived user access tokens for long-lived tokens
and retrieves page access tokens. It uses config.ini for configuration management
and provides both CLI and interactive modes.

By default, tokens are saved to timestamped JSON files in the tokens/ directory.
Use --no-save to skip saving tokens.

Usage:
    python tokens.py --user-token <token> [--page-id <id>]
    python tokens.py --config <config_file> [--no-save]
"""

import sys
import json
import time
import argparse
import urllib.parse
import urllib.request
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from higherdose.utils.style import ansi
from higherdose.utils.logs import report
from higherdose.facebook import engine
from higherdose.facebook.engine import TokenManager
from higherdose.facebook.schema import Token, Page

logger = report.settings(__file__)
config = engine.load(Path("config", "facebook", "facebook.ini"))


def make_api_request(url: str) -> Dict[str, Any]:
    """Make a request to Facebook Graph API"""
    logger.info("Making API request to: %s", url)
    print(f"Making API request to: {ansi.cyan}{url[:100]}"
          f"{'...' if len(url) > 100 else ''}{ansi.reset}")

    try:
        with urllib.request.urlopen(url) as response:
            logger.info("API request successful, status: %s", response.status)
            print(f"API request {ansi.green}successful{ansi.reset}, "
                  f"status: {ansi.green}{response.status}{ansi.reset}")

            response_text = response.read().decode()
            logger.debug("Raw API response: %s", response_text)
            print(f"Raw API response: {ansi.grey}{response_text[:200]}"
                  f"{'...' if len(response_text) > 200 else ''}{ansi.reset}")

            data = json.loads(response_text)
            logger.info("API response parsed successfully")
            return data

    except urllib.error.HTTPError as e:
        logger.error("HTTP Error %s: %s", e.code, e.reason)
        print(f"HTTP {ansi.red}Error{ansi.reset} {e.code}: {e.reason}")

        try:
            error_text = e.read().decode()
            error_data = json.loads(error_text)
            logger.error("API Error details: %s", error_data)
            print(f"API Error details: {ansi.red}{error_data}{ansi.reset}")
        except json.JSONDecodeError as parse_error:
            logger.error("Could not parse error response: %s", parse_error)
            print(f"{ansi.red}Could not parse error response: {parse_error}{ansi.reset}")
        raise

    except (urllib.error.URLError, OSError) as e:
        logger.error("Request failed with exception: %s", str(e))
        print(f"Request {ansi.red}failed{ansi.reset}: {ansi.red}{str(e)}{ansi.reset}")
        raise


def get_long_lived_user_token(short_lived_token: str) -> Token:
    """Exchange short-lived user token for long-lived token"""
    logger.info("Exchanging short-lived token for long-lived token")
    print(f"Exchanging {ansi.yellow}short-lived token{ansi.reset} for "
          f"{ansi.green}long-lived token{ansi.reset}")

    # Log the parameters being used (with sensitive data masked)
    logger.info("Token exchange parameters - grant_type: fb_exchange_token, "
                "client_id: %s, client_secret: %s..., token: %s...",
                config.app.app_id,
                config.app.app_secret[:8] if config.app.app_secret else 'None',
                short_lived_token[:20] if short_lived_token else 'None')

    print("Token exchange parameters:")
    print(f"  Grant Type: {ansi.yellow}fb_exchange_token{ansi.reset}")
    print(f"  Client ID: {ansi.yellow}{config.app.app_id}{ansi.reset}")
    client_secret_display = (
        f"{config.app.app_secret[:8]}"
        f"{'...' if config.app.app_secret and len(config.app.app_secret) > 8 else ''}"
        if config.app.app_secret else 'None'
    )
    print(f"  Client Secret: {ansi.yellow}{client_secret_display}{ansi.reset}")
    token_display = (
        f"{short_lived_token[:20]}"
        f"{'...' if short_lived_token and len(short_lived_token) > 20 else ''}"
        if short_lived_token else 'None'
    )
    print(f"  Token: {ansi.yellow}{token_display}{ansi.reset}")
    print(f"  API Base URL: {ansi.cyan}{config.app.base_url}{ansi.reset}")

    params = {
        'grant_type': 'fb_exchange_token',
        'client_id': config.app.app_id,
        'client_secret': config.app.app_secret,
        'fb_exchange_token': short_lived_token
    }

    url = f"{config.app.base_url}/oauth/access_token?{urllib.parse.urlencode(params)}"

    logger.info("Requesting long-lived user access token...")
    print("Requesting long-lived user access token...")
    data = make_api_request(url)

    expires_at = None
    if 'expires_in' in data:
        expires_at = int(time.time() + data['expires_in'])

    return Token(
        access_token=data['access_token'],
        expires_in=data.get('expires_in'),
        expires_at=expires_at,
        token_type=data.get('token_type', 'bearer')
    )


def get_page_access_tokens(
        user_token: str,
        target_page_id: Optional[str] = None
) -> tuple[Dict[str, Page], dict]:
    """Get page access tokens for all pages or a specific page"""
    logger.info("Getting page access tokens")
    print(f"Getting {ansi.magenta}page access tokens{ansi.reset}...")

    # First get user ID - we need this for the accounts endpoint
    logger.info("Getting user ID via /me endpoint")
    print(f"Getting {ansi.cyan}user ID{ansi.reset} via /me endpoint...")

    user_url = f"{config.app.base_url}/me?access_token={user_token}"
    try:
        user_data = make_api_request(user_url)
        user_id = user_data['id']
        user_name = user_data.get('name', 'Unknown')
        logger.info("User info retrieved - ID: %s, Name: %s", user_id, user_name)
        print("User info retrieved:")
        print(f"  ID: {ansi.yellow}{user_id}{ansi.reset}")
        print(f"  Name: {ansi.yellow}{user_name}{ansi.reset}")
    except Exception as e:
        logger.error("Failed to get user ID: %s", str(e))
        print(f"{ansi.red}Failed to get user ID{ansi.reset}: {str(e)}")
        print(f"\n{ansi.yellow}Possible solutions:{ansi.reset}")
        print(f"  1. Go to {ansi.cyan}Facebook Graph API Explorer{ansi.reset}")
        print(f"  2. Select your app: {ansi.cyan}Page Content Toolkit{ansi.reset}")
        print(f"  3. Click {ansi.cyan}Add permissions{ansi.reset} and add:")
        print(f"     - {ansi.cyan}email{ansi.reset}")
        print(f"     - {ansi.cyan}public_profile{ansi.reset}")
        print(f"     - {ansi.cyan}pages_show_list{ansi.reset}")
        print(f"     - {ansi.cyan}pages_read_engagement{ansi.reset}")
        print(f"  4. Generate a new {ansi.cyan}User Access Token{ansi.reset}")
        print("  5. Run the script again with the new token")
        raise

    # Get page access tokens
    pages_url = f"{config.app.base_url}/{user_id}/accounts?access_token={user_token}"

    logger.info("Requesting page access tokens for user: %s", user_id)
    print(f"Requesting {ansi.magenta}page access tokens{ansi.reset} for "
          f"user: {ansi.yellow}{user_id}{ansi.reset}")
    data = make_api_request(pages_url)

    pages = {}
    logger.info("Processing %d pages from API response", len(data.get('data', [])))

    for page_data in data.get('data', []):
        page_id = page_data['id']
        page_name = page_data.get('name')

        # If target_page_id is specified, only process that page
        if target_page_id and page_id != target_page_id:
            logger.info("Skipping page: %s (%s) - not target page",
                       page_name, page_id)
            continue

        logger.info("Processing page: %s (%s)", page_name, page_id)
        page_config = Page(
            page_id=page_id,
            page_name=page_name,
            category=page_data.get('category'),
            page_access_token=Token(
                access_token=page_data['access_token'],
                # Page tokens typically don't expire for pages you admin
                expires_at=None
            )
        )

        pages[page_id] = page_config

    user_info = {
        'user_id': user_id,
        'user_name': user_name
    }

    return pages, user_info


def convert_expiration_time(expires_in: Optional[int]) -> Optional[datetime]:
    """Convert expires_in seconds to local datetime"""
    if expires_in is None:
        return None

    expiry_timestamp = time.time() + expires_in
    return datetime.fromtimestamp(expiry_timestamp, tz=timezone.utc).astimezone()


def display_expiration_info(token_info: Token, token_name: str) -> None:
    """Display token expiration information"""
    logger.info("Displaying token info for: %s", token_name)
    print(f"\n{ansi.cyan}{token_name}{ansi.reset} Token Information:")
    print(f"  Token: {ansi.yellow}{token_info.access_token[:20]}...{ansi.reset}")

    if token_info.expires_at:
        local_time = datetime.fromtimestamp(token_info.expires_at,
                                           tz=timezone.utc).astimezone()
        time_until = token_info.time_until_expiry()

        logger.info("Token expires at: %s", local_time.isoformat())
        print(f"  Expires: {ansi.yellow}{local_time.strftime('%Y-%m-%d %H:%M:%S %Z')}"
              f"{ansi.reset}")
        if time_until:
            days = time_until // 86400
            hours = (time_until % 86400) // 3600
            logger.info("Time until expiry: %d days, %d hours", days, hours)
            print(f"  Time until expiry: {ansi.green}{days}{ansi.reset} days, "
                  f"{ansi.green}{hours}{ansi.reset} hours")
        else:
            logger.warning("Token is expired")
            print(f"  Status: {ansi.red}EXPIRED{ansi.reset}")
    else:
        logger.info("Token does not expire")
        print(f"  Expires: {ansi.green}Never (or very long-lived){ansi.reset}")


def setup_argument_parser() -> argparse.ArgumentParser:
    """Set up and return the argument parser"""
    parser = argparse.ArgumentParser(description='Facebook Graph API Token Generator')
    parser.add_argument('-ai', '--app-id', help='App ID')
    parser.add_argument('-as', '--app-secret', help='App Secret')
    parser.add_argument('-t', '--temp-token', help='Short-lived user access token')
    parser.add_argument('-p', '--page-id', help='Specific page ID to get token for')
    return parser


def validate_token_input(args: argparse.Namespace) -> tuple[str, Optional[str]]:
    """Validate and return user token and page ID"""
    # Get token from CLI arg or config file
    temp_user_token = args.temp_token or config.token.access_token
    fb_page_id = args.page_id or config.page.page_id

    logger.info("Token source determination - CLI token: %s, Config token: %s",
                'provided' if args.temp_token else 'not provided',
                'available' if config.token.access_token else 'not available')

    if not fb_page_id:
        logger.info("No specific page ID specified, will process all pages")
        print(f"No specific {ansi.yellow}page ID{ansi.reset} specified, will process all pages")

    if not temp_user_token:
        logger.error("No user access token available")
        print(f"{ansi.red}Error:{ansi.reset} No user access token provided.")
        print("Please either:")
        print(f"  1. Use {ansi.cyan}--temp-token <token>{ansi.reset} argument")
        print(f"  2. Set {ansi.cyan}short_lived_token{ansi.reset} in the config file")
        print(f"  3. Get a token from {ansi.cyan}Facebook Graph API Explorer{ansi.reset}")
        sys.exit(1)

    logger.info("Using user token: %s... (length: %d)",
                temp_user_token[:20], len(temp_user_token))
    print(f"Using user token: {ansi.yellow}{temp_user_token[:20]}...{ansi.reset} "
          f"(length: {ansi.yellow}{len(temp_user_token)}{ansi.reset})")

    return temp_user_token, fb_page_id


def process_long_lived_token(temp_user_token: str, token_manager: TokenManager) -> Token:
    """Process step 1: Get long-lived user access token"""
    logger.info("Starting Step 1: Get long-lived user access token")
    print(f"\n{ansi.blue}Step 1:{ansi.reset} Getting long-lived user access token...")
    long_lived_user_token = get_long_lived_user_token(temp_user_token)

    # Update TokenManager with new token info
    token_manager.update_user_config(
        short_lived_token=temp_user_token,
        long_lived_token=long_lived_user_token
    )

    logger.info("Step 1 completed successfully")
    print(f"{ansi.green}Step 1 completed{ansi.reset}")
    display_expiration_info(long_lived_user_token, "Long-lived User")

    return long_lived_user_token


def process_page_tokens(long_lived_user_token: Token, fb_page_id: Optional[str],
                       token_manager: TokenManager) -> tuple[Dict[str, Page], dict]:
    """Process step 2: Get page access tokens"""
    logger.info("Starting Step 2: Get page access tokens")
    print(f"\n{ansi.blue}Step 2:{ansi.reset} Getting page access tokens...")
    pages, user_info = get_page_access_tokens(long_lived_user_token.access_token,
                                             fb_page_id)

    # Update TokenManager with retrieved user info
    token_manager.update_user_config(
        user_id=user_info['user_id'],
        user_name=user_info['user_name']
    )
    logger.info("Updated user config with ID: %s, Name: %s",
                user_info['user_id'], user_info['user_name'])

    if not pages:
        print("No pages found or no access to specified page.")
        return pages, user_info

    # Display page information and update TokenManager
    for page_id, page_cfg in pages.items():
        print(f"\nPage: {page_cfg.page_name} ({page_id})")
        print(f"  Category: {page_cfg.category}")
        display_expiration_info(page_cfg.page_access_token, "Page Access")

        # Add page to TokenManager
        token_manager.add_page_config(page_id, page_cfg)
        logger.info("Added page config for: %s", page_cfg.page_name)
        print(f"  → {ansi.green}Added to token manager{ansi.reset}")

    return pages, user_info


def save_and_display_results(token_manager: TokenManager) -> None:
    """Process step 3: Save tokens and display results"""
    logger.info("Starting Step 3: Save token data")
    print(f"\n{ansi.blue}Step 3:{ansi.reset} Saving token data...")
    saved_file = token_manager.save_run_data()
    logger.info("Token data saved to: %s", saved_file)
    print(f"Token data saved to: {ansi.cyan}{saved_file}{ansi.reset}")

    # Display summary
    summary = token_manager.get_summary()
    print(f"\n{ansi.magenta}Token Summary:{ansi.reset}")
    print(f"  Run ID: {ansi.yellow}{summary['run_id']}{ansi.reset}")
    print(f"  User: {ansi.yellow}{summary['user_name']}{ansi.reset} "
          f"({ansi.yellow}{summary['user_id']}{ansi.reset})")
    print(f"  Pages: {ansi.yellow}{summary['page_count']}{ansi.reset}")
    for page_name in summary['page_names']:
        print(f"    - {ansi.yellow}{page_name}{ansi.reset}")

    logger.info("Token generation completed successfully")
    print(f"\n✅ Token generation {ansi.green}completed successfully{ansi.reset}!")

    print("💡 Your tokens are now saved as timestamped JSON files.")
    print("📅 Tip: Add token expiration dates to your calendar for tracking.")


def main():
    """Main function - orchestrates the token generation workflow"""
    parser = setup_argument_parser()
    args = parser.parse_args()

    # Validate input and get tokens
    temp_user_token, fb_page_id = validate_token_input(args)

    # Initialize TokenManager
    token_manager = TokenManager()

    try:
        # Step 1: Get long-lived user token
        long_lived_user_token = process_long_lived_token(temp_user_token, token_manager)

        # Step 2: Get page access tokens
        process_page_tokens(long_lived_user_token, fb_page_id, token_manager)

        # Step 3: Save tokens and display results
        save_and_display_results(token_manager)

    except urllib.error.HTTPError as e:
        logger.error("HTTP error during token generation: %s", str(e))
        print(f"\n❌ HTTP {ansi.red}Error{ansi.reset}: {e}")
        sys.exit(1)

    except (urllib.error.URLError, OSError) as e:
        logger.error("Unexpected error during token generation: %s", str(e))
        print(f"\n❌ Unexpected {ansi.red}Error{ansi.reset}: {e}")
        print("Check the log file for detailed error information.")
        sys.exit(1)


if __name__ == '__main__':
    main()
