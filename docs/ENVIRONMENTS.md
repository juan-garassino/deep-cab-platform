# Environments

> **Pre-migration doc (2026-06-07):** GCP project `deepcab-dev` cold-deleted; the staging/prod env tiers are DEPRECATED. Only `dev` is funded under the €25/mo workspace cap, targeting `garassino-ml` / `europe-west1` in show-and-destroy mode. Body below describes the original three-env design — kept as historical narrative.

Three GCP projects, one per env. Same Terraform module set; per-env composition
in `terraform/envs/<env>/`.

## At a glance

| Knob | dev | staging | prod |
|---|---|---|---|
| **Cloud Run CPU/mem** | 1 / 512Mi | 1 / 1Gi | 2 / 2Gi |
| **Cloud Run min/max** | 0 / 2 | 0 / 4 | 1 / 10 |
| **Container concurrency** | 40 | 80 | 80 |
| **Cloud Run Job CPU/mem** | 2 / 4Gi | 4 / 8Gi | 4 / 8Gi |
| **Job timeout** | 1800s | 3600s | 3600s |
| **Job args** | `data=1k` | `data=10k` | `data=full` |
| **Cloud SQL tier** | db-f1-micro | db-g1-small | db-custom-2-4096 |
| **Cloud SQL HA** | ZONAL | ZONAL | REGIONAL + PITR |
| **Cloud SQL networking** | public IP | private IP | private IP |
| **Backups retained** | 7 | 7 | 14 |
| **VPC** | disabled | enabled | enabled |
| **DNS** | disabled | optional | enabled |
| **GKE** | disabled | disabled | gated by `enable_gke` |
| **Cloud Scheduler** | paused | active | active |
| **Budget alert** | none | none | $200/mo |
| **Deployer roles** | broad defaults | broad defaults | tightened (no `roles/editor`) |

## URLs (after first apply)

| Env | API URL | MLflow URL |
|---|---|---|
| dev | https://deepcab-api-<hash>-uc.a.run.app | http://mlflow.dev.deepcab.local:5000 (in-cluster only) |
| staging | https://deepcab-api-<hash>-uc.a.run.app (or api.staging.deepcab.com if DNS enabled) | https://mlflow.staging.deepcab.com |
| prod | https://api.deepcab.com (if DNS enabled) | https://mlflow.deepcab.com |

## Who can deploy

| Env | Who | Mechanism |
|---|---|---|
| dev | any contributor | `make ENV=dev plan/apply` locally OR auto-applied on merge to main |
| staging | platform reviewer | `apply-staging` job requires `staging` env approval in GitHub |
| prod | platform reviewer + on-call | `apply-prod` job requires `prod` env approval + 5-min wait timer |

Configure approvers in: repo Settings → Environments → `staging` / `prod` → Required reviewers.

## Per-env required GitHub variables

For each env (suffix `_DEV`, `_STAGING`, `_PROD`):

```
GCP_PROJECT_<ENV>           # full project ID
GCP_PROJECT_NUMBER_<ENV>    # numeric project number
GCP_REGION_<ENV>            # us-central1
GCP_WIF_PROVIDER_<ENV>      # projects/<n>/locations/global/workloadIdentityPools/github-pool/providers/github-provider
GCP_TERRAFORM_SA_<ENV>      # deepcab-terraform@<project>.iam.gserviceaccount.com
GCP_DEPLOYER_SA_<ENV>       # deepcab-deployer@<project>.iam.gserviceaccount.com  (consumed by 001)
```

Repo secrets:

```
SLACK_WEBHOOK_URL           # optional — Slack notifications from platform-apply
```

## Drift detection

`platform-plan.yml` runs on every PR. A scheduled drift-detection cron (TBD —
weekly Sunday `0 5 * * 0`) can be added by appending a `schedule:` trigger
that posts non-empty plans to Slack instead of a PR comment.

## Cost shapes

See `COSTS.md`.
