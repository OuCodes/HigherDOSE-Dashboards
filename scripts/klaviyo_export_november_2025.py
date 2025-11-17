#!/usr/bin/env python3
"""Export November 2025 Klaviyo campaigns (sent + scheduled)"""

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

# Load API key
BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / "config" / "klaviyo" / ".env")
API_KEY = os.getenv('KLAVIYO_API_KEY')

HEADERS = {
    'Authorization': f'Klaviyo-API-Key {API_KEY}',
    'revision': '2024-10-15',
    'Accept': 'application/json'
}

def export_campaigns(start_date, end_date):
    """Export all campaigns (sent + scheduled) for the date range"""
    print("📧 Fetching Klaviyo campaigns...")
    
    all_campaigns = []
    url = 'https://a.klaviyo.com/api/campaigns/'
    params = {'filter': "equals(messages.channel,'email')"}
    
    # Fetch all pages
    for page in range(1, 16):
        if page == 1:
            response = requests.get(url, headers=HEADERS, params=params)
        else:
            response = requests.get(url, headers=HEADERS)
        
        data = response.json()
        campaigns = data.get('data', [])
        all_campaigns.extend(campaigns)
        
        print(f"   Page {page}: {len(campaigns)} campaigns")
        
        url = data.get('links', {}).get('next')
        if not url:
            break
    
    print(f"\n✅ Total: {len(all_campaigns)} campaigns")
    
    # Filter for campaigns in November 2025 (sent + scheduled)
    november_campaigns = []
    for camp in all_campaigns:
        attrs = camp.get('attributes', {})
        status = attrs.get('status')
        send_time = attrs.get('send_time') or attrs.get('scheduled_time')
        name = attrs.get('name', 'Unnamed')
        
        # Include Sent, Scheduled, and Adding Recipients statuses
        if status not in ['Sent', 'Scheduled', 'Adding Recipients']:
            continue
            
        if not send_time:
            continue
        
        try:
            send_dt = datetime.fromisoformat(send_time.replace('Z', '+00:00'))
            if start_date <= send_dt <= end_date:
                november_campaigns.append({
                    'campaign_name': name,
                    'send_datetime': send_dt,
                    'status': status,
                    'year': 2025,
                    'type': 'actual' if status == 'Sent' else 'planned'
                })
        except:
            continue
    
    print(f"\n📅 Found {len(november_campaigns)} campaigns in November 2025")
    return november_campaigns

# Main
start = datetime(2025, 11, 1, tzinfo=timezone.utc)
end = datetime(2025, 11, 30, 23, 59, 59, tzinfo=timezone.utc)

campaigns = export_campaigns(start, end)

if campaigns:
    df = pd.DataFrame(campaigns)
    df = df.sort_values('send_datetime')
    
    output = BASE_DIR / "data" / "mail" / "klaviyo_campaigns_november_2025.csv"
    df.to_csv(output, index=False)
    
    print(f"\n💾 Saved to: {output}")
    print(f"\n📊 Campaigns by Status:")
    print(f"   Sent: {len(df[df['status'] == 'Sent'])}")
    print(f"   Scheduled: {len(df[df['status'] == 'Scheduled'])}")
    print(f"   Adding Recipients: {len(df[df['status'] == 'Adding Recipients'])}")
    
    print(f"\n📧 Sample campaigns:")
    for _, row in df.head(10).iterrows():
        status_icon = '✅' if row['status'] == 'Sent' else '📅'
        print(f"   {status_icon} {row['send_datetime'].strftime('%b %d, %I:%M %p')} - {row['campaign_name'][:80]}")
    
    if len(df) > 10:
        print(f"   ... and {len(df) - 10} more")
    
    print(f"\n✅ Done!")
else:
    print("\n❌ No campaigns found in November 2025")

