# AWS mapping: local demo to cloud architecture

This document helps explain the architecture without provisioning paid cloud resources. **Do not claim the local edition is deployed on AWS.**

| Local component | AWS counterpart | What changes in a real deployment |
|---|---|---|
| FastAPI webhook service | Amazon API Gateway + AWS Lambda (or ECS/Fargate) | Use HTTPS endpoint, private networking where appropriate, and an AWS-managed secret; replace local demo HMAC key. |
| RabbitMQ main/retry/DLQ queues | Amazon SQS Standard + redrive policy/DLQ | Change the publisher/consumer adapter to the SQS SDK; choose Standard or FIFO based on ordering/deduplication requirements. |
| PostgreSQL event ledger/current state | Amazon DynamoDB, or Amazon RDS PostgreSQL | Choose based on query patterns, transactional needs, and operating overhead; keep event idempotency atomic. |
| Local JSON archive volume | Amazon S3 with SSE-S3 or SSE-KMS | Use private bucket policies, lifecycle retention, versioning if justified, and deterministic event keys. |
| Prometheus + Grafana | Amazon CloudWatch metrics/logs/alarms/dashboard (or self-managed observability) | Configure retention, alarms, sampling and dimensions intentionally to control cost. |
| Docker Compose | Terraform for AWS resources; Compose remains a local developer environment | Store Terraform state securely; review `plan`; use least-privilege IAM and GitHub OIDC rather than long-lived access keys. |
| GitHub Actions CI | GitHub Actions CI/CD | Public repository standard runners are free; cloud deployment credentials are unnecessary for this local-only workflow. Add OIDC only if/when deploying. |

## Interview discussion points

- RabbitMQ makes retry routing visible; SQS reduces broker operations in the AWS version.
- PostgreSQL provides flexible relational querying; DynamoDB can simplify scaling for key-based event/state access, but requires careful key design.
- Current-state updates are conditional on `occurred_at` so stale events cannot overwrite newer state.
- The raw archive and database are not one distributed transaction. Retrying with deterministic archive keys is helpful, but production requires a documented reconciliation strategy.
- The local environment is reproducible and free of cloud charges, but does not validate IAM, cloud network design, managed-service quotas, or provider-specific operational behavior.

## Optional cloud deployment later

Only after completing and documenting the local tests, you may choose a cloud provider's free usage allowances. Check the provider's current pricing for your account, region, storage, egress and observability. Free allowance does not guarantee a $0 bill; do not deploy if zero cost is a strict requirement.
