#!/usr/bin/env python3
import os, sys, requests, datetime, time, subprocess

KICK_USER = os.environ.get("USER") or os.environ.get("KICK_USER")
TOKEN = os.environ.get("TOKEN") or os.environ.get("DISCORD_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL") or os.environ.get("DISCORD_CHANNEL_ID")
GIT_TOKEN = os.environ.get("GIT_TOKEN") or os.environ.get("GITHUB_TOKEN")
NOTIFY_WINDOW = int(os.environ.get("NOTIFY_WINDOW", "5"))
RENAME_CHANNEL_ID = os.environ.get("RENAME_CHANNEL_ID") or "1407412902973149246"
LIVE_NAME = "🟢 LIVE"
OFFLINE_NAME = "🔴 OFFLINE"
API = f"https://kick.com/api/v1/channels/{KICK_USER}"

if not KICK_USER:
    print("Missing required env: USER")
    sys.exit(1)
if not TOKEN:
    print("Missing required env: TOKEN")
    sys.exit(1)
if not CHANNEL_ID:
    print("Missing required env: CHANNEL")
    sys.exit(1)

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

def discord_send(token, channel_id, payload, max_retries=3):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    for i in range(max_retries):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            if r.status_code == 429:
                try:
                    retry_after = r.json().get("retry_after")
                except Exception:
                    retry_after = r.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else 5
                time.sleep(wait + 0.25)
                continue
            r.raise_for_status()
            return True
        except requests.RequestException:
            time.sleep(1)
    return False

def discord_get_channel(token, channel_id):
    url = f"https://discord.com/api/v10/channels/{channel_id}"
    headers = {"Authorization": f"Bot {token}"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            return r.json()
    except requests.RequestException:
        pass
    return None

def discord_rename_channel(token, channel_id, new_name, max_retries=3):
    url = f"https://discord.com/api/v10/channels/{channel_id}"
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    current = discord_get_channel(token, channel_id)
    if current and isinstance(current, dict):
        if current.get("name") == new_name:
            return True
    for i in range(max_retries):
        try:
            r = requests.patch(url, json={"name": new_name}, headers=headers, timeout=15)
            if r.status_code == 429:
                try:
                    retry_after = r.json().get("retry_after")
                except Exception:
                    retry_after = r.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else 5
                time.sleep(wait + 0.25)
                continue
            r.raise_for_status()
            return True
        except requests.RequestException:
            time.sleep(1)
    return False

def read_last_notified(path="last_stream_id.txt"):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return None

def write_last_notified(stream_id, path="last_stream_id.txt"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(stream_id))

def commit_file(path="last_stream_id.txt"):
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo or not GIT_TOKEN:
        return False
    branch = os.environ.get("GITHUB_REF", "").split("/")[-1] or "main"
    try:
        subprocess.run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], check=True)
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=True)
        subprocess.run(["git", "add", path], check=True)
        subprocess.run(["git", "commit", "-m", f"chore: update {path}"], check=True)
        push_url = f"https://x-access-token:{GIT_TOKEN}@github.com/{repo}.git"
        subprocess.run(["git", "push", push_url, f"HEAD:{branch}"], check=True)
        return True
    except subprocess.CalledProcessError:
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
    if discord_rename_channel(TOKEN, RENAME_CHANNEL_ID, OFFLINE_NAME):
        print("Renamed channel to OFFLINE")
    else:
        print("Rename OFFLINE failed")
    print("Not live.")
    sys.exit(0)

stream_id = None
if isinstance(livestream, dict):
    for k in ("id", "stream_id", "_id"):
        if k in livestream:
            stream_id = livestream.get(k)
            break

if discord_rename_channel(TOKEN, RENAME_CHANNEL_ID, LIVE_NAME):
    print("Renamed channel to LIVE")
else:
    print("Rename LIVE failed")

start_ts = None
if isinstance(livestream, dict):
    for k in ("started_at", "startedAt", "created_at", "createdAt", "start_time", "stream_started_at"):
        if k in livestream:
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
    should_notify = True

if stream_id and GIT_TOKEN:
    last = read_last_notified()
    if last and last == str(stream_id):
        print("Already notified for this stream id. Skipping.")
        sys.exit(0)

user = (data.get("user") or {}).get("username") or KICK_USER
title = (livestream.get("title") or livestream.get("name") or "Live now") if isinstance(livestream, dict) else "Live now"
link = f"https://kick.com/{KICK_USER}"
thumb = None
if isinstance(livestream, dict):
    thumb = livestream.get("thumbnail") or livestream.get("thumbnail_url") or livestream.get("thumbnailUrl")

embed = {"title": f"{user} is LIVE", "url": link, "description": title, "timestamp": now.isoformat(), "footer": {"text": "via kick.com"}}
if thumb:
    embed["thumbnail"] = {"url": thumb}
payload = {"embeds": [embed], "allowed_mentions": {"parse": []}}

if should_notify:
    ok = discord_send(TOKEN, CHANNEL_ID, payload)
    if not ok:
        print("Failed to send message.")
        sys.exit(1)
    if stream_id and GIT_TOKEN:
        write_last_notified(stream_id)
        commit_file("last_stream_id.txt")

sys.exit(0)
