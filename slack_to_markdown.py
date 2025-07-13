#!/usr/bin/env python3
import json
import re
from datetime import datetime
from typing import Dict, List, Optional

def load_slack_data(file_path: str) -> dict:
    """Load Slack JSON export data."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

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

def extract_messages_to_markdown(json_file_path: str, output_file_path: str):
    """Extract all messages from Slack JSON and save as markdown."""
    
    # Load the data
    data = load_slack_data(json_file_path)
    
    # Create user mapping
    user_map = create_user_map(data.get('users', []))
    
    # Get channel info
    channel = data.get('channel', {})
    channel_name = channel.get('name', 'Unknown Channel')
    
    # Start building markdown content
    markdown_content = f"# Slack Channel: {channel_name}\n\n"
    
    # Get messages
    messages = data.get('history', {}).get('messages', [])
    
    # Sort messages by timestamp (oldest first)
    messages.sort(key=lambda x: float(x.get('ts', '0')))
    
    # Process each message
    for message in messages:
        formatted_message = format_message(message, user_map)
        if formatted_message:
            markdown_content += formatted_message
    
    # Save to file
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print(f"Successfully converted {len(messages)} messages to markdown.")
    print(f"Output saved to: {output_file_path}")

if __name__ == "__main__":
    # Use the provided JSON file
    json_file = "slack.json"
    output_file = "slack_messages.md"
    
    extract_messages_to_markdown(json_file, output_file) 