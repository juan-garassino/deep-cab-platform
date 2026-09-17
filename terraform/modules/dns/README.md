# Module: `dns`

Cloud DNS — **optional**, default disabled. Provisions (or references) a managed zone and a map of A/CNAME records pointing at Cloud Run services (typically `ghs.googlehosted.com` for domain mappings). Module is a no-op when `enabled=false` or `zone_name=""`.

**Gated off in dev** — dev uses the raw `*.run.app` Cloud Run URLs. Staging/prod can be flipped on to manage `api.[staging.]deepcab.com` and friends.

## Cross-repo contract

None directly — DNS is purely about exposing platform URLs at custom hostnames. The 001/003 services keep getting their `*.run.app` URLs swapped by CI; this module just adds friendly aliases on top.

## Inputs (key)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `enabled` | `bool` | `false` | Module no-op when false (or zone_name empty). |
| `project_id` | `string` | — | GCP project ID. |
| `env` | `string` | — | Environment short name. |
| `zone_name` | `string` | `""` | Managed zone name (e.g. `deepcab-com`). |
| `dns_name` | `string` | `""` | DNS name with trailing dot (e.g. `deepcab.com.`). |
| `create_zone` | `bool` | `false` | If true, create the zone; else look up an existing one. |
| `records` | `map(object)` | `{}` | Map of `subdomain -> { type, ttl, rrdatas }`. |

## Outputs

| Name | Description |
| --- | --- |
| `enabled` | Whether DNS records were actually managed. |
| `zone_name` | Effective managed zone name (created or referenced). |
| `record_names` | Fully-qualified DNS record names that were managed. |

## Example usage

```hcl
# Dev — disabled
module "dns" {
  source     = "../../modules/dns"
  project_id = var.project_id
  env        = local.env
  enabled    = false
}

# Prod — manage api.deepcab.com → Cloud Run
module "dns" {
  source      = "../../modules/dns"
  project_id  = var.project_id
  env         = local.env
  enabled     = true
  zone_name   = "deepcab-com"
  dns_name    = "deepcab.com."
  create_zone = false

  records = {
    "api" = {
      type    = "CNAME"
      ttl     = 300
      rrdatas = ["ghs.googlehosted.com."]
    }
  }
}
```

## Consumed by

- `terraform/envs/dev/main.tf` — `enabled = false`.
- `terraform/envs/staging/main.tf` — optional zone for `api.staging.deepcab.com`.
- `terraform/envs/prod/main.tf` — optional zone for `api.deepcab.com`.
