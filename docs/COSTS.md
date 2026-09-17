# Cost estimates

> **Pre-migration doc (2026-06-07):** GCP project `deepcab-dev` cold-deleted; numbers below describe the original three-env design. Current reality: only `dev` runs (in `garassino-ml` / `europe-west1`) under the **€25/mo workspace cap**, in show-and-destroy mode — true idle cost is ≈ €0/mo, demo runs incur Cloud Run / Cloud SQL for the duration of `make showcase_up`.

Back-of-napkin monthly cost per env. Real cost depends on traffic, idle time, and
how aggressive the retrain schedule is. Numbers below assume `us-central1`,
moderate dev usage (a few hundred predictions per day), and a single nightly
retrain job.

> **All numbers are estimates.** Always cross-check with the GCP Pricing Calculator
> against your specific workload before claiming a budget commitment.

## dev — ~$5-15/month idle

| Resource | Spec | ~Cost/mo |
|---|---|---|
| Cloud Run service | min=0, ~10k requests/mo | $0-2 (well under free tier) |
| Cloud Run Job | manual runs only (scheduler paused) | $0-1 |
| Cloud SQL | db-f1-micro, ZONAL, public IP | $7-8 |
| GCS buckets | < 1GB total | $0.02 |
| Artifact Registry | < 5GB | $0.50 |
| Secret Manager | 4 secrets x 1 version | free tier |
| Workload Identity | — | free |
| Cloud Scheduler | 0 active jobs | free |
| **Total** | | **~$8-12/mo** |

## staging — ~$20-40/month

| Resource | Spec | ~Cost/mo |
|---|---|---|
| Cloud Run service | min=0, ~100k requests/mo | $1-3 |
| Cloud Run Job | nightly, ~10 min @ 4cpu/8Gi | $3-5 |
| Cloud SQL | db-g1-small, ZONAL, private IP | $13-15 |
| VPC + Cloud NAT | 1 NAT gateway | $1-3 (NAT is the bulk) |
| GCS | < 10GB | $0.20 |
| Artifact Registry | < 10GB | $1 |
| Cloud Scheduler | 1 job (free tier) | $0 |
| **Total** | | **~$22-30/mo** |

## prod — ~$50-150/month (no traffic)

| Resource | Spec | ~Cost/mo |
|---|---|---|
| Cloud Run service | min=1 (always warm) cpu=2 mem=2Gi | $25-40 |
| Cloud Run Job | nightly, ~30 min @ 4cpu/8Gi | $8-15 |
| Cloud SQL | db-custom-2-4096, REGIONAL HA + PITR | $80-100 |
| VPC + Cloud NAT | 1 NAT gateway | $3-8 |
| GCS | < 100GB w/ COLDLINE archival | $1-3 |
| Artifact Registry | < 20GB | $2 |
| Cloud Scheduler | 1 active job | free |
| Cloud Logging + Monitoring | std volume | $0-10 |
| **Total (no real traffic)** | | **~$120-180/mo** |

> **The HA Cloud SQL is the cost driver in prod.** Halve the cost by dropping to
> ZONAL availability + db-custom-1-3840 (~$40-50/mo total). Tune in
> `terraform/envs/prod/main.tf` → `module.cloud_sql.tier` + the underlying
> `availability_type` override.

## Cost guardrails

- **`prod` budget alert**: $200/mo via `terraform/modules/iam` (configure
  `budget_alert_email` + `billing_account` in `terraform/envs/prod/terraform.tfvars`).
- **GAR cleanup policies**: prune untagged images after 7 days; keep ≤10 versions per package.
- **GCS lifecycle**: mlflow artifacts → NEARLINE after 30 days; models → COLDLINE after 90 days.
- **Cloud Run min=0**: dev + staging scale to zero between requests.

## What is NOT in these numbers

- Egress (data leaving GCP): negligible for an API that ships small JSON.
- GKE: gated off. When enabled, add ~$70/mo for the control plane + ~$25/node-month.
- DNS: Cloud DNS is $0.20/zone/month + $0.40 per million queries — well under $1.
- Sustained use / committed use discounts: not modeled.
- Free trial credits ($300 over 90 days for new GCP accounts).
