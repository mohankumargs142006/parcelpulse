import pytest

from parcelpulse.common import parse_event, sign_body, verify_signature


def valid_event():
    return {
        "event_id": "evt-001",
        "shipment_id": "SHIP-1001",
        "status": "in_transit",
        "occurred_at": "2026-10-12T09:00:00+05:30",
        "source": "demo-carrier",
    }


def test_signature_round_trip():
    body = b'{"hello":"world"}'
    sig = sign_body(body, "secret")
    assert verify_signature(body, sig, "secret")
    assert not verify_signature(body + b" ", sig, "secret")
    assert not verify_signature(body, sig, "different-secret")


def test_missing_or_malformed_signature_rejected():
    assert not verify_signature(b"{}", None, "secret")
    assert not verify_signature(b"{}", "abc", "secret")


def test_parse_event_normalizes_status_and_timezone():
    event = parse_event(valid_event())
    assert event["status"] == "IN_TRANSIT"
    assert event["occurred_at"] == "2026-10-12T03:30:00Z"


def test_parse_event_rejects_unknown_status():
    event = valid_event()
    event["status"] = "TELEPORTED"
    with pytest.raises(ValueError, match="status must be one of"):
        parse_event(event)


def test_parse_event_requires_timezone():
    event = valid_event()
    event["occurred_at"] = "2026-10-12T09:00:00"
    with pytest.raises(ValueError, match="must include a timezone"):
        parse_event(event)


def test_parse_event_rejects_unsafe_id():
    event = valid_event()
    event["event_id"] = "../../secrets"
    with pytest.raises(ValueError, match="unsupported characters"):
        parse_event(event)


def test_parse_event_requires_json_object():
    with pytest.raises(ValueError, match="must be an object"):
        parse_event(["not", "an", "object"])
