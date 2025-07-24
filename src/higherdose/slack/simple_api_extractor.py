#!/usr/bin/env python3
"""
Simple Slack API extractor - intercepts Slack's API calls like the original script but much simpler.
No DOM interaction to avoid bot detection.
"""

import asyncio
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from playwright.async_api import async_playwright, Route, Request


# -------------- Config -------------------------------------------------------
EXPORT_DIR = Path("slack/api_exports")
WORKSPACE_URL = "https://higherdosemanagement.slack.com"
TEAM_ID = "TA97020CV"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


class SimpleAPIExtractor:
    def __init__(self):
        self.page = None
        self.context = None
        self.browser = None
        self.intercepted_data = []
        self.users = {}
        
    async def start(self, headless: bool = False):
        """Start browser using existing Chrome profile."""
        playwright = await async_playwright().start()
        
        # Use existing Chrome profile (same as original script)
        chrome_profile_path = os.path.expanduser("~/Library/Application Support/Google/Chrome/Default")
        
        if os.path.exists(chrome_profile_path):
            print(f"🔗 Using existing Chrome profile")
            self.context = await playwright.chromium.launch_persistent_context(
                user_data_dir=chrome_profile_path,
                headless=headless,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
            )
            self.browser = self.context.browser
            
            # Use existing page or create new one
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
                
            # Setup API interception (key part from original script)
            await self.page.route("**/api/**", self._intercept_api_call)
            print("🔍 Set up API interception")
            
            return True
        else:
            print("❌ Chrome profile not found")
            return False
    
    async def _intercept_api_call(self, route: Route, request: Request):
        """Intercept Slack API calls to extract data (simplified from original)."""
        try:
            # Continue the request normally
            response = await route.fetch()
            
            # Only capture conversation-related API calls
            if any(endpoint in request.url for endpoint in [
                "conversations.history", 
                "conversations.list", 
                "conversations.info",
                "conversations.replies",
                "users.list",
                "client.boot",
                "client.counts"
            ]):
                try:
                    response_text = await response.text()
                    response_data = json.loads(response_text)
                    
                    self.intercepted_data.append({
                        "url": request.url,
                        "response": response_data,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    print(f"📥 Captured: {request.url.split('/')[-1]}")
                    
                except Exception as e:
                    print(f"⚠️  Error parsing response: {e}")
            
            # Continue with the response
            await route.fulfill(response=response)
            
        except Exception as e:
            print(f"⚠️  Error intercepting: {e}")
            await route.continue_()
    
    async def navigate_to_slack(self):
        """Navigate to Slack and let it load naturally."""
        print(f"🌐 Navigating to {WORKSPACE_URL}")
        print("💡 If the page doesn't load properly, try refreshing or navigating manually")
        
        try:
            # Try multiple navigation approaches
            navigation_urls = [
                WORKSPACE_URL,
                f"https://app.slack.com/client/{TEAM_ID}",
                "https://app.slack.com"
            ]
            
            for i, url in enumerate(navigation_urls):
                try:
                    print(f"🔄 Trying URL {i+1}/{len(navigation_urls)}: {url}")
                    await self.page.goto(url, timeout=10000)
                    await self.page.wait_for_timeout(3000)
                    
                    current_url = self.page.url
                    print(f"📍 Current URL: {current_url}")
                    
                    if "slack.com" in current_url:
                        print("✅ Successfully loaded Slack")
                        print("🔍 API interception is running - you can browse Slack normally")
                        print("📝 The script will capture API calls in the background")
                        return True
                    
                except Exception as e:
                    print(f"⚠️  Error with URL {i+1}: {e}")
                    if i < len(navigation_urls) - 1:
                        print("🔄 Trying next URL...")
                        continue
            
            print("⚠️  All automatic navigation attempts failed")
            print("💡 Please manually navigate to your Slack workspace in the browser")
            print("⏳ Waiting 10 seconds for manual navigation...")
            await self.page.wait_for_timeout(10000)
            
            current_url = self.page.url
            if "slack.com" in current_url:
                print("✅ Successfully reached Slack via manual navigation")
                return True
            else:
                print(f"❌ Still not in Slack. Current URL: {current_url}")
                return False
                
        except Exception as e:
            print(f"❌ Error navigating: {e}")
            return False
    
    async def extract_conversation(self, channel_id: str):
        """Extract a specific conversation by navigating to it."""
        print(f"📥 Extracting conversation: {channel_id}")
        
        # Clear previous data
        self.intercepted_data.clear()
        
        # Navigate to the channel
        channel_url = f"{WORKSPACE_URL}/archives/{channel_id}"
        
        try:
            await self.page.goto(channel_url)
            print(f"🌐 Navigated to channel: {channel_id}")
            
            # Wait for messages to load and API calls to happen
            await self.page.wait_for_timeout(5000)
            
            # Scroll to load more history (minimal interaction)
            print("📜 Scrolling to load history...")
            for i in range(10):  # Scroll 10 times
                await self.page.keyboard.press("PageUp")
                await self.page.wait_for_timeout(1000)
                print(f"  Scroll {i+1}/10")
            
            # Wait for final API calls
            await self.page.wait_for_timeout(3000)
            
            # Extract messages from intercepted data
            messages = self._extract_messages_from_api_data()
            
            print(f"✅ Extracted {len(messages)} messages")
            return messages
            
        except Exception as e:
            print(f"❌ Error extracting conversation: {e}")
            return []
    
    def _extract_messages_from_api_data(self) -> List[Dict[str, Any]]:
        """Extract messages from intercepted API data (simplified from original)."""
        all_messages = []
        
        for data in self.intercepted_data:
            try:
                url = data["url"]
                response = data["response"]
                
                if not response.get("ok"):
                    continue
                
                # Extract messages from different API endpoints
                if "conversations.history" in url:
                    messages = response.get("messages", [])
                    all_messages.extend(messages)
                    
                elif "conversations.replies" in url:
                    messages = response.get("messages", [])
                    # Skip first message (parent) for replies
                    all_messages.extend(messages[1:])
                
                # Extract user data
                elif "users.list" in url:
                    users = response.get("members", [])
                    for user in users:
                        self.users[user.get("id", "")] = user.get("real_name", user.get("name", "Unknown"))
                
                elif "client.boot" in url:
                    # Extract users from boot data
                    if "users" in response:
                        for user_id, user_data in response["users"].items():
                            self.users[user_id] = user_data.get("real_name", user_data.get("name", "Unknown"))
                
            except Exception as e:
                print(f"⚠️  Error processing API data: {e}")
                continue
        
        # Remove duplicates and sort by timestamp
        seen_ts = set()
        unique_messages = []
        for msg in all_messages:
            ts = msg.get("ts")
            if ts and ts not in seen_ts:
                seen_ts.add(ts)
                unique_messages.append(msg)
        
        unique_messages.sort(key=lambda x: float(x.get("ts", 0)))
        return unique_messages
    
    def save_to_markdown(self, messages: List[Dict[str, Any]], channel_name: str):
        """Save messages to markdown (simplified formatting)."""
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', channel_name)
        md_path = EXPORT_DIR / f"{safe_name}.md"
        
        with md_path.open("w", encoding="utf-8") as f:
            f.write(f"# {channel_name}\n\n")
            f.write(f"Extracted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Messages: {len(messages)}\n\n")
            f.write("---\n\n")
            
            for msg in messages:
                # Basic message formatting
                try:
                    ts = float(msg.get("ts", 0))
                    dt = datetime.fromtimestamp(ts)
                    time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    time_str = "Unknown time"
                
                user_id = msg.get("user", "")
                user_name = self.users.get(user_id, f"User_{user_id[-6:] if user_id else 'Unknown'}")
                text = msg.get("text", "")
                
                f.write(f"**{time_str}** - **{user_name}**: {text}\n\n")
        
        print(f"✅ Saved to {md_path}")
    
    def save_raw_json(self, channel_name: str):
        """Save raw API data as JSON for debugging."""
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', channel_name)
        json_path = EXPORT_DIR / f"{safe_name}_raw.json"
        
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(self.intercepted_data, f, indent=2)
        
        print(f"💾 Saved raw API data to {json_path}")
    
    async def list_conversations(self):
        """Get conversation list from API data."""
        print("📋 Getting conversation list...")
        
        # Navigate to main workspace to trigger conversation list APIs
        await self.page.goto(WORKSPACE_URL)
        await self.page.wait_for_timeout(5000)
        
        conversations = {}
        
        for data in self.intercepted_data:
            try:
                response = data["response"]
                if not response.get("ok"):
                    continue
                
                # Extract conversations from various API responses
                if "conversations" in response:
                    for conv in response["conversations"]:
                        conv_id = conv.get("id", "")
                        conv_name = conv.get("name", f"channel_{conv_id}")
                        if conv_id:
                            conversations[conv_id] = conv_name
                
                elif "channels" in response:
                    for conv in response["channels"]:
                        conv_id = conv.get("id", "")
                        conv_name = conv.get("name", f"channel_{conv_id}")
                        if conv_id:
                            conversations[conv_id] = conv_name
            
            except Exception as e:
                continue
        
        return conversations
    
    async def close(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()


async def main():
    """Main function."""
    print("🚀 Simple API Extractor")
    print("Intercepts Slack API calls without DOM interaction")
    print()
    
    extractor = SimpleAPIExtractor()
    
    try:
        # Start browser
        if not await extractor.start(headless=False):
            print("❌ Failed to start browser")
            return
        
        # Navigate to Slack
        if not await extractor.navigate_to_slack():
            print("❌ Failed to navigate to Slack")
            return
        
        print("✅ Ready to extract conversations!")
        print()
        print("📋 How to use:")
        print("  1. Navigate to any Slack conversation in the browser")
        print("  2. The script will automatically capture API calls")
        print("  3. Use commands below to extract specific conversations")
        print()
        print("🎯 Commands:")
        print("  • Enter channel ID (like C1234567890) to extract")
        print("  • 'list' to try getting conversation list from captured data")
        print("  • 'browse' to manually navigate and capture more data")
        print("  • 'show' to see what data has been captured so far")
        print("  • 'q' to quit")
        
        while True:
            user_input = input("\nEnter command: ").strip()
            
            if user_input.lower() == 'q':
                break
            elif user_input.lower() == 'list':
                conversations = await extractor.list_conversations()
                if conversations:
                    print(f"\nFound {len(conversations)} conversations:")
                    for conv_id, conv_name in conversations.items():
                        print(f"  {conv_id}: {conv_name}")
                else:
                    print("No conversations found in API data")
                    print("💡 Try browsing some channels first, then run 'list' again")
            
            elif user_input.lower() == 'browse':
                print("🌐 Browser is ready for manual navigation")
                print("💡 Navigate to any Slack conversation to capture API calls")
                print("⏳ Waiting 30 seconds for you to browse...")
                await extractor.page.wait_for_timeout(30000)
                print("✅ Browse time complete")
            
            elif user_input.lower() == 'show':
                print(f"📊 Captured {len(extractor.intercepted_data)} API calls")
                if extractor.intercepted_data:
                    recent_calls = extractor.intercepted_data[-10:]
                    print("📋 Recent API calls:")
                    for call in recent_calls:
                        url_parts = call["url"].split("/")
                        endpoint = url_parts[-1] if url_parts else call["url"]
                        print(f"  • {endpoint}")
                else:
                    print("💡 No API calls captured yet. Try browsing some channels first.")
            elif user_input.startswith('C') and len(user_input) > 5:
                # Looks like a channel ID
                channel_id = user_input
                messages = await extractor.extract_conversation(channel_id)
                
                if messages:
                    channel_name = f"channel_{channel_id}"
                    extractor.save_to_markdown(messages, channel_name)
                    extractor.save_raw_json(channel_name)
                else:
                    print("No messages found")
            else:
                print("Invalid command. Enter a channel ID or 'list' or 'q'")
    
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await extractor.close()


if __name__ == "__main__":
    asyncio.run(main()) 