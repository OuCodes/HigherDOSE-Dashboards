#!/usr/bin/env python3
"""
Script to extract a single Slack conversation to markdown file.
"""

import os
import sys
import asyncio

# Import from the slack fetcher script
from higherdose.slack.slack_fetcher_playwright import SlackBrowser, ConversationType, EXPORT_DIR, _load_tracker, _save_tracker, _markdown_line, _create_safe_filename

async def extract_single_conversation(conversation_name, headless=False):
    """Extract a single conversation directly using the SlackBrowser."""
    print(f"🔍 Extracting: {conversation_name}")
    
    browser = SlackBrowser()
    
    try:
        # Start browser (headless=False for authentication, True for automation)
        print(f"🚀 Starting browser (headless={headless})...")
        await browser.start(headless=headless)
        
        # Ensure we're logged in
        print("🔐 Checking authentication...")
        if not await browser.ensure_logged_in():
            print("❌ Failed to log in. Make sure you're authenticated.")
            if headless:
                print("💡 Try running without headless mode first to establish authentication.")
                print("💡 Run: python slack/extract_single_conversation.py '<conversation_name>' --no-headless")
            return False
        
        # Get initial data
        print("📊 Loading workspace data...")
        conversations = await browser.get_conversations()
        users = await browser.get_user_list()
        
        if not conversations:
            print("⚠️  No conversations found.")
            print("💡 Try navigating to different pages in the browser to load conversation data.")
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
            print("Available conversations:")
            for name in sorted(conversations.keys()):
                print(f"  - {name}")
            return False
        
        channel_id = conv_info.id
        
        # Load tracking data
        tracker = _load_tracker()
        last_ts = tracker["channels"].get(channel_id, 0)
        
        print(f"📥 Fetching messages from {conv_info} (since {last_ts})")
        
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
        
        with md_path.open("a", encoding="utf-8") as f:
            for msg in messages:
                f.write(_markdown_line(msg, users) + "\n")
        
        # Update tracker
        if messages:
            highest_ts = max(float(m["ts"]) for m in messages)
            tracker["channels"][channel_id] = highest_ts
            _save_tracker(tracker)
        
        print(f"✅ Added {len(messages)} messages to {md_path}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        await browser.close()

def main():
    """Main function to extract a single conversation."""
    if len(sys.argv) < 2:
        print("Usage: python extract_single_conversation.py '<conversation_name>' [--no-headless]")
        print("Example: python extract_single_conversation.py 'sb-higherdose'")
        print("Example: python extract_single_conversation.py 'dm_with_ingrid' --no-headless")
        sys.exit(1)
    
    conversation_name = sys.argv[1]
    
    # Check for headless mode flag
    headless = True
    if len(sys.argv) > 2 and sys.argv[2] == "--no-headless":
        headless = False
        print("🖥️  Running in non-headless mode (browser window will be visible)")
    
    print(f"🚀 Starting extraction of: {conversation_name}")
    
    # Ensure we're in the correct directory
    original_dir = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)
    
    try:
        # Run the async extraction
        success = asyncio.run(extract_single_conversation(conversation_name, headless))
        
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