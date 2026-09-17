# Module: `cloud_run_job`

Cloud Run **v2** Job for the nightly deepCab retrain. Same container image as the `cloud_run_service` api, just a different entrypoint (`python -m deepCab.training.train`). The job is wired to be triggered by the `scheduler` module — this module also binds `roles/run.invoker` on itself to the scheduler SA so Cloud Scheduler can fire it.

## Cross-repo contract

001-deepCab-api CI builds the image, pushes to GAR, then runs:

```bash
gcloud run jobs update ${JOB_NAME} \
  --image=${GAR_REPO_URL}/api:${TAG} \
  --region=${REGION} --project=${PROJECT}
```

`lifecycle.ignore_changes` covers `containers[0].image` so TF does not revert the CI image swap on the next plan. Shape (CPU/memory/args/env) is TF-owned — change it via a PR against the env's `main.tf`.

## Inputs (key)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project_id` | `string` | — | GCP project ID. |
| `region` | `string` | — | Region for the job. |
| `env` | `string` | — | Environment short name (dev/staging/prod). |
| `image` | `string` | — | Initial image; overwritten by CI on every deploy. |
| `service_account_email` | `string` | — | Runtime SA (from `wif` module). |
| `scheduler_sa_email` | `string` | — | Scheduler SA — granted `run.invoker` on this job. |
| `job_name` | `string` | `deepcab-retrain` | Cloud Run Job name. |
| `command` / `args` | `list(string)` | `["python"]` / `[-m, deepCab.training.train, backend=tf_mlp, data=full]` | Entrypoint override. |
| `cpu` / `memory` | `string` | `4` / `8Gi` | Per-task limits. |
| `task_timeout_seconds` | `number` | `3600` | Per-task wall-clock. |
| `env_vars` / `secret_env_vars` | `map(string)` | `{}` | Plain + Secret-Manager-backed env vars. |
| `cloudsql_instances` | `list(string)` | `[]` | Optional Cloud SQL connections mounted at `/cloudsql`. |

See `variables.tf` for the full list (parallelism, task_count, max_retries, labels).

## Outputs

| Name | Description |
| --- | --- |
| `job_name` | Cloud Run Job name. |
| `job_id` | Fully-qualified job resource ID. |
| `location` | Region the job lives in. |
| `execute_uri` | HTTPS URI used by Cloud Scheduler to fire the job. |

## Example usage

```hcl
module "cloud_run_job" {
  source     = "../../modules/cloud_run_job"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  image                 = var.retrain_image
  service_account_email = module.wif.runtime_sa_email
  scheduler_sa_email    = module.wif.scheduler_sa_email

  cpu                  = "2"
  memory               = "4Gi"
  task_timeout_seconds = 1800

  args = ["-m", "deepCab.training.train", "backend=tf_mlp", "data=1k"]

  env_vars = {
    APP_ENV             = "dev"
    MLFLOW_TRACKING_URI = module.cloud_run_mlflow.service_url
    REGISTRY_GCS_BUCKET = module.storage.models_bucket
  }

  secret_env_vars = { MLFLOW_DB_PASSWORD = "mlflow-db-password" }

  depends_on = [module.secrets]
}
```

## Consumed by

- `terraform/envs/dev/main.tf` — `data=1k` smoke retrain, scheduler paused.
- `terraform/envs/staging/main.tf` — larger split, scheduler active.
- `terraform/envs/prod/main.tf` — full retrain, scheduled at 02:00 UTC.
