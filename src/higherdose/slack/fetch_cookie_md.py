#!/usr/bin/env python3
"""
Fetch Slack messages (channels or DMs) using existing browser cookies.

• Supports multiple workspaces by keeping one creds file per team in
  ~/.slack_cookies/<TEAM_ID>*.env
• Appends new messages to a Markdown file per conversation instead of
  overwriting.
• Remembers the latest timestamp fetched for every channel in a single
  JSON tracker, so subsequent runs grab only the delta.
• Automatically updates rolodex.json with new contacts found.

Dependencies (add to requirements.txt):
    requests
    python-dateutil
"""
from __future__ import annotations

import json
import os
import sys
import time
import pathlib
import re
from datetime import datetime
from typing import Dict, Tuple, List, Any, Optional

import requests
from dateutil import parser as date_parser


# -------------- Config -------------------------------------------------------
# Directory containing per-workspace credential files.
# Can be overridden with the environment variable SLACK_COOKIE_DIR so that
# repositories can keep creds inside the repo if desired.
COOKIE_DIR = pathlib.Path(os.environ.get("SLACK_COOKIE_DIR", "config/slack"))
TRACK_FILE = pathlib.Path("config/slack/conversion_tracker.json")
EXPORT_DIR = pathlib.Path("data/processed/slack/markdown_exports")
ROLODEX_FILE = pathlib.Path("rolodex.json")
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


# -------------- Helpers ------------------------------------------------------

def _load_creds(team_id: str) -> Tuple[str, str, str | None]:
    """Return (cookie, crumb, optional xoxc token)."""
    pattern = list(COOKIE_DIR.glob(f"{team_id}*.env"))
    if not pattern:
        sys.exit(f"⚠️  No creds file matching {team_id}*.env in {COOKIE_DIR}")

    env_path = pattern[0]
    env: Dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        env[key.strip()] = val.strip().strip("'\"")

    try:
        cookie = env["SLACK_COOKIE"]
    except KeyError as e:
        sys.exit(f"Missing {e.args[0]} in {env_path}")

    # Extract xoxc token from cookie if not provided separately
    token = env.get("SLACK_TOKEN") or env.get("SLACK_XOXC")
    if not token and "d=" in cookie:
        # Try to extract from d= cookie value - newer Slack embeds tokens there
        import urllib.parse
        d_matches = re.findall(r'd=([^;]*)', cookie)
        for d_val_encoded in d_matches:
            d_val = urllib.parse.unquote(d_val_encoded)
            # Look for xoxc- or xoxd- pattern in the decoded value
            if d_val.startswith(('xoxc-', 'xoxd-')):
                token = d_val
                break

    crumb = env.get("SLACK_CRUMB", "")  # Make crumb optional
    return cookie, crumb, token


def _api_post(domain: str, endpoint: str, cookie: str, crumb: str, payload: Dict[str, Any]) -> Dict:
    import time
    import random
    
    # Generate boundary similar to what browsers use
    boundary = f"----WebKitFormBoundary{''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789', k=16))}"
    
    headers = {
        "cookie": cookie,
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "content-type": f"multipart/form-data; boundary={boundary}",
        "origin": "https://app.slack.com",
        "priority": "u=1, i",
        "sec-ch-ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
        "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    }
    
    # Create multipart form data
    form_parts = []
    
    # Add token first (required)
    if 'token' in payload:
        form_parts.append(f'--{boundary}')
        form_parts.append('Content-Disposition: form-data; name="token"')
        form_parts.append('')
        form_parts.append(payload['token'])
    
    # Add other fields
    for key, value in payload.items():
        if key != 'token':
            form_parts.append(f'--{boundary}')
            form_parts.append(f'Content-Disposition: form-data; name="{key}"')
            form_parts.append('')
            form_parts.append(str(value))
    
    # Add required Slack form fields based on your cURL
    standard_fields = {
        "_x_reason": "client_redux_store",
        "_x_mode": "online", 
        "_x_sonic": "true",
        "_x_app_name": "client"
    }
    
    for key, value in standard_fields.items():
        if key not in payload:  # Don't override if already provided
            form_parts.append(f'--{boundary}')
            form_parts.append(f'Content-Disposition: form-data; name="{key}"')
            form_parts.append('')
            form_parts.append(value)
    
    form_parts.append(f'--{boundary}--')
    
    # Join with \r\n
    body = '\r\n'.join(form_parts)
    
    # Build URL with query parameters like your working cURL
    timestamp = int(time.time() * 1000)
    base_id = "f77c7f65"  # Use similar pattern to your cURL
    
    url_params = {
        '_x_id': f'{base_id}-{timestamp}',
        'slack_route': 'TA97020CV',
        '_x_version_ts': '1752635551',
        '_x_frontend_build_type': 'current',
        '_x_desktop_ia': '4',
        '_x_gantry': 'true',
        'fp': 'a3',
        '_x_num_retries': '0'
    }
    
    if crumb:
        url_params['_x_csid'] = crumb
    
    # Build URL
    param_string = '&'.join([f'{k}={v}' for k, v in url_params.items()])
    url = f"https://{domain}/api/{endpoint}?{param_string}"
    
    resp = requests.post(url, headers=headers, data=body, timeout=30)
    resp.raise_for_status()
    result = resp.json()
    
    # Check for authentication errors
    if not result.get("ok") and result.get("error") in ["invalid_auth", "not_authed", "token_revoked"]:
        print(f"\n❌ Authentication failed: {result.get('error')}")
        print("🔄 Your Slack credentials have expired. Please update them manually.")
        print()
        print("To update credentials:")
        print("1. Open HigherDOSE Slack in your browser")
        print("2. Open DevTools (F12 or Cmd+Option+I)")
        print("3. Go to Network tab")
        print("4. Do any action in Slack (click channel, send message)")
        print("5. Find any request to 'higherdosemanagement.slack.com' or '/api/'")
        print("6. Right-click → Copy → Copy as cURL")
        print("7. Save the cURL command to a file called 'slack_curl.txt'")
        print("8. Run: python slack/update_credentials.py")
        print()
        print("After updating credentials, restart this script.")
        sys.exit(1)
    
    return result


def _load_rolodex() -> Dict[str, Any]:
    """Load existing rolodex or create empty structure."""
    if ROLODEX_FILE.exists():
        return json.loads(ROLODEX_FILE.read_text())
    return {
        "people": [],
        "companies": [
            {
                "name": "HigherDOSE",
                "type": "Client Company",
                "industry": "Health & Wellness",
                "description": "Sells health and wellness electronic devices, beauty topicals, and supplements"
            },
            {
                "name": "Sharma Brands",
                "type": "Agency",
                "industry": "Digital Marketing",
                "description": "Manages advertising channels including Google and Meta for HigherDOSE"
            }
        ],
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "source_files": ["slack_exports"]
    }


def _save_rolodex(rolodex_data: Dict[str, Any]) -> None:
    """Save rolodex with updated timestamp."""
    rolodex_data["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    ROLODEX_FILE.write_text(json.dumps(rolodex_data, indent=2))


def _add_to_rolodex(user_id: str, username: str, display_name: str, email: str = None) -> None:
    """Add new contact to rolodex if not already present."""
    rolodex = _load_rolodex()
    
    # Check if person already exists (by username or display name)
    existing_names = {person.get("name", "").lower() for person in rolodex["people"]}
    existing_usernames = {person.get("username", "").lower() for person in rolodex["people"]}
    
    name_to_check = display_name or username
    if name_to_check.lower() in existing_names or username.lower() in existing_usernames:
        return  # Already exists
    
    # Determine company based on email domain
    company = "Unknown"
    if email:
        if "@higherdose.com" in email.lower():
            company = "HigherDOSE"
        elif "@sharmabrands.com" in email.lower():
            company = "Sharma Brands"
        elif "@redstagfulfillment.com" in email.lower():
            company = "RedStag Fulfillment"
        elif any(domain in email.lower() for domain in ["@gmail.com", "@yahoo.com", "@hotmail.com"]):
            company = "External/Contractor"
    
    # Add new person
    new_person = {
        "name": name_to_check,
        "username": username,
        "user_id": user_id,
        "role": "Team Member",  # Default role, can be updated manually
        "company": company,
        "email": email,
        "notes": f"Found in Slack conversations - added automatically on {datetime.now().strftime('%Y-%m-%d')}"
    }
    
    rolodex["people"].append(new_person)
    _save_rolodex(rolodex)
    print(f"📝 Added {name_to_check} (@{username}) to rolodex [{company}]")


def _channels_lookup(domain: str, cookie: str, crumb: str, token: str | None) -> Dict[str, str]:
    """Return mapping name->channel_id for public/priv/mpim/im"""
    out: Dict[str, str] = {}
    
    # First test with the working endpoint to verify authentication
    try:
        data = {}
        if token:
            data["token"] = token
            
        print("🔍 Testing authentication with users.list...")
        r = _api_post(domain, "users.list", cookie, crumb, data)
        
        if r.get("ok"):
            print("✅ Authentication successful!")
            print(f"📊 Found {len(r.get('members', []))} users")
        else:
            print(f"❌ Users list API failed: {r.get('error', 'unknown_error')}")
            return out
            
    except Exception as e:
        print(f"⚠️  Error with users.list: {e}")
        return out
        
    # Now try to get user list for creating DM mappings
    try:
        print("🔍 Trying to get user list...")
        user_data = {"token": token} if token else {}
        user_resp = _api_post(domain, "users.list", cookie, crumb, user_data)
        
        if user_resp.get("ok"):
            members = user_resp.get("members", [])
            print(f"✅ Found {len(members)} users")
            
            for user in members:
                user_id = user.get("id", "")
                username = user.get("name", "")
                if user_id and not user.get("is_bot", False) and not user.get("deleted", False):
                    # Create DM channel entries using user ID
                    out[user_id] = user_id  # Map user ID to itself for DM lookup
                    if username:
                        out[username] = user_id  # Also map username to user ID
        else:
            print(f"⚠️  Users list failed: {user_resp.get('error', 'unknown_error')}")
            
    except Exception as e:
        print(f"⚠️  Error getting users: {e}")
    
    # If we still don't have any users, add some manual entries from existing conversations
    if not out:
        print("⚠️  Adding known channel IDs from previous conversations...")
        # Add channels we know exist from tracking file
        out["C092D2U5CD6"] = "C092D2U5CD6"  # Group conversation
        out["D09430T3YBF"] = "D09430T3YBF"  # Rahul DM  
        out["D093VHXRG9K"] = "D093VHXRG9K"  # Jake DM
        
        # Add user IDs we know
        out["U05KD2RULPN"] = "D09430T3YBF"  # Rahul
        out["U06SRGR9M7E"] = "D093VHXRG9K"  # Jake
    
    return out


def _load_tracker() -> Dict[str, Any]:
    if TRACK_FILE.exists():
        data = json.loads(TRACK_FILE.read_text())
        # Ensure channels key exists
        if "channels" not in data:
            data["channels"] = {}
        return data
    return {"channels": {}}


def _save_tracker(data: Dict[str, Any]) -> None:
    TRACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRACK_FILE.write_text(json.dumps(data, indent=2))


def _build_user_map(domain: str, cookie: str, crumb: str, token: str | None) -> Dict[str, str]:
    """Build user ID to display name mapping and update rolodex."""
    user_map: Dict[str, str] = {}
    
    # First, load existing rolodex to check for manual mappings
    rolodex = _load_rolodex()
    for person in rolodex.get("people", []):
        user_id = person.get("user_id")
        name = person.get("name")
        username = person.get("username")
        if user_id and name:
            # Use display name, with @username fallback
            display_name = f"{name} (@{username})" if username else name
            user_map[user_id] = display_name
    
    print(f"📋 Loaded {len(user_map)} users from existing rolodex")
    
    if not token:
        print("⚠️  No token available - using rolodex data only")
        return user_map
    
    try:
        print("🔍 Fetching additional users from Slack API...")
        cursor = None
        total_users = 0
        new_users = 0
        
        while True:
            payload = {"limit": 1000}
            if cursor:
                payload["cursor"] = cursor
            if token:
                payload["token"] = token
                
            user_resp = _api_post(domain, "users.list", cookie, crumb, payload)
            
            if not user_resp.get("ok"):
                print(f"⚠️  User lookup failed: {user_resp.get('error', 'unknown_error')}")
                break
                
            members = user_resp.get("members", [])
            total_users += len(members)
            
            for user in members:
                user_id = user.get("id", "")
                username = user.get("name", "")
                profile = user.get("profile", {})
                display_name = profile.get("display_name", "") or profile.get("real_name", "") or username
                email = profile.get("email", "")
                
                if user_id and display_name:
                    # Only add if not already in user_map (from rolodex)
                    if user_id not in user_map:
                        user_map[user_id] = display_name
                        new_users += 1
                        # Add to rolodex if it's a real user (not bot)
                        if not user.get("is_bot", False) and not user.get("deleted", False):
                            _add_to_rolodex(user_id, username, display_name, email)
            
            cursor = user_resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.5)
            
        print(f"✅ Added {new_users} new users from API (total fetched: {total_users}, total mapped: {len(user_map)})")
        
    except Exception as e:
        print(f"⚠️  Error fetching users from API: {e}")
        print(f"📋 Continuing with {len(user_map)} users from rolodex")
    
    return user_map


def _markdown_line(msg: Dict[str, Any], users: Dict[str, str], missing_users: Dict[str, str]) -> str:
    ts_float = float(msg["ts"])
    ts_str = datetime.fromtimestamp(ts_float).strftime("%Y-%m-%d %H:%M")
    
    user_id = msg.get("user", "")
    user_name = users.get(user_id)
    
    # If not in main user map, check missing users cache
    if not user_name and user_id in missing_users:
        user_name = missing_users[user_id]
    
    # If still no name, try some fallbacks
    if not user_name and user_id:
        if msg.get("bot_id"):
            user_name = f"(bot:{msg.get('bot_id')})"
        elif msg.get("username"):
            user_name = msg.get("username")
        else:
            # Create a friendlier unknown name
            user_name = f"Unknown_User_{user_id[-6:]}"
            missing_users[user_id] = user_name  # Cache for consistency
    
    if not user_name:
        user_name = "(system)"
    
    text = msg.get("text", "").replace("\n", "  \n")
    # indent replies for threads
    prefix = "    " if msg.get("parent_user_id") else ""
    return f"{prefix}- **{ts_str}** *{user_name}*: {text}"


def _get_dm_participants(chan_id: str, domain: str, cookie: str, crumb: str, token: str, user_map: Dict[str, str]) -> List[str]:
    """Get list of participant names for a DM conversation."""
    try:
        payload = {"channel": chan_id}
        if token:
            payload["token"] = token
        
        info_resp = _api_post(domain, "conversations.info", cookie, crumb, payload)
        if info_resp.get("ok"):
            channel = info_resp.get("channel", {})
            
            # For regular DMs (is_im), get the other user
            if channel.get("is_im"):
                user_id = channel.get("user")
                if user_id:
                    name = user_map.get(user_id, f"User_{user_id[-6:]}")  # Use last 6 chars of ID as fallback
                    return [name]
            
            # For group DMs (is_mpim), get all members
            elif channel.get("is_mpim"):
                members = channel.get("members", [])
                names = []
                for user_id in members:
                    name = user_map.get(user_id, f"User_{user_id[-6:]}")
                    names.append(name)
                return names
                
    except Exception as e:
        print(f"⚠️  Could not get DM participant info: {e}")
    
    return []


def _create_conversation_filename(chan_name: str, chan_id: str, domain: str, cookie: str, crumb: str, token: str, user_map: Dict[str, str], missing_users: Dict[str, str] = None) -> str:
    """Create an appropriate filename for the conversation."""
    
    if missing_users is None:
        missing_users = {}
    
    # Check if this looks like a DM (starts with 'D' or is a user ID pattern)
    if chan_id.startswith('D') or chan_name.startswith('U'):
        # First, check if we have direct identification from missing_users
        if chan_name.startswith('U') and chan_name in missing_users:
            identified_name = missing_users[chan_name]
            if " (@" in identified_name:
                identified_name = identified_name.split(" (@")[0]
            safe_name = f"dm_with_{identified_name}_{chan_id[-6:]}"  # Add channel ID suffix to prevent conflicts
            return re.sub(r'[<>:"/\\|?*@]', '_', safe_name).strip('_')
        
        # Fallback to API-based participant detection
        participants = _get_dm_participants(chan_id, domain, cookie, crumb, token, user_map)
        
        if participants:
            # Clean up participant names for filenames
            clean_participants = []
            for participant in participants:
                # Extract just the name part if it has (@username) format
                if " (@" in participant:
                    name = participant.split(" (@")[0]
                else:
                    name = participant
                # Remove "Unknown_User_" prefix if present
                if name.startswith("Unknown_User_"):
                    name = name.replace("Unknown_User_", "User_")
                clean_participants.append(name)
            
            if len(clean_participants) == 1:
                # 1-on-1 DM - add channel ID suffix to prevent conflicts between different DM channels
                safe_name = f"dm_with_{clean_participants[0]}_{chan_id[-6:]}"
            else:
                # Group DM
                safe_name = f"group_dm_{'-'.join(clean_participants)}"
        else:
            # Fallback: check if we have the user ID as channel name and can resolve it
            if chan_name.startswith('U'):
                user_name = user_map.get(chan_name) or missing_users.get(chan_name)
                if user_name:
                    # Clean the name
                    if " (@" in user_name:
                        user_name = user_name.split(" (@")[0]
                    if user_name.startswith("Unknown_User_"):
                        user_name = user_name.replace("Unknown_User_", "User_")
                    safe_name = f"dm_with_{user_name}_{chan_id[-6:]}"
                else:
                    safe_name = f"dm_with_User_{chan_name[-6:]}_{chan_id[-6:]}"
            else:
                # For non-DM channels or when participant detection fails
                # Check if channel ID maps to a user in missing_users
                potential_user = missing_users.get(chan_id) or missing_users.get(chan_name)
                if potential_user:
                    if " (@" in potential_user:
                        potential_user = potential_user.split(" (@")[0]
                    safe_name = f"dm_with_{potential_user}_{chan_id[-6:]}"
                else:
                    safe_name = f"dm_{chan_id}"
    else:
        # Regular channel - use the channel name
        safe_name = chan_name
    
    # Make filename safe
    safe_name = re.sub(r'[<>:"/\\|?*@]', '_', safe_name)
    safe_name = re.sub(r'_{2,}', '_', safe_name)  # Replace multiple underscores with single
    safe_name = safe_name.strip('_')  # Remove leading/trailing underscores
    
    return safe_name


def _identify_unknown_user(user_id: str, messages: List[Dict[str, Any]], rolodex_data: Dict[str, Any]) -> Optional[str]:
    """Try to identify an unknown user by analyzing conversation context."""
    
    # Get all messages from this user
    user_messages = [msg for msg in messages if msg.get("user") == user_id]
    if not user_messages:
        return None
    
    # Extract text content from user's messages
    user_text = " ".join([msg.get("text", "") for msg in user_messages])
    
    # Look for email addresses in their messages
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails_found = re.findall(email_pattern, user_text, re.IGNORECASE)
    
    # Cross-reference with rolodex
    for person in rolodex_data.get("people", []):
        person_email = person.get("email", "")
        person_name = person.get("name", "")
        person_username = person.get("username", "")
        person_notes = person.get("notes", "")
        
        # Direct email match
        if person_email and person_email in emails_found:
            return f"{person_name} (@{person_username})" if person_username else person_name
        
        # Check if their email appears in the user's messages
        if person_email and person_email.lower() in user_text.lower():
            return f"{person_name} (@{person_username})" if person_username else person_name
        
        # Look for name mentions in the conversation
        if person_name and len(person_name.split()) >= 2:  # Only check full names
            first_name = person_name.split()[0]
            last_name = person_name.split()[-1]
            
            # Check if this user is mentioned by first name in other messages
            other_messages = [msg for msg in messages if msg.get("user") != user_id]
            other_text = " ".join([msg.get("text", "") for msg in other_messages])
            
            # Look for patterns like "thanks [first_name]", "@[first_name]", etc.
            name_patterns = [
                rf'\b{re.escape(first_name)}\b',
                rf'\b{re.escape(person_name)}\b',
                rf'@{re.escape(first_name)}\b',
            ]
            
            for pattern in name_patterns:
                if re.search(pattern, other_text, re.IGNORECASE):
                    # Additional confidence check: see if user responds after being mentioned
                    for i, msg in enumerate(messages):
                        if (msg.get("user") != user_id and 
                            re.search(pattern, msg.get("text", ""), re.IGNORECASE)):
                            # Check if our unknown user responds within next few messages
                            for j in range(i+1, min(i+4, len(messages))):
                                if messages[j].get("user") == user_id:
                                    return f"{person_name} (@{person_username})" if person_username else person_name
        
        # Check company domain patterns in conversation
        if person_email and "@" in person_email:
            domain = person_email.split("@")[1]
            if domain.lower() in user_text.lower():
                return f"{person_name} (@{person_username})" if person_username else person_name
        
        # Check company-specific keywords and role patterns
        company = person.get("company", "")
        role = person.get("role", "")
        
        # Sharma Brands patterns (marketing agency) - be more specific
        if company == "Sharma Brands":
            # Count keyword matches for confidence
            sharma_keywords = ["meta", "ads manager", "campaigns", "attribution", "google", "facebook", 
                             "pmax", "roas", "cpm", "cpc", "impressions", "scaling", "creative", "duplicate"]
            keyword_matches = sum(1 for keyword in sharma_keywords if keyword in user_text.lower())
            
            # Rahul-specific patterns (Google Campaign Manager)
            if person_name == "Rahul" and (
                "ads manager" in user_text.lower() or 
                ("google" in user_text.lower() and keyword_matches >= 2) or
                ("meta" in user_text.lower() and "campaigns" in user_text.lower())
            ):
                return f"{person_name} (@{person_username})" if person_username else person_name
            
            # Other Sharma Brands members - need different patterns
            elif person_name != "Rahul" and keyword_matches >= 2:
                return f"{person_name} (@{person_username})" if person_username else person_name
        
        # HigherDOSE patterns (client company)
        if company == "HigherDOSE" and any(keyword in user_text.lower() for keyword in [
            "internal", "product", "bundle", "red light", "sauna", "pemf", "brand", "internally"
        ]):
            return f"{person_name} (@{person_username})" if person_username else person_name
        
        # Role-based patterns
        if "campaign" in role.lower() and any(keyword in user_text.lower() for keyword in [
            "campaign", "ads", "performance", "testing", "scaling"
        ]):
            return f"{person_name} (@{person_username})" if person_username else person_name
    
    return None


def _enhance_user_identification(messages: List[Dict[str, Any]], user_map: Dict[str, str], missing_users: Dict[str, str]) -> None:
    """Enhance user identification by analyzing conversation context."""
    
    # Load rolodex for cross-reference
    rolodex = _load_rolodex()
    
    # Find all unknown users in this conversation
    unknown_user_ids = set()
    for msg in messages:
        user_id = msg.get("user", "")
        if user_id and user_id not in user_map and user_id not in missing_users:
            unknown_user_ids.add(user_id)
    
    # Try to identify each unknown user
    for user_id in unknown_user_ids:
        identified_name = _identify_unknown_user(user_id, messages, rolodex)
        if identified_name:
            missing_users[user_id] = identified_name
            print(f"🔍 Identified {user_id} as: {identified_name}")
            
            # Add to rolodex if we found a confident match
            if " (@" in identified_name:  # Has username, likely confident match
                name_part = identified_name.split(" (@")[0]
                username_part = identified_name.split(" (@")[1].rstrip(")")
                
                # Check if already exists
                existing = any(
                    person.get("user_id") == user_id or person.get("name") == name_part
                    for person in rolodex.get("people", [])
                )
                
                if not existing:
                    new_person = {
                        "name": name_part,
                        "username": username_part,
                        "user_id": user_id,
                        "role": "Team Member",
                        "company": "Unknown",
                        "email": None,
                        "notes": f"Identified from conversation analysis on {datetime.now().strftime('%Y-%m-%d')}"
                    }
                    rolodex["people"].append(new_person)
                    _save_rolodex(rolodex)
                    print(f"📝 Added {name_part} to rolodex based on conversation analysis")
        else:
            # Fallback to user-friendly unknown name
            missing_users[user_id] = f"Unknown_User_{user_id[-6:]}"


# -------------- Main ---------------------------------------------------------

def main() -> None:
    # Hardcoded HigherDose workspace details
    domain = "higherdosemanagement.slack.com"
    team_id = "TA97020CV"
    
    print(f"🔗 HigherDose Slack Fetcher")
    print(f"📍 Workspace: {domain}")
    print()

    cookie, crumb, token = _load_creds(team_id)

    # resolve channel names once
    print("Fetching channel list…")
    name_map = _channels_lookup(domain, cookie, crumb, token)
    print(f"→ {len(name_map)} conversations available")

    # Build user map once and update rolodex
    user_map = _build_user_map(domain, cookie, crumb, token)

    while True:
        user_input = input("Slack URL, channel name, or command ('list', 'refresh <channel>', 'q' to quit): ").strip()
        
        if user_input.lower() == "q":
            print("Bye 👋")
            break
            
        if user_input.lower() == "list":
            print(f"\nAvailable conversations ({len(name_map)}):")
            for name in sorted(name_map.keys())[:50]:  # Show first 50
                print(f"  {name}")
            if len(name_map) > 50:
                print(f"  ... and {len(name_map) - 50} more")
            print()
            continue
            
        if user_input.lower().startswith("refresh "):
            # Refresh mode: clear tracker and re-fetch entire conversation
            refresh_target = user_input[8:].strip().lstrip("#@")
            if refresh_target not in name_map:
                print("❌  Channel not found for refresh. Type 'list' to see available channels.")
                continue
            refresh_chan_id = name_map[refresh_target]
            tracker = _load_tracker()
            if refresh_chan_id in tracker["channels"]:
                del tracker["channels"][refresh_chan_id]
                _save_tracker(tracker)
                print(f"🔄 Cleared tracking for {refresh_target} - will re-fetch entire conversation")
            
            # Don't delete files during refresh - let the renaming logic handle it
            print("📁 Files will be renamed after processing if needed")
            
            # Now process it as a normal channel request
            user_input = refresh_target

        # Check if input is a Slack URL
        chan_id = None
        chan_name = None
        
        if "slack.com" in user_input:
            # Extract channel ID from URL patterns:
            # https://app.slack.com/client/TA97020CV/C123ABC
            # https://higherdosemanagement.slack.com/archives/C123ABC/p123456
            url_patterns = [
                r'/client/[^/]+/([A-Z0-9]+)',           # app.slack.com format
                r'/archives/([A-Z0-9]+)',               # permalink format
                r'channel=([A-Z0-9]+)',                 # query parameter
            ]
            for pattern in url_patterns:
                match = re.search(pattern, user_input)
                if match:
                    chan_id = match.group(1)
                    # Find the name for this ID (for nice filenames)
                    chan_name = next((name for name, cid in name_map.items() if cid == chan_id), chan_id)
                    break
            
            if not chan_id:
                print("❌  Couldn't extract channel ID from URL. Try copying the URL again.")
                continue
        else:
            # Treat as channel name
            chan_name = user_input.lstrip("#@")
            if chan_name not in name_map:
                print("❌  Channel not found. Type 'list' to see available channels.")
                continue
            chan_id = name_map[chan_name]

        print(f"📥 Fetching: {chan_name} ({chan_id})")

        tracker = _load_tracker()
        last_ts = tracker["channels"].get(chan_id, 0)

        # Fetch messages newer than last_ts
        print(f"🔍 Looking for messages newer than {last_ts}…")
        messages: List[Dict[str, Any]] = []
        cursor = None
        while True:
            payload = {
                "channel": chan_id,
                "limit": 1000,
                "oldest": last_ts,
                "inclusive": False,
            }
            if cursor:
                payload["cursor"] = cursor
            if token:
                payload["token"] = token
            resp = _api_post(domain, "conversations.history", cookie, crumb, payload)
            if not resp.get("ok"):
                err = resp.get("error", "unknown_error")
                sys.exit(f"Slack error: {err}")
            messages.extend(resp.get("messages", []))
            cursor = resp.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            time.sleep(0.5)

        # For each message, fetch replies if any
        full_msgs: List[Dict[str, Any]] = []
        for m in messages:
            full_msgs.append(m)
            if m.get("reply_count", 0):
                rep_cursor = None
                while True:
                    rep_payload = {
                        "channel": chan_id,
                        "ts": m["ts"],
                    }
                    if rep_cursor:
                        rep_payload["cursor"] = rep_cursor
                    if token:
                        rep_payload["token"] = token
                    r = _api_post(domain, "conversations.replies", cookie, crumb, rep_payload)
                    full_msgs.extend(r.get("messages", [])[1:])  # skip root
                    rep_cursor = r.get("response_metadata", {}).get("next_cursor")
                    if not rep_cursor:
                        break
                    time.sleep(0.3)

        if not full_msgs:
            print("📭 No new messages.")
            continue

        # Track missing users for consistent naming within this conversation
        missing_users: Dict[str, str] = {}
        
        # Enhance user identification by analyzing conversation context
        _enhance_user_identification(full_msgs, user_map, missing_users)
        
        # Use a safe filename (replace problematic characters) - AFTER user identification
        safe_name = _create_conversation_filename(chan_name, chan_id, domain, cookie, crumb, token, user_map, missing_users)
        md_path = EXPORT_DIR / f"{safe_name}.md"
        
        # Check if we need to rename from old filename format
        old_safe_name = re.sub(r'[<>:"/\\|?*]', '_', chan_name)
        old_md_path = EXPORT_DIR / f"{old_safe_name}.md"
        
        if old_md_path.exists() and old_md_path != md_path:
            print(f"🔄 Renaming {old_md_path.name} → {md_path.name}")
            if md_path.exists():
                md_path.unlink()  # Remove new file if it exists
            old_md_path.rename(md_path)  # Rename old file to new name
        
        with md_path.open("a", encoding="utf-8") as f:
            for msg in sorted(full_msgs, key=lambda x: float(x["ts"])):
                f.write(_markdown_line(msg, user_map, missing_users) + "\n")

        # Update tracker
        highest_ts = max(float(m["ts"]) for m in full_msgs)
        tracker["channels"][chan_id] = highest_ts
        _save_tracker(tracker)

        print(f"✅  Added {len(full_msgs)} messages to {md_path}")
        print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted. Bye!") 