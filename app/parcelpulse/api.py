from __future__ import annotations

import json
import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest

from .common import parse_event, verify_signature
from .db import get_events, get_shipment, init_db
from .messaging import publish_event

app = FastAPI(title="ParcelPulse", version="1.0.0", description="Local-first reliable shipment-event intake demo")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "local-demo-secret-change-me")
REQUESTS = Counter("parcelpulse_webhook_requests_total", "Webhook requests by result", ["result"])
ACCEPTED = Counter("parcelpulse_events_accepted_total", "Events accepted into queue")

@app.on_event("startup")
def startup() -> None:
    init_db()

@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}

@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/v1/shipments/events", status_code=202)
async def ingest(request: Request, x_signature_sha256: str | None = Header(default=None)) -> dict[str, Any]:
    raw = await request.body()
    if not verify_signature(raw, x_signature_sha256, WEBHOOK_SECRET):
        REQUESTS.labels(result="invalid_signature").inc()
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        parsed = parse_event(json.loads(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        REQUESTS.labels(result="invalid_payload").inc()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        publish_event(parsed)
    except Exception as exc:
        REQUESTS.labels(result="queue_unavailable").inc()
        raise HTTPException(status_code=503, detail="Event queue temporarily unavailable") from exc
    REQUESTS.labels(result="accepted").inc()
    ACCEPTED.inc()
    return {"accepted": True, "event_id": parsed["event_id"], "shipment_id": parsed["shipment_id"]}

@app.get("/v1/shipments/{shipment_id}")
def shipment(shipment_id: str) -> dict[str, Any]:
    found = get_shipment(shipment_id)
    if not found:
        raise HTTPException(status_code=404, detail="Shipment not found yet; processing may be pending")
    return dict(found)

@app.get("/v1/shipments/{shipment_id}/events")
def shipment_events(shipment_id: str) -> list[dict[str, Any]]:
    return [dict(row) for row in get_events(shipment_id)]
