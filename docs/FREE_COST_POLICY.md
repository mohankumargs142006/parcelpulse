# How this edition stays free

This package is intentionally local-first. No commands in `docker-compose.yml` create cloud resources. Application containers, PostgreSQL, RabbitMQ, Prometheus and Grafana run on the user's own computer.

## Expected direct cost

- Cloud infrastructure: $0 because none is provisioned.
- Paid API usage: $0; no paid external API is called.
- Source control and CI: public GitHub repositories can use standard GitHub-hosted Actions runners at no charge under GitHub's current policy. Private repo quotas can vary by plan.
- Docker Desktop: Docker Personal is $0 for individual use and education within the current Docker terms.
- Local storage/CPU/electricity and internet access: supplied by the user; these are not cloud service charges.

## Do not do these if a $0 bill is mandatory

- Do not run `terraform apply` against AWS/Azure/GCP.
- Do not add an AWS access key or cloud deployment secrets to GitHub.
- Do not select paid hosting, managed databases, paid APIs, premium monitoring, or trial plans that auto-convert to paid subscriptions.
- Do not assume a provider's free tier protects against every billable resource, region, or overage.

## Current official pricing references

- Docker Personal: https://www.docker.com/products/personal/
- GitHub Actions billing: https://docs.github.com/en/billing/managing-billing-for-your-products/about-billing-for-github-actions
- AWS Free Tier terms (for later reference only): https://aws.amazon.com/free/free-tier-faqs/
- Google Cloud Free Program (for later reference only): https://cloud.google.com/free/docs/free-cloud-features

A cloud-hosted deployment cannot be guaranteed to cost exactly $0 across every account and region. This local version is the safe option when zero cloud charges is a strict requirement.
