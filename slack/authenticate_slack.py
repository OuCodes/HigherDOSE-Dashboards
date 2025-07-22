#!/usr/bin/env python3
"""
Helper script to establish Slack authentication for subsequent headless operations.
Run this first to set up authentication, then use extract_single_conversation.py in headless mode.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the current directory to Python path so we can import the slack fetcher
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from slack_fetcher_playwright import SlackBrowser

async def authenticate_slack():
    """Establish Slack authentication and save credentials."""
    print("🔐 Slack Authentication Setup")
    print("=" * 50)
    print("This script will help you establish authentication for the Slack workspace.")
    print("Once authenticated, you can run extract_single_conversation.py in headless mode.")
    print()
    
    browser = SlackBrowser()
    
    try:
        # Start browser in non-headless mode for authentication
        print("🚀 Starting browser (non-headless mode)...")
        await browser.start(headless=False)
        
        # Attempt to ensure we're logged in
        print("🔍 Checking authentication...")
        if await browser.ensure_logged_in():
            print("✅ Authentication successful!")
            
            # Test getting conversations to verify everything works
            print("🧪 Testing data access...")
            conversations = await browser.get_conversations()
            users = await browser.get_user_list()
            
            if conversations:
                print(f"✅ Found {len(conversations)} conversations")
                print("Available conversations:")
                for name in sorted(list(conversations.keys())[:10]):  # Show first 10
                    print(f"  - {name}")
                if len(conversations) > 10:
                    print(f"  ... and {len(conversations) - 10} more")
            else:
                print("⚠️  No conversations found, but authentication appears successful")
                print("💡 Try navigating to different pages in the browser to load conversation data")
            
            if users:
                print(f"✅ Found {len(users)} users")
            
            print()
            print("🎉 Authentication setup complete!")
            print("✅ You can now run extract_single_conversation.py in headless mode")
            print()
            print("Example usage:")
            print("  python slack/extract_single_conversation.py 'sb-higherdose'")
            print("  python slack/extract_single_conversation.py 'dm_with_ingrid'")
            
            return True
            
        else:
            print("❌ Authentication failed")
            print("💡 Make sure you're logged into the HigherDOSE Slack workspace")
            print("💡 The browser window should show the workspace with channel sidebar")
            return False
            
    except Exception as e:
        print(f"❌ Error during authentication: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        print("\n🔄 Closing browser...")
        await browser.close()

def main():
    """Main function."""
    print("🚀 Starting Slack authentication setup...")
    
    # Ensure we're in the correct directory
    original_dir = os.getcwd()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    os.chdir(project_dir)
    
    try:
        success = asyncio.run(authenticate_slack())
        
        if success:
            print("✅ Setup completed successfully!")
            sys.exit(0)
        else:
            print("❌ Setup failed!")
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