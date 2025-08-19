#!/usr/bin/env python3
import os
import sys
import requests
import datetime
import time
import json
import subprocess

KICK_USER = os.environ.get("USER")
TOKEN = os.environ.get("TOKEN") 
CHANNEL_ID = os.environ.get("CHANNEL")
NOTIFY_WINDOW = int(os.environ.get("NOTIFY_WINDOW", "15"))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") 

if not KICK_USER:
    print("Missing required env: KICK_USER")
    sys.exit(1)
if not TOKEN:
    print("Missing required env: DISCORD_TOKEN")
    sys.exit(1)

API = f"https://kick.com/api/v1/channels/{KICK_USER}"

def parse_iso(s):
    if not s:
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc)
        except Exception:
            return None

def send_via_bot(token, channel_id, payload_json, max_retries=3):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json"
    }
    attempt = 0
    while attempt < max_retries:
        attempt += 1
        try:
            r = requests.post(url, json=payload_json, headers=headers, timeout=15)
            if r.status_code == 429:
                retry_after = r.json().get("retry_after", None) or r.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else 5
                print(f"Rate limited; retry_after={wait}s. Attempt {attempt}/{max_retries}")
                time.sleep(wait + 0.5)
                continue
            r.raise_for_status()
            print("Message sent via bot token.")
            return True
        except requests.RequestException as e:
            print("Failed to send via bot:", e, "status:", getattr(e.response, "status_code", None))
            time.sleep(1)
    return False

def read_last_notified(filepath="last_stream_id.txt"):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None

def write_last_notified(stream_id, filepath="last_stream_id.txt"):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(str(stream_id))

def commit_file_to_repo(filepath="last_stream_id.txt"):
    repo = os.environ.get("GITHUB_REPOSITORY") 
    if not repo:
        print("GITHUB_REPOSITORY not found; skipping commit.")
        return False
    branch = os.environ.get("GITHUB_REF", "").split("/")[-1] or "main"
    token = GITHUB_TOKEN
    if not token:
        print("No GITHUB_TOKEN; skipping commit.")
        return False
    try:
        subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "add", filepath], check=True)
        subprocess.run(["git", "commit", "-m", f"chore: update last notified stream id ({filepath})"], check=True)
        push_url = f"https://x-access-token:{token}@github.com/{repo}.git"
        subprocess.run(["git", "push", push_url, f"HEAD:{branch}"], check=True)
        print("Committed and pushed last_stream_id.")
        return True
    except subprocess.CalledProcessError as e:
        print("Failed to commit/push last_stream_id:", e)
        return False

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

stream_id = None
for k in ("id", "stream_id", "_id"):
    if isinstance(livestream, dict) and k in livestream:
        stream_id = livestream.get(k)
        break

if stream_id and GITHUB_TOKEN:
    last = read_last_notified()
    if last and last == str(stream_id):
        print("Already notified for this stream id (persisted). Skipping.")
        sys.exit(0)

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
    should_notify = True
    print("No start timestamp from Kick — sending once per run while live (may duplicate if you don't enable GITHUB_TOKEN persistence).")

if not should_notify:
    sys.exit(0)

user = (data.get("user") or {}).get("username") or KICK_USER
title = (livestream.get("title") or livestream.get("name") or "Live now") if isinstance(livestream, dict) else "Live now"
link = f"https://kick.com/{KICK_USER}"
thumbnail = None
try:
    if isinstance(livestream, dict):
        thumbnail = livestream.get("thumbnail") or livestream.get("thumbnail_url") or livestream.get("thumbnailUrl")
except Exception:
    thumbnail = None

embed = {
    "title": f"{user} is LIVE",
    "url": link,
    "description": title,
    "timestamp": now.isoformat(),
    "footer": {"text": "via kick.com"},
}
if thumbnail:
    embed["thumbnail"] = {"url": thumbnail}

payload = {
    "embeds": [embed],
    "allowed_mentions": {"parse": []} 
}

success = send_via_bot(TOKEN, CHANNEL_ID, payload)
if not success:
    print("Failed to send message. Exiting.")
    sys.exit(1)

if stream_id and GITHUB_TOKEN:
    write_last_notified(stream_id)
    committed = commit_file_to_repo("last_stream_id.txt")
    if not committed:
        print("Warning: could not persist last_stream_id.txt (commit failed).")

sys.exit(0)
