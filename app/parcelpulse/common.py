from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_STATUSES = {"CREATED", "PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "EXCEPTION"}
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")


def verify_signature(raw_body: bytes, signature: str | None, secret: str) -> bool:
    """Verify an HMAC-SHA256 signature over the exact received request bytes."""
    if not signature or not signature.startswith("sha256="):
        return False
    supplied = signature.removeprefix("sha256=").strip().lower()
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(supplied, expected)


def sign_body(raw_body: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def parse_event(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("JSON body must be an object")
    required = ("event_id", "shipment_id", "status", "occurred_at")
    if any(not isinstance(value.get(key), str) or not value[key].strip() for key in required):
        raise ValueError("event_id, shipment_id, status, and occurred_at must be non-empty strings")
    for key in ("event_id", "shipment_id"):
        if not ID_RE.fullmatch(value[key]):
            raise ValueError(f"{key} contains unsupported characters or is too long")
    status = value["status"].strip().upper()
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of: {', '.join(sorted(VALID_STATUSES))}")
    try:
        occurred = datetime.fromisoformat(value["occurred_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("occurred_at must be ISO 8601 datetime") from exc
    if occurred.tzinfo is None:
        raise ValueError("occurred_at must include a timezone, e.g. Z or +05:30")
    normalized = dict(value)
    normalized["status"] = status
    normalized["occurred_at"] = occurred.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return normalized


def archive_event(event: dict[str, Any]) -> Path:
    """Write deterministic archive object via atomic rename to tolerate retries."""
    archive_dir = Path(os.getenv("ARCHIVE_DIR", "./data/archive"))
    archive_dir.mkdir(parents=True, exist_ok=True)
    safe_name = hashlib.sha256(event["event_id"].encode("utf-8")).hexdigest() + ".json"
    target = archive_dir / safe_name
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(event, sort_keys=True, indent=2), encoding="utf-8")
    temporary.replace(target)
    return target
