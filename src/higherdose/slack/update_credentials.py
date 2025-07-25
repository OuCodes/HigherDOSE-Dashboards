#!/usr/bin/env python3
"""
Helper script to extract Slack credentials from cURL and update credentials file.
"""

import os
import re
import pathlib
from typing import Optional, Tuple

def extract_credentials_from_curl(curl_command: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract cookie and token from cURL command."""
    
    # Extract cookie from -b flag (most common)
    cookie_match = re.search(r"-b ['\"]?([^'\"\\n]+)['\"]?", curl_command)
    if not cookie_match:
        # Fallback to -H Cookie format
        cookie_match = re.search(r"-H ['\"]Cookie: ([^'\"\\n]+)['\"]", curl_command)
    if not cookie_match:
        cookie_match = re.search(r"--header ['\"]Cookie: ([^'\"\\n]+)['\"]", curl_command)
    
    cookie = cookie_match.group(1) if cookie_match else None
    
    # Extract token from various places
    token = None
    
    # Look for token in form data
    token_patterns = [
        r"token=([^&\s'\"]+)",  # Form data
        r"'token':\s*'([^']+)'",  # JSON data
        r'"token":\s*"([^"]+)"',  # JSON data
        r'name="token"[^\\r]*\\r\\n\\r\\n([^\\r]+)\\r\\n',  # Multipart form data
    ]
    
    for pattern in token_patterns:
        match = re.search(pattern, curl_command)
        if match:
            token = match.group(1)
            break
    
    # If no explicit token found, try to extract from cookie d= parameter
    if not token and cookie:
        d_match = re.search(r'd=([^;]+)', cookie)
        if d_match:
            import urllib.parse
            d_value = urllib.parse.unquote(d_match.group(1))
            if d_value.startswith(('xoxc-', 'xoxd-')):
                token = d_value
    
    # Extract x-slack-crumb if present
    crumb = None
    crumb_match = re.search(r"_x_csid=([^&]+)", curl_command)
    if crumb_match:
        crumb = crumb_match.group(1)
    
    return cookie, token, crumb


def update_credentials_file(team_id: str, cookie: str, token: str, crumb: str = "") -> bool:
    """Update the credentials file with new values."""
    
    # Get cookie directory
    cookie_dir = pathlib.Path(os.environ.get("SLACK_COOKIE_DIR", "config/slack"))
    cookie_dir.mkdir(exist_ok=True)
    
    # Find existing file or create new one
    pattern = list(cookie_dir.glob(f"{team_id}*.env"))
    if pattern:
        env_file = pattern[0]
    else:
        env_file = cookie_dir / f"{team_id}-higherdose.env"
    
    # Create new credentials content
    content = f"SLACK_COOKIE='{cookie}'\nSLACK_TOKEN='{token}'"
    if crumb:
        content += f"\nSLACK_CRUMB='{crumb}'"
    
    # Write to file
    env_file.write_text(content)
    print(f"✅ Updated credentials in {env_file}")
    return True


def update_from_file(team_id: str = "TA97020CV", curl_file: str = "slack_curl.txt") -> bool:
    """Read cURL command from file and update credentials."""
    
    curl_file_path = pathlib.Path(curl_file)
    
    if not curl_file_path.exists():
        print(f"❌ File {curl_file} not found")
        print()
        print("To create the cURL file:")
        print("1. Open HigherDOSE Slack in your browser")
        print("2. Open DevTools (F12 or Cmd+Option+I)")
        print("3. Go to Network tab")
        print("4. Do any action in Slack (click channel, send message)")
        print("5. Find any request to 'higherdosemanagement.slack.com' or '/api/'")
        print("6. Right-click → Copy → Copy as cURL")
        print(f"7. Save the cURL command to {curl_file}")
        print("8. Run this script again")
        return False
    
    try:
        curl_command = curl_file_path.read_text().strip()
    except Exception as e:
        print(f"❌ Error reading {curl_file}: {e}")
        return False
    
    if not curl_command:
        print(f"❌ File {curl_file} is empty")
        return False
    
    # Extract credentials
    cookie, token, crumb = extract_credentials_from_curl(curl_command)
    
    if not cookie:
        print("❌ Could not extract cookie from cURL command")
        print("Make sure the cURL includes a 'Cookie:' header")
        return False
    
    if not token:
        print("⚠️  Could not extract token from cURL command")
        print("The script will try to extract it from the cookie")
    
    # Update credentials file
    try:
        update_credentials_file(team_id, cookie, token or "", crumb or "")
        print("🎉 Credentials updated successfully!")
        return True
    except Exception as e:
        print(f"❌ Error updating credentials: {e}")
        return False


if __name__ == "__main__":
    import sys
    
    # Check for custom file argument
    curl_file = "slack_curl.txt"
    if len(sys.argv) > 1:
        curl_file = sys.argv[1]
    
    print(f"🔄 Looking for cURL command in: {curl_file}")
    success = update_from_file(curl_file=curl_file)
    
    if success:
        print("✅ Ready to use the updated credentials!")
    else:
        sys.exit(1) 