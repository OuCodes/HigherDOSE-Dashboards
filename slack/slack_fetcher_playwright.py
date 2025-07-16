#!/usr/bin/env python3
"""
Playwright-based Slack message fetcher with automatic authentication.

This script uses Playwright to:
1. Automatically log into Slack (or use existing session)
2. Intercept API requests to extract fresh tokens/cookies
3. Fetch messages using either intercepted API calls or direct browser automation
4. Handle authentication expiration automatically
5. Categorize conversations by type (channels, DMs, multi-person DMs)

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
from enum import Enum

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


# -------------- Conversation Type Enum ---------------------------------------

class ConversationType(Enum):
    CHANNEL = "channel"
    DM = "dm"
    MULTI_PERSON_DM = "multi_person_dm"
    UNKNOWN = "unknown"


# -------------- Conversation Data Structure ---------------------------------

class ConversationInfo:
    def __init__(self, 
                 name: str, 
                 id: str, 
                 conversation_type: ConversationType,
                 is_private: bool = False,
                 member_count: int = 0,
                 members: List[str] = None):
        self.name = name
        self.id = id
        self.conversation_type = conversation_type
        self.is_private = is_private
        self.member_count = member_count
        self.members = members or []
    
    def __repr__(self):
        type_symbol = {
            ConversationType.CHANNEL: "#",
            ConversationType.DM: "@",
            ConversationType.MULTI_PERSON_DM: "👥",
            ConversationType.UNKNOWN: "?"
        }
        symbol = type_symbol.get(self.conversation_type, "?")
        private_marker = "🔒" if self.is_private else ""
        member_info = f" ({self.member_count} members)" if self.member_count > 0 else ""
        return f"{symbol}{self.name}{private_marker}{member_info}"


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
        
    async def start(self, headless: bool = False, use_existing_profile: bool = True):
        """Start browser and setup interception."""
        playwright = await async_playwright().start()
        
        if use_existing_profile:
            # Use your existing Chrome profile where you're already logged into Slack
            chrome_profile_path = os.path.expanduser("~/Library/Application Support/Google/Chrome/Default")
            
            # Check if Chrome profile exists
            if os.path.exists(chrome_profile_path):
                print(f"🔗 Using existing Chrome profile: {chrome_profile_path}")
                self.context = await playwright.chromium.launch_persistent_context(
                    user_data_dir=chrome_profile_path,
                    headless=headless,
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
                )
                self.browser = self.context.browser
            else:
                print("⚠️  Chrome profile not found, falling back to new browser")
                use_existing_profile = False
        
        if not use_existing_profile:
            # Fallback to new browser instance
            self.browser = await playwright.chromium.launch(headless=headless)
            self.context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
            )
        
        # Get or create page
        if use_existing_profile and hasattr(self.context, 'pages') and self.context.pages:
            # Use existing page from persistent context
            self.page = self.context.pages[0]
            print("📄 Using existing browser page")
        else:
            # Create new page
            self.page = await self.context.new_page()
            print("📄 Created new browser page")
            
            # Restore cookies if we have them (only for new contexts)
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
        
        # Setup request/response interception
        await self.page.route("**/api/**", self._intercept_api_call)
        print("🔍 Set up API interception for **/api/**")
        
    async def _intercept_api_call(self, route: Route, request: Request):
        """Intercept Slack API calls to extract credentials and data."""
        try:
            # Continue the request
            response = await route.fetch()
            
            # Update credentials from this request
            self.credentials.update_from_request(request)
            
            # Debug: Log all API calls
            if "/api/" in request.url:
                print(f"🔍 Intercepted API call: {request.url}")
            
            # If this is an API call we're interested in, store the response
            if any(endpoint in request.url for endpoint in [
                "conversations.history", "conversations.list", "users.list", 
                "conversations.info", "conversations.replies", "conversations.listPrefs",
                "conversations.browse", "conversations.search", "channels.list",
                "channels.info", "channels.browse", "channels.search",
                "client.boot", "client.counts", "rtm.start", "rtm.connect",
                "team.info", "workspace.info", "api"  # Include any API call
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
                    
                    print(f"💾 Stored response from: {request.url}")
                    
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
        # Since we're using existing Chrome profile, try going directly to workspace
        try:
            print("🔗 Navigating to HigherDOSE workspace...")
            await self.page.goto(WORKSPACE_URL, timeout=15000)
            await self.page.wait_for_timeout(3000)
            print(f"✅ Successfully navigated to: {self.page.url}")
        except Exception as e:
            print(f"⚠️  Direct navigation failed: {e}")
            print("💡 Working with current page...")
            # Continue with whatever page is already open
        
        # Check if we're already logged in
        try:
            # Look for signs we're logged in (channel list, user menu, etc.)
            logged_in_selectors = [
                '[data-qa="channel_sidebar"]',
                '[data-qa="user_menu"]', 
                '.c-virtual_list',
                '[data-qa="workspace-name"]',
                '.p-channel_sidebar',
                '.c-channel_list',
                '[data-qa="slack_kit_list"]',
                '.c-unified_member',
                '.p-workspace_layout',
                '.c-workspace__primary_view'
            ]
            
            print("🔍 Checking for workspace indicators...")
            for i, selector in enumerate(logged_in_selectors):
                try:
                    element = await self.page.wait_for_selector(selector, timeout=2000)
                    if element:
                        print(f"✅ Found workspace indicator: {selector}")
                        print("✅ Already logged into Slack!")
                        return True
                except:
                    print(f"   ❌ {selector}")
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
            
            # Quick URL check
            current_url = self.page.url
            if "higherdosemanagement.slack.com" in current_url:
                print("✅ Confirmed: In HigherDOSE workspace")
            else:
                print(f"⚠️  Current URL: {current_url}")
                print("💡 Please make sure you're in the HigherDOSE workspace")
                
        except Exception as e:
            print(f"⚠️  Navigation error: {e}")
            pass
        
        # Verify login worked - try multiple selectors
        verification_selectors = [
            '[data-qa="channel_sidebar"]',
            '.p-channel_sidebar', 
            '.c-channel_list',
            '.p-workspace_layout',
            '.c-workspace__primary_view'
        ]
        
        print("🔍 Verifying workspace access...")
        for selector in verification_selectors:
            try:
                await self.page.wait_for_selector(selector, timeout=3000)
                print(f"✅ Verified with: {selector}")
                print("✅ Login successful!")
                return True
            except:
                print(f"   ❌ {selector}")
                continue
        
        # If all selectors failed, provide guidance
        print("❌ Could not detect HigherDOSE workspace.")
        print("💡 Make sure you're in the HigherDOSE workspace, not just logged into Slack.")
        print("   You should see channels like #general, #marketing, etc.")
        print(f"   Current URL: {self.page.url}")
        
        retry = input("Try again? (y/N): ")
        if retry.lower() == 'y':
            return await self.ensure_logged_in()
        return False
    
    def _parse_conversation_data(self, conv_data: Dict[str, Any]) -> Optional[ConversationInfo]:
        """Parse conversation data and return ConversationInfo object."""
        if not isinstance(conv_data, dict):
            return None
            
        name = conv_data.get("name", "")
        conv_id = conv_data.get("id", "")
        
        if not conv_id:
            return None
        
        # Determine conversation type based on ID and other properties
        conversation_type = ConversationType.UNKNOWN
        
        # Check if it's a DM (starts with D)
        if conv_id.startswith('D'):
            # Check if it's a multi-person DM
            if conv_data.get("is_mpim", False) or conv_data.get("is_group", False):
                conversation_type = ConversationType.MULTI_PERSON_DM
            else:
                conversation_type = ConversationType.DM
        # Check if it's a channel (starts with C)
        elif conv_id.startswith('C'):
            conversation_type = ConversationType.CHANNEL
        # Check if it's a group (starts with G)
        elif conv_id.startswith('G'):
            if conv_data.get("is_mpim", False):
                conversation_type = ConversationType.MULTI_PERSON_DM
            else:
                # Groups are usually private channels
                conversation_type = ConversationType.CHANNEL
        
        # Handle multi-person DMs - they often have specific naming patterns
        if name.startswith('mpdm-') or '-' in name and len(name.split('-')) > 2:
            conversation_type = ConversationType.MULTI_PERSON_DM
        
        # If name is empty, generate one based on type and ID
        if not name:
            if conversation_type == ConversationType.DM:
                name = f"dm_{conv_id}"
            elif conversation_type == ConversationType.MULTI_PERSON_DM:
                name = f"mpdm_{conv_id}"
            else:
                name = f"channel_{conv_id}"
        
        # Get additional properties
        is_private = conv_data.get("is_private", False)
        member_count = conv_data.get("num_members", 0)
        members = conv_data.get("members", [])
        
        return ConversationInfo(
            name=name,
            id=conv_id,
            conversation_type=conversation_type,
            is_private=is_private,
            member_count=member_count,
            members=members
        )
    
    def _print_conversation_summary(self, conversations: Dict[str, ConversationInfo]):
        """Print a summary of conversations by type."""
        type_counts = {
            ConversationType.CHANNEL: 0,
            ConversationType.DM: 0,
            ConversationType.MULTI_PERSON_DM: 0,
            ConversationType.UNKNOWN: 0
        }
        
        for conv_info in conversations.values():
            type_counts[conv_info.conversation_type] += 1
        
        print(f"\n📊 Conversation Summary:")
        print(f"  📁 Channels: {type_counts[ConversationType.CHANNEL]}")
        print(f"  💬 DMs: {type_counts[ConversationType.DM]}")
        print(f"  👥 Multi-person DMs: {type_counts[ConversationType.MULTI_PERSON_DM]}")
        print(f"  ❓ Unknown: {type_counts[ConversationType.UNKNOWN]}")
        print(f"  🔢 Total: {sum(type_counts.values())}")
        
        # Show examples of each type
        examples = {conv_type: [] for conv_type in ConversationType}
        for conv_info in conversations.values():
            if len(examples[conv_info.conversation_type]) < 3:
                examples[conv_info.conversation_type].append(str(conv_info))
        
        for conv_type, example_list in examples.items():
            if example_list:
                print(f"  Examples of {conv_type.value}: {', '.join(example_list)}")
        print()
    
    async def get_channel_list(self) -> Dict[str, ConversationInfo]:
        """Get list of conversations by triggering Slack to load them."""
        if not self.page:
            return {}
            
        print("📋 Getting conversation list...")
        
        # Clear previous intercepted data
        self.intercepted_data.clear()
        
        # Navigate to main workspace to trigger API calls
        try:
            # Try the main workspace URL first
            await self.page.goto(WORKSPACE_URL, timeout=10000)
            await self.page.wait_for_timeout(2000)
        except:
            try:
                # Fallback to client URL format
                await self.page.goto(f"https://app.slack.com/client/{TEAM_ID}")
                await self.page.wait_for_timeout(2000)
            except:
                print("⚠️  Using current page for channel detection")
                # Use whatever page we're currently on
        
        # Try multiple approaches to trigger channel list API calls
        print("🔄 Triggering channel list API calls...")
        
        # Approach 1: Reload to trigger fresh API calls
        try:
            await self.page.reload()
            await self.page.wait_for_timeout(4000)
            print("  ✅ Page reloaded to trigger fresh API calls")
        except:
            print("  ⚠️  Page reload failed")
        
        # Approach 2: Try to interact with sidebar elements
        try:
            sidebar_selectors = [
                '[data-qa="channel_sidebar"]',
                '.p-channel_sidebar',
                '.c-channel_list',
                '.c-virtual_list',
                '[aria-label="Channel browser"]',
                '[data-qa="channel_list"]'
            ]
            
            for selector in sidebar_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=2000)
                    if element:
                        await element.click()
                        await self.page.wait_for_timeout(1000)
                        print(f"  ✅ Clicked on {selector}")
                        break
                except:
                    continue
                    
        except Exception as e:
            print(f"  ⚠️  Error interacting with sidebar: {e}")
        
        # Approach 3: Try to navigate to specific pages that trigger channel lists
        navigation_attempts = [
            f"{WORKSPACE_URL}/admin/settings",
            f"{WORKSPACE_URL}/customize/emoji",
            f"https://app.slack.com/client/{TEAM_ID}/browse-channels",
            f"https://app.slack.com/client/{TEAM_ID}/channels"
        ]
        
        for url in navigation_attempts:
            try:
                await self.page.goto(url, timeout=8000)
                await self.page.wait_for_timeout(2000)
                print(f"  ✅ Navigated to {url}")
                break
            except:
                continue
        
        # Approach 4: Try keyboard shortcuts that might trigger channel lists
        try:
            # Ctrl+K opens quick switcher which loads channels
            await self.page.keyboard.press('Meta+K')  # Cmd+K on Mac
            await self.page.wait_for_timeout(1000)
            await self.page.keyboard.press('Escape')  # Close the switcher
            await self.page.wait_for_timeout(1000)
            print("  ✅ Tried keyboard shortcut Cmd+K")
        except:
            print("  ⚠️  Keyboard shortcut failed")
        
        # Wait a bit more for any delayed API calls
        await self.page.wait_for_timeout(3000)
        
        # Navigate to the workspace homepage (not a specific channel)
        workspace_homepage_urls = [
            f"https://app.slack.com/client/{TEAM_ID}/",  # With trailing slash
            f"https://app.slack.com/client/{TEAM_ID}",   # Without trailing slash
            f"{WORKSPACE_URL}/"  # Direct workspace URL
        ]
        
        print("🏠 Navigating to workspace homepage to find channel sidebar...")
        for url in workspace_homepage_urls:
            try:
                await self.page.goto(url, timeout=10000)
                await self.page.wait_for_timeout(5000)  # Wait longer for page to load
                print(f"✅ Navigated to: {url}")
                break
            except Exception as e:
                print(f"⚠️  Could not navigate to {url}: {e}")
                continue
        
        # Debug: See what's actually on the page
        print("🔍 Debugging page content...")
        try:
            page_title = await self.page.title()
            page_url = self.page.url
            print(f"  📄 Page title: {page_title}")
            print(f"  🔗 Page URL: {page_url}")
            
            # Try to find any elements that might be channels
            all_links = await self.page.query_selector_all('a')
            print(f"  🔗 Found {len(all_links)} links on page")
            
            # Check for any text that looks like channel names
            all_text = await self.page.query_selector_all('*')
            channel_like_text = []
            for element in all_text[:100]:  # Check first 100 elements
                try:
                    text = await element.text_content()
                    if text and text.strip():
                        text = text.strip()
                        # Look for short text that might be channel names
                        if text.startswith('#') and len(text) > 1 and len(text) < 50:
                            channel_like_text.append(text)
                        elif len(text) < 30 and text.islower() and '-' in text:
                            # Channel names are often lowercase with dashes
                            channel_like_text.append(f"#{text}")
                except:
                    continue
            
            if channel_like_text:
                print(f"  📌 Found channel-like text: {channel_like_text[:10]}")  # Show first 10
            else:
                print("  ❌ No channel-like text found")
            
            # Also check for sidebar elements specifically
            sidebar_elements = await self.page.query_selector_all('.p-channel_sidebar, [data-qa="channel_sidebar"], nav, .c-virtual_list')
            print(f"  📋 Found {len(sidebar_elements)} sidebar-like elements")
            
            # Check what's in the sidebar
            for i, sidebar in enumerate(sidebar_elements[:3]):  # Check first 3
                try:
                    sidebar_text = await sidebar.text_content()
                    if sidebar_text and len(sidebar_text) > 10:
                        print(f"    📋 Sidebar {i+1}: {sidebar_text[:100]}...")
                except:
                    continue
                
        except Exception as e:
            print(f"  ⚠️  Error debugging page: {e}")
        
        # Try to find and click on elements that would show the channel list
        print("🔍 Looking for channel list triggers...")
        try:
            # Try to find "Browse channels" or similar buttons
            channel_triggers = [
                'button[aria-label*="Browse"]',
                'button[aria-label*="browse"]',
                'button[aria-label*="Channel"]',
                'button[aria-label*="channel"]',
                '[data-qa="browse_channels"]',
                '[data-qa="add_channel"]',
                'a[href*="browse"]',
                'a[href*="channels"]',
                # Look for "+" buttons that might add channels
                'button[aria-label*="Create"]',
                'button[aria-label*="Add"]',
                # Look for expandable sections
                'button[aria-expanded="false"]',
                '[role="button"][aria-label*="expand"]'
            ]
            
            for selector in channel_triggers:
                try:
                    elements = await self.page.query_selector_all(selector)
                    print(f"  🔍 Found {len(elements)} elements with selector: {selector}")
                    
                    if elements:
                        # Try clicking the first element
                        await elements[0].click()
                        await self.page.wait_for_timeout(2000)
                        print(f"  ✅ Clicked on {selector}")
                        break
                except Exception as e:
                    print(f"  ⚠️  Error clicking {selector}: {e}")
                    continue
                    
        except Exception as e:
            print(f"⚠️  Error finding channel triggers: {e}")
        
        # Try direct navigation to channel browse/list pages
        print("🔍 Trying direct navigation to channel browser...")
        channel_browser_urls = [
            f"https://app.slack.com/client/{TEAM_ID}/browse-channels",
            f"https://app.slack.com/client/{TEAM_ID}/channels",
            f"https://app.slack.com/client/{TEAM_ID}/browse-public-channels",
            f"{WORKSPACE_URL}/channels/browse",
            f"{WORKSPACE_URL}/admin/channels",
            f"{WORKSPACE_URL}/browse",
            # Try more specific URLs that might trigger channel list API calls
            f"https://app.slack.com/client/{TEAM_ID}/browse-channels?filter=all",
            f"https://app.slack.com/client/{TEAM_ID}/browse-channels?type=public",
            f"https://app.slack.com/client/{TEAM_ID}/browse-channels?type=private",
            f"https://app.slack.com/client/{TEAM_ID}/channels-browse"
        ]
        
        for url in channel_browser_urls:
            try:
                print(f"  🔗 Trying to navigate to: {url}")
                await self.page.goto(url, timeout=15000)
                await self.page.wait_for_timeout(5000)  # Wait longer for page to load
                
                # Check if URL actually changed (not redirected back to channel)
                current_url = self.page.url
                if "/browse" in current_url or "/channels" in current_url:
                    print(f"  ✅ Successfully navigated to channel browser: {current_url}")
                    
                    # Wait for channel list to load and try to trigger more API calls
                    await self.page.wait_for_timeout(5000)  # Wait longer for initial load
                    
                    # Look for signs that the page is fully loaded
                    print("  🔍 Waiting for channel data to load...")
                    
                    # Try to trigger the client.boot or similar calls by refreshing or interacting
                    try:
                        # Try refreshing to trigger client.boot
                        await self.page.reload()
                        await self.page.wait_for_timeout(8000)  # Wait for reload to complete
                        print("  🔄 Reloaded page to trigger client.boot")
                        
                        # Try to trigger additional channel loading
                        await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                        await self.page.wait_for_timeout(3000)
                        await self.page.evaluate("window.scrollTo(0, 0);")
                        await self.page.wait_for_timeout(3000)
                        
                        # Try pressing keys that might trigger channel list loading
                        await self.page.keyboard.press('PageDown')
                        await self.page.wait_for_timeout(2000)
                        await self.page.keyboard.press('PageUp')
                        await self.page.wait_for_timeout(2000)
                        
                        # Try clicking on filter buttons to trigger channel loading
                        filter_buttons = await self.page.query_selector_all('button[data-qa*="channel"]')
                        if filter_buttons:
                            try:
                                # Try clicking "All channels" button
                                await filter_buttons[0].click()
                                await self.page.wait_for_timeout(3000)
                                print("  📋 Clicked on channel filter button")
                            except:
                                pass
                        
                        print(f"  📋 Triggered additional loading actions")
                        
                    except Exception as e:
                        print(f"  ⚠️  Error triggering additional loading: {e}")
                    
                    # Debug: See what's on the channel browser page
                    try:
                        page_title = await self.page.title()
                        print(f"    📄 Channel browser title: {page_title}")
                        print(f"    🔗 Channel browser URL: {current_url}")
                        
                        # Look for channel browser specific elements
                        browser_elements = await self.page.query_selector_all('div, section, main, article')
                        channel_texts = []
                        for element in browser_elements[:20]:  # Check first 20 elements
                            try:
                                text = await element.text_content()
                                if text and text.strip():
                                    text = text.strip()
                                    # Look for potential channel names (simple, short text)
                                    if (len(text) < 100 and len(text) > 2 and 
                                        not any(word in text.lower() for word in ['yesterday', 'today', 'am', 'pm', 'ago', 'hour', 'min', 'sec', 'edit', 'reply', 'thread'])):
                                        channel_texts.append(text)
                            except:
                                continue
                        
                        if channel_texts:
                            print(f"    📋 Channel browser content samples: {channel_texts[:5]}")
                        
                        # Look for specific channel browser elements
                        channel_browser_selectors = [
                            'div[data-qa="channel_browser"]',
                            'section[aria-label*="channel"]',
                            'ul[role="list"]',
                            'div[role="list"]',
                            'div[data-qa="browse_channels"]'
                        ]
                        
                        for selector in channel_browser_selectors:
                            elements = await self.page.query_selector_all(selector)
                            if elements:
                                print(f"    📋 Found {len(elements)} elements with {selector}")
                                
                    except Exception as e:
                        print(f"    ⚠️  Error debugging channel browser: {e}")
                    
                    break
                else:
                    print(f"  ⚠️  Redirected back to: {current_url}")
                    
            except Exception as e:
                print(f"  ⚠️  Could not navigate to {url}: {e}")
                continue
        
        # Try to extract channels directly from the DOM
        print("🔍 Trying to extract channels from DOM...")
        dom_channels = await self.extract_channels_from_dom()
        
        # Extract channels from intercepted data - try multiple API endpoints
        channels = {}
        channel_endpoints = [
            "conversations.list",
            "conversations.info", 
            "channels.list",
            "channels.info",
            "client.counts",
            "client.boot",
            "rtm.start",
            # Additional endpoints that might contain channel data
            "conversations.browse",
            "conversations.search",
            "channels.browse",
            "channels.search",
            "team.info",
            "workspace.info",
            "client.boot",
            "rtm.connect"
        ]
        
        print(f"🔍 Looking for conversations in {len(self.intercepted_data)} intercepted calls...")
        
        # First, let's see if any API calls contain a large number of conversations
        large_conversation_responses = []
        client_boot_responses = []
        
        for data in self.intercepted_data:
            response = data.get("response", {})
            url = data.get("url", "")
            
            if isinstance(response, dict):
                # Look specifically for client.boot calls (most likely to have all conversations)
                if "client.boot" in url:
                    client_boot_responses.append((url, response))
                    print(f"  🎯 Found client.boot call: {url}")
                    
                    # Check if it has conversations in various locations
                    conversation_count = 0
                    if "channels" in response:
                        conversation_count += len(response["channels"]) if isinstance(response["channels"], list) else 0
                    if "ims" in response:
                        conversation_count += len(response["ims"]) if isinstance(response["ims"], list) else 0
                    if "groups" in response:
                        conversation_count += len(response["groups"]) if isinstance(response["groups"], list) else 0
                    if "mpims" in response:
                        conversation_count += len(response["mpims"]) if isinstance(response["mpims"], list) else 0
                    if "self" in response:
                        self_data = response["self"]
                        if "channels" in self_data:
                            conversation_count += len(self_data["channels"]) if isinstance(self_data["channels"], list) else 0
                        if "ims" in self_data:
                            conversation_count += len(self_data["ims"]) if isinstance(self_data["ims"], list) else 0
                        if "groups" in self_data:
                            conversation_count += len(self_data["groups"]) if isinstance(self_data["groups"], list) else 0
                        if "mpims" in self_data:
                            conversation_count += len(self_data["mpims"]) if isinstance(self_data["mpims"], list) else 0
                    print(f"    📋 client.boot has {conversation_count} total conversations")
                
                # Look for responses that might contain many conversations
                total_conversations = 0
                if "channels" in response:
                    total_conversations += len(response["channels"]) if isinstance(response["channels"], list) else 0
                if "ims" in response:
                    total_conversations += len(response["ims"]) if isinstance(response["ims"], list) else 0
                if "groups" in response:
                    total_conversations += len(response["groups"]) if isinstance(response["groups"], list) else 0
                if "mpims" in response:
                    total_conversations += len(response["mpims"]) if isinstance(response["mpims"], list) else 0
                if "conversations" in response:
                    total_conversations += len(response["conversations"]) if isinstance(response["conversations"], list) else 0
                
                if total_conversations > 5:  # More than 5 conversations suggests a full list
                    large_conversation_responses.append((url, total_conversations))
                    print(f"  🎯 Found API call with {total_conversations} conversations: {url}")
        
        if client_boot_responses:
            print(f"  🎯 Found {len(client_boot_responses)} client.boot calls (most likely to have all conversations)")
        
        if large_conversation_responses:
            print(f"  📋 Found {len(large_conversation_responses)} API calls with substantial conversation data")
        else:
            print("  ⚠️  No API calls found with substantial conversation data")
        
        # Parse intercepted API responses for conversations
        conversations = {}
        
        for data in self.intercepted_data:
            url = data.get("url", "")
            response = data.get("response", {})
            
            # Check if this is a successful API response
            if response and isinstance(response, dict):
                # Look for conversations in various response formats
                conversations_data = []
                
                # Look for conversations in different response structures
                if response.get("ok", False):  # Successful responses
                    
                    if "channels" in response:
                        conversations_data.extend(response["channels"])
                    
                    if "conversations" in response:
                        conversations_data.extend(response["conversations"])
                    
                    if "ims" in response:
                        conversations_data.extend(response["ims"])
                    
                    if "groups" in response:
                        conversations_data.extend(response["groups"])
                    
                    if "mpims" in response:
                        conversations_data.extend(response["mpims"])
                    
                    if "self" in response:
                        self_data = response["self"]
                        if "channels" in self_data:
                            conversations_data.extend(self_data["channels"])
                        if "conversations" in self_data:
                            conversations_data.extend(self_data["conversations"])
                        if "ims" in self_data:
                            conversations_data.extend(self_data["ims"])
                        if "groups" in self_data:
                            conversations_data.extend(self_data["groups"])
                        if "mpims" in self_data:
                            conversations_data.extend(self_data["mpims"])
                
                # Special handling for client.boot responses (try even without "ok" status)
                if "client.boot" in url:
                    print(f"  🎯 Processing client.boot response from {url}")
                    
                    # Look for conversations in all possible locations
                    conversation_locations = [
                        response.get("channels", []),
                        response.get("conversations", []),
                        response.get("ims", []),
                        response.get("groups", []),
                        response.get("mpims", []),
                        response.get("self", {}).get("channels", []),
                        response.get("self", {}).get("conversations", []),
                        response.get("self", {}).get("ims", []),
                        response.get("self", {}).get("groups", []),
                        response.get("self", {}).get("mpims", []),
                        response.get("data", {}).get("channels", []),
                        response.get("data", {}).get("conversations", []),
                        response.get("team", {}).get("channels", []),
                        response.get("workspace", {}).get("channels", [])
                    ]
                    
                    for location in conversation_locations:
                        if isinstance(location, list):
                            conversations_data.extend(location)
                    
                    # Also check for conversation data as objects with conversation IDs as keys
                    for key, value in response.items():
                        if isinstance(value, dict):
                            for sub_key, sub_value in value.items():
                                if isinstance(sub_key, str) and (sub_key.startswith('C') or sub_key.startswith('D') or sub_key.startswith('G')) and len(sub_key) > 5:
                                    if isinstance(sub_value, dict):
                                        conversations_data.append({
                                            "id": sub_key,
                                            "name": sub_value.get("name", sub_key),
                                            "is_channel": sub_key.startswith('C'),
                                            "is_group": sub_key.startswith('G'),
                                            "is_im": sub_key.startswith('D'),
                                            "is_mpim": sub_value.get("is_mpim", False),
                                            "is_private": sub_value.get("is_private", False),
                                            "num_members": sub_value.get("num_members", 0),
                                            "members": sub_value.get("members", [])
                                        })
                
                # Process all found conversation data
                for conv_data in conversations_data:
                    if isinstance(conv_data, dict):
                        conv_info = self._parse_conversation_data(conv_data)
                        if conv_info:
                            conversations[conv_info.name] = conv_info
                            print(f"  📌 Found conversation: {conv_info}")
        
        # If no conversations found, show what API calls we DID capture AND their content
        if not conversations:
            print("🔍 No conversations found. Analyzing captured API calls for hidden conversation data...")
            for i, data in enumerate(self.intercepted_data[-10:]):  # Show last 10
                url = data.get("url", "")
                response = data.get("response", {})
                
                if "api" in url:
                    print(f"  {i+1}. {url}")
                    
                    # Look for any conversation-related data in the response
                    if response and isinstance(response, dict):
                        # Check for conversations in various possible locations
                        conversation_locations = [
                            "channels", "channel", "conversations", "conversation",
                            "ims", "im", "groups", "group", "mpims", "mpim",
                            "prefs", "preferences", "team", "workspace", "data", "results"
                        ]
                        
                        for location in conversation_locations:
                            if location in response:
                                content = response[location]
                                if isinstance(content, dict):
                                    # Look for conversation-like data in dictionaries
                                    for key, value in content.items():
                                        if key and isinstance(key, str) and (key.startswith('C') or key.startswith('D') or key.startswith('G')) and len(key) > 5:
                                            print(f"    🔍 Found conversation-like key: {key}")
                                            if isinstance(value, dict):
                                                conv_info = self._parse_conversation_data({
                                                    "id": key,
                                                    "name": value.get("name", key),
                                                    **value
                                                })
                                                if conv_info:
                                                    conversations[conv_info.name] = conv_info
                                                    print(f"    📌 Found conversation: {conv_info}")
                                elif isinstance(content, list) and content:
                                    # Look for conversation-like data in lists
                                    for item in content[:10]:  # Check first 10 items
                                        if isinstance(item, dict) and "id" in item:
                                            conv_info = self._parse_conversation_data(item)
                                            if conv_info:
                                                conversations[conv_info.name] = conv_info
                                                print(f"    📌 Found conversation: {conv_info}")
            
            print(f"🔍 After analyzing responses, found {len(conversations)} conversations")
        
        # Merge DOM conversations with API conversations
        for name, channel_id in dom_channels.items():
            if name not in conversations:
                # Create a basic conversation info for DOM-found channels
                conv_info = ConversationInfo(
                    name=name,
                    id=channel_id,
                    conversation_type=ConversationType.CHANNEL  # Assume channel for DOM-found items
                )
                conversations[name] = conv_info
        
        # Print summary by conversation type
        self._print_conversation_summary(conversations)
        
        print(f"✅ Found {len(conversations)} conversations total")
        return conversations
    
    async def extract_channels_from_dom(self) -> Dict[str, str]:
        """Extract channels directly from the DOM elements."""
        channels = {}
        
        try:
            # Try multiple selectors that might contain channel information
            channel_selectors = [
                # Channel browser specific selectors (try these first)
                'div[data-qa="channel_browser"] a',
                'div[data-qa="channel_browser"] [role="listitem"]',
                'div[data-qa="browse_channels"] a',
                'div[data-qa="browse_channels"] [role="listitem"]',
                '[data-qa="channel_browser"] a[href*="/archives/C"]',
                '[data-qa="browse_channels"] a[href*="/archives/C"]',
                # Channel list items in browser
                'ul[role="list"] li a',
                'div[role="list"] div a',
                'section[aria-label*="channel"] a',
                # Channel sidebar - more specific selectors
                '.p-channel_sidebar [data-qa="virtual_list_item"] a',
                '.p-channel_sidebar [role="listitem"] a',
                '.p-channel_sidebar [data-qa="sidebar_item"]',
                '.p-channel_sidebar [data-qa="sidebar_item_channel"]',
                # Channel links with specific patterns
                'a[href*="/archives/C"]',  # Channel IDs start with C
                'a[href*="/channels/C"]',
                'a[data-qa="channel_name"]',
                # Navigation sidebar
                '[data-qa="sidebar"] [data-qa="virtual_list_item"]',
                '[data-qa="sidebar"] [role="listitem"]',
                # Generic navigation elements
                'nav [role="listitem"]',
                'nav a[href*="/archives/"]',
                # Button elements that might be channels
                'button[data-qa*="channel"]',
                'button[aria-label*="channel"]',
                # Less specific fallbacks
                '[data-qa*="channel"]',
                '[aria-label*="channel"]',
                '[aria-label*="Channel"]'
            ]
            
            for selector in channel_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    print(f"  🔍 Found {len(elements)} elements with selector: {selector}")
                    
                    for element in elements:
                        # Try to get channel name and ID from various attributes
                        name = ""
                        channel_id = ""
                        
                        # Try to get from href attribute
                        href = await element.get_attribute('href')
                        if href:
                            if '/archives/' in href:
                                channel_id = href.split('/archives/')[-1].split('?')[0].split('/')[0]
                            elif '/channels/' in href:
                                channel_id = href.split('/channels/')[-1].split('?')[0].split('/')[0]
                        
                        # Try to get from data attributes
                        if not channel_id:
                            for attr in ['data-qa-channel-id', 'data-channel-id', 'data-qa']:
                                attr_value = await element.get_attribute(attr)
                                if attr_value and attr_value.startswith('C'):
                                    channel_id = attr_value
                                    break
                        
                        # Try to get channel name from text content
                        text = await element.text_content()
                        if text:
                            text = text.strip()
                            # Look for actual channel names (short, simple text)
                            if text.startswith('#'):
                                potential_name = text[1:]  # Remove #
                                # Only accept if it looks like a channel name (no spaces, reasonable length)
                                if len(potential_name) > 0 and len(potential_name) < 50 and ' ' not in potential_name:
                                    name = potential_name
                            elif text and len(text) < 50 and not text.startswith('+') and not text.startswith('@'):
                                # Simple text that might be a channel name
                                # Avoid message content (which tends to be longer)
                                if not any(word in text.lower() for word in ['am', 'pm', 'yesterday', 'ago', 'reply', 'thread', 'edited']):
                                    name = text
                        
                        # Try to get name from aria-label
                        if not name:
                            aria_label = await element.get_attribute('aria-label')
                            if aria_label:
                                if 'channel' in aria_label.lower():
                                    # Extract channel name from aria-label like "general channel"
                                    name = aria_label.lower().replace('channel', '').strip()
                                elif aria_label.startswith('#'):
                                    name = aria_label[1:]
                        
                        # If we found both name and ID, or at least a name, add it
                        if name and channel_id:
                            channels[name] = channel_id
                            print(f"    📌 Found channel: #{name} ({channel_id})")
                        elif name and len(name) > 0 and not name.isspace():
                            # Use a placeholder ID if we can't find the real one
                            channels[name] = f"C_PLACEHOLDER_{name}"
                            print(f"    📌 Found channel: #{name} (placeholder ID)")
                    
                    if elements:
                        break  # If we found elements with this selector, don't try others
                        
                except Exception as e:
                    print(f"  ⚠️  Error with selector {selector}: {e}")
                    continue
            
            print(f"🔍 DOM extraction found {len(channels)} channels")
            
        except Exception as e:
            print(f"⚠️  Error extracting channels from DOM: {e}")
        
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
        conversations = await browser.get_channel_list()
        users = await browser.get_user_list()
        
        if not conversations:
            print("⚠️  No conversations found. You may need to navigate manually in the browser.")
        
        # Interactive loop
        while True:
            print(f"\nAvailable commands:")
            print(f"  • 'list' - Show available conversations ({len(conversations)} found)")
            print(f"  • '<conversation_name>' - Fetch messages from conversation")
            print(f"  • 'refresh <conversation>' - Re-fetch entire conversation")
            print(f"  • 'q' - Quit")
            
            user_input = input("\nCommand: ").strip()
            
            if user_input.lower() == "q":
                print("👋 Goodbye!")
                break
            
            if user_input.lower() == "list":
                print(f"\nConversations ({len(conversations)}):")
                
                # Group by conversation type
                by_type = {
                    ConversationType.CHANNEL: [],
                    ConversationType.DM: [],
                    ConversationType.MULTI_PERSON_DM: []
                }
                
                for name, conv_info in conversations.items():
                    if conv_info.conversation_type in by_type:
                        by_type[conv_info.conversation_type].append(conv_info)
                
                # Show channels first
                if by_type[ConversationType.CHANNEL]:
                    print(f"\n  📁 Channels ({len(by_type[ConversationType.CHANNEL])}):")
                    for conv_info in sorted(by_type[ConversationType.CHANNEL], key=lambda x: x.name)[:20]:
                        print(f"    {conv_info}")
                
                # Show DMs
                if by_type[ConversationType.DM]:
                    print(f"\n  💬 Direct Messages ({len(by_type[ConversationType.DM])}):")
                    for conv_info in sorted(by_type[ConversationType.DM], key=lambda x: x.name)[:20]:
                        print(f"    {conv_info}")
                
                # Show multi-person DMs
                if by_type[ConversationType.MULTI_PERSON_DM]:
                    print(f"\n  👥 Multi-person DMs ({len(by_type[ConversationType.MULTI_PERSON_DM])}):")
                    for conv_info in sorted(by_type[ConversationType.MULTI_PERSON_DM], key=lambda x: x.name)[:20]:
                        print(f"    {conv_info}")
                
                total_shown = sum(min(len(convs), 20) for convs in by_type.values())
                if len(conversations) > total_shown:
                    print(f"  ... and {len(conversations) - total_shown} more")
                continue
            
            refresh_mode = False
            if user_input.lower().startswith("refresh "):
                refresh_mode = True
                conversation_name = user_input[8:].strip().lstrip("#@")
            else:
                conversation_name = user_input.lstrip("#@")
            
            if conversation_name not in conversations:
                print(f"❌ Conversation '{conversation_name}' not found. Use 'list' to see available conversations.")
                continue
            
            conv_info = conversations[conversation_name]
            channel_id = conv_info.id
            
            # Load tracking data
            tracker = _load_tracker()
            last_ts = 0 if refresh_mode else tracker["channels"].get(channel_id, 0)
            
            if refresh_mode:
                print(f"🔄 Refreshing entire conversation for {conv_info}")
            else:
                print(f"📥 Fetching new messages from {conv_info} (since {last_ts})")
            
            # Fetch messages
            messages = await browser.fetch_conversation_history(channel_id, last_ts)
            
            if not messages:
                print("📭 No new messages found.")
                continue
            
            # Save to markdown
            safe_name = _create_safe_filename(conv_info.name, channel_id)
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