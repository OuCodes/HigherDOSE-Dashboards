#!/usr/bin/env python3
"""
Wrapper script to run the Playwright-based Slack fetcher.

This ensures the script runs in the virtual environment and handles setup.
"""
import subprocess
import sys
import os
from pathlib import Path


def main():
    """Main function to run the Slack fetcher."""
    print("🔗 HigherDOSE Slack Fetcher (Playwright Edition)")
    print()
    
    # Check if we're in the project directory
    # No longer relies on relative file paths – uses the installed package path
    
    # Check if virtual environment exists
    venv_path = Path("venv")
    if not venv_path.exists():
        print("⚠️  Virtual environment not found. Creating one...")
        try:
            subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
            print("✅ Virtual environment created")
        except subprocess.CalledProcessError:
            print("❌ Failed to create virtual environment")
            return 1
    
    # Determine the correct python executable
    if os.name == "nt":  # Windows
        python_exe = venv_path / "Scripts" / "python.exe"
        pip_exe = venv_path / "Scripts" / "pip.exe"
    else:  # Unix/Linux/macOS
        python_exe = venv_path / "bin" / "python"
        pip_exe = venv_path / "bin" / "pip"
    
    if not python_exe.exists():
        print("❌ Virtual environment appears to be corrupted. Please delete 'venv' folder and try again.")
        return 1
    
    # Install requirements
    print("📦 Installing/updating project package (editable mode)...")
    try:
        # Install the project itself using pyproject.toml as the single source of truth
        subprocess.run([str(pip_exe), "install", "-e", "."], check=True)
        print("✅ Project installed/updated")
    except subprocess.CalledProcessError:
        print("❌ Failed to install project dependencies")
        return 1
    
    # Install Playwright browsers if needed
    print("🌐 Checking Playwright browsers...")
    try:
        # Check if Playwright is installed and browsers are available
        result = subprocess.run([str(python_exe), "-c", "from playwright.sync_api import sync_playwright; print('ok')"], 
                                capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print("🔄 Installing Playwright...")
            subprocess.run([str(pip_exe), "install", "playwright"], check=True)
            subprocess.run([str(python_exe), "-m", "playwright", "install", "chromium"], check=True)
            print("✅ Playwright setup complete")
        else:
            print("✅ Playwright ready")
    except subprocess.CalledProcessError:
        print("❌ Failed to setup Playwright")
        print("💡 Try running: python slack/setup_playwright.py")
        return 1
    
    # Run the main script
    print("🚀 Starting Slack fetcher...")
    print()
    try:
        subprocess.run([str(python_exe), "-m", "higherdose.slack.slack_fetcher_playwright"], check=True)
    except subprocess.CalledProcessError:
        print("❌ Slack fetcher encountered an error")
        return 1
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        return 0
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
