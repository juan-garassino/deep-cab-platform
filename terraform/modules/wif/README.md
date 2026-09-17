# Module: `wif`

Workload Identity Federation between GitHub Actions and GCP, plus the **four canonical service accounts** every deepCab env uses:

- **`deployer`** — impersonated by 001 + 003 CI to push images to GAR and run `gcloud run services update --image=...`.
- **`runtime`** — attached to Cloud Run services and the retrain Job; holds `secretAccessor`, `storage.objectViewer`, `aiplatform.user`, `cloudsql.client`, etc.
- **`scheduler`** — used by Cloud Scheduler to mint OAuth tokens against the Cloud Run Job `:run` endpoint.
- **`terraform`** — used by THIS platform repo's CI to `terraform plan/apply`. Broad roles — only ever federated to the `platform_gh_repo`.

Federation is scoped per repo: the `deployer` SA is federated to `gh_repo` (001) and `website_gh_repo` (003); the `terraform` SA only to `platform_gh_repo` (002). **No long-lived JSON keys** — OIDC only. All required APIs (IAM, GAR, Cloud Run, GKE, Secret Manager, Scheduler, SQL, Compute) are enabled by this module.

Replaces `001-deepCab-api/infra/gcp/workload-identity/bootstrap.sh`.

## Cross-repo contract

001-deepCab-api and 003-deepCab-website CI authenticate via:

```yaml
- uses: google-github-actions/auth@v2
  with:
    workload_identity_provider: ${{ vars.GCP_WIF_PROVIDER }}
    service_account: ${{ vars.GCP_DEPLOYER_SA }}
```

The provider name comes from `module.wif.provider_name`; the deployer SA email from `module.wif.deployer_sa_email`. Both are surfaced into GitHub repo variables via `scripts/sync-gh-secrets.sh`.

## Inputs (key)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project_id` | `string` | — | GCP project ID. |
| `project_number` | `string` | — | Numeric project number (used in principalSet identifiers). |
| `gh_owner` | `string` | — | GitHub org/user that hosts the API repo. |
| `gh_repo` | `string` | — | 001 API repo name allowed to impersonate the deployer SA. |
| `platform_gh_repo` | `string` | `deepCab-platform` | THIS repo — allowed to run terraform plan/apply. |
| `website_gh_repo` | `string` | `deepCab-website` | 003 website repo — also impersonates the deployer SA. |
| `pool_id` / `provider_id` | `string` | `github-pool` / `github-provider` | WIF pool + provider IDs. |
| `deployer_sa_id` / `runtime_sa_id` / `scheduler_sa_id` / `terraform_sa_id` | `string` | `deepcab-{deployer,runtime,scheduler,terraform}` | SA account IDs. |
| `*_project_roles` | `list(string)` | (see `variables.tf`) | Project-level role bundles. Tune per env — prod should drop `roles/editor`. |

## Outputs

| Name | Description |
| --- | --- |
| `pool_name` | Fully-qualified Workload Identity Pool resource name. |
| `provider_name` | Provider name — value for GH Actions `workload_identity_provider`. |
| `deployer_sa_email` | Deployer SA — `service_account` in GH Actions auth step. |
| `runtime_sa_email` | Runtime SA — attached to Cloud Run services + Job. |
| `scheduler_sa_email` | Scheduler SA — used by `scheduler` module. |
| `terraform_sa_email` | Terraform CI SA — used by this platform repo's workflows. |

## Example usage

```hcl
module "wif" {
  source           = "../../modules/wif"
  project_id       = var.project_id
  project_number   = var.project_number
  gh_owner         = var.gh_owner
  gh_repo          = var.gh_api_repo
  platform_gh_repo = var.gh_platform_repo
  website_gh_repo  = var.gh_website_repo

  labels = local.common_labels
}
```

## Consumed by

- `terraform/envs/dev/main.tf` — every downstream module consumes one of its SA emails.
- `terraform/envs/staging/main.tf` — same.
- `terraform/envs/prod/main.tf` — same; tighten `deployer_project_roles` / `terraform_project_roles`.
