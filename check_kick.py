import os, sys, json, datetime, requests

WEBHOOK = os.environ.get("DISCORD_WEBHOOK")
USER = os.environ.get("KICK_USER", "gragyu")
if not WEBHOOK or not USER:
    print("Missing envs"); sys.exit(1)

API = f"https://kick.com/api/v1/channels/{USER}"
try:
    r = requests.get(API, timeout=15)
    r.raise_for_status()
    data = r.json()
except Exception as e:
    print("API error", e); sys.exit(0)

livestream = data.get("livestream")
if not livestream:
    print("Not live")
    sys.exit(0)

# Try to find a start timestamp in common fields
for key in ("started_at", "startedAt", "created_at", "createdAt", "start_time"):
    t = livestream.get(key) if isinstance(livestream, dict) else None
    if t:
        start_str = t
        break
else:
    start_str = None

def parse_iso(s):
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
sent = False

if start_str:
    start = parse_iso(start_str)
    if start:
        delta = (now - start).total_seconds()
        if delta <= 10*60:
            sent = True

if (not start_str) and not sent:
    sent = True

if sent:
    title = livestream.get("title") or livestream.get("name") or "Live now"
    link = f"https://kick.com/{USER}"
    payload = {"content": f"🔴 **{USER} is LIVE** — **{title}**\n{link}"}
    try:
        resp = requests.post(WEBHOOK, json=payload, timeout=10)
        print("sent", resp.status_code, resp.text)
    except Exception as e:
        print("webhook send failed", e)
else:
    print("Not within start window; skipping notification")
