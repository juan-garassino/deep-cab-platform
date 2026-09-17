# Module: `secret_manager`

Provisions a fixed list of Secret Manager secrets (no initial values — values are pushed separately via `gcloud secrets versions add` or by adjacent TF resources like the env composition's `google_secret_manager_secret_version "mlflow_db_password"`). Grants the runtime SA `roles/secretmanager.secretAccessor` on each secret so Cloud Run can mount them as env vars.

## Cross-repo contract

001-deepCab-api Cloud Run services reference these secret IDs in their `secret_env_vars` map. Adding a new secret is a 2-step PR:

1. Append to `secret_ids` here, apply.
2. Reference the new ID in the consumer's `secret_env_vars` (in the env's `main.tf`).

## Inputs (key)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project_id` | `string` | — | GCP project ID. |
| `region` | `string` | — | Region for the user-managed replica policy. |
| `env` | `string` | — | Environment short name. |
| `runtime_sa_email` | `string` | — | Runtime SA granted `secretAccessor` on every secret. |
| `secret_ids` | `list(string)` | `["slack-webhook-url", "openai-api-key", "deepcab-api-key", "kuma-admin-password", "neon-deepcab-dsn"]` | Secret IDs to provision. |
| `labels` | `map(string)` | `{}` | Labels applied to each secret. |

## Outputs

| Name | Description |
| --- | --- |
| `secret_ids` | Provisioned secret IDs. |
| `secret_names` | Map `secret_id -> fully-qualified resource name`. |

## Populate after `terraform apply`

```bash
echo -n "https://hooks.slack.com/..." | gcloud secrets versions add slack-webhook-url --data-file=- --project=$PROJECT
echo -n "sk-..."                       | gcloud secrets versions add openai-api-key   --data-file=- --project=$PROJECT
openssl rand -hex 32 | tr -d '\n'      | gcloud secrets versions add deepcab-api-key  --data-file=- --project=$PROJECT
```

The `kuma-admin-password` is auto-populated by an adjacent TF resource in the env composition. The `neon-deepcab-dsn` is populated manually after one-time Neon project provisioning (see `docs/RUNBOOK.md §1.7`).

## Example usage

```hcl
module "secrets" {
  source           = "../../modules/secret_manager"
  project_id       = var.project_id
  region           = var.region
  env              = local.env
  runtime_sa_email = module.wif.runtime_sa_email

  labels = local.common_labels
}
```

## Consumed by

- `terraform/envs/dev/main.tf` — full secret set; mlflow + kuma passwords auto-populated.
- `terraform/envs/staging/main.tf` — same set.
- `terraform/envs/prod/main.tf` — same set; values rotated manually.
