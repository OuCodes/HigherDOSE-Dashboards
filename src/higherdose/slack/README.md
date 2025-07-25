# Slack Message Fetcher

This directory contains tools for fetching Slack messages from the HigherDOSE workspace.

## New: Playwright-Based Fetcher (Recommended)

The new `slack_fetcher_playwright.py` uses Playwright to automatically handle authentication and fetch messages without manual credential management.

### Quick Start

```bash
# From project root
python run_slack_fetcher.py
```

This wrapper script will:
1. Set up virtual environment if needed
2. Install requirements
3. Set up Playwright browsers
4. Run the fetcher

### Manual Setup (Alternative)

```bash
# Install dependencies
pip install -r requirements.txt

# Set up Playwright
python slack/setup_playwright.py

# Run the fetcher
python slack/slack_fetcher_playwright.py
```

### How It Works

1. **Automatic Authentication**: Opens a browser and checks if you're logged into Slack
2. **Manual Login**: If not logged in, waits for you to log in manually (one-time setup)
3. **Credential Interception**: Automatically captures fresh tokens and cookies from browser requests
4. **Message Fetching**: Uses intercepted API calls to fetch conversation history
5. **Incremental Updates**: Tracks last fetched timestamp per conversation

### Benefits over Old Method

- ✅ **No manual credential extraction** - automatically grabs fresh tokens
- ✅ **Handles token expiration** - refreshes credentials automatically  
- ✅ **More reliable** - uses actual browser authentication
- ✅ **Better conversation detection** - handles DMs and group chats better
- ✅ **One-time login** - saves session for future runs

### Usage

1. Run the script: `python slack/slack_fetcher_playwright.py`
2. Browser opens and checks Slack login status
3. If not logged in, manually log in when prompted
4. Use interactive commands:
   - `list` - Show available channels/conversations
   - `<channel_name>` - Fetch new messages from channel
   - `refresh <channel>` - Re-fetch entire conversation history
   - `q` - Quit

### Files Created

- `config/slack/playwright_creds.json` - Cached credentials (auto-updated)
- `slack/markdown_exports/` - Exported conversations in Markdown format
- `config/slack/conversion_tracker.json` - Tracks last fetched timestamps

## Legacy: Manual Cookie Method

The original `fetch_cookie_md.py` requires manual credential extraction but may still work for some users.

### Issues with Legacy Method

- ❌ Frequent authentication failures
- ❌ Manual credential extraction required
- ❌ Tokens expire frequently
- ❌ Complex setup process

### Migration

If you've been using the legacy method:

1. Your existing conversation tracking will be preserved
2. Exported files will continue to be updated in the same location
3. No data loss - the new method appends to existing files

## Troubleshooting

### Browser Won't Open
```bash
playwright install --force chromium
```

### Authentication Issues
1. Clear browser data for slack.com
2. Try logging in manually in a regular browser first
3. Run the script again

### Headless Mode
Edit `slack_fetcher_playwright.py` and change:
```python
await browser.start(headless=True)  # Set to True for headless
```

### Virtual Environment Issues
```bash
# Delete and recreate virtual environment
rm -rf venv
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Files Structure

```
slack/
├── slack_fetcher_playwright.py    # New Playwright-based fetcher
├── setup_playwright.py            # Setup script for Playwright
├── fetch_cookie_md.py             # Legacy cookie-based fetcher
├── playwright_creds.json          # Cached credentials (auto-generated)
├── conversion_tracker.json        # Message tracking data
├── markdown_exports/              # Exported conversations
└── README.md                      # This file
``` 