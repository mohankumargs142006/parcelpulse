import json
import urllib.error
import urllib.request

url = "http://localhost:8000/v1/shipments/events"

payload = {
    "event_id": "evt-invalid-signature-001",
    "shipment_id": "SHIP-SEC-001",
    "status": "IN_TRANSIT",
    "occurred_at": "2026-10-14T12:00:00Z",
}

body = json.dumps(payload).encode("utf-8")

request = urllib.request.Request(
    url,
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-Signature-Sha256": "sha256=" + ("0" * 64),
    },
    method="POST",
)

try:
    with urllib.request.urlopen(request, timeout=10) as response:
        print("Unexpected response:", response.status)
        print(response.read().decode())
except urllib.error.HTTPError as exc:
    print("HTTP status:", exc.code)
    print("Response:", exc.read().decode())

    if exc.code == 401:
        print("PASS: Invalid signature rejected.")
    else:
        print("FAIL: Expected HTTP 401.")
except urllib.error.URLError as exc:
    print("Connection error:", exc)
