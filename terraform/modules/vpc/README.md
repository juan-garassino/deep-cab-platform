# Module: `vpc`

Custom-mode VPC with a single regional subnet, an optional Cloud NAT for outbound internet from private workloads, and a Service Networking peering reservation (reserved global address + `service_networking_connection`) for Google-managed services that need private IP (Cloud SQL, Memorystore, etc.).

**Gated off in dev** (`enabled = false`) — dev Cloud SQL uses public IP with authorized networks to keep the bill near zero. Staging/prod flip it on so Cloud SQL can run with private IP only.

## Cross-repo contract

None directly. The VPC outputs feed `cloud_sql` (`private_network`, `private_services_connection`) and `gke` (`network`, `subnet`) when those modules are enabled.

## Inputs (key)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | `true` | Module is a no-op when false. |
| `project_id` | `string` | — | GCP project ID. |
| `region` | `string` | — | Primary region. |
| `env` | `string` | — | Environment short name. |
| `network_name` | `string` | `deepcab-vpc` | VPC network name. |
| `subnet_cidr` | `string` | `10.20.0.0/20` | Primary subnet CIDR (Cloud Run direct VPC egress / GKE nodes). |
| `private_services_cidr` | `string` | `10.30.0.0/16` | CIDR reserved for Google-managed services (Cloud SQL private IP). |
| `enable_nat` | `bool` | `true` | Provision Cloud NAT for outbound internet from private workloads. |

## Outputs

| Name | Description |
| --- | --- |
| `enabled` | Whether the VPC module actually provisioned anything. |
| `network_id` | Full ID of the VPC network (empty when disabled). |
| `network_self_link` | Self-link of the VPC network. |
| `subnet_id` | ID of the primary regional subnet. |
| `private_services_connection` | Service Networking connection ID (input for Cloud SQL private IP). |

## Example usage

```hcl
# Dev — disabled
module "vpc" {
  source     = "../../modules/vpc"
  project_id = var.project_id
  region     = var.region
  env        = local.env
  enabled    = false
}

# Prod — enabled, downstream wires to cloud_sql
module "vpc" {
  source     = "../../modules/vpc"
  project_id = var.project_id
  region     = var.region
  env        = local.env
  enabled    = true
}

module "cloud_sql" {
  # ...
  use_private_ip              = true
  private_network             = module.vpc.network_self_link
  private_services_connection = module.vpc.private_services_connection
}
```

## Consumed by

- `terraform/envs/dev/main.tf` — `enabled = false`.
- `terraform/envs/staging/main.tf` — `enabled = true`, feeds Cloud SQL private IP.
- `terraform/envs/prod/main.tf` — `enabled = true`, feeds Cloud SQL private IP.
