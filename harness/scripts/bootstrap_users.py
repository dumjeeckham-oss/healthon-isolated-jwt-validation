"""Create disposable users through local GoTrue signup; never logs secrets."""
import json, os, sys, urllib.request, urllib.error

base = os.environ.get("AUTH_URL", "").rstrip("/")
if not base or "127.0.0.1" not in base and "localhost" not in base:
    raise SystemExit("bootstrap requires localhost AUTH_URL")

def signup(email, password):
    req = urllib.request.Request(base + "/signup", data=json.dumps({"email": email, "password": password}).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if e.code == 422 and "already" in body.lower():
            return
        raise
    if not data.get("id"):
        raise RuntimeError("signup returned no user id")

for suffix in ("A", "B"):
    email = os.environ[f"USER_{suffix}_EMAIL"]
    password = os.environ[f"USER_{suffix}_PASSWORD"]
    signup(email, password)
print("disposable local users ready")
