import sys
import time
import email
import pickle
import base64
import re
from pathlib import Path
from email.utils import parsedate_to_datetime
from email.header import decode_header

# Add project root to path to allow absolute imports from 'utils'
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import markdownify
import google.auth.transport.requests
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.logs import report
from utils.style import clean
from utils.style import ansi

logger = report.settings(__file__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def clean_subject(subject):
    """Clean and decode email subject lines."""
    # Decode any encoded subject lines
    decoded_parts = decode_header(subject)
    decoded_subject = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_subject += part.decode(encoding or 'utf-8', errors='ignore')
        else:
            decoded_subject += part
    
    # Remove any remaining odd encoding artifacts
    decoded_subject = re.sub(r'utf-8[a-zA-Z0-9]*', '', decoded_subject)
    return decoded_subject.strip()

def clean_email_content(content):
    """Clean up email content by removing tracking pixels, normalizing whitespace, and shortening URLs."""
    if not content:
        return content
    
    # Remove invisible/zero-width characters commonly used for tracking
    # These include zero-width space, zero-width non-joiner, zero-width joiner, etc.
    invisible_chars = [
        '\u200B',  # Zero-width space
        '\u200C',  # Zero-width non-joiner  
        '\u200D',  # Zero-width joiner
        '\u2060',  # Word joiner
        '\uFEFF',  # Zero-width non-breaking space
        '͏',       # Combining grapheme joiner (common in email tracking)
        '‌',       # Zero-width non-joiner (another variant)
    ]
    
    for char in invisible_chars:
        content = content.replace(char, '')
    
    # Clean up excessive whitespace patterns
    # Replace multiple consecutive spaces with single space
    content = re.sub(r' {3,}', ' ', content)
    
    # Replace multiple consecutive line breaks with double line breaks (paragraph spacing)
    content = re.sub(r'\n{4,}', '\n\n', content)
    
    # Clean up lines that are just whitespace
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        # If line is just whitespace, replace with empty line
        if line.strip() == '':
            cleaned_lines.append('')
        else:
            cleaned_lines.append(line.strip())
    
    # Rejoin and normalize paragraph spacing
    content = '\n'.join(cleaned_lines)
    
    # Remove excessive line breaks at start/end
    content = content.strip()
    
    # Shorten extremely long URLs (optional)
    def shorten_url(match):
        url = match.group(0)
        if len(url) > 100:
            # Extract domain for readability
            domain_match = re.search(r'https?://([^/]+)', url)
            if domain_match:
                domain = domain_match.group(1)
                return f"[Long URL: {domain}...]({url})"
        return url
    
    # Apply URL shortening to very long URLs
    content = re.sub(r'https?://[^\s)]{100,}', shorten_url, content)
    
    return content
TOKEN   = Path("mail", "token.pickle")
CURSOR  = Path("mail", "cursor.txt")
OUTDIR  = Path("mail", "archive")
OUTDIR.mkdir(exist_ok=True)

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

def latest_history_id(gmail):
    """Fetches the latest history ID from Gmail."""
    logger.info("Fetching latest history ID from Gmail...")
    print(f"{ansi.magenta}Fetching{ansi.reset} latest history ID from Gmail...")
    prof = gmail.users().getProfile(userId="me").execute()
    history_id = prof["historyId"]
    logger.info("Latest history ID is %s", history_id)
    print(f"  Latest history ID is {ansi.green}{history_id}{ansi.reset}")
    return history_id

def fetch_deltas(gmail, start):
    """Fetches new messages since a given history ID."""
    logger.info("Fetching message deltas since history ID: %s", start)
    print(f"{ansi.magenta}Fetching{ansi.reset} message deltas since history ID: {ansi.cyan}{start}{ansi.reset}")
    page = gmail.users().history().list(
        userId="me", startHistoryId=start, historyTypes=["messageAdded"]
    ).execute()
    messages = []
    for h in page.get("history", []):
        messages.extend(m["id"] for m in h.get("messages", []))

    new_history_id = page.get("historyId")
    logger.info("Found %d new messages. New history ID: %s", len(messages), new_history_id)
    print(f"  Found {ansi.green}{len(messages)}{ansi.reset} new messages. New history ID: {ansi.cyan}{new_history_id or 'N/A'}{ansi.reset}")
    return messages, page.get("historyId")

def save_msg(gmail, mid):
    """Saves a single email message to a structured markdown file."""
    logger.info("Saving message with ID: %s", mid)
    raw = gmail.users().messages().get(userId="me", id=mid, format="raw").execute()["raw"]
    mime = email.message_from_bytes(base64.urlsafe_b64decode(raw))

        # Extract email metadata
    subject = clean_subject(mime.get('Subject', 'No Subject'))
    from_addr = mime.get('From', 'No From')
    to_addr = mime.get('To', 'No To')
    date_str = mime.get('Date', 'No Date')
    
    # Extract body content - prefer plain text over HTML
    text_parts = []
    html_parts = []
    
    for part in mime.walk():
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if payload:
                text_parts.append(payload.decode(errors="ignore"))
        elif part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if payload:
                html_parts.append(payload.decode(errors="ignore"))
    
    # Prefer plain text, fall back to HTML if needed
    if text_parts:
        raw_content = "\n\n".join(text_parts)
        body_content = clean_email_content(raw_content)
    elif html_parts:
        # Only use markdownify if we actually have HTML content
        html_content = "\n\n".join(html_parts)
        markdown_content = markdownify.markdownify(html_content)
        body_content = clean_email_content(markdown_content)
    else:
        body_content = "No body content found."

    # Create structured markdown content
    structured_content = f"""## Date

{date_str}

## Address

from: {from_addr}
to: {to_addr}

## Subject

{subject}

## Body

{body_content.strip()}
"""

    # Parse email date using RFC 2822 parser (handles all email date formats)
    chronodate = parsedate_to_datetime(date_str).strftime("%Y%m%d")
    filename = f"{chronodate}-{clean.up(subject)}-{mid}.md"
    output_path = OUTDIR / filename

    output_path.write_text(structured_content, encoding="utf-8")
    logger.info("Message saved to %s", output_path)

def main():
    """Runs the Gmail archiving script."""
    logger.info("Starting Gmail archive script.")
    print("Starting Gmail archive script...")

    gmail = build("gmail", "v1", credentials=get_creds(), cache_discovery=False)
    logger.info("Gmail service client created successfully.")
    print(f"Gmail service client {ansi.green}created successfully{ansi.reset}.")

    if not CURSOR.exists():
        logger.warning("Cursor file not found at %s. Creating a new one.", CURSOR)
        print(f"{ansi.yellow}Cursor file not found{ansi.reset} at {ansi.cyan}{CURSOR}{ansi.reset}. Creating a new one.")
        initial_cursor = latest_history_id(gmail)
        CURSOR.write_text(str(initial_cursor), encoding='utf-8')
        logger.info("Cursor file created with history ID: %s", initial_cursor)
        print(f"  Cursor file {ansi.green}created{ansi.reset} with history ID: {ansi.cyan}{initial_cursor}{ansi.reset}")

    cursor = CURSOR.read_text(encoding='utf-8').strip()
    logger.info("Starting with cursor: %s", cursor)
    print(f"Starting with cursor: {ansi.cyan}{cursor}{ansi.reset}")

    while True:
        try:
            logger.info("Checking for new messages...")
            print(f"\n{ansi.magenta}Checking for new messages...{ansi.reset}")
            message_ids, new_cursor = fetch_deltas(gmail, cursor)

            if message_ids:
                logger.info("Found %d new messages to archive.", len(message_ids))
                print(f"Found {ansi.green}{len(message_ids)}{ansi.reset} new messages to archive.")
                for i, mid in enumerate(message_ids):
                    print(f"  {ansi.magenta}Processing {i+1}{ansi.reset}/{ansi.green}{len(message_ids)}{ansi.reset}: {mid}")
                    save_msg(gmail, mid)
            else:
                logger.info("No new messages found.")
                print("No new messages found.")

            if new_cursor and new_cursor != cursor:
                logger.info("Updating cursor from %s to %s", cursor, new_cursor)
                print(f"  Updating cursor from {ansi.yellow}{cursor}{ansi.reset} to {ansi.green}{new_cursor}{ansi.reset}")
                cursor = new_cursor
                CURSOR.write_text(str(cursor), encoding='utf-8')

        except HttpError as e:
            logger.error("An HTTP error occurred: %s", e)
            print(f"{ansi.red}An HTTP error occurred:{ansi.reset} {e}")
            if e.resp.status == 404:
                logger.warning("History ID is too old; performing a full resync.")
                print(f"  {ansi.yellow}History ID is too old; performing a full resync.{ansi.reset}")
                cursor = latest_history_id(gmail)

        logger.info("Waiting for 30 seconds before next check...")
        print(f"Waiting for {ansi.yellow}30 seconds{ansi.reset} before next check...")
        time.sleep(30)

if __name__ == "__main__":
    main()
