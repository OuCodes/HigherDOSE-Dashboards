#!/usr/bin/env python3
"""Run the Playwright-based Slack export."""
from higherdose.slack._init_config import ensure_workspace_config

if __name__ == "__main__":
    ensure_workspace_config()
    from higherdose.slack.slack_fetcher import run_main  # import after config exists
    run_main()
