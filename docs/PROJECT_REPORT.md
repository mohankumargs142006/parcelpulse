---
title: "ParcelPulse: Zero-Cost Cloud-Native Shipment Event Platform"
author: "Cloud Engineering Project Guide"
date: "12 October 2026"
geometry: margin=0.7in
toc: true
toc-depth: 2
colorlinks: true
---

# ParcelPulse: Zero-Cost Cloud-Native Shipment Event Platform

**Author:** [Your Name]  
**Duration:** 4-6 weeks  
**Project type:** Cloud engineering / DevOps / platform engineering portfolio  
**Cost model:** $0 cloud resources; local compute only  
**Status:** educational local implementation; not a public-cloud deployment

## Executive summary

ParcelPulse demonstrates a resilient event ingestion platform for logistics updates. External carriers send signed webhook events. The API validates HMAC signatures and the event contract, then acknowledges only after a durable queue publish. A worker processes events asynchronously, stores the history in PostgreSQL, advances current state only when the event is newer, archives each payload to persistent local storage, and exposes metrics. RabbitMQ provides retry and dead-letter paths. Prometheus and Grafana make processing behavior observable. Docker Compose reproduces the environment, while GitHub Actions runs free CI on a public repository.

## Business problem

Synchronous webhook handlers couple external provider reliability to database speed and worker availability. Duplicate deliveries, out-of-order statuses, and transient dependency failures can cause repeated updates, incorrect current state, and hard-to-diagnose failures. ParcelPulse decouples acceptance from processing and makes event history and failure paths visible.

## Architecture

```text
Carrier simulator --HTTPS + HMAC--> FastAPI ingestion API
                                         |
                                  validate and publish
                                         v
                           RabbitMQ durable event queue
                                         |
                         +---------------+----------------+
                         |                                |
                   retry queue (TTL)              dead-letter queue
                         |                                |
                         +---- back to main queue         +--> operator inspection
                                         |
                                         v
                               Python worker service
                                   |           |
                                   v           v
                           PostgreSQL       JSON archive volume
                          event ledger       (persistent volume)
                           current state

Prometheus scrapes API/worker metrics; Grafana visualizes queue and worker behavior.
GitHub Actions runs tests, lint, and container build on pushes/PRs.
```

## Implementation phases

1. **Contract and threat model:** define event ID, shipment ID, enumerated statuses, timezone-aware timestamps, HMAC signature and replay/duplicate assumptions.
2. **Secure intake:** implement raw-body HMAC validation, schema validation, HTTP error behavior and durable queue publishing.
3. **Asynchronous processing:** configure a durable main queue, retry queue with TTL, and DLQ. Use manual acknowledgements only after processing or confirmed retry/DLQ publication.
4. **State and audit:** store unique event IDs in PostgreSQL; reject duplicate state transitions and conditionally advance current state when `occurred_at` is newer. Archive payloads using deterministic names.
5. **Observability:** expose request outcomes, accepted-event counts, processed events, duplicates, worker failures, stale events and DLQ counts. Scrape with Prometheus and visualize in Grafana.
6. **CI and reproducibility:** GitHub Actions installs dependencies, runs Ruff and pytest, then builds the container image. Compose defines the local stack.
7. **Validation and portfolio:** test invalid signatures, duplicates, out-of-order events, worker outage, retry/DLQ routing, backlog drain, restarts and persistence; record observed results.

## Step-by-step development guide (eight phases)

### Phase 1 - Contract and threat model (2-3 days)

**Objective:** define what a valid event is and what must never happen.

**Tasks:** define the JSON schema and version; list accepted shipment statuses; require timezone-aware event timestamps; choose a stable event ID; document the raw-body HMAC format; define HTTP status codes; identify replay, duplicate, out-of-order, malformed-body, queue-outage and database-outage scenarios.

**Tools:** Markdown, Python, pytest. These are free and let the contract be reviewed before any infrastructure is started.

**Pitfalls:** signing parsed/re-serialized JSON instead of the original bytes; accepting naive timestamps; using user-provided IDs directly as filesystem paths; claiming HMAC alone prevents all replay attacks.

### Phase 2 - Secure API intake (3-4 days)

**Objective:** accept only authentic, valid events and publish them durably.

**Tasks:** implement `/v1/shipments/events`; validate `X-Signature-SHA256`; return 401 for invalid signatures and 400 for malformed payloads; publish to the durable RabbitMQ main queue with publisher confirms; respond 202 only after the broker confirms publication; expose `/healthz` and `/metrics`.

**Tools:** FastAPI, Python `hmac`, RabbitMQ and Docker Compose.

**Pitfalls:** logging secrets; returning 202 before queue publication is confirmed; sending credentials in source code; exposing the RabbitMQ management port publicly.

### Phase 3 - Queue, retry and DLQ (3-4 days)

**Objective:** isolate the caller from worker delays and make repeat failures inspectable.

**Tasks:** declare the durable main queue; add a 5-second retry queue with dead-letter routing back to the main queue; carry a bounded retry counter; send repeated failures to a DLQ; acknowledge the original only after a retry/DLQ copy is confirmed.

**Tools:** RabbitMQ management UI and Pika.

**Pitfalls:** infinite requeue loops; acknowledging before confirmed retry publication; retrying poison messages without a remediation plan.

### Phase 4 - Event ledger and shipment state (4-5 days)

**Objective:** retain history without allowing duplicate or stale events to corrupt current state.

**Tasks:** create PostgreSQL tables and indexes; use event ID as a unique idempotency key; write each unique event to the ledger; update shipment state only when the incoming timestamp is newer; persist raw event JSON with a deterministic hash-based filename.

**Tools:** PostgreSQL, psycopg, Docker named volumes and SQL.

**Pitfalls:** treating event time and arrival time as interchangeable; assuming the archive and database form one transaction; ignoring same-ID/different-payload conflicts; using a non-unique idempotency key.

### Phase 5 - Metrics and dashboard (3-4 days)

**Objective:** make the processing path observable.

**Tasks:** expose request result counters, accepted-event counts, worker success/duplicate/failure/stale/DLQ counters; configure Prometheus scrapes; provision a Grafana dashboard; record baseline queue-drain time and failure behavior.

**Tools:** Prometheus and Grafana OSS in local containers.

**Pitfalls:** dashboard without actionable metrics; high-cardinality metric labels such as shipment ID; confusing request acceptance latency with end-to-end processing latency.

### Phase 6 - CI and reproducible environment (2-3 days)

**Objective:** make quality checks repeatable from a clean clone.

**Tasks:** commit the Docker Compose definition; keep `.env` out of Git; add Ruff and pytest; build the app container in GitHub Actions; verify a pull request fails when tests fail; document required ports and RAM.

**Tools:** Git, GitHub Actions, Docker Compose.

**Pitfalls:** committing `.env`; using a private repository then assuming unlimited free CI; confusing CI container build with cloud deployment.

### Phase 7 - Failure injection and security review (4-5 days)

**Objective:** prove the system's behavior under deliberate faults.

**Tasks:** test valid and invalid signatures, malformed schemas, duplicate IDs, out-of-order timestamps, queue outage, worker outage, retry exhaustion, DLQ inspection, container restart, volume persistence and queue backlog drain. Save test output/screenshots.

**Tools:** pytest, PowerShell, RabbitMQ UI, Prometheus, Grafana and Docker logs.

**Pitfalls:** inventing benchmark numbers; testing only the happy path; leaving the failure simulation flag enabled; failing to restore the app after fault injection.

### Phase 8 - Portfolio and AWS migration design (3-4 days)

**Objective:** turn the implementation into interview-ready evidence while staying at $0 cloud spend.

**Tasks:** draw the architecture; record actual test results; write one-page ADRs for RabbitMQ vs SQS, PostgreSQL vs DynamoDB, and local archive vs S3; include threat model, runbook, teardown, trade-offs, and future cloud deployment plan. Do not create AWS resources for this phase.

**Tools:** Markdown, Mermaid/diagram tool, GitHub README, screenshots and Terraform CLI for optional offline syntax/format checks.

**Pitfalls:** representing the local replica as an AWS deployment; copying a public repo without attribution; stating theoretical throughput or cloud cost as measured fact.

## Acceptance checklist

- [ ] Invalid HMAC request returns 401 and does not enqueue an event.
- [ ] Invalid schema returns 400.
- [ ] Valid signed event returns 202 only after queue publication is confirmed.
- [ ] Duplicate event IDs create only one logical history row.
- [ ] An older event cannot overwrite a newer shipment status.
- [ ] Worker retry is bounded and persistent failures are visible in the DLQ.
- [ ] Queue backlog and worker failure metrics appear in Prometheus/Grafana.
- [ ] Containers restart without losing named-volume data.
- [ ] GitHub Actions passes lint, unit tests and container build.
- [ ] The report states this is a local implementation and contains actual measured results only.
- [ ] `docker compose down -v` removes local persisted data when requested; no cloud resources have been created.

## Tool stack and free alternatives

| Tool | Purpose | Cost model |
|---|---|---|
| Python + FastAPI | API and validation | Free/open-source |
| RabbitMQ | Async queue/retries/DLQ | Free/open-source, local container |
| PostgreSQL | Event ledger/current state | Free/open-source, local container |
| Docker Desktop Personal | Local container runtime | Free for individual/student use subject to Docker terms |
| Docker Compose | Local infrastructure definition | Included with Docker Desktop |
| Prometheus | Metrics scraping and time series | Free/open-source |
| Grafana OSS | Dashboard visualization | Free/open-source, local container |
| GitHub Actions | CI checks | Free for public repositories on standard hosted runners under current GitHub policy |
| VS Code + Git | Editing/version control | Free |
| Terraform | Optional cloud IaC practice | Free CLI; no need to create cloud resources for this edition |

## Security controls

- Verify an HMAC-SHA256 signature over the exact raw request bytes using constant-time comparison.
- Reject unsupported status values, malformed identifiers, and timestamps without a timezone.
- Bind demo service ports to localhost only.
- Use local demonstration credentials only; never commit real secrets.
- Run the application as a non-root user inside the container.
- Use durable queues and manual acknowledgements; avoid losing messages during known retry paths.

## Failure modes and trade-offs

- **Duplicate delivery:** unique event ID is the idempotency key. Reused IDs with different payloads should be treated as a producer-contract error.
- **Out-of-order event:** history retains the event, but latest state advances only when the event timestamp is newer.
- **Database outage:** worker fails without acknowledging; it retries with a bounded retry queue and then dead-letters persistent failures.
- **Queue outage:** API returns a retryable error rather than falsely acknowledging the event.
- **Archive/DB partial success:** the file archive and database are not one transaction. Deterministic archive keys make retries idempotent, but reconciliation remains a production requirement.
- **Broker trade-off:** RabbitMQ is useful locally because retries are easy to inspect. On AWS, SQS may reduce operations; FIFO may be appropriate if strict per-shipment ordering is required.

## Results and metrics

Do not invent or pre-fill performance results. After running experiments, include a measured table such as:

| Experiment | Sample size | Observed result | Evidence |
|---|---:|---|---|
| Valid signed events | [N] | [P50/P95 acceptance latency] | [CSV/log/screenshot] |
| Invalid signatures | [N] | [Rejected count] | [test report] |
| Duplicate event replay | [N] | [Unique ledger rows] | [SQL query] |
| Out-of-order delivery | [N] | [Current status remained newest] | [API response] |
| Worker outage and recovery | [duration] | [Backlog drain time] | [Prometheus graph] |
| Retry/DLQ injection | [N] | [Retry attempts, DLQ count] | [RabbitMQ UI/logs] |

## Future enhancements

- Add a restricted DLQ replay CLI with audit logs.
- Detect the same `event_id` arriving with a different payload hash.
- Add schema versioning and compatibility tests.
- Add per-carrier rate limits and replay-window checks.
- Replace local files with S3 and RabbitMQ with SQS in an optional AWS implementation.
- Add Terraform modules and OIDC-based deployment only after estimating and accepting the possible cloud cost.

## Originality disclosure

The queue-worker-database pattern is an established architecture, not a novel invention. Differentiation comes from shipment-specific event validation, HMAC, duplicate/out-of-order handling, bounded retry/DLQ behavior, failure-injection experiments, observability, recovery documentation, and an explicit migration map to AWS managed services. Cite inspiration and document any code copied from a public repository.

## Suggested resume entry

**ParcelPulse - Resilient Event Ingestion Platform (Python, FastAPI, RabbitMQ, PostgreSQL, Docker Compose, Prometheus, Grafana, GitHub Actions)**  
Built a local cloud-native event processing platform with HMAC-secured webhooks, asynchronous queues, idempotent event persistence, out-of-order state protection, bounded retries/DLQ, and metrics dashboards. Automated tests and container builds through GitHub Actions; evaluated failure modes and documented an AWS migration architecture. Add quantitative results only after measuring them.
