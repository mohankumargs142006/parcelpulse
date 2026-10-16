"""Send one HMAC-signed local demo event with only Python's standard library."""
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone

def load_dotenv_value(key: str, default: str) -> str:
    # Tiny .env reader to keep this sender dependent on the standard library only.
    try:
        for line in open(".env", encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                if name.strip() == key:
                    return os.getenv(key, value.strip().strip('"').strip("'"))
    except FileNotFoundError:
        pass
    return os.getenv(key, default)

URL = os.getenv("PARCELPULSE_URL", "http://localhost:8000/v1/shipments/events")
SECRET = load_dotenv_value("WEBHOOK_SECRET", "local-demo-secret-change-me")

payload = {
    "event_id": "evt-demo-0001",
    "shipment_id": "SHIP-1001",
    "status": "IN_TRANSIT",
    "occurred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "source": "local-demo-carrier",
}
raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
signature = "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
request = urllib.request.Request(URL, data=raw, headers={
    "Content-Type": "application/json",
    "X-Signature-SHA256": signature,
}, method="POST")
try:
    with urllib.request.urlopen(request, timeout=10) as response:
        print(f"HTTP {response.status}")
        print(response.read().decode("utf-8"))
except urllib.error.HTTPError as exc:
    print(f"HTTP {exc.code}: {exc.read().decode('utf-8')}")
    raise
