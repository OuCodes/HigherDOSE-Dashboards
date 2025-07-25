#!/usr/bin/env python3
"""
Comprehensive Slack conversation extraction script.
This script handles authentication and extraction in one command.
"""

import asyncio
import sys
import os
import argparse

from higherdose.slack.slack_fetcher_playwright import SlackBrowser, ConversationType, EXPORT_DIR, _load_tracker, _save_tracker, _markdown_line, _create_safe_filename

async def extract_conversation(conversation_name, headless=False, refresh=False):
    """Extract a conversation with proper authentication handling."""
    print(f"🔍 Extracting: {conversation_name}")
    
    browser = SlackBrowser()
    
    try:
        # Start browser
        print(f"🚀 Starting browser (headless={headless})...")
        await browser.start(headless=headless)
        
        # Ensure we're logged in
        print("🔐 Checking authentication...")
        auth_success = await browser.ensure_logged_in()
        
        if not auth_success:
            if headless:
                print("❌ Authentication failed in headless mode.")
                print("💡 Try running with --no-headless first to establish authentication:")
                print(f"   python slack/extract_conversation.py '{conversation_name}' --no-headless")
                return False
            else:
                print("❌ Authentication failed.")
                print("💡 Make sure you're logged into the HigherDOSE Slack workspace.")
                return False
        
        print("✅ Authentication successful!")
        
        # Get initial data
        print("📊 Loading workspace data...")
        conversations = await browser.get_conversations()
        users = await browser.get_user_list()
        
        # Debug info
        print(f"📋 Found {len(conversations)} conversations and {len(users)} users")
        
        if not conversations:
            print("⚠️  No conversations found.")
            print("💡 This might happen if the workspace data hasn't loaded yet.")
            print("💡 Try navigating to different pages in the browser or wait a moment.")
            
            # Try to navigate to main workspace to load data
            print("🔄 Attempting to navigate to workspace to load conversation data...")
            await browser.page.goto("https://higherdosemanagement.slack.com")
            await browser.page.wait_for_timeout(3000)
            
            # Try getting conversations again
            conversations = await browser.get_conversations()
            print(f"📋 After navigation: Found {len(conversations)} conversations")
            
            if not conversations:
                print("❌ Still no conversations found.")
                return False
        
        # Clean conversation name (remove # or @ prefix)
        clean_name = conversation_name.lstrip("#@")
        
        # Try to find the conversation using multiple matching strategies
        conv_info = None
        
        # Strategy 1: Look for exact match with the input name
        if conversation_name in conversations:
            conv_info = conversations[conversation_name]
        
        # Strategy 2: Look for clean name (without prefixes)
        elif clean_name in conversations:
            conv_info = conversations[clean_name]
        
        # Strategy 3: Try adding prefixes back
        elif f"#{clean_name}" in conversations:
            conv_info = conversations[f"#{clean_name}"]
        elif f"@{clean_name}" in conversations:
            conv_info = conversations[f"@{clean_name}"]
        
        # Strategy 4: Case-insensitive search
        else:
            # Try case-insensitive matching
            for conv_name, conv_data in conversations.items():
                if conv_name.lower() == conversation_name.lower():
                    conv_info = conv_data
                    break
                elif conv_name.lower() == clean_name.lower():
                    conv_info = conv_data
                    break
                elif conv_name.lower() == f"#{clean_name}".lower():
                    conv_info = conv_data
                    break
                elif conv_name.lower() == f"@{clean_name}".lower():
                    conv_info = conv_data
                    break
        
        if not conv_info:
            print(f"❌ Conversation '{conversation_name}' not found.")
            print("\n📋 Available conversations:")
            for name in sorted(conversations.keys()):
                print(f"  - {name}")
            return False
        
        channel_id = conv_info.id
        
        # Load tracking data
        tracker = _load_tracker()
        last_ts = 0 if refresh else tracker["channels"].get(channel_id, 0)
        
        if refresh:
            print(f"🔄 Refreshing entire conversation for {conv_info}")
        else:
            print(f"📥 Fetching new messages from {conv_info} (since {last_ts})")
        
        # Fetch messages
        messages = await browser.fetch_conversation_history(channel_id, last_ts)
        
        if not messages:
            print("📭 No new messages found.")
            return True
        
        # Save to markdown
        safe_name = _create_safe_filename(conv_info.name, channel_id)
        md_path = EXPORT_DIR / f"{safe_name}.md"
        
        # Create directory if it doesn't exist
        md_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write messages to file
        mode = "w" if refresh else "a"
        with md_path.open(mode, encoding="utf-8") as f:
            if refresh:
                f.write(f"# {conv_info.name}\n\n")
            
            for msg in messages:
                f.write(_markdown_line(msg, users) + "\n")
        
        # Update tracker
        if messages:
            highest_ts = max(float(m["ts"]) for m in messages)
            tracker["channels"][channel_id] = highest_ts
            _save_tracker(tracker)
        
        print(f"✅ {'Refreshed' if refresh else 'Added'} {len(messages)} messages to {md_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await browser.close()

async def list_conversations():
    """List all available conversations."""
    print("📋 Listing available conversations...")
    
    browser = SlackBrowser()
    
    try:
        # Start browser
        await browser.start(headless=False)
        
        # Ensure we're logged in
        if not await browser.ensure_logged_in():
            print("❌ Authentication failed.")
            return False
        
        # Get conversations
        conversations = await browser.get_conversations()
        
        if not conversations:
            print("⚠️  No conversations found.")
            return False
        
        # Group by type
        by_type = {
            ConversationType.CHANNEL: [],
            ConversationType.DM: [],
            ConversationType.MULTI_PERSON_DM: [],
            ConversationType.UNKNOWN: []
        }
        
        for name, conv_info in conversations.items():
            by_type[conv_info.conversation_type].append(conv_info)
        
        # Display results
        print(f"\n📊 Found {len(conversations)} conversations:")
        
        if by_type[ConversationType.CHANNEL]:
            print(f"\n  📢 Channels ({len(by_type[ConversationType.CHANNEL])}):")
            for conv_info in sorted(by_type[ConversationType.CHANNEL], key=lambda x: x.name):
                print(f"    {conv_info.name}")
        
        if by_type[ConversationType.DM]:
            print(f"\n  💬 Direct Messages ({len(by_type[ConversationType.DM])}):")
            for conv_info in sorted(by_type[ConversationType.DM], key=lambda x: x.name):
                print(f"    {conv_info.name}")
        
        if by_type[ConversationType.MULTI_PERSON_DM]:
            print(f"\n  👥 Multi-person DMs ({len(by_type[ConversationType.MULTI_PERSON_DM])}):")
            for conv_info in sorted(by_type[ConversationType.MULTI_PERSON_DM], key=lambda x: x.name):
                print(f"    {conv_info.name}")
        
        print("\n💡 Usage: python slack/extract_conversation.py '<conversation_name>'")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await browser.close()

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Extract Slack conversations to markdown")
    parser.add_argument("conversation", nargs="?", help="Name of the conversation to extract")
    parser.add_argument("--list", action="store_true", help="List all available conversations")
    parser.add_argument("--no-headless", action="store_true", help="Run in non-headless mode (browser window visible)")
    parser.add_argument("--refresh", action="store_true", help="Refresh entire conversation (ignore tracking)")
    
    args = parser.parse_args()
    
    if args.list:
        print("🚀 Starting conversation list...")
        
        # Ensure we're in the correct directory
        original_dir = os.getcwd()
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(script_dir)
        os.chdir(project_dir)
        
        try:
            success = asyncio.run(list_conversations())
            sys.exit(0 if success else 1)
        except KeyboardInterrupt:
            print("\n⚠️  Interrupted by user")
            sys.exit(1)
        finally:
            os.chdir(original_dir)
    
    if not args.conversation:
        print("Usage: python slack/extract_conversation.py '<conversation_name>' [options]")
        print("       python slack/extract_conversation.py --list")
        print()
        print("Examples:")
        print("  python slack/extract_conversation.py 'sb-higherdose'")
        print("  python slack/extract_conversation.py 'dm_with_ingrid' --no-headless")
        print("  python slack/extract_conversation.py 'sb-higherdose' --refresh")
        print("  python slack/extract_conversation.py --list")
        sys.exit(1)
    
    conversation_name = args.conversation
    headless = not args.no_headless
    refresh = args.refresh
    
    print(f"🔍 Debug: args.no_headless = {args.no_headless}")
    print(f"🔍 Debug: headless = {headless}")
    
    if not headless:
        print("🖥️  Running in non-headless mode (browser window will be visible)")
    
    print(f"🚀 Starting extraction of: {conversation_name}")
    
    # Ensure we're in the correct directory
    original_dir = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)
    
    try:
        success = asyncio.run(extract_conversation(conversation_name, headless, refresh))
        
        if success:
            print(f"✅ Successfully extracted: {conversation_name}")
            print(f"📁 Check the data/processed/slack/markdown_exports directory for the file")
        else:
            print(f"❌ Failed to extract: {conversation_name}")
            if headless:
                print("💡 Try running with --no-headless flag to debug authentication issues")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Exception: {e}")
        sys.exit(1)
    finally:
        os.chdir(original_dir)

if __name__ == "__main__":
    main() 