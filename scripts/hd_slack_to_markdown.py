#!/usr/bin/env python3
"""
This script converts a Slack JSON export to markdown format.

It handles:
- User mentions
- Channel mentions
- Links
- Bold, italic, and strikethrough formatting
"""

import re
import os
import json
from datetime import datetime
from typing import Dict, List, Set
from higherdose.utils.logs import report
from higherdose.utils.style import ansi
from higherdose.slack.track_conversions import is_file_converted, mark_file_converted, print_conversion_status

# Initialize logging
logger = report.settings(__file__)

def load_slack_data(file_path: str) -> dict:
    """Load Slack JSON export data."""
    logger.info("Loading Slack data from %s", file_path)
    print(f"Loading Slack data from: {ansi.cyan}{file_path}{ansi.reset}")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        message_count = len(data.get('history', {}).get('messages', []))
        logger.info("Successfully loaded Slack data with %d messages", message_count)
        print(f"Successfully loaded Slack data with {ansi.green}{message_count}{ansi.reset} messages")
        return data
    except Exception as e:
        logger.error("Failed to load Slack data from %s: %s", file_path, str(e))
        print(f"{ansi.red}Failed{ansi.reset} to load Slack data from {file_path}: {str(e)}")
        raise

def create_user_map(users: List[dict]) -> Dict[str, str]:
    """Create a mapping of user IDs to display names."""
    user_map = {}
    for user in users:
        user_id = user['id']
        # Prefer display_name, fall back to real_name, then to username
        display_name = (
            user.get('profile', {}).get('display_name') or
            user.get('profile', {}).get('real_name') or
            user.get('name', 'Unknown User')
        )
        user_map[user_id] = display_name
    return user_map

def get_channel_info(data: dict, user_map: Dict[str, str]) -> tuple:
    """Extract channel information from Slack data."""
    # Check if it's a channel or DM
    if 'channel' in data:
        channel = data['channel']
        channel_name = channel.get('name', 'unknown_channel')
        channel_type = 'channel'
    elif 'im' in data:
        # It's a direct message
        im = data['im']
        channel_type = 'dm'

        # Check if there's a meaningful name for this IM
        im_name = im.get('name', '').strip()
        if im_name and im_name not in ['', 'Unknown', 'unknown']:
            # Use the provided IM name
            channel_name = im_name
        else:
            # No meaningful name, create one from participants
            messages = data.get('history', {}).get('messages', [])
            participants = set()
            for message in messages:
                if message.get('user'):
                    participants.add(message.get('user'))

            # Create readable channel name from participants
            participant_names = []
            for user_id in sorted(participants):  # Sort for consistent naming
                username = user_map.get(user_id, user_id)
                # Clean username (remove spaces, convert to lowercase)
                clean_name = username.lower().replace(' ', '_')
                participant_names.append(clean_name)

            if participant_names:
                channel_name = f"dm_{'_'.join(participant_names)}"
            else:
                channel_name = f"dm_{im.get('id', 'unknown_dm')}"
    else:
        # Fallback - could be a group DM or other type
        # Check if there's any name available
        name = data.get('name', '').strip()
        if name and name not in ['', 'Unknown', 'unknown']:
            channel_name = name
            channel_type = 'group'
        else:
            # Create name from participants as fallback
            messages = data.get('history', {}).get('messages', [])
            participants = set()
            for message in messages:
                if message.get('user'):
                    participants.add(message.get('user'))

            if participants:
                participant_names = []
                for user_id in sorted(participants):
                    username = user_map.get(user_id, user_id)
                    clean_name = username.lower().replace(' ', '_')
                    participant_names.append(clean_name)
                channel_name = f"group_{'_'.join(participant_names)}"
                channel_type = 'group'
            else:
                channel_name = 'unknown_channel'
                channel_type = 'unknown'

    return channel_name, channel_type

def extract_existing_timestamps(file_path: str) -> Set[str]:
    """Extract timestamps from existing markdown file to avoid duplicates."""
    timestamps = set()

    if not os.path.exists(file_path):
        return timestamps

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Look for timestamp patterns in the format: (2025-07-10 17:39:04)
        timestamp_pattern = r'\((\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\)'
        matches = re.findall(timestamp_pattern, content)

        for match in matches:
            # Convert back to timestamp format for comparison
            dt = datetime.strptime(match, '%Y-%m-%d %H:%M:%S')
            timestamps.add(str(dt.timestamp()))

    except (IOError, OSError) as e:
        print(f"Warning: Could not read existing file {file_path}: {e}")
    except UnicodeDecodeError as e:
        print(f"Warning: File {file_path} has invalid encoding: {e}")

    return timestamps

def timestamp_to_datetime(ts: str) -> datetime:
    """Convert Slack timestamp to datetime object."""
    return datetime.fromtimestamp(float(ts))

def clean_slack_formatting(text: str) -> str:
    """Clean up Slack-specific formatting and convert to markdown."""
    if not text:
        return ""

    # Convert user mentions <@U123456> to @username (will be handled later)
    text = re.sub(r'<@([^>]+)>', r'@\1', text)

    # Convert channel mentions <#C123456|channel-name> to #channel-name
    text = re.sub(r'<#[^|]+\|([^>]+)>', r'#\1', text)

    # Convert links <https://example.com|text> to [text](https://example.com)
    text = re.sub(r'<([^|]+)\|([^>]+)>', r'[\2](\1)', text)

    # Convert simple links <https://example.com> to [https://example.com](https://example.com)
    text = re.sub(r'<(https?://[^>]+)>', r'[\1](\1)', text)

    # Convert bold *text* to **text**
    text = re.sub(r'\*([^*]+)\*', r'**\1**', text)

    # Convert italic _text_ to *text*
    text = re.sub(r'_([^_]+)_', r'*\1*', text)

    # Convert code `text` (keep as is)
    # Convert strikethrough ~text~ to ~~text~~
    text = re.sub(r'~([^~]+)~', r'~~\1~~', text)

    return text

def extract_text_from_blocks(blocks: List[dict]) -> str:
    """Extract plain text from Slack's rich text blocks."""
    text_parts = []

    for block in blocks:
        if block.get('type') == 'rich_text':
            elements = block.get('elements', [])
            for element in elements:
                if element.get('type') == 'rich_text_section':
                    section_elements = element.get('elements', [])
                    for section_element in section_elements:
                        if section_element.get('type') == 'text':
                            text_parts.append(section_element.get('text', ''))
                        elif section_element.get('type') == 'user':
                            text_parts.append(f"<@{section_element.get('user_id', '')}>")
                        elif section_element.get('type') == 'link':
                            url = section_element.get('url', '')
                            text = section_element.get('text', url)
                            text_parts.append(f"<{url}|{text}>")
                elif element.get('type') == 'rich_text_list':
                    # Handle bullet points and numbered lists
                    list_items = element.get('elements', [])
                    for item in list_items:
                        if item.get('type') == 'rich_text_section':
                            item_elements = item.get('elements', [])
                            item_text = ''
                            for item_element in item_elements:
                                if item_element.get('type') == 'text':
                                    item_text += item_element.get('text', '')
                                elif item_element.get('type') == 'user':
                                    item_text += f"<@{item_element.get('user_id', '')}>"
                                elif item_element.get('type') == 'link':
                                    url = item_element.get('url', '')
                                    text = item_element.get('text', url)
                                    item_text += f"<{url}|{text}>"
                            text_parts.append(f"• {item_text}")

    return '\n'.join(text_parts)

def replace_user_mentions(text: str, user_map: Dict[str, str]) -> str:
    """Replace user ID mentions with actual usernames."""
    def replace_mention(match):
        user_id = match.group(1)
        return f"@{user_map.get(user_id, user_id)}"

    return re.sub(r'@([A-Z0-9]+)', replace_mention, text)

def format_message(message: dict, user_map: Dict[str, str], thread_level: int = 0) -> str:
    """Format a single message as markdown."""
    # Skip bot messages and system messages
    if message.get('subtype') in ['bot_message', 'channel_join', 'channel_leave']:
        return ""

    user_id = message.get('user', '')
    username = user_map.get(user_id, 'Unknown User')

    # Convert timestamp
    timestamp = timestamp_to_datetime(message.get('ts', '0'))
    date_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')

    # Get message text
    text = message.get('text', '')

    # If text is empty, try to extract from blocks
    if not text and message.get('blocks'):
        text = extract_text_from_blocks(message.get('blocks', []))

    # Clean and format the text
    text = clean_slack_formatting(text)
    text = replace_user_mentions(text, user_map)

    # Skip empty messages
    if not text.strip():
        return ""

    # Format with appropriate indentation for threads
    indent = "  " * thread_level

    # Format the message
    formatted_message = f"{indent}**{username}** ({date_str}):\n"

    # Add the message text with proper indentation
    text_lines = text.split('\n')
    for line in text_lines:
        formatted_message += f"{indent}{line}\n"

    formatted_message += "\n"

    return formatted_message

def create_export_metadata(data: dict, new_messages_count: int, total_messages: int) -> str:
    """Create metadata header for the export."""
    now = datetime.now()
    export_time = now.strftime('%Y-%m-%d %H:%M:%S')

    # Get date range of messages
    messages = data.get('history', {}).get('messages', [])
    if messages:
        timestamps = [float(msg.get('ts', '0')) for msg in messages]
        oldest = datetime.fromtimestamp(min(timestamps)).strftime('%Y-%m-%d')
        newest = datetime.fromtimestamp(max(timestamps)).strftime('%Y-%m-%d')
        date_range = f"{oldest} to {newest}"
    else:
        date_range = "No messages"

    metadata = f"""<!-- Export Metadata -->
<!-- Last updated: {export_time} -->
<!-- Message date range: {date_range} -->
<!-- New messages added: {new_messages_count} -->
<!-- Total messages: {total_messages} -->

"""
    return metadata

def extract_messages_to_markdown(json_file_path: str):
    """Extract messages from Slack JSON and save as organized markdown with deduplication."""
    logger.info("Starting Slack to markdown conversion for %s", json_file_path)
    print(f"Starting Slack to markdown conversion for: {ansi.cyan}{json_file_path}{ansi.reset}")

    # Check if file has already been converted
    if is_file_converted(json_file_path):
        logger.info("File %s has already been converted, skipping", json_file_path)
        print(f"{ansi.yellow}File has already been converted, skipping.{ansi.reset}")
        return None

    # Load the data
    data = load_slack_data(json_file_path)

    # Create user mapping
    user_map = create_user_map(data.get('users', []))

    # Get channel info
    channel_name, channel_type = get_channel_info(data, user_map)
    logger.info("Processing %s: %s", channel_type, channel_name)
    print(f"Processing {ansi.magenta}{channel_type}{ansi.reset}: {ansi.cyan}{channel_name}{ansi.reset}")

    # Create directory structure in the processed folder
    base_dir = "data/processed/slack"
    channel_dir = os.path.join(base_dir, channel_name)
    os.makedirs(channel_dir, exist_ok=True)

    # Create output file path using channel name
    # Clean the channel name for filename (remove special characters)
    safe_filename = re.sub(r'[<>:"/\\|?*]', '_', channel_name)
    output_file = os.path.join(channel_dir, f"{safe_filename}.md")

    # Get existing timestamps to avoid duplicates
    existing_timestamps = extract_existing_timestamps(output_file)
    logger.info("Found %d existing messages in output file", len(existing_timestamps))
    print(f"Found {ansi.yellow}{len(existing_timestamps)}{ansi.reset} existing messages in output file")

    # Get messages and filter out duplicates
    messages = data.get('history', {}).get('messages', [])
    new_messages = []

    for message in messages:
        # Extract the fractional part for more precise comparison
        msg_ts = message.get('ts', '0')
        if msg_ts not in existing_timestamps:
            new_messages.append(message)

    # Sort messages by timestamp (oldest first)
    new_messages.sort(key=lambda x: float(x.get('ts', '0')))

    # Format new messages
    new_content = ""
    for message in new_messages:
        formatted_message = format_message(message, user_map)
        if formatted_message:
            new_content += formatted_message

    # Handle file creation or appending
    if os.path.exists(output_file):
        # File exists, append new messages
        if new_messages:
            with open(output_file, 'r', encoding='utf-8') as f:
                existing_content = f.read()

            # Update metadata
            total_messages = len(existing_timestamps) + len(new_messages)
            metadata = create_export_metadata(data, len(new_messages), total_messages)

            # Remove old metadata and add new
            pattern = r'<!-- Export Metadata -->.*?<!-- Total messages: \d+ -->\n\n'
            content_without_metadata = re.sub(pattern, '', existing_content, flags=re.DOTALL)

            # Write updated file
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(metadata)
                f.write(content_without_metadata)
                if new_content:
                    f.write("---\n\n")
                    f.write(new_content)

            logger.info("Added %d new messages to existing file", len(new_messages))
            print(f"Added {ansi.green}{len(new_messages)}{ansi.reset} new messages to existing file.")
        else:
            logger.info("No new messages to add")
            print(f"{ansi.yellow}No new messages to add.{ansi.reset}")
    else:
        # File doesn't exist, create new
        if new_messages:
            metadata = create_export_metadata(data, len(new_messages), len(new_messages))

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(metadata)
                # Create a more readable title based on channel type
                if channel_type == 'dm':
                    if channel_name.startswith('dm_'):
                        # Extract participant names from channel_name (remove dm_ prefix)
                        participants = channel_name.replace('dm_', '').replace('_', ' & ').title()
                        f.write(f"# Direct Message: {participants}\n\n")
                    else:
                        # Use the actual channel name
                        f.write(f"# Direct Message: {channel_name}\n\n")
                elif channel_type == 'group':
                    if channel_name.startswith('group_'):
                        # Extract participant names from channel_name (remove group_ prefix)
                        participants = channel_name.replace('group_', '').replace('_', ', ').title()
                        f.write(f"# Group Chat: {participants}\n\n")
                    else:
                        # Use the actual channel name
                        f.write(f"# Group Chat: {channel_name}\n\n")
                else:
                    # Regular channel
                    f.write(f"# Slack {channel_type.title()}: {channel_name}\n\n")
                f.write(new_content)

            logger.info("Created new file with %d messages", len(new_messages))
            print(f"Created new file with {ansi.green}{len(new_messages)}{ansi.reset} messages.")
        else:
            logger.warning("No messages to process")
            print(f"{ansi.yellow}No messages to process.{ansi.reset}")

    # Mark file as converted if we processed any messages
    if messages:
        mark_file_converted(json_file_path, output_file, len(messages))
    
    logger.info("Conversion completed. Output saved to: %s", output_file)
    print(f"Output saved to: {ansi.cyan}{output_file}{ansi.reset}")
    return output_file

def process_all_slack_exports():
    """Process all JSON files in the raw_exports directory."""
    raw_exports_dir = "data/raw/slack/raw_exports"
    
    # Create raw_exports directory if it doesn't exist
    os.makedirs(raw_exports_dir, exist_ok=True)
    
    # Find all JSON files in raw_exports directory
    json_files = []
    if os.path.exists(raw_exports_dir):
        for file in os.listdir(raw_exports_dir):
            if file.endswith('.json'):
                json_files.append(os.path.join(raw_exports_dir, file))
    
    # Also check root directory for any legacy files
    for file in ['slack.json', 'slack-2.json']:
        if os.path.exists(file):
            json_files.append(file)
    
    if not json_files:
        print(f"{ansi.yellow}No JSON files found to process.{ansi.reset}")
        print(f"Please place Slack export JSON files in: {ansi.cyan}{raw_exports_dir}{ansi.reset}")
        return
    
    print(f"Found {ansi.green}{len(json_files)}{ansi.reset} JSON files to process:")
    for file in json_files:
        print(f"  - {ansi.cyan}{file}{ansi.reset}")
    
    print()
    
    processed_count = 0
    skipped_count = 0
    
    for json_file in json_files:
        result = extract_messages_to_markdown(json_file)
        if result is None:
            skipped_count += 1
        else:
            processed_count += 1
        print()  # Add spacing between files
    
    print(f"\n{ansi.magenta}Processing Summary{ansi.reset}")
    print("=" * 30)
    print(f"Files processed: {ansi.green}{processed_count}{ansi.reset}")
    print(f"Files skipped: {ansi.yellow}{skipped_count}{ansi.reset}")
    print(f"Total files: {ansi.cyan}{len(json_files)}{ansi.reset}")
    
    # Show overall conversion status
    print()
    print_conversion_status()

if __name__ == "__main__":
    process_all_slack_exports()
