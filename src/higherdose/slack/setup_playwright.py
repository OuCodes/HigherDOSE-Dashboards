#!/usr/bin/env python3
"""
Setup script for Playwright-based Slack fetcher.

This script will:
1. Install Playwright browsers
2. Test the setup
3. Provide usage instructions
"""
import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd: str, description: str) -> bool:
    """Run a command and return True if successful."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(cmd.split(), capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ {description} completed successfully")
            return True
        else:
            print(f"❌ {description} failed:")
            print(f"   {result.stderr}")
            return False
    except Exception as e:
        print(f"❌ {description} failed with error: {e}")
        return False


def main():
    print("🚀 Setting up Playwright for Slack Fetcher")
    print("=" * 50)
    
    # Check if we're in a virtual environment
    if not hasattr(sys, 'base_prefix') or sys.base_prefix == sys.prefix:
        print("⚠️  It's recommended to use a virtual environment.")
        print("   Consider running: python -m venv venv && source venv/bin/activate")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Setup cancelled.")
            return
    else:
        print("✅ Virtual environment detected")
    
    print()
    
    # Install Playwright
    if not run_command("pip install playwright", "Installing Playwright"):
        return
    
    print()
    
    # Install browsers
    if not run_command("playwright install chromium", "Installing Chromium browser"):
        return
    
    print()
    
    # Test setup
    print("🧪 Testing Playwright setup...")
    try:
        import playwright
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("https://example.com")
            title = page.title()
            browser.close()
            
        if title:
            print("✅ Playwright setup test successful!")
        else:
            print("⚠️  Playwright setup test had issues")
            
    except Exception as e:
        print(f"❌ Playwright setup test failed: {e}")
        return
    
    print()
    print("🎉 Setup Complete!")
    print("=" * 50)
    print()
    print("📖 Usage Instructions:")
    print("1. Run the Playwright-based fetcher:")
    print("   python slack/slack_fetcher_playwright.py")
    print()
    print("2. The script will:")
    print("   • Open a browser window (first time)")
    print("   • Check if you're logged into Slack")
    print("   • If not logged in, wait for you to log in manually")
    print("   • Automatically capture fresh credentials")
    print("   • Let you fetch messages interactively")
    print()
    print("3. Benefits over the old script:")
    print("   • No manual credential extraction needed")
    print("   • Automatically handles token expiration")
    print("   • More reliable authentication")
    print("   • Better handling of different conversation types")
    print()
    print("🔧 Troubleshooting:")
    print("• If browser doesn't open, try: playwright install --force chromium")
    print("• If login fails, clear browser data and try again")
    print("• For headless mode, edit the script and set headless=True")


if __name__ == "__main__":
    main() 