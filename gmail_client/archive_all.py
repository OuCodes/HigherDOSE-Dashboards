from pathlib import Path
import sys
import time

# Add project root to path to allow absolute imports from 'utils'
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Reuse components from the existing script
from gmail_client.gmail_archive import get_creds, save_msg, ansi, logger

def fetch_all_message_ids(gmail):
    """Fetches all message IDs from the user's Gmail account."""
    logger.info("Fetching all message IDs...")
    print(f"{ansi.magenta}Fetching all message IDs...{ansi.reset}")

    messages = []
    page_token = None
    page_num = 0
    while True:
        try:
            page_num += 1
            response = gmail.users().messages().list(
                userId='me',
                pageToken=page_token
            ).execute()

            message_batch = response.get('messages', [])
            if message_batch:
                messages.extend(message_batch)
                print(f"  Page {ansi.cyan}{page_num}{ansi.reset}: Found {ansi.green}{len(message_batch)}{ansi.reset} messages. Total: {ansi.green}{len(messages)}{ansi.reset}")

            page_token = response.get('nextPageToken')
            if not page_token:
                break
        except HttpError as e:
            logger.error("An HTTP error occurred during message list fetch: %s", e)
            print(f"{ansi.red}An HTTP error occurred during message list fetch:{ansi.reset} {e}")
            break

    logger.info("Total messages found: %d", len(messages))
    print(f"Total messages found: {ansi.green}{len(messages)}{ansi.reset}")
    return [msg['id'] for msg in messages]

def main():
    """Runs the full Gmail archiving script."""
    logger.info("Starting full Gmail archive script.")
    print("Starting full Gmail archive script...")

    gmail = build("gmail", "v1", credentials=get_creds(), cache_discovery=False)
    logger.info("Gmail service client created successfully.")
    print(f"Gmail service client {ansi.green}created successfully{ansi.reset}.")

    message_ids = fetch_all_message_ids(gmail)

    if message_ids:
        total = len(message_ids)
        logger.info("Found %d total messages to archive.", total)
        print(f"Found {ansi.green}{total}{ansi.reset} total messages to archive.")
        
        for i, mid in enumerate(message_ids):
            print(f"  {ansi.magenta}Processing {i+1}{ansi.reset}/{ansi.green}{total}{ansi.reset}: {mid}")
            try:
                save_msg(gmail, mid)
            except HttpError as e:
                logger.error("Could not process message %s: %s", mid, e)
                print(f"  {ansi.red}Could not process message {mid}:{ansi.reset} {e}")
            # Be a good API citizen; avoid hitting rate limits.
            time.sleep(0.05)
    else:
        logger.info("No messages found to archive.")
        print("No messages found.")

    logger.info("Full archive complete.")
    print(f"\n{ansi.green}Full archive complete.{ansi.reset}")

if __name__ == "__main__":
    main()
