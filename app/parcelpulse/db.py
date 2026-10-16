from __future__ import annotations

import os
import time
from datetime import datetime

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://parcelpulse:local_dev_only_change_me@localhost:5432/parcelpulse")


def _event_time(event: dict) -> datetime:
    return datetime.fromisoformat(event["occurred_at"].replace("Z", "+00:00"))

DDL = """
CREATE TABLE IF NOT EXISTS shipment_events (
    event_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL,
    status TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_shipment_events_shipment_time
    ON shipment_events (shipment_id, occurred_at DESC);
CREATE TABLE IF NOT EXISTS shipments (
    shipment_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_event_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def connect() -> psycopg.Connection:
    return psycopg.connect(DATABASE_URL, row_factory=dict_row, connect_timeout=3)


def init_db(retries: int = 30, delay_seconds: float = 2.0) -> None:
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            with connect() as conn:
                with conn.transaction():
                    for statement in DDL.split(";"):
                        if statement.strip():
                            conn.execute(statement)
            return
        except Exception as exc:  # startup dependency may still be warming
            last_error = exc
            time.sleep(delay_seconds)
    raise RuntimeError(f"PostgreSQL did not become ready: {last_error}")


def store_event(event: dict) -> tuple[bool, bool]:
    """Return (inserted, state_advanced); event ID uniqueness supplies idempotency."""
    with connect() as conn:
        with conn.transaction():
            inserted = conn.execute(
                """INSERT INTO shipment_events (event_id, shipment_id, status, occurred_at, payload)
                   VALUES (%s, %s, %s, %s, %s)
                   ON CONFLICT (event_id) DO NOTHING
                   RETURNING event_id""",
                (event["event_id"], event["shipment_id"], event["status"], _event_time(event), Jsonb(event)),
            ).fetchone()
            if not inserted:
                return False, False
            state = conn.execute(
                """INSERT INTO shipments (shipment_id, status, last_event_at)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (shipment_id) DO UPDATE
                   SET status = EXCLUDED.status,
                       last_event_at = EXCLUDED.last_event_at,
                       updated_at = now()
                   WHERE EXCLUDED.last_event_at > shipments.last_event_at
                   RETURNING shipment_id""",
                (event["shipment_id"], event["status"], _event_time(event)),
            ).fetchone()
            return True, bool(state)


def get_shipment(shipment_id: str) -> dict | None:
    with connect() as conn:
        return conn.execute(
            "SELECT shipment_id, status, last_event_at, updated_at FROM shipments WHERE shipment_id = %s",
            (shipment_id,),
        ).fetchone()


def get_events(shipment_id: str) -> list[dict]:
    with connect() as conn:
        return conn.execute(
            """SELECT event_id, shipment_id, status, occurred_at, received_at
               FROM shipment_events WHERE shipment_id = %s ORDER BY occurred_at DESC""",
            (shipment_id,),
        ).fetchall()
