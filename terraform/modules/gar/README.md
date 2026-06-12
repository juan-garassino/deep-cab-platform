# Module: `gar`

Google Artifact Registry **Docker** repository for all deepCab container images — api, retrain job, website, and any mirrored bases (e.g. `mlflow:v2.16.2`). Single repository per env. Must exist before any Cloud Run module can reference an image.

Ships with two opinionated cleanup policies: `keep-tagged-recent` (10 most recent tagged versions per package) and `delete-untagged` (untagged blobs older than 7 days).

## Cross-repo contract

001-deepCab-api and 003-deepCab-website push images here from their CI:

```bash
docker push ${GAR_REPO_URL}/api:${TAG}
docker push ${GAR_REPO_URL}/website:${TAG}
```

`GAR_REPO_URL` = `${region}-docker.pkg.dev/${project_id}/${repo_id}` — exposed as the `repo_url` output and surfaced into GitHub Actions secrets via `scripts/sync-gh-secrets.sh`. The deployer SA from the `wif` module holds `roles/artifactregistry.writer` on the project.

## Inputs (key)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project_id` | `string` | — | GCP project ID hosting the repo. |
| `region` | `string` | — | Region (e.g. `europe-west1`). |
| `repo_id` | `string` | `deepcab` | Repository ID; forms the second path segment of the image URL. |
| `description` | `string` | `deepCab container images (api, retrain job, website)` | Free-form description. |
| `labels` | `map(string)` | `{}` | Labels for cost-allocation. |

## Outputs

| Name | Description |
| --- | --- |
| `repo_id` | Short repository ID. |
| `repo_url` | Docker image URL prefix, e.g. `europe-west1-docker.pkg.dev/PROJECT/deepcab`. |
| `repo_name` | Fully-qualified GAR resource name. |

## Example usage

```hcl
module "gar" {
  source     = "../../modules/gar"
  project_id = var.project_id
  region     = var.region
  labels     = local.common_labels
}
```

## Consumed by

- `terraform/envs/dev/main.tf` — must precede every Cloud Run service module.
- `terraform/envs/staging/main.tf` — same.
- `terraform/envs/prod/main.tf` — same.
