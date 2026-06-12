# Module: `storage`

GCS buckets used across the deepCab platform:

- **`mlflow_artifacts`** — `--default-artifact-root` for the MLflow tracking server; lifecycle to NEARLINE after `mlflow_artifacts_lifecycle_days`.
- **`models`** — trained-model artifacts (`runs/<id>/` mirrored by `deepCab.training.train` via `REGISTRY_GCS_BUCKET`); COLDLINE after `models_archive_days`.
- **`tfstate`** — Terraform remote-state backend for this very repo. Chicken-and-egg: the bucket is created manually during first-time bootstrap (see `docs/RUNBOOK.md`), then imported into state.
- **`status_state`** — gcsfuse-mounted into the Uptime Kuma container at `/app/data` so probe history survives revisions.

Every bucket uses uniform bucket-level access and gets the canonical label block.

## Cross-repo contract

001-deepCab-api's training pipeline writes to `models_bucket` when `REGISTRY_GCS_BUCKET` is set in the Cloud Run Job env. The MLflow server (deployed via `cloud_run_service`) writes artifacts into `mlflow_artifacts_bucket`. Both buckets are granted `roles/storage.objectAdmin` to the runtime SA in the env composition (the module itself does not bind IAM beyond uniform access).

## Inputs (key)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project_id` | `string` | — | GCP project ID. |
| `region` | `string` | — | Single-region location (e.g. `europe-west1`). |
| `env` | `string` | — | Environment short name. |
| `name_prefix` | `string` | `deepcab` | Prefix for unique bucket names. |
| `force_destroy` | `bool` | `false` | Allow `terraform destroy` to wipe non-empty buckets. Dev only. |
| `mlflow_artifacts_lifecycle_days` | `number` | `30` | Days before MLflow artifacts move to NEARLINE. |
| `models_archive_days` | `number` | `90` | Days before model artifacts archive to COLDLINE. |
| `labels` | `map(string)` | `{}` | Labels applied to every bucket. |

## Outputs

| Name | Description |
| --- | --- |
| `mlflow_artifacts_bucket` / `mlflow_artifacts_url` | Name and `gs://` URL of the MLflow artifacts bucket. |
| `models_bucket` / `models_url` | Name and `gs://` URL of the trained-models bucket. |
| `tfstate_bucket` | Name of the Terraform remote-state bucket. |
| `status_state_bucket` | Name of the bucket gcsfuse-mounted into Uptime Kuma. |

## Example usage

```hcl
module "storage" {
  source     = "../../modules/storage"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  force_destroy = true   # dev only — painless iteration

  labels = local.common_labels
}
```

## Consumed by

- `terraform/envs/dev/main.tf` — `force_destroy = true`.
- `terraform/envs/staging/main.tf` — default lifecycles.
- `terraform/envs/prod/main.tf` — long retention, `force_destroy = false`.
