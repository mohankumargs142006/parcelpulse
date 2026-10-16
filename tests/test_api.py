import json
from fastapi.testclient import TestClient

from parcelpulse import api
from parcelpulse.common import sign_body


def test_signed_event_is_accepted(monkeypatch):
    monkeypatch.setattr(api, "init_db", lambda: None)
    monkeypatch.setattr(api, "WEBHOOK_SECRET", "test-secret")
    published = []
    monkeypatch.setattr(api, "publish_event", lambda event: published.append(event))
    payload = {
        "event_id": "evt-api-1",
        "shipment_id": "SHIP-2001",
        "status": "CREATED",
        "occurred_at": "2026-10-12T10:00:00Z",
    }
    raw = json.dumps(payload, separators=(",", ":")).encode()
    with TestClient(api.app) as client:
        response = client.post("/v1/shipments/events", content=raw, headers={
            "content-type": "application/json",
            "x-signature-sha256": sign_body(raw, "test-secret"),
        })
    assert response.status_code == 202
    assert published[0]["event_id"] == "evt-api-1"


def test_bad_signature_is_rejected(monkeypatch):
    monkeypatch.setattr(api, "init_db", lambda: None)
    monkeypatch.setattr(api, "WEBHOOK_SECRET", "test-secret")
    published = []
    monkeypatch.setattr(api, "publish_event", lambda event: published.append(event))
    raw = b'{"event_id":"e1","shipment_id":"s1","status":"CREATED","occurred_at":"2026-10-12T10:00:00Z"}'
    with TestClient(api.app) as client:
        response = client.post("/v1/shipments/events", content=raw, headers={
            "content-type": "application/json", "x-signature-sha256": "sha256=bad"
        })
    assert response.status_code == 401
    assert published == []
