#!/usr/bin/env python3
import os
import sys

# robust env reading — prefers the names you used in the workflow, but falls back to older names
KICK_USER = os.environ.get("KICK_USER") or os.environ.get("USER")
TOKEN = os.environ.get("DISCORD_TOKEN") or os.environ.get("TOKEN")
CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID") or os.environ.get("CHANNEL")
NOTIFY_WINDOW = int(os.environ.get("NOTIFY_WINDOW", "15"))
GIT_TOKEN = os.environ.get("GIT_TOKEN") or os.environ.get("GITHUB_TOKEN")

# Helpful explicit error messages (match what your logs will show)
if not KICK_USER:
    print("Missing required env: KICK_USER / USER")
    sys.exit(1)
if not TOKEN:
    print("Missing required env: DISCORD_TOKEN / TOKEN")
    sys.exit(1)
if not CHANNEL_ID:
    print("Missing required env: DISCORD_CHANNEL_ID / CHANNEL")
    sys.exit(1)
