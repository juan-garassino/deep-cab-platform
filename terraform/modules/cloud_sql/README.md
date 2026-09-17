# Module: `cloud_sql`

Cloud SQL for PostgreSQL — the MLflow backing store (and optionally a Prefect DB). Per-env tier (`db-f1-micro` in dev, `db-custom-2-4096` in prod), per-env IP mode (public + authorized networks in dev; private IP + Service Networking in staging/prod). Users are created with **randomized passwords** surfaced via the `user_passwords` (sensitive) output, which the env composition writes into Secret Manager (`mlflow-db-password`).

Supports a `showcase_mode` style toggle via `activation_policy` — flip to `NEVER` to stop the instance and bill only storage (~$1/mo) for an idle demo.

## Cross-repo contract

None directly. MLflow (running as a `cloud_run_service`) connects through the Cloud SQL Unix socket mounted at `/cloudsql/<connection_name>` (volume defined on the Cloud Run service), authenticating with the password pulled from Secret Manager.

## Inputs (key)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project_id` | `string` | — | GCP project ID. |
| `region` | `string` | — | Region for the instance. |
| `env` | `string` | — | Environment short name. |
| `instance_name` | `string` | `deepcab-mlflow` | Instance name (globally unique in project). |
| `tier` | `string` | `db-f1-micro` | Machine tier — dev=micro, staging=small, prod=custom-2-4096. |
| `activation_policy` | `string` | `ALWAYS` | `ALWAYS` / `NEVER` / `ON_DEMAND`. Validated. |
| `database_version` | `string` | `POSTGRES_16` | |
| `deletion_protection` | `bool` | `true` | On in prod; off in dev. |
| `use_private_ip` | `bool` | `true` | False in dev (public IP + authorized networks). |
| `private_network` / `private_services_connection` | `string` | `""` | Required when `use_private_ip=true`; comes from `vpc` module. |
| `authorized_networks` | `list(object)` | `[]` | CIDR blocks when running with public IP. |
| `databases` / `users` | `list(string)` | `["mlflow"]` / `["mlflow"]` | Logical DBs and users to create. |
| `enable_prefect_db` | `bool` | `false` | Convenience flag — adds `prefect` to `databases`. |

See `variables.tf` for full list (disk size, backups, labels).

## Outputs

| Name | Description |
| --- | --- |
| `instance_name` | Cloud SQL instance name. |
| `connection_name` | Cloud SQL connection name (for Cloud SQL Proxy / Cloud Run integration). |
| `private_ip_address` | Private IP (empty when public-only). |
| `public_ip_address` | Public IP (empty when private-only). |
| `host` | Best-effort host (private if set, else public). |
| `database_names` | List of databases created. |
| `user_passwords` | **Sensitive** map `username -> generated password`. Push into Secret Manager — do not log. |

## Example usage

```hcl
module "cloud_sql" {
  source     = "../../modules/cloud_sql"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  tier                = "db-f1-micro"
  activation_policy   = var.showcase_mode ? "ALWAYS" : "NEVER"
  deletion_protection = false
  use_private_ip      = false

  authorized_networks = [
    { name = "world-readonly-temp", value = "0.0.0.0/0" },
  ]

  labels = local.common_labels
}
```

## Consumed by

- `terraform/envs/dev/main.tf` — public IP, smallest tier, deletion off.
- `terraform/envs/staging/main.tf` — private IP via VPC.
- `terraform/envs/prod/main.tf` — private IP, prod tier, deletion protection on.
