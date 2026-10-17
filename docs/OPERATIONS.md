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


## 8. Failure recovery and dead-letter queue verification

This procedure verifies bounded retries, dead-letter queue (DLQ) routing, worker recovery, and monitoring using the local Docker Compose environment.

### Prerequisites

- Start the Docker Compose stack and confirm PostgreSQL and RabbitMQ are healthy.
- Confirm the API is reachable at `http://localhost:8000/healthz`.
- Confirm RabbitMQ has the queues `shipment.events`, `shipment.events.retry`, and `shipment.events.dlq`.
- Use a dedicated test event. Do not use production data.
- Do not delete Docker volumes or purge queues during this test.

### A. Record the initial queue state

In PowerShell, run:

```powershell
docker compose ps
docker compose exec rabbitmq rabbitmqctl list_queues name messages_ready messages_unacknowledged
```

Record the initial message counts so you can distinguish test messages from existing messages.

### B. Enable controlled worker failure

Enable failure injection in the current PowerShell session:

```powershell
$env:SIMULATE_WORKER_FAILURE = "true"
docker compose up -d --no-deps --force-recreate worker
docker compose exec worker sh -lc 'echo SIMULATE_WORKER_FAILURE=$SIMULATE_WORKER_FAILURE'
```

Confirm that the final command prints `SIMULATE_WORKER_FAILURE=true`.

### C. Submit a failure-test event

Run the reusable test sender:

```powershell
py .\scripts_send_failure_demo.py
```

Record the returned event ID and shipment ID. An HTTP 202 response means the API accepted the event for asynchronous processing; it does not mean that processing succeeded.

Wait approximately 20 seconds, allowing for the initial failed attempt, the configured five-second retry delay, and the retry limit:

```powershell
Start-Sleep -Seconds 20
docker compose exec rabbitmq rabbitmqctl list_queues name messages_ready messages_unacknowledged
docker compose logs --tail 80 worker
```

Expected outcome for an isolated test with an initially empty queue:

- The main queue has no ready messages.
- The retry queue has no ready messages.
- The DLQ contains the failed test message.
- Worker logs show the deliberately injected processing failures.

Message counts may differ if other events are being processed concurrently. Confirm the test message's identity before drawing conclusions.
Before restoring the worker, wait until Prometheus has scraped the final dead-letter queue (DLQ) counter for this run. Worker counters are held in process memory and reset when the worker is recreated.

After the final failure/DLQ log appears, allow at least 20 seconds for the configured 15-second scrape interval. Then query the current counter and inspect its sample timestamp:

```powershell
$q = [uri]::EscapeDataString("parcelpulse_worker_dlq_total")
$r = Invoke-RestMethod "http://localhost:9090/api/v1/query?query=$q"

$r.data.result | ForEach-Object {
    [pscustomobject]@{
        Value = $_.value[1]
        SampleTimeUtc = [DateTimeOffset]::FromUnixTimeMilliseconds(
            [long]([double]$_.value[0] * 1000)
        ).UtcDateTime
    }
}
```

Confirm that the sample was recorded after the final DLQ transition and reflects the counter increment for this test run. If the sample has not updated, wait another five seconds and query again. Do not recreate the worker until the scrape is confirmed.

### D. Restore normal worker operation

Disable failure injection and recreate only the worker:

```powershell
$env:SIMULATE_WORKER_FAILURE = "false"
docker compose up -d --no-deps --force-recreate worker
docker compose exec worker sh -lc 'echo SIMULATE_WORKER_FAILURE=$SIMULATE_WORKER_FAILURE'
```

Confirm that the worker reports `SIMULATE_WORKER_FAILURE=false`.

Do not purge or automatically replay the DLQ message. Keep it available for inspection unless a deliberate cleanup or replay is required.

### E. Verify successful processing after recovery

Submit a separate event while the worker is operating normally:

```powershell
py .\scripts_send_success_recovery.py
```

Record the `shipment_id` returned in the response. Then query its state, replacing the example identifier with the actual returned ID:

```powershell
$shipmentId = Read-Host "Enter the shipment_id from the response"
Invoke-RestMethod "http://localhost:8000/v1/shipments/$shipmentId"
```

Wait a few seconds and retry the query if processing is still pending. For the test event with status `IN_TRANSIT`, the API confirms that normal processing resumed after failure injection was disabled.

### F. Verify Prometheus and Grafana

Open Prometheus at `http://localhost:9090` and query:

```promql
increase(parcelpulse_worker_failures_total[15m])
```

```promql
increase(parcelpulse_worker_dlq_total[15m])
```

```promql
increase(parcelpulse_worker_processed_total[5m])
```

```promql
up{job="parcelpulse-worker"}
```

A worker scrape value of `1` means Prometheus can currently scrape that target. The increase queries report estimated counter increases over their respective time windows. Fractional results can occur because Prometheus extrapolates range-query values, and restarting the worker resets its in-memory counters.

Open the Grafana reliability dashboard at `http://localhost:3000/d/parcelpulse-main/parcelpulse-reliability`. Review the accepted webhook rate, unique events processed, worker failures, and DLQ/duplicate events panels.

### G. Record test evidence

For each demonstration, record:

- Date and time of the run.
- Test event ID and shipment ID.
- API response status.
- Initial and final RabbitMQ queue counts.
- Relevant worker logs.
- Prometheus query results and Grafana observations.
- Confirmation that failure injection was disabled afterward.

### Safety notes

- Use a dedicated local test event and never expose webhook secrets in logs or documentation.
- `docker compose down` stops the stack but preserves named volumes.
- `docker compose down -v` removes named volumes and may delete database, archive, and monitoring data. Use it only when intentionally resetting the environment.
- Do not claim a message was successfully processed from an HTTP 202 response alone. Verify the shipment state and worker/monitoring evidence.
