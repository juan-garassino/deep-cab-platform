# Module: `cloud_run_service`

Generic Cloud Run **v2** service module. Consolidates the previous
`cloud_run` (api), `cloud_run_website`, `cloud_run_mlflow`, and
`cloud_run_status` modules into one. Each caller passes the variant-specific
image, env vars, command/args, probes, and volumes.

Owns the **service shape** (CPU/memory/scale/env/IAM/probes). For services
whose image is swapped by CI (`001-deepCab-api`, `003-deepCab-website`),
`lifecycle.ignore_changes` keeps TF from reverting `gcloud run services
update --image=...` between plans.

## Inputs (highlights)

| Name | Default | Notes |
|---|---|---|
| `service_name` | — required | Cloud Run service name. |
| `component` | — required | Short label (e.g. `cloud-run-api`, `cloud-run-mlflow`). |
| `image` | — required | Initial image. Overridden by CI on api/website. |
| `service_account_email` | — required | Runtime SA from `wif` module. |
| `cpu` / `memory` | `1` / `512Mi` | |
| `min_instances` / `max_instances` | `0` / `4` | |
| `container_concurrency` | `80` | |
| `timeout_seconds` | `60` | |
| `container_port` | `8000` | Override per service (80 nginx, 5000 mlflow, 3001 kuma). |
| `env_vars` | `{}` | Plain values: `APP_ENV`, `MLFLOW_TRACKING_URI`, etc. |
| `secret_env_vars` | `{}` | `{ENV_VAR = secret_id}` — read from Secret Manager `latest`. |
| `command` / `args` | `null` | Optional entrypoint/args override (mlflow uses bash -c). |
| `volumes` | `[]` | List of `{name, type ("cloud_sql"\|"gcs"), ...}`. |
| `volume_mounts` | `[]` | List of `{name, mount_path}`. |
| `startup_probe_path` | `/healthz` | API uses `/healthz`; website/mlflow/status use `/`. |
| `liveness_probe_path` | `/healthz` | Same. |
| `allow_unauthenticated` | `true` | Public service. |
| `ingress` | `INGRESS_TRAFFIC_ALL` | Tighten with `INTERNAL_ONLY` if fronting via LB. |

## Volumes

The `volumes` input is a list of typed entries. Two types are supported:

```hcl
volumes = [
  {
    name                = "cloudsql"
    type                = "cloud_sql"
    cloud_sql_instances = [module.cloud_sql.connection_name]
  },
  {
    name          = "kuma-data"
    type          = "gcs"
    gcs_bucket    = module.storage.status_state_bucket
    gcs_read_only = false
  },
]

volume_mounts = [
  { name = "cloudsql",  mount_path = "/cloudsql" },
  { name = "kuma-data", mount_path = "/app/data" },
]
```

## Outputs

| Name | Description |
|---|---|
| `service_name` | Pass to `gcloud run services update --image=...`. |
| `service_url` | Stable HTTPS URL. |
| `location` / `latest_revision` | Operational handles. |

## Cross-repo contract (api + website)

The 001/003 deploy workflows run:
```bash
gcloud run services update ${TF_SERVICE_NAME} \
  --image=${GAR_REPO_URL}/<api|website>:${TAG} \
  --region=${REGION} --project=${PROJECT}
```

Nothing else. CPU/memory/env vars/IAM are TF's territory — change them by
editing the env's `main.tf`, opening a PR, getting a TF plan in CI, and merging.

## Migration from the old per-service modules

The previous 4 modules (`cloud_run`, `cloud_run_website`, `cloud_run_mlflow`,
`cloud_run_status`) all wrapped the same `google_cloud_run_v2_service`
resource named `this`. The env compositions use `moved {}` blocks (TF 1.5+)
to point old addresses at the new module instances, so state migrates
cleanly with `terraform plan && terraform apply` — no `terraform state mv`
required.
