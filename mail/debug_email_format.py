from pathlib import Path
import base64, email, pickle
import sys
import json

# Add project root to path to allow absolute imports from 'utils'
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import markdownify
import google.auth.transport.requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from utils.logs import report
from utils.style import ansi

logger = report.settings(__file__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
TOKEN   = Path("mail", "token.pickle")
DEBUG_OUTDIR = Path("mail", "debug")
DEBUG_OUTDIR.mkdir(exist_ok=True)

def get_creds():
    """Authenticates with Google and returns credentials."""
    logger.info("Authenticating with Google...")
    print(f"{ansi.magenta}Authenticating{ansi.reset} with Google...")
    if TOKEN.exists():
        logger.info("Token file found at %s", TOKEN)
        print(f"  Token file found at {ansi.cyan}{TOKEN}{ansi.reset}")
        creds = pickle.loads(TOKEN.read_bytes())
        if creds.expired and creds.refresh_token:
            logger.info("Token expired, refreshing...")
            print(f"  Token {ansi.yellow}expired{ansi.reset}, refreshing...")
            creds.refresh(google.auth.transport.requests.Request())
            TOKEN.write_bytes(pickle.dumps(creds))
            logger.info("Token refreshed successfully.")
            print(f"  Token refreshed {ansi.green}successfully{ansi.reset}.")
        else:
            logger.info("Token is valid.")
            print(f"  Token is {ansi.green}valid{ansi.reset}.")
        return creds

    # Attempt to locate the downloaded OAuth client secret JSON
    logger.warning("No token file found, starting OAuth flow...")
    print(f"  {ansi.yellow}No token file found{ansi.reset}, starting OAuth flow...")
    secret_files = list(Path(__file__).resolve().parent.glob("client_secret_*.json"))

    client_secrets_file = str(secret_files[0])
    logger.info("Using client secrets file: %s", client_secrets_file)
    print(f"  Using client secrets file: {ansi.cyan}{client_secrets_file}{ansi.reset}")
    flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN.write_bytes(pickle.dumps(creds))
    logger.info("Token created and saved to %s", TOKEN)
    print(f"  Token {ansi.green}created{ansi.reset} and saved to {ansi.cyan}{TOKEN}{ansi.reset}")
    return creds

def debug_email_formats(gmail, mid):
    """Debug function to show email at different processing stages."""
    print(f"\n{ansi.cyan}=== DEBUGGING EMAIL ID: {mid} ==={ansi.reset}")
    
    # Stage 1: Raw Gmail API response (base64 encoded)
    print(f"\n{ansi.yellow}Stage 1: Raw Gmail API Response{ansi.reset}")
    raw_response = gmail.users().messages().get(userId="me", id=mid, format="raw").execute()
    raw_data = raw_response["raw"]
    print(f"Raw data type: {type(raw_data)}")
    print(f"Raw data length: {len(raw_data)} characters")
    print(f"First 200 chars: {raw_data[:200]}...")
    
    # Save raw data
    raw_file = DEBUG_OUTDIR / f"{mid}_1_raw.txt"
    raw_file.write_text(raw_data, encoding="utf-8")
    print(f"Saved to: {raw_file}")
    
    # Stage 2: Base64 decoded bytes
    print(f"\n{ansi.yellow}Stage 2: Base64 Decoded Bytes{ansi.reset}")
    decoded_bytes = base64.urlsafe_b64decode(raw_data)
    print(f"Decoded bytes length: {len(decoded_bytes)} bytes")
    print(f"First 500 chars: {decoded_bytes[:500].decode(errors='ignore')}")
    
    # Save decoded bytes
    decoded_file = DEBUG_OUTDIR / f"{mid}_2_decoded.txt"
    decoded_file.write_bytes(decoded_bytes)
    print(f"Saved to: {decoded_file}")
    
    # Stage 3: Parsed MIME message
    print(f"\n{ansi.yellow}Stage 3: Parsed MIME Message{ansi.reset}")
    mime_msg = email.message_from_bytes(decoded_bytes)
    print(f"Message type: {type(mime_msg)}")
    print(f"Subject: {mime_msg.get('Subject', 'No Subject')}")
    print(f"From: {mime_msg.get('From', 'No From')}")
    print(f"To: {mime_msg.get('To', 'No To')}")
    print(f"Date: {mime_msg.get('Date', 'No Date')}")
    print(f"Content-Type: {mime_msg.get_content_type()}")
    print(f"Is multipart: {mime_msg.is_multipart()}")
    
    # Save MIME headers and structure
    mime_info = {
        "headers": dict(mime_msg.items()),
        "content_type": mime_msg.get_content_type(),
        "is_multipart": mime_msg.is_multipart(),
        "parts": []
    }
    
    print(f"\n{ansi.yellow}MIME Parts Analysis:{ansi.reset}")
    for i, part in enumerate(mime_msg.walk()):
        part_info = {
            "part_number": i,
            "content_type": part.get_content_type(),
            "charset": part.get_content_charset(),
            "content_disposition": part.get('Content-Disposition'),
            "filename": part.get_filename()
        }
        mime_info["parts"].append(part_info)
        print(f"  Part {i}: {part.get_content_type()}")
        if part.get_filename():
            print(f"    Filename: {part.get_filename()}")
    
    mime_file = DEBUG_OUTDIR / f"{mid}_3_mime_info.json"
    mime_file.write_text(json.dumps(mime_info, indent=2), encoding="utf-8")
    print(f"Saved MIME info to: {mime_file}")
    
    # Stage 4: Extracted body content (before markdown conversion)
    print(f"\n{ansi.yellow}Stage 4: Extracted Body Content{ansi.reset}")
    body_parts = []
    for part in mime_msg.walk():
        if part.get_content_type() in ("text/html", "text/plain"):
            try:
                payload = part.get_payload(decode=True)
                if payload:
                    content = payload.decode(errors="ignore")
                    body_parts.append({
                        "content_type": part.get_content_type(),
                        "charset": part.get_content_charset(),
                        "content": content
                    })
                    print(f"Found {part.get_content_type()} part:")
                    print(f"  Charset: {part.get_content_charset()}")
                    print(f"  Length: {len(content)} characters")
                    print(f"  First 300 chars: {content[:300]}")
                    print(f"  Last 100 chars: {content[-100:]}")
                    
                    # Save this body part
                    body_file = DEBUG_OUTDIR / f"{mid}_4_body_{part.get_content_type().replace('/', '_')}.txt"
                    body_file.write_text(content, encoding="utf-8")
                    print(f"  Saved to: {body_file}")
            except Exception as e:
                print(f"  Error extracting part: {e}")
    
    # Stage 5: What the original script would extract
    print(f"\n{ansi.yellow}Stage 5: Original Script Extraction{ansi.reset}")
    original_body = next(
        (p.get_payload(decode=True) for p in mime_msg.walk()
         if p.get_content_type() in ("text/html", "text/plain")), b""
    )
    if original_body:
        original_content = original_body.decode(errors="ignore")
        print(f"Original script would extract: {len(original_content)} characters")
        print(f"First 300 chars: {original_content[:300]}")
        
        original_file = DEBUG_OUTDIR / f"{mid}_5_original_extraction.txt"
        original_file.write_text(original_content, encoding="utf-8")
        print(f"Saved to: {original_file}")
        
        # Stage 6: Final markdown conversion
        print(f"\n{ansi.yellow}Stage 6: Markdown Conversion{ansi.reset}")
        md_content = markdownify.markdownify(original_content)
        print(f"Markdown length: {len(md_content)} characters")
        print(f"First 300 chars: {md_content[:300]}")
        
        md_file = DEBUG_OUTDIR / f"{mid}_6_final_markdown.md"
        md_file.write_text(md_content, encoding="utf-8")
        print(f"Saved to: {md_file}")
    else:
        print("No body content found!")
    
    print(f"\n{ansi.green}=== DEBUG COMPLETE FOR {mid} ==={ansi.reset}")

def get_recent_messages(gmail, count=5):
    """Get a few recent messages for debugging."""
    print(f"{ansi.magenta}Fetching recent messages for debugging...{ansi.reset}")
    results = gmail.users().messages().list(userId="me", maxResults=count).execute()
    messages = results.get('messages', [])
    print(f"Found {len(messages)} recent messages")
    return [msg['id'] for msg in messages]

def main():
    """Debug version of the Gmail script."""
    print("Starting Gmail Debug Script...")
    print(f"Debug files will be saved to: {DEBUG_OUTDIR}")
    
    gmail = build("gmail", "v1", credentials=get_creds(), cache_discovery=False)
    print(f"Gmail service client {ansi.green}created successfully{ansi.reset}.")
    
    # Get a few recent messages to debug
    message_ids = get_recent_messages(gmail, 3)
    
    for i, mid in enumerate(message_ids):
        print(f"\n{ansi.cyan}Processing message {i+1}/{len(message_ids)}{ansi.reset}")
        debug_email_formats(gmail, mid)
        if i < len(message_ids) - 1:
            input(f"\n{ansi.yellow}Press Enter to continue to next message...{ansi.reset}")
    
    print(f"\n{ansi.green}Debug complete! Check the files in {DEBUG_OUTDIR} to see email formats.{ansi.reset}")

if __name__ == "__main__":
    main() 