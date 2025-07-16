#!/usr/bin/env python3
"""
Playwright-based Slack message fetcher with automatic authentication.

This script uses Playwright to:
1. Automatically log into Slack (or use existing session)
2. Intercept API requests to extract fresh tokens/cookies
3. Fetch messages using either intercepted API calls or direct browser automation
4. Handle authentication expiration automatically

Dependencies:
    playwright
    python-dateutil
    requests (fallback)
"""
from __future__ import annotations

import json
import os
import sys
import time
import pathlib
import re
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse, parse_qs

from playwright.async_api import async_playwright, Page, Route, Request, Response
from dateutil import parser as date_parser


# -------------- Config -------------------------------------------------------
EXPORT_DIR = pathlib.Path("slack/markdown_exports")
TRACK_FILE = pathlib.Path("slack/conversion_tracker.json")
ROLODEX_FILE = pathlib.Path("rolodex.json")
CREDENTIALS_FILE = pathlib.Path("slack/playwright_creds.json")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

# Slack workspace config
WORKSPACE_URL = "https://higherdosemanagement.slack.com"
TEAM_ID = "TA97020CV"


# -------------- Credential Management ----------------------------------------

class SlackCredentials:
    def __init__(self):
        self.cookies: Dict[str, str] = {}
        self.token: str = ""
        self.user_id: str = ""
        self.team_id: str = ""
        self.last_updated: float = 0
        
    def is_valid(self) -> bool:
        """Check if credentials are recent and have required fields."""
        if not self.token or not self.cookies:
            return False
        # Consider credentials stale after 1 hour
        return (time.time() - self.last_updated) < 3600
    
    def save(self):
        """Save credentials to file."""
        data = {
            "cookies": self.cookies,
            "token": self.token,
            "user_id": self.user_id,
            "team_id": self.team_id,
            "last_updated": self.last_updated
        }
        CREDENTIALS_FILE.write_text(json.dumps(data, indent=2))
    
    @classmethod
    def load(cls) -> 'SlackCredentials':
        """Load credentials from file."""
        creds = cls()
        if CREDENTIALS_FILE.exists():
            try:
                data = json.loads(CREDENTIALS_FILE.read_text())
                creds.cookies = data.get("cookies", {})
                creds.token = data.get("token", "")
                creds.user_id = data.get("user_id", "")
                creds.team_id = data.get("team_id", "")
                creds.last_updated = data.get("last_updated", 0)
            except Exception as e:
                print(f"⚠️  Error loading credentials: {e}")
        return creds
    
    def update_from_request(self, request: Request, response_data: Dict[str, Any] = None):
        """Update credentials from intercepted request."""
        # Extract token from request
        if request.method == "POST":
            try:
                post_data = request.post_data
                if post_data and "token" in post_data:
                    # Extract token from form data
                    if "xoxc-" in post_data:
                        token_match = re.search(r'(xoxc-[a-zA-Z0-9-]+)', post_data)
                        if token_match:
                            self.token = token_match.group(1)
            except:
                pass
        
        # Extract from headers or cookies
        headers = request.headers
        if "cookie" in headers:
            cookie_str = headers["cookie"]
            # Parse cookies
            for cookie_pair in cookie_str.split(";"):
                if "=" in cookie_pair:
                    key, value = cookie_pair.strip().split("=", 1)
                    self.cookies[key] = value
                    
                    # Extract token from 'd' cookie if present
                    if key == "d" and value and not self.token:
                        try:
                            import urllib.parse
                            decoded = urllib.parse.unquote(value)
                            if decoded.startswith(('xoxc-', 'xoxd-')):
                                self.token = decoded
                        except:
                            pass
        
        # Update from response data if available
        if response_data:
            if "user_id" in response_data:
                self.user_id = response_data["user_id"]
            if "team_id" in response_data:
                self.team_id = response_data["team_id"]
        
        if self.token:  # Only update timestamp if we got something useful
            self.last_updated = time.time()


# -------------- Playwright Browser Manager ----------------------------------

class SlackBrowser:
    def __init__(self):
        self.page: Optional[Page] = None
        self.context = None
        self.browser = None
        self.credentials = SlackCredentials.load()
        self.intercepted_data: List[Dict[str, Any]] = []
        
    async def start(self, headless: bool = True):
        """Start browser and setup interception."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=headless)
        
        # Create context with persistent session
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
        )
        
        # Restore cookies if we have them
        if self.credentials.cookies:
            cookies = []
            for name, value in self.credentials.cookies.items():
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": ".slack.com",
                    "path": "/"
                })
            await self.context.add_cookies(cookies)
        
        self.page = await self.context.new_page()
        
        # Setup request/response interception
        await self.page.route("**/api/**", self._intercept_api_call)
        
    async def _intercept_api_call(self, route: Route, request: Request):
        """Intercept Slack API calls to extract credentials and data."""
        try:
            # Continue the request
            response = await route.fetch()
            
            # Update credentials from this request
            self.credentials.update_from_request(request)
            
            # If this is a conversations.history or similar call, store the response
            if any(endpoint in request.url for endpoint in [
                "conversations.history", "conversations.list", "users.list", 
                "conversations.info", "conversations.replies"
            ]):
                try:
                    response_text = await response.text()
                    response_data = json.loads(response_text)
                    
                    self.intercepted_data.append({
                        "url": request.url,
                        "method": request.method,
                        "post_data": request.post_data,
                        "response": response_data,
                        "timestamp": time.time()
                    })
                    
                    # Update credentials from response if it contains user/team info
                    self.credentials.update_from_request(request, response_data)
                    
                except Exception as e:
                    print(f"⚠️  Error parsing API response: {e}")
            
            # Continue with the response
            await route.fulfill(response=response)
            
        except Exception as e:
            print(f"⚠️  Error intercepting request: {e}")
            await route.continue_()
    
    async def ensure_logged_in(self) -> bool:
        """Ensure we're logged into Slack."""
        if not self.page:
            return False
            
        print("🔍 Checking Slack login status...")
        # Start at main Slack page - more intuitive for users
        await self.page.goto("https://slack.com")
        
        # Wait a moment for page to load
        await self.page.wait_for_timeout(3000)
        
        # Try to navigate to workspace after initial load
        try:
            await self.page.goto(WORKSPACE_URL)
            await self.page.wait_for_timeout(2000)
        except Exception as e:
            print(f"⚠️  Could not navigate directly to workspace: {e}")
            print("💡 Please navigate to your HigherDOSE workspace manually")
        
        # Check if we're already logged in
        try:
            # Look for signs we're logged in (channel list, user menu, etc.)
            logged_in_selectors = [
                '[data-qa="channel_sidebar"]',
                '[data-qa="user_menu"]',
                '.c-virtual_list',
                '[data-qa="workspace-name"]'
            ]
            
            for selector in logged_in_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=5000)
                    if element:
                        print("✅ Already logged into Slack!")
                        return True
                except:
                    continue
                    
        except Exception as e:
            print(f"⚠️  Error checking login status: {e}")
        
        # If we reach here, we need to login
        print("🔐 Need to log into Slack...")
        print("📖 Please follow these steps in the browser window:")
        print("   1. Log into your Slack account if prompted")
        print("   2. Navigate to: HigherDOSE workspace")
        print("   3. You should see the channel sidebar")
        print("   4. Once you see the workspace, press Enter here...")
        print()
        
        # Wait for user to log in manually
        input("Press Enter after you can see the HigherDOSE workspace...")
        
        # Try to navigate to workspace one more time to verify
        try:
            await self.page.goto(WORKSPACE_URL)
            await self.page.wait_for_timeout(3000)
        except:
            pass
        
        # Verify login worked
        try:
            await self.page.wait_for_selector('[data-qa="channel_sidebar"]', timeout=10000)
            print("✅ Login successful!")
            return True
        except:
            # Give more specific guidance
            print("❌ Could not detect HigherDOSE workspace.")
            print("💡 Make sure you're in the HigherDOSE workspace, not just logged into Slack.")
            print("   You should see channels like #general, #marketing, etc.")
            
            retry = input("Try again? (y/N): ")
            if retry.lower() == 'y':
                return await self.ensure_logged_in()
            return False
    
    async def get_channel_list(self) -> Dict[str, str]:
        """Get list of channels by triggering Slack to load them."""
        if not self.page:
            return {}
            
        print("📋 Getting channel list...")
        
        # Clear previous intercepted data
        self.intercepted_data.clear()
        
        # Navigate to main workspace to trigger API calls
        await self.page.goto(f"{WORKSPACE_URL}/ssb/redirect")
        await self.page.wait_for_timeout(3000)
        
        # Try to trigger channel list loading
        try:
            # Click on "Channels" or channel sidebar to load channel list
            selectors_to_try = [
                '[data-qa="channel_sidebar"]',
                '.c-virtual_list',
                '[data-qa="workspace-name"]'
            ]
            
            for selector in selectors_to_try:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=3000)
                    if element:
                        await element.click()
                        await self.page.wait_for_timeout(2000)
                        break
                except:
                    continue
                    
        except Exception as e:
            print(f"⚠️  Error triggering channel list: {e}")
        
        # Extract channels from intercepted data
        channels = {}
        for data in self.intercepted_data:
            if "conversations.list" in data["url"]:
                response = data.get("response", {})
                if response.get("ok"):
                    for channel in response.get("channels", []):
                        name = channel.get("name", "")
                        channel_id = channel.get("id", "")
                        if name and channel_id:
                            channels[name] = channel_id
        
        print(f"✅ Found {len(channels)} channels")
        return channels
    
    async def fetch_conversation_history(self, channel_id: str, oldest_ts: float = 0) -> List[Dict[str, Any]]:
        """Fetch conversation history for a channel."""
        if not self.page:
            return []
        
        print(f"📥 Fetching history for channel {channel_id}...")
        
        # Clear previous data
        self.intercepted_data.clear()
        
        # Navigate to the channel to trigger history loading
        channel_url = f"{WORKSPACE_URL}/archives/{channel_id}"
        await self.page.goto(channel_url)
        
        # Wait for messages to load
        await self.page.wait_for_timeout(5000)
        
        # Scroll up to load more history if needed
        for _ in range(3):
            await self.page.keyboard.press("PageUp")
            await self.page.wait_for_timeout(1000)
        
        # Extract messages from intercepted API calls
        all_messages = []
        for data in self.intercepted_data:
            if "conversations.history" in data["url"] or "conversations.replies" in data["url"]:
                response = data.get("response", {})
                if response.get("ok"):
                    messages = response.get("messages", [])
                    for msg in messages:
                        if float(msg.get("ts", "0")) > oldest_ts:
                            all_messages.append(msg)
        
        # Remove duplicates and sort by timestamp
        seen_ts = set()
        unique_messages = []
        for msg in all_messages:
            ts = msg.get("ts")
            if ts not in seen_ts:
                seen_ts.add(ts)
                unique_messages.append(msg)
        
        unique_messages.sort(key=lambda x: float(x.get("ts", "0")))
        
        print(f"✅ Found {len(unique_messages)} new messages")
        return unique_messages
    
    async def get_user_list(self) -> Dict[str, str]:
        """Get user list from intercepted API calls."""
        print("👥 Getting user list...")
        
        # Clear previous data
        self.intercepted_data.clear()
        
        # Navigate to workspace settings or members page to trigger user list loading
        try:
            await self.page.goto(f"{WORKSPACE_URL}/admin")
            await self.page.wait_for_timeout(3000)
        except:
            # Fallback to main page
            await self.page.goto(f"{WORKSPACE_URL}/ssb/redirect")
            await self.page.wait_for_timeout(3000)
        
        # Extract users from intercepted data
        users = {}
        for data in self.intercepted_data:
            if "users.list" in data["url"]:
                response = data.get("response", {})
                if response.get("ok"):
                    for member in response.get("members", []):
                        user_id = member.get("id", "")
                        profile = member.get("profile", {})
                        display_name = (
                            profile.get("display_name") or 
                            profile.get("real_name") or 
                            member.get("name", "")
                        )
                        if user_id and display_name:
                            users[user_id] = display_name
        
        print(f"✅ Found {len(users)} users")
        return users
    
    async def save_credentials(self):
        """Save intercepted credentials."""
        if self.credentials.token:
            self.credentials.save()
            print("💾 Saved fresh credentials")
    
    async def close(self):
        """Close browser and save credentials."""
        await self.save_credentials()
        if self.browser:
            await self.browser.close()


# -------------- Utility Functions -------------------------------------------

def _load_tracker() -> Dict[str, Any]:
    """Load conversation tracking data."""
    if TRACK_FILE.exists():
        data = json.loads(TRACK_FILE.read_text())
        if "channels" not in data:
            data["channels"] = {}
        return data
    return {"channels": {}}


def _save_tracker(data: Dict[str, Any]) -> None:
    """Save conversation tracking data."""
    TRACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACK_FILE.write_text(json.dumps(data, indent=2))


def _markdown_line(msg: Dict[str, Any], users: Dict[str, str]) -> str:
    """Convert message to markdown line."""
    ts_float = float(msg["ts"])
    ts_str = datetime.fromtimestamp(ts_float).strftime("%Y-%m-%d %H:%M")
    
    user_id = msg.get("user", "")
    user_name = users.get(user_id, f"User_{user_id[-6:]}" if user_id else "System")
    
    text = msg.get("text", "").replace("\n", "  \n")
    # Indent replies for threads
    prefix = "    " if msg.get("parent_user_id") else ""
    return f"{prefix}- **{ts_str}** *{user_name}*: {text}"


def _create_safe_filename(channel_name: str, channel_id: str) -> str:
    """Create a safe filename for the channel."""
    if channel_id.startswith('D'):
        # DM channel
        safe_name = f"dm_{channel_id}"
    else:
        # Regular channel
        safe_name = channel_name or f"channel_{channel_id}"
    
    # Make filename safe
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', safe_name)
    safe_name = re.sub(r'_{2,}', '_', safe_name)
    safe_name = safe_name.strip('_')
    
    return safe_name


# -------------- Main Script -------------------------------------------------

async def main():
    """Main async function."""
    print("🚀 Playwright-based Slack Fetcher")
    print(f"📍 Workspace: {WORKSPACE_URL}")
    print()
    
    browser = SlackBrowser()
    
    try:
        # Start browser (headless=False to allow manual login if needed)
        await browser.start(headless=False)
        
        # Ensure we're logged in
        if not await browser.ensure_logged_in():
            print("❌ Failed to log in. Exiting.")
            return
        
        # Get initial data
        print("📊 Loading workspace data...")
        channels = await browser.get_channel_list()
        users = await browser.get_user_list()
        
        if not channels:
            print("⚠️  No channels found. You may need to navigate manually in the browser.")
        
        # Interactive loop
        while True:
            print(f"\nAvailable commands:")
            print(f"  • 'list' - Show available channels ({len(channels)} found)")
            print(f"  • '<channel_name>' - Fetch messages from channel")
            print(f"  • 'refresh <channel>' - Re-fetch entire conversation")
            print(f"  • 'q' - Quit")
            
            user_input = input("\nCommand: ").strip()
            
            if user_input.lower() == "q":
                print("👋 Goodbye!")
                break
            
            if user_input.lower() == "list":
                print(f"\nChannels ({len(channels)}):")
                for name in sorted(channels.keys())[:50]:
                    print(f"  #{name}")
                if len(channels) > 50:
                    print(f"  ... and {len(channels) - 50} more")
                continue
            
            refresh_mode = False
            if user_input.lower().startswith("refresh "):
                refresh_mode = True
                channel_name = user_input[8:].strip().lstrip("#")
            else:
                channel_name = user_input.lstrip("#")
            
            if channel_name not in channels:
                print(f"❌ Channel '{channel_name}' not found. Use 'list' to see available channels.")
                continue
            
            channel_id = channels[channel_name]
            
            # Load tracking data
            tracker = _load_tracker()
            last_ts = 0 if refresh_mode else tracker["channels"].get(channel_id, 0)
            
            if refresh_mode:
                print(f"🔄 Refreshing entire conversation for #{channel_name}")
            else:
                print(f"📥 Fetching new messages from #{channel_name} (since {last_ts})")
            
            # Fetch messages
            messages = await browser.fetch_conversation_history(channel_id, last_ts)
            
            if not messages:
                print("📭 No new messages found.")
                continue
            
            # Save to markdown
            safe_name = _create_safe_filename(channel_name, channel_id)
            md_path = EXPORT_DIR / f"{safe_name}.md"
            
            with md_path.open("a", encoding="utf-8") as f:
                for msg in messages:
                    f.write(_markdown_line(msg, users) + "\n")
            
            # Update tracker
            if messages:
                highest_ts = max(float(m["ts"]) for m in messages)
                tracker["channels"][channel_id] = highest_ts
                _save_tracker(tracker)
            
            print(f"✅ Added {len(messages)} messages to {md_path}")
    
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await browser.close()


def run_main():
    """Run the async main function."""
    asyncio.run(main())


if __name__ == "__main__":
    run_main() 