#!/usr/bin/env python3
"""
One-time setup: create a private GitHub Gist that stores SIGG Hub state
(portfolio, contest cURL, settings) for multi-device sync on Render.

Usage:
  export SIGG_GITHUB_TOKEN=ghp_xxx   # gist scope
  python scripts/bootstrap_cloud_state.py

Then put on Render (and keep secret):
  SIGG_GITHUB_TOKEN=ghp_xxx
  SIGG_STATE_GIST_ID=<printed id>
  CRON_SECRET=<any long random string>
"""

import json
import os
import sys
import requests

TOKEN = os.environ.get("SIGG_GITHUB_TOKEN", "").strip()
if not TOKEN:
    print("Set SIGG_GITHUB_TOKEN (classic PAT with 'gist' scope) first.")
    sys.exit(1)

bundle = {
    "portfolio": {
        "initial_capital": 20000.0,
        "cash": 20000.0,
        "positions": [],
        "closed_trades": [],
        "contest_sync": {"status": "unconfigured"},
        "last_updated": None,
    },
    "contest_curl": {
        "portfolio_curl": "",
        "ranking_curl": "",
        "enabled": False,
        "last_status": "unconfigured",
    },
    "settings": {
        "discord_webhook_url": "",
        "active_strategy": "breakout_trend",
        "sound_alerts_enabled": True,
        "auto_dispatch_0905": True,
        "auto_dispatch_1635": True,
        "auto_dispatch_1650": True,
    },
    "notifications": [],
    "updated_at": None,
}

payload = {
    "description": "SIGG Hub shared multi-device state (private)",
    "public": False,
    "files": {
        "sigg_hub_state.json": {
            "content": json.dumps(bundle, indent=2)
        }
    },
}

resp = requests.post(
    "https://api.github.com/gists",
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "sigg-hub-bootstrap",
    },
    json=payload,
    timeout=30,
)
if resp.status_code not in (200, 201):
    print("Failed:", resp.status_code, resp.text)
    sys.exit(1)

data = resp.json()
gist_id = data["id"]
print("Created private gist:", gist_id)
print("URL:", data.get("html_url"))
print()
print("Add these env vars on Render:")
print(f"  SIGG_STATE_GIST_ID={gist_id}")
print("  SIGG_GITHUB_TOKEN=<same token>")
print("  CRON_SECRET=<generate a long random string>")
print()
print("Add these GitHub Actions secrets on the REAL repo (not this zip):")
print("  SIGG_HUB_URL=https://<your-service>.onrender.com")
print("  CRON_SECRET=<same as Render>")
print("  DISCORD_WEBHOOK_URL=<optional>")
