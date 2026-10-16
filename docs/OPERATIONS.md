# ParcelPulse operations and failure runbook

## 1. First checks

```powershell
docker compose ps
docker compose logs --tail 100 api worker rabbitmq postgres
iwr http://localhost:8000/healthz
```

Confirm containers are healthy, API is reachable, RabbitMQ queue bindings exist, and PostgreSQL accepts connections.

## 2. If API responds 401

- Confirm `.env` has the same `WEBHOOK_SECRET` used by the sender.
- The HMAC is over the exact raw request body, including whitespace. If JSON bytes change after signing, the signature must be recalculated.
- Do not log the secret or put it in Git.

## 3. If API returns 503

- Check RabbitMQ health and credentials.
- Inspect `docker compose logs rabbitmq api`.
- Do not acknowledge a webhook as accepted if the queue publish was not confirmed.

## 4. If queue depth grows

- Check worker logs and PostgreSQL health.
- Inspect RabbitMQ UI at http://localhost:15672.
- Restart a stopped worker with `docker compose restart worker`.
- Avoid scaling multiple consumers until you understand DB connection limits and idempotency behavior.

## 5. If messages reach the DLQ

- Inspect queue `shipment.events.dlq` in RabbitMQ UI and review worker logs.
- Identify the failure cause before replaying messages.
- In this local starter, DLQ replay is deliberately a controlled manual exercise: use RabbitMQ UI to move/re-publish a specific message after correcting the cause. For a polished submission, implement a restricted replay command that records who replayed which event and when.
- Do not automatically replay poison messages indefinitely.

## 6. Data looks stale

- Query `/v1/shipments/{shipment_id}/events` and compare `occurred_at` values.
- The latest shipment row only advances when an incoming event timestamp is strictly newer than the stored timestamp.
- A duplicate `event_id` is intentionally ignored, even if its payload differs. Treat conflicting payloads for a reused event ID as a producer-contract violation and add an alert/test for this case as an enhancement.

## 7. Safe reset

`docker compose down` stops containers but preserves the named data volumes.

`docker compose down -v` deletes the PostgreSQL database, event archive, Prometheus data, and Grafana data. Use it only when you intend to reset the demo.
