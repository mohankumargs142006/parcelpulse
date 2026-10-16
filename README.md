# ParcelPulse Zero-Cost Edition

[![ParcelPulse CI](https://github.com/mohankumargs142006/parcelpulse/actions/workflows/ci.yml/badge.svg)](https://github.com/mohankumargs142006/parcelpulse/actions/workflows/ci.yml)

A local-first, event-driven shipment webhook platform for a cloud engineering portfolio.

A local-first, event-driven shipment webhook platform for a cloud engineering portfolio. It is designed to run on your own Windows 11 laptop using free developer tools. **No AWS/GCP/Azure account, paid API, hosted database, or cloud bill is required to build and demonstrate this edition.**

> Scope honesty: this edition demonstrates cloud-native architecture patterns locally. It is not deployed to a public cloud. Use `docs/AWS_MAPPING.md` to explain how the local components map to an AWS deployment. A real cloud deployment is optional and may incur charges.

## What you will demonstrate

- HMAC-SHA256 signed webhook validation
- Asynchronous processing through RabbitMQ
- Retry queue and dead-letter queue (DLQ)
- PostgreSQL event ledger and shipment current state
- Idempotency for duplicate event IDs
- Out-of-order event protection using `occurred_at`
- Persistent raw-event archive on a Docker volume
- Prometheus metrics and Grafana dashboard
- Docker Compose as repeatable infrastructure-as-code for the local environment
- GitHub Actions CI checks (free for public repositories with standard hosted runners)
- Failure injection and an operational runbook

## Free tools

- Python 3.12
- Docker Desktop Personal (free for individual/student use under Docker's terms)
- Git and GitHub
- VS Code
- Terraform CLI (optional; no cloud resource is created in the local-only edition)

The project itself uses no paid APIs. You still need a computer and an internet connection to download open-source dependencies/container images. Cloud charges are avoided by not provisioning cloud resources.

## Prerequisites (Windows 11)

1. Install Docker Desktop: https://www.docker.com/products/personal/
2. Install Git: https://git-scm.com/downloads
3. Install VS Code: https://code.visualstudio.com/
4. Open Docker Desktop and wait until the engine is running.
5. Extract this ZIP to a folder such as `C:\Projects\parcelpulse-zero-cost`.

## Start the entire local stack

Open PowerShell in the project directory:

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
```

Wait for all services to become healthy. Open:

| Service | Local URL | Purpose |
|---|---|---|
| API | http://localhost:8000/docs | Swagger API docs |
| API health | http://localhost:8000/healthz | Liveness check |
| RabbitMQ | http://localhost:15672 | Queue dashboard; demo login from `.env` |
| Prometheus | http://localhost:9090 | Metrics and queries |
| Grafana | http://localhost:3000 | Dashboard; demo login from `.env` |

Default credentials and the webhook secret are local demo values only. Never expose these ports to the public internet or reuse the values in a real deployment.

## Send a signed test event

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r app/requirements.txt
python scripts_send_event.py
```

The sample sender posts a signed `IN_TRANSIT` event to the API. Change the event data in `scripts_send_event.py` to test other shipment statuses. You can also submit through `/docs`, but the HMAC header must be generated correctly; using the sender is easier.

## Query shipment state

```powershell
Invoke-RestMethod http://localhost:8000/v1/shipments/SHIP-1001
Invoke-RestMethod http://localhost:8000/v1/shipments/SHIP-1001/events
```

## Run tests

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r app/requirements-dev.txt
$env:PYTHONPATH="app"
pytest -q
```

## Failure and reliability experiments

1. **Bad signature:** change the secret used by the sender; expect HTTP 401 and no queued message.
2. **Duplicate:** send the same event twice; expect one ledger row and one logical state transition.
3. **Out of order:** send `DELIVERED` with a later timestamp, then `IN_TRANSIT` with an earlier timestamp; current status should remain `DELIVERED`.
4. **Worker retry/DLQ:** edit `.env` to set `SIMULATE_WORKER_FAILURE=true`, then run `docker compose up -d --force-recreate worker`. Send an event and observe retry/DLQ behavior. Restore the value to `false` and recreate the worker again after the test.
5. **Queue backlog:** stop the worker and submit several valid events; observe RabbitMQ queue depth and the Prometheus/Grafana metrics. Restart the worker and monitor drain time.
6. **Restart persistence:** restart containers and confirm that PostgreSQL data and archived JSON files remain in named volumes.

Use the runbook in `docs/OPERATIONS.md` to understand recovery steps.

## Useful commands

```powershell
# View logs
docker compose logs -f api worker

# Restart only worker
docker compose restart worker

# Stop without deleting stored data
docker compose down

# Reset the demonstration environment AND delete all named volumes
# Warning: this removes the database and archive.
docker compose down -v
```

## Six-week plan

1. Week 1: event contract, local setup, basic API and tests.
2. Week 2: RabbitMQ topology, retries, DLQ, and worker.
3. Week 3: PostgreSQL schema, idempotency, ordering, raw archive.
4. Week 4: Prometheus/Grafana, dashboards, alerts, failure-injection tests.
5. Week 5: GitHub Actions CI, code quality, secrets, threat model, documentation.
6. Week 6: load experiments, cost/risk comparison, screenshots, architecture decisions, demo recording.

## Important resume wording

Until you deploy to a real cloud provider, describe this as a **local cloud-native event-processing platform with an AWS migration design**, not as a production AWS deployment. State measured local test results only; do not invent cloud uptime, cost, or throughput numbers.

## Teardown

```powershell
docker compose down -v
```

This removes local containers and named volumes. No cloud resources are created by the supplied Compose file.
