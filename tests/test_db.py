import os
from urllib.parse import urlsplit

import pytest

from parcelpulse import db


TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL must point to a dedicated test database",
)


@pytest.fixture(autouse=True)
def prepare_test_database(monkeypatch):
    database_url = os.environ["TEST_DATABASE_URL"]

    # Never run these tests against the demo or production database.
    if urlsplit(database_url).path.lstrip("/") != "parcelpulse_test":
        pytest.fail(
            "Database tests require the dedicated parcelpulse_test database"
        )

    monkeypatch.setattr(db, "DATABASE_URL", database_url)
    db.init_db(retries=3, delay_seconds=0)

    # This cleanup runs ONLY against parcelpulse_test.
    with db.connect() as conn:
        with conn.transaction():
            conn.execute("TRUNCATE TABLE shipment_events, shipments")


def make_event(event_id, shipment_id, status, occurred_at):
    return {
        "event_id": event_id,
        "shipment_id": shipment_id,
        "status": status,
        "occurred_at": occurred_at,
    }


def test_duplicate_event_is_stored_once():
    event = make_event(
        "evt-duplicate-001",
        "SHIP-TEST-001",
        "IN_TRANSIT",
        "2026-10-17T10:00:00Z",
    )

    assert db.store_event(event) == (True, True)
    assert db.store_event(event) == (False, False)

    assert len(db.get_events("SHIP-TEST-001")) == 1
    assert db.get_shipment("SHIP-TEST-001")["status"] == "IN_TRANSIT"


def test_older_event_does_not_overwrite_newer_state():
    delivered = make_event(
        "evt-order-newer",
        "SHIP-TEST-002",
        "DELIVERED",
        "2026-10-17T12:00:00Z",
    )

    older_transit = make_event(
        "evt-order-older",
        "SHIP-TEST-002",
        "IN_TRANSIT",
        "2026-10-17T10:00:00Z",
    )

    assert db.store_event(delivered) == (True, True)
    assert db.store_event(older_transit) == (True, False)

    # Both events are recorded, but the older event cannot regress state.
    assert len(db.get_events("SHIP-TEST-002")) == 2
    shipment = db.get_shipment("SHIP-TEST-002")
    assert shipment["status"] == "DELIVERED"