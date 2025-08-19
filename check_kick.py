# check_kick.py
import os
import sys
import requests
import datetime

KICK_USER = os.environ.get("USER")
TOKEN = os.environ.get("TOKEN") or os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL")
NOTIFY_WINDOW = int(os.environ.get("NOTIFY_WINDOW", "15"))

if not KICK_USER or not TOKEN:
    print("Missing required envs: USER and TOKEN.")
    sys.exit(1)

API = f"https://kick.com/api/v1/channels/{KICK_USER}"

def parse_iso(s):
    if not s:
        return None
    try:
        # handle Z suffix
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        try:
            # fallback common formats
            return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc)
        except Exception:
            return None

def send_via_webhook(webhook_url, content):
    payload = {"content": content}
    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        r.raise_for_status()
        print("Webhook sent.")
    except Exception as e:
        print("Failed to send webhook:", e)

def send_via_bot(token, channel_id, content):
    if not channel_id:
        print("CHANNEL_ID is required when using a bot token. Set CHANNEL_ID or DISCORD_CHANNEL_ID.")
        return
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    payload = {"content": content}
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        print("Message sent via bot token.")
    except Exception as e:
        print("Failed to send via bot:", e, getattr(e, "response", None))

# fetch Kick API
try:
    r = requests.get(API, timeout=15)
    r.raise_for_status()
    data = r.json()
except Exception as e:
    print("Kick API error:", e)
    sys.exit(0)

livestream = data.get("livestream")
if not livestream:
    print("Not live.")
    sys.exit(0)

# find start timestamp if present
start_keys = ("started_at", "startedAt", "created_at", "createdAt", "start_time", "stream_started_at")
start_ts = None
for k in start_keys:
    if isinstance(livestream, dict) and k in livestream:
        start_ts = parse_iso(livestream.get(k))
        if start_ts:
            break

now = datetime.datetime.now(datetime.timezone.utc)
should_notify = False
if start_ts:
    delta = (now - start_ts).total_seconds()
    if delta <= NOTIFY_WINDOW * 60:
        should_notify = True
    else:
        print(f"Stream started {int(delta//60)} minutes ago (> {NOTIFY_WINDOW}m), skipping notify.")
else:
    # fallback: no start time available from Kick — we will send (risk of duplicates)
    should_notify = True
    print("No start timestamp from Kick — sending once per run while live (may duplicate).")

if not should_notify:
    sys.exit(0)

# build message
user = (data.get("user") or {}).get("username") or KICK_USER
title = (livestream.get("title") or livestream.get("name") or "Live now") if isinstance(livestream, dict) else "Live now"
link = f"https://kick.com/{KICK_USER}"
content = f"🔴 **{user} is LIVE** — **{title}**\n{link}"

# choose send method
if TOKEN.startswith("http://") or TOKEN.startswith("https://"):
    send_via_webhook(TOKEN, content)
else:
    send_via_bot(TOKEN, CHANNEL_ID, content)
