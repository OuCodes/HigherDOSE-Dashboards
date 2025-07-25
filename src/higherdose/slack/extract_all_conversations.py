#!/usr/bin/env python3
"""
Script to automatically extract all Slack conversations to markdown files.
"""

import asyncio
import subprocess
import sys
import time
import os
from pathlib import Path

# All conversations to extract (from the list output)
CONVERSATIONS = [
    # Channels (5)
    "##channel_C0888LHLRM2",
    "##channel_C08JS5H7JFP", 
    "##channel_C08MBRQQ340",
    "##channel_CA9V9JACE",
    "##sb-higherdose",
    
    # Direct Messages (14)
    "@@Anastasia",
    "@@Jake Panzer",
    "@@Laura", 
    "@@Rahul",
    "@@Slackbot",
    "@@dm_D0913R7S684",
    "@@dm_D0913R7SPD2",
    "@@dm_D091C4YDWBF",
    "@@dm_D0921V28JJW",
    "@@dm_D093PPS8VAP",
    "@@dm_D093VHXRG9K",
    "@@dm_D09430T3YBF",
    "@@dm_D095M5L4Q59",
    "@@dm_ingrid_jourdan",
    
    # Multi-person DMs (7)
    "👥@mpdm-anastasia--ingrid--jourdan-1🔒",
    "👥@mpdm-anastasia--ingrid--laura--jourdan-1🔒",
    "👥@mpdm-berkeley--jake--ari--ashan--jourdan-1🔒",
    "👥@mpdm-carly--ari--berkeley--jake--ingrid--jourdan-1🔒",
    "👥@mpdm-chris--ingrid--jourdan--anastasia-1🔒",
    "👥@mpdm-chris--jourdan--ingrid-1🔒",
    "👥@mpdm-elyse--fionahillery--anastasia--mariajose108e--anthony--ingrid--sajel--jourdan-1🔒"
]

def extract_conversation(conversation_name):
    """Extract a single conversation using the slack fetcher script."""
    print(f"\n🔍 Extracting: {conversation_name}")
    
    try:
        # Run the slack fetcher script with the conversation name as input
        cmd = ["python", "slack/slack_fetcher_playwright.py"]
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd="/Users/jourdansmith/code/research/HigherDOSE"
        )
        
        # Send the conversation name and quit command
        input_commands = f"{conversation_name}\nq\n"
        stdout, stderr = process.communicate(input=input_commands, timeout=120)
        
        if process.returncode == 0:
            print(f"✅ Successfully extracted: {conversation_name}")
            return True
        else:
            print(f"❌ Error extracting {conversation_name}: {stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ Timeout extracting: {conversation_name}")
        process.kill()
        return False
    except Exception as e:
        print(f"❌ Exception extracting {conversation_name}: {e}")
        return False

def main():
    """Main function to extract all conversations."""
    print("🚀 Starting extraction of all Slack conversations...")
    print(f"📝 Total conversations to extract: {len(CONVERSATIONS)}")
    
    # Ensure we're in the correct directory
    os.chdir("/Users/jourdansmith/code/research/HigherDOSE")
    
    # Activate virtual environment
    try:
        subprocess.run(["source", "venv/bin/activate"], shell=True, check=True)
    except:
        pass  # May already be activated
    
    successful = 0
    failed = 0
    
    for i, conversation in enumerate(CONVERSATIONS, 1):
        print(f"\n{'='*60}")
        print(f"Progress: {i}/{len(CONVERSATIONS)} ({i/len(CONVERSATIONS)*100:.1f}%)")
        
        if extract_conversation(conversation):
            successful += 1
        else:
            failed += 1
        
        # Small delay between extractions
        time.sleep(2)
    
    print(f"\n{'='*60}")
    print(f"🎉 Extraction complete!")
    print(f"✅ Successfully extracted: {successful}")
    print(f"❌ Failed to extract: {failed}")
    print(f"📁 Check the data/processed/slack/markdown_exports directory for your files")

if __name__ == "__main__":
    main() 