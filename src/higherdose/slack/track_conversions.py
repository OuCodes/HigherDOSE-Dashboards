#!/usr/bin/env python3
"""
Slack Export Conversion Tracker
Keeps track of which JSON files have been converted to avoid reprocessing
"""

import os
import json
import hashlib
from datetime import datetime
from typing import Dict, Set
from higherdose.utils.logs import report
from higherdose.utils.style import ansi

logger = report.settings(__file__)

TRACKING_FILE = "slack/conversion_tracker.json"

def get_file_hash(file_path: str) -> str:
    """Get MD5 hash of a file to track changes."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.error("Failed to hash file %s: %s", file_path, str(e))
        return ""

def load_tracking_data() -> Dict:
    """Load the conversion tracking data."""
    if not os.path.exists(TRACKING_FILE):
        logger.info("No tracking file found, creating new one")
        return {"conversions": {}, "last_updated": None}
    
    try:
        with open(TRACKING_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        logger.info("Loaded tracking data with %d entries", len(data.get("conversions", {})))
        return data
    except Exception as e:
        logger.error("Failed to load tracking data: %s", str(e))
        return {"conversions": {}, "last_updated": None}

def save_tracking_data(data: Dict) -> None:
    """Save the conversion tracking data."""
    data["last_updated"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(TRACKING_FILE), exist_ok=True)
    
    try:
        with open(TRACKING_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("Saved tracking data")
    except Exception as e:
        logger.error("Failed to save tracking data: %s", str(e))

def is_file_converted(file_path: str) -> bool:
    """Check if a JSON file has already been converted."""
    tracking_data = load_tracking_data()
    conversions = tracking_data.get("conversions", {})
    
    if file_path not in conversions:
        return False
    
    # Check if file has changed since last conversion
    current_hash = get_file_hash(file_path)
    stored_hash = conversions[file_path].get("file_hash", "")
    
    if current_hash != stored_hash:
        logger.info("File %s has changed since last conversion", file_path)
        return False
    
    return True

def mark_file_converted(file_path: str, output_path: str, message_count: int) -> None:
    """Mark a file as converted with metadata."""
    tracking_data = load_tracking_data()
    
    tracking_data["conversions"][file_path] = {
        "file_hash": get_file_hash(file_path),
        "output_path": output_path,
        "message_count": message_count,
        "converted_at": datetime.now().isoformat(),
        "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0
    }
    
    save_tracking_data(tracking_data)
    logger.info("Marked %s as converted (%d messages)", file_path, message_count)

def get_conversion_status() -> Dict:
    """Get summary of conversion status."""
    tracking_data = load_tracking_data()
    conversions = tracking_data.get("conversions", {})
    
    total_files = len(conversions)
    total_messages = sum(conv.get("message_count", 0) for conv in conversions.values())
    
    return {
        "total_converted_files": total_files,
        "total_messages_processed": total_messages,
        "last_updated": tracking_data.get("last_updated"),
        "conversions": conversions
    }

def print_conversion_status() -> None:
    """Print a summary of conversion status."""
    status = get_conversion_status()
    
    print(f"\n{ansi.magenta}Slack Conversion Status{ansi.reset}")
    print("=" * 50)
    print(f"Total converted files: {ansi.green}{status['total_converted_files']}{ansi.reset}")
    print(f"Total messages processed: {ansi.green}{status['total_messages_processed']}{ansi.reset}")
    
    if status['last_updated']:
        print(f"Last updated: {ansi.cyan}{status['last_updated']}{ansi.reset}")
    
    if status['conversions']:
        print(f"\n{ansi.yellow}Recent conversions:{ansi.reset}")
        for file_path, data in list(status['conversions'].items())[-5:]:
            filename = os.path.basename(file_path)
            message_count = data.get('message_count', 0)
            converted_at = data.get('converted_at', 'Unknown')
            print(f"  {ansi.cyan}{filename}{ansi.reset}: {message_count} messages ({converted_at})")

if __name__ == "__main__":
    print_conversion_status()