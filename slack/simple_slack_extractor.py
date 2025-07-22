#!/usr/bin/env python3
"""
Simple Slack conversation extractor using Playwright DOM extraction.
This version extracts conversation data directly from DOM elements instead of API interception.
"""

import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from playwright.async_api import async_playwright, Browser, Page


# -------------- Config -------------------------------------------------------
EXPORT_DIR = Path("slack/simple_exports")
WORKSPACE_URL = "https://higherdosemanagement.slack.com"
TEAM_ID = "TA97020CV"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


class SimpleSlackExtractor:
    def __init__(self):
        self.page: Optional[Page] = None
        self.context = None
        self.browser = None
        
    async def start(self, headless: bool = False):
        """Start browser using existing Chrome profile."""
        playwright = await async_playwright().start()
        
        # Use existing Chrome profile where user is already logged into Slack
        chrome_profile_path = os.path.expanduser("~/Library/Application Support/Google/Chrome/Default")
        
        if os.path.exists(chrome_profile_path):
            print(f"🔗 Using existing Chrome profile")
            # More realistic browser settings to avoid detection
            self.context = await playwright.chromium.launch_persistent_context(
                user_data_dir=chrome_profile_path,
                headless=headless,
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                },
                ignore_https_errors=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=VizDisplayCompositor',
                    '--disable-dev-shm-usage',
                    '--no-first-run',
                    '--disable-web-security',
                    '--allow-running-insecure-content',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding'
                ]
            )
            self.browser = self.context.browser
            
            # Use existing page or create new one
            if self.context.pages:
                self.page = self.context.pages[0]
            else:
                self.page = await self.context.new_page()
            
            # Add stealth scripts to avoid detection
            await self.page.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => false,
                });
                
                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5],
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                
                // Override permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """)
        else:
            print("❌ Chrome profile not found")
            return False
            
        return True
    
    async def navigate_to_workspace(self):
        """Navigate to Slack workspace."""
        # Try the direct app URL first since user is already logged in
        app_url = f"https://app.slack.com/client/{TEAM_ID}"
        print(f"🌐 Navigating to {app_url}")
        
        try:
            await self.page.goto(app_url, timeout=15000)
            
            # Add human-like delay
            import random
            delay = random.randint(2000, 4000)
            await self.page.wait_for_timeout(delay)
            
            # Simulate human activity - small mouse movement
            await self.page.mouse.move(100, 100)
            await self.page.wait_for_timeout(500)
            
            print("✅ Successfully navigated to app.slack.com")
        except Exception as e:
            print(f"⚠️ Error with app.slack.com, trying workspace URL: {e}")
            try:
                await self.page.goto(WORKSPACE_URL, timeout=15000)
                await self.page.wait_for_timeout(3000)
            except Exception as e2:
                print(f"❌ Error with both URLs: {e2}")
                return False
        
        # Quick check for any app launcher prompts
        try:
            await self._bypass_launch_screen()
        except:
            pass
        
        # Final check if we're in the workspace
        await self.page.wait_for_timeout(2000)
        current_url = self.page.url
        print(f"📍 Final URL: {current_url}")
        
        if "app.slack.com" in current_url or "slack.com" in current_url:
            # Check for workspace elements with multiple attempts
            sidebar_found = False
            for attempt in range(3):
                try:
                    print(f"🔍 Looking for workspace sidebar (attempt {attempt + 1}/3)...")
                    await self.page.wait_for_selector('[data-qa="sidebar"], .p-channel_sidebar, .c-team_sidebar, nav', timeout=3000)
                    print("✅ Successfully reached workspace")
                    sidebar_found = True
                    break
                except:
                    if attempt < 2:
                        print("⏳ Waiting a bit more for workspace to load...")
                        await self.page.wait_for_timeout(2000)
                    continue
            
            if not sidebar_found:
                print("⚠️  In Slack but workspace sidebar not found")
                print("🔍 You may need to complete authentication manually in the browser")
                print("⏳ Waiting 10 seconds for manual authentication...")
                await self.page.wait_for_timeout(10000)
                
                # Try one more time after manual wait
                try:
                    await self.page.wait_for_selector('[data-qa="sidebar"], .p-channel_sidebar, .c-team_sidebar, nav', timeout=5000)
                    print("✅ Found workspace after manual wait")
                    sidebar_found = True
                except:
                    print("❌ Still no workspace sidebar found")
            
            return sidebar_found
        else:
            print("❌ Still not in Slack workspace")
            return False
    
    async def _bypass_launch_screen(self):
        """Bypass the Slack launch screen that tries to open the desktop app."""
        try:
            # Check if we're on the launch screen by looking for common elements
            launch_screen_selectors = [
                # "Continue in browser" button
                'button:has-text("Continue in browser")',
                'a:has-text("Continue in browser")',
                '[data-qa="continue_in_browser"]',
                
                # "Use Slack in your browser" button  
                'button:has-text("Use Slack in your browser")',
                'a:has-text("Use Slack in your browser")',
                
                # "Open in browser" button
                'button:has-text("Open in browser")',
                'a:has-text("Open in browser")',
                
                # Skip app download
                'button:has-text("Skip")',
                'a:has-text("Skip")',
                'button:has-text("No thanks")',
                'button:has-text("Not now")',
                'button:has-text("Maybe later")',
                
                # Generic "browser" link
                'a:has-text("browser")',
                
                # App download dismissal
                '.p-download_page__cta--skip',
                '.p-download_page__skip',
                
                # Close buttons on app prompts
                '[data-qa="app-download-banner-close"]',
                '[data-qa="download-banner-close"]',
                '.c-banner__close',
                '.c-alert__close',
            ]
            
            for selector in launch_screen_selectors:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=1000)
                    if element:
                        print(f"🔍 Found app launcher element: {selector}")
                        await element.click()
                        print("✅ Dismissed app launcher/popup")
                        await self.page.wait_for_timeout(1000)
                        return True
                except:
                    continue
            
            # Check for app download banner in URL and dismiss
            current_url = self.page.url
            if any(term in current_url for term in ["/getting-started", "/download", "/app-redirect"]):
                print("🔍 Detected app download page, navigating back to workspace...")
                await self.page.goto(WORKSPACE_URL)
                await self.page.wait_for_timeout(2000)
                return True
            
            # Try pressing Escape to dismiss any overlays
            try:
                await self.page.keyboard.press("Escape")
                await self.page.wait_for_timeout(500)
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"⚠️ Error handling app launcher: {e}")
            return False
    
    async def get_conversations_from_sidebar(self) -> List[Dict[str, str]]:
        """Extract conversation list from the sidebar."""
        print("📋 Extracting conversations from sidebar...")
        
        conversations = []
        
        # Wait for sidebar to load
        try:
            await self.page.wait_for_selector('[data-qa="sidebar"]', timeout=10000)
        except:
            print("⚠️  Sidebar not found, trying alternative selectors...")
        
        # Try multiple selectors for conversation items in sidebar
        selectors = [
            '[data-qa="sidebar"] [data-qa="virtual_list_item"] a',
            '.p-channel_sidebar [role="listitem"] a',
            '.p-channel_sidebar a[href*="/archives/"]',
            '.p-channel_sidebar a[href*="/client/"]',
            '[data-qa="channel_sidebar"] a',
            'nav a[href*="/archives/"]',
            'nav a[href*="/client/"]'
        ]
        
        for selector in selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                print(f"  🔍 Found {len(elements)} elements with selector: {selector}")
                
                for element in elements:
                    try:
                        # Get conversation name and URL
                        text = await element.text_content()
                        href = await element.get_attribute('href')
                        
                        if text and href and text.strip():
                            # Clean up the name
                            name = text.strip()
                            # Remove notification badges, timestamps, etc.
                            name = re.sub(r'\d+$', '', name).strip()  # Remove trailing numbers
                            name = re.sub(r'\s+', ' ', name)  # Normalize whitespace
                            
                            # Extract channel ID from URL
                            channel_id = ""
                            if '/archives/' in href:
                                channel_id = href.split('/archives/')[-1].split('?')[0].split('/')[0]
                            elif '/client/' in href and '/' in href.split('/client/')[-1]:
                                parts = href.split('/client/')[-1].split('/')
                                if len(parts) > 1:
                                    channel_id = parts[1]
                            
                            if name and channel_id:
                                conv = {
                                    'name': name,
                                    'id': channel_id,
                                    'url': href,
                                    'type': 'channel' if name.startswith('#') else 'dm' if name.startswith('@') else 'unknown'
                                }
                                
                                # Avoid duplicates
                                if not any(c['id'] == channel_id for c in conversations):
                                    conversations.append(conv)
                                    print(f"    📌 Found: {name} ({channel_id})")
                    
                    except Exception as e:
                        print(f"    ⚠️  Error processing element: {e}")
                        continue
                
                if conversations:
                    break  # Found conversations, no need to try other selectors
                    
            except Exception as e:
                print(f"  ⚠️  Error with selector {selector}: {e}")
                continue
        
        print(f"✅ Found {len(conversations)} conversations")
        return conversations
    
    async def extract_messages_from_dom(self, channel_id: str, channel_name: str) -> List[Dict[str, Any]]:
        """Extract messages directly from DOM by scrolling through conversation."""
        print(f"📥 Extracting messages from {channel_name} ({channel_id})")
        
        # Navigate to the conversation
        channel_url = f"{WORKSPACE_URL}/archives/{channel_id}"
        await self.page.goto(channel_url)
        await self.page.wait_for_timeout(3000)
        
        messages = []
        last_message_count = 0
        scroll_attempts = 0
        max_scrolls = 30
        
        while scroll_attempts < max_scrolls:
            # Extract current messages from DOM
            current_messages = await self._extract_visible_messages()
            
            # Add new messages (avoid duplicates by timestamp)
            existing_timestamps = {msg.get('ts') for msg in messages}
            new_messages = [msg for msg in current_messages 
                          if msg.get('ts') and msg['ts'] not in existing_timestamps]
            
            messages.extend(new_messages)
            
            print(f"  📊 Scroll {scroll_attempts + 1}: Found {len(new_messages)} new messages (total: {len(messages)})")
            
            # Check if we found new messages
            if len(messages) == last_message_count:
                # No new messages, try different scroll methods
                if scroll_attempts < 10:
                    await self.page.keyboard.press("PageUp")
                elif scroll_attempts < 20:
                    await self.page.keyboard.press("Home")
                else:
                    # Try scrolling to top of message area
                    try:
                        await self.page.evaluate("window.scrollTo(0, 0)")
                        # Also try scrolling message container
                        await self.page.evaluate("""
                            const messageList = document.querySelector('.c-message_list__scrollbar, .c-virtual_list__scroll_container, [data-qa="slack_kit_scrollbar"]');
                            if (messageList) messageList.scrollTop = 0;
                        """)
                    except:
                        pass
                
                # If no new messages for several attempts, we might be done
                if scroll_attempts > 5 and len(messages) == last_message_count:
                    print("    ✅ Reached beginning of conversation")
                    break
            else:
                last_message_count = len(messages)
            
            await self.page.wait_for_timeout(1500)  # Wait for messages to load
            scroll_attempts += 1
        
        # Sort messages by timestamp
        messages.sort(key=lambda x: float(x.get('ts', 0)))
        
        print(f"✅ Extracted {len(messages)} total messages")
        return messages
    
    async def _extract_visible_messages(self) -> List[Dict[str, Any]]:
        """Extract message data from currently visible DOM elements."""
        messages = []
        
        # Try multiple selectors for message containers
        message_selectors = [
            '[data-qa="virtual_list_item"]',  # Main message items
            '.c-message_kit__message',        # Message kit format
            '.c-message__message_body',       # Classic message format  
            '[data-qa="message"]',            # Generic message selector
            '.c-virtual_list__item'           # Virtual list items
        ]
        
        for selector in message_selectors:
            try:
                message_elements = await self.page.query_selector_all(selector)
                if message_elements:
                    print(f"    🔍 Using selector: {selector} ({len(message_elements)} elements)")
                    break
            except:
                continue
        else:
            print("    ⚠️  No message elements found with any selector")
            return messages
        
        for element in message_elements:
            try:
                message_data = await self._parse_message_element(element)
                if message_data:
                    messages.append(message_data)
            except Exception as e:
                print(f"    ⚠️  Error parsing message element: {e}")
                continue
        
        return messages
    
    async def _parse_message_element(self, element) -> Optional[Dict[str, Any]]:
        """Parse a single message element from the DOM."""
        try:
            # Extract timestamp (this is tricky since Slack shows relative times)
            timestamp = await self._extract_timestamp(element)
            if not timestamp:
                return None
            
            # Extract user name
            user_name = await self._extract_user_name(element)
            
            # Extract message text
            message_text = await self._extract_message_text(element)
            
            # Extract any reactions
            reactions = await self._extract_reactions(element)
            
            # Check if it's a thread reply
            is_thread_reply = await self._check_if_thread_reply(element)
            
            message_data = {
                'ts': timestamp,
                'user_name': user_name,
                'text': message_text,
                'reactions': reactions,
                'is_thread_reply': is_thread_reply,
                'raw_html': await element.inner_html()  # Keep raw HTML for debugging
            }
            
            return message_data
            
        except Exception as e:
            print(f"      ⚠️  Error parsing message: {e}")
            return None
    
    async def _extract_timestamp(self, element) -> Optional[str]:
        """Extract timestamp from message element."""
        try:
            # Try to find timestamp elements
            timestamp_selectors = [
                '[data-qa="message_timestamp"]',
                '.c-timestamp',
                '.c-message__timestamp',
                'time',
                '[data-ts]'
            ]
            
            for selector in timestamp_selectors:
                try:
                    ts_element = await element.query_selector(selector)
                    if ts_element:
                        # Try to get data-ts attribute first (most accurate)
                        data_ts = await ts_element.get_attribute('data-ts')
                        if data_ts:
                            return data_ts
                        
                        # Try datetime attribute
                        datetime_attr = await ts_element.get_attribute('datetime')
                        if datetime_attr:
                            # Convert ISO datetime to timestamp
                            dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                            return str(dt.timestamp())
                        
                        # Try aria-label or title for time info
                        for attr in ['aria-label', 'title']:
                            time_text = await ts_element.get_attribute(attr)
                            if time_text and ('AM' in time_text or 'PM' in time_text):
                                # Parse time text and convert to timestamp
                                parsed_ts = self._parse_time_text(time_text)
                                if parsed_ts:
                                    return parsed_ts
                        
                        # Get visible text as fallback
                        text = await ts_element.text_content()
                        if text:
                            parsed_ts = self._parse_time_text(text)
                            if parsed_ts:
                                return parsed_ts
                except:
                    continue
            
            # Fallback: use current time with a small offset to maintain order
            import time
            return str(time.time())
            
        except Exception as e:
            return None
    
    def _parse_time_text(self, time_text: str) -> Optional[str]:
        """Parse human-readable time text into timestamp."""
        try:
            import re
            from datetime import datetime, timedelta
            
            # Handle relative times like "2 hours ago", "yesterday"
            if 'ago' in time_text.lower():
                if 'minute' in time_text:
                    minutes = int(re.search(r'(\d+)', time_text).group(1))
                    dt = datetime.now() - timedelta(minutes=minutes)
                    return str(dt.timestamp())
                elif 'hour' in time_text:
                    hours = int(re.search(r'(\d+)', time_text).group(1))
                    dt = datetime.now() - timedelta(hours=hours)
                    return str(dt.timestamp())
                elif 'day' in time_text:
                    days = int(re.search(r'(\d+)', time_text).group(1))
                    dt = datetime.now() - timedelta(days=days)
                    return str(dt.timestamp())
            
            # Handle "yesterday"
            if 'yesterday' in time_text.lower():
                dt = datetime.now() - timedelta(days=1)
                return str(dt.timestamp())
            
            # Handle absolute times like "2:30 PM"
            time_match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', time_text, re.IGNORECASE)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                ampm = time_match.group(3).upper()
                
                if ampm == 'PM' and hour != 12:
                    hour += 12
                elif ampm == 'AM' and hour == 12:
                    hour = 0
                
                # Assume today unless date is specified
                today = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
                return str(today.timestamp())
            
            return None
            
        except Exception as e:
            return None
    
    async def _extract_user_name(self, element) -> str:
        """Extract user name from message element."""
        try:
            user_selectors = [
                '[data-qa="message_sender_name"]',
                '.c-message__sender',
                '.c-message_kit__sender',
                '.c-message__sender_name',
                '[data-qa="message_sender"]'
            ]
            
            for selector in user_selectors:
                try:
                    user_element = await element.query_selector(selector)
                    if user_element:
                        name = await user_element.text_content()
                        if name and name.strip():
                            return name.strip()
                except:
                    continue
            
            return "Unknown User"
            
        except Exception as e:
            return "Unknown User"
    
    async def _extract_message_text(self, element) -> str:
        """Extract message text from message element."""
        try:
            text_selectors = [
                '[data-qa="message_text"]',
                '.c-message__message_text',
                '.c-message_kit__text',
                '.c-message__content',
                '.p-rich_text_section'
            ]
            
            for selector in text_selectors:
                try:
                    text_element = await element.query_selector(selector)
                    if text_element:
                        text = await text_element.text_content()
                        if text and text.strip():
                            return text.strip()
                except:
                    continue
            
            # Fallback: get all text content but exclude user name area
            all_text = await element.text_content()
            if all_text:
                # Try to remove timestamp and user name from the text
                lines = all_text.split('\n')
                # Usually message text is in later lines
                for line in lines[1:]:  # Skip first line (usually user/time)
                    if line.strip() and not re.match(r'^\d{1,2}:\d{2}', line.strip()):
                        return line.strip()
            
            return ""
            
        except Exception as e:
            return ""
    
    async def _extract_reactions(self, element) -> List[Dict[str, Any]]:
        """Extract reactions from message element."""
        reactions = []
        try:
            reaction_selectors = [
                '.c-reaction',
                '[data-qa="reaction"]',
                '.c-message__reaction'
            ]
            
            for selector in reaction_selectors:
                try:
                    reaction_elements = await element.query_selector_all(selector)
                    for reaction_element in reaction_elements:
                        emoji = await reaction_element.get_attribute('data-emoji-name')
                        text = await reaction_element.text_content()
                        
                        if text:
                            # Parse reaction text like "👍 2" or "heart 3"
                            parts = text.strip().split()
                            if len(parts) >= 2 and parts[-1].isdigit():
                                reactions.append({
                                    'emoji': emoji or parts[0],
                                    'count': int(parts[-1])
                                })
                except:
                    continue
        except:
            pass
        
        return reactions
    
    async def _check_if_thread_reply(self, element) -> bool:
        """Check if message is a thread reply."""
        try:
            # Look for thread indicators in the element
            thread_indicators = [
                '[data-qa="thread_reply"]',
                '.c-message__thread_reply',
                '.c-message_kit__thread_reply'
            ]
            
            for indicator in thread_indicators:
                if await element.query_selector(indicator):
                    return True
            
            # Check for visual indicators like indentation
            classes = await element.get_attribute('class') or ""
            if 'thread' in classes.lower() or 'reply' in classes.lower():
                return True
            
            return False
            
        except:
            return False
    
    async def save_conversation_to_markdown(self, messages: List[Dict[str, Any]], channel_name: str, channel_id: str):
        """Save extracted messages to markdown file."""
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', channel_name.lstrip('#@'))
        md_path = EXPORT_DIR / f"{safe_name}.md"
        
        with md_path.open("w", encoding="utf-8") as f:
            f.write(f"# {channel_name}\n\n")
            f.write(f"Channel ID: {channel_id}\n")
            f.write(f"Extracted: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total Messages: {len(messages)}\n\n")
            f.write("---\n\n")
            
            for msg in messages:
                # Convert timestamp to readable format
                try:
                    ts = float(msg.get('ts', 0))
                    dt = datetime.fromtimestamp(ts)
                    time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    time_str = "Unknown time"
                
                # Format message
                user = msg.get('user_name', 'Unknown')
                text = msg.get('text', '')
                reactions = msg.get('reactions', [])
                is_reply = msg.get('is_thread_reply', False)
                
                # Add thread indicator
                prefix = "  ↳ " if is_reply else ""
                
                f.write(f"{prefix}**{time_str}** - **{user}**: {text}\n")
                
                # Add reactions if any
                if reactions:
                    reaction_text = ", ".join([f"{r['emoji']} {r['count']}" for r in reactions])
                    f.write(f"  *Reactions: {reaction_text}*\n")
                
                f.write("\n")
        
        print(f"✅ Saved {len(messages)} messages to {md_path}")
    
    async def close(self):
        """Close browser."""
        if self.browser:
            await self.browser.close()


async def main():
    """Main function."""
    print("🚀 Simple Slack Extractor (DOM-based)")
    print("This version extracts data directly from DOM elements")
    print()
    
    extractor = SimpleSlackExtractor()
    
    try:
        # Start browser (non-headless to maintain authentication)
        print("🔧 Starting browser with visible UI...")
        if not await extractor.start(headless=False):
            print("❌ Failed to start browser")
            return
        
        # Navigate to workspace
        navigation_success = await extractor.navigate_to_workspace()
        if not navigation_success:
            print("❌ Failed to navigate to workspace")
            print("💡 Make sure you're logged into Slack in your Chrome browser")
            return
        
        # Get conversation list
        conversations = await extractor.get_conversations_from_sidebar()
        
        if not conversations:
            print("❌ No conversations found")
            return
        
        # Interactive mode
        while True:
            print(f"\nAvailable conversations ({len(conversations)}):")
            for i, conv in enumerate(conversations):
                print(f"  {i+1}. {conv['name']} ({conv['type']})")
            
            print(f"\nCommands:")
            print(f"  • Enter number (1-{len(conversations)}) to extract conversation")
            print(f"  • 'all' to extract all conversations")
            print(f"  • 'q' to quit")
            
            choice = input("Choice: ").strip()
            
            if choice.lower() == 'q':
                break
            elif choice.lower() == 'all':
                for conv in conversations:
                    try:
                        messages = await extractor.extract_messages_from_dom(
                            conv['id'], conv['name']
                        )
                        await extractor.save_conversation_to_markdown(
                            messages, conv['name'], conv['id']
                        )
                    except Exception as e:
                        print(f"❌ Error extracting {conv['name']}: {e}")
                        continue
            else:
                try:
                    index = int(choice) - 1
                    if 0 <= index < len(conversations):
                        conv = conversations[index]
                        messages = await extractor.extract_messages_from_dom(
                            conv['id'], conv['name']
                        )
                        await extractor.save_conversation_to_markdown(
                            messages, conv['name'], conv['id']
                        )
                    else:
                        print("❌ Invalid choice")
                except ValueError:
                    print("❌ Invalid choice")
    
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