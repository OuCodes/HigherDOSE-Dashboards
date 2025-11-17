#!/usr/bin/env python3
"""Quick Klaviyo BFCM export - simplified version"""

import requests
import pandas as pd
from pathlib import Path
from datetime import datetime
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

def quick_export(start_date, end_date):
    """Quick export of BFCM campaigns"""
    print("📧 Fetching Klaviyo campaigns...")
    
    all_campaigns = []
    url = 'https://a.klaviyo.com/api/campaigns/'
    params = {'filter': "equals(messages.channel,'email')"}
    
    # Fetch all pages (limit to 15 pages = ~1500 campaigns)
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
    
    # Filter for sent campaigns in BFCM period
    bfcm_campaigns = []
    for camp in all_campaigns:
        attrs = camp.get('attributes', {})
        status = attrs.get('status')
        send_time = attrs.get('send_time')
        name = attrs.get('name', 'Unnamed')
        
        if status != 'Sent' or not send_time:
            continue
        
        try:
            send_dt = datetime.fromisoformat(send_time.replace('Z', '+00:00'))
            if start_date <= send_dt <= end_date:
                bfcm_campaigns.append({
                    'campaign_name': name,
                    'send_datetime': send_dt,
                    'status': status,
                    'recipients': 0,  # Would need additional API call
                    'open_rate': 0,
                    'click_rate': 0,
                    'revenue': 0,
                    'orders': 0
                })
        except:
            continue
    
    print(f"\n📅 Found {len(bfcm_campaigns)} campaigns in BFCM period")
    return bfcm_campaigns

# Main
from datetime import timezone
start = datetime(2024, 11, 1, tzinfo=timezone.utc)
end = datetime(2024, 11, 30, 23, 59, 59, tzinfo=timezone.utc)

campaigns = quick_export(start, end)

if campaigns:
    df = pd.DataFrame(campaigns)
    df = df.sort_values('send_datetime')
    
    output = BASE_DIR / "data" / "mail" / "klaviyo_campaigns_november_2024.csv"
    df.to_csv(output, index=False)
    
    print(f"\n💾 Saved to: {output}")
    print(f"\n📊 Campaigns:")
    for _, row in df.iterrows():
        print(f"   {row['send_datetime'].strftime('%b %d, %I:%M %p')} - {row['campaign_name']}")
    
    print(f"\n✅ Done! Run: python3 scripts/integrate_email_campaigns.py")
else:
    print("\n❌ No campaigns found in BFCM period")

