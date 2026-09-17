# Module: `gke`

Regional GKE Standard cluster with Workload Identity — **optional**, default disabled (`enabled=false`). Cloud Run covers all current workloads; this module is the escape hatch for future GPU training pods, batch CronJobs, or anything that needs raw Kubernetes.

When enabled: one regional cluster (`deepcab-gke-${env}`), private nodes with a public endpoint (tighten authorized networks in prod), shielded VMs, a separately-managed default node pool with autoscaling, and deletion protection auto-enabled when `env == "prod"`.

**Gated off in every env today.** When you flip it on, also wire the `vpc` module on and pass `network` / `subnet` from it.

## Cross-repo contract

None today. When activated, the `deploy-gke.yml` workflow in 001-deepCab-api would `kustomize apply` manifests against the cluster endpoint using the deployer SA (which holds `roles/container.admin` via the `wif` module). The `cluster_endpoint` + `cluster_ca_certificate` outputs are what `gcloud container clusters get-credentials` would produce — use them to wire a kubeconfig in CI.

## Inputs (key)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | Module no-op when false. |
| `project_id` | `string` | — | GCP project ID. |
| `region` | `string` | — | Region for the regional cluster. |
| `env` | `string` | — | Environment short name. |
| `cluster_name` | `string` | `deepcab-gke` | Cluster name. |
| `network` / `subnet` | `string` | `""` / `""` | VPC self_link + subnet ID (required when enabled). |
| `release_channel` | `string` | `REGULAR` | GKE release channel. |
| `node_machine_type` | `string` | `e2-standard-2` | Node pool machine type. |
| `min_node_count` / `max_node_count` | `number` | `1` / `3` | Autoscaler bounds per zone. |
| `runtime_sa_email` | `string` | `""` | Runtime SA — bound to GKE workload identity for pods. |
| `enable_workload_identity` | `bool` | `true` | Recommended on. |

## Outputs

| Name | Description |
| --- | --- |
| `enabled` | Whether the module is active. |
| `cluster_name` | Cluster name (empty when disabled). |
| `cluster_endpoint` | **Sensitive.** Public endpoint of the control plane. |
| `cluster_ca_certificate` | **Sensitive.** Base64 CA cert for kubeconfig. |
| `location` | Region the cluster lives in. |

## Example usage

```hcl
# All envs today
module "gke" {
  source     = "../../modules/gke"
  project_id = var.project_id
  region     = var.region
  env        = local.env
  enabled    = false
}

# Hypothetical activation
module "gke" {
  source           = "../../modules/gke"
  project_id       = var.project_id
  region           = var.region
  env              = local.env
  enabled          = true
  network          = module.vpc.network_self_link
  subnet           = module.vpc.subnet_id
  runtime_sa_email = module.wif.runtime_sa_email
}
```

## Consumed by

- `terraform/envs/dev/main.tf` — `enabled = false`.
- `terraform/envs/staging/main.tf` — `enabled = false`.
- `terraform/envs/prod/main.tf` — `enabled = false`.
