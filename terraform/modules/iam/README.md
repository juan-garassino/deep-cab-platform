# Module: `iam`

Cross-cutting IAM escape hatch. Most IAM lives next to the resource that owns it (e.g. the `wif` module owns SA roles; `cloud_run_service` owns its `roles/run.invoker`). This module handles bindings that don't fit cleanly anywhere else — a developer's user account needing `roles/run.viewer`, a Slack incident-bot SA needing `roles/monitoring.viewer`, etc.

Also provisions an optional **billing budget** with 50/90/100% alerts (prod cost guardrail). Budget is a no-op unless all three of `budget_alert_email`, `billing_account`, and `budget_amount_usd` are set.

## Cross-repo contract

None directly. Cross-cutting IAM exists for human and bot identities outside the deepCab service mesh.

## Inputs (key)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project_id` | `string` | — | GCP project ID. |
| `env` | `string` | — | Environment short name. |
| `extra_project_bindings` | `list(object({role, member}))` | `[]` | Extra project-level IAM. Member must be IAM-friendly (`serviceAccount:…`, `user:…`, `group:…`). |
| `budget_alert_email` | `string` | `""` | Email recipient for budget alerts. Empty disables the budget. |
| `budget_amount_usd` | `number` | `0` | Monthly amount in USD. Alerts fire at 50/90/100%. |
| `billing_account` | `string` | `""` | Billing account ID (required when budget is set). |

## Outputs

| Name | Description |
| --- | --- |
| `extras_count` | Number of extra IAM bindings provisioned. |
| `budget_enabled` | Whether a billing budget was provisioned. |

## Example usage

```hcl
# Dev — no extras, no budget
module "iam" {
  source     = "../../modules/iam"
  project_id = var.project_id
  env        = local.env
}

# Prod — Slack bot read access + $200/mo budget
module "iam" {
  source     = "../../modules/iam"
  project_id = var.project_id
  env        = local.env

  extra_project_bindings = [
    { role = "roles/monitoring.viewer", member = "serviceAccount:slack-bot@..." },
  ]

  budget_alert_email = "ops@deepcab.com"
  budget_amount_usd  = 200
  billing_account    = var.billing_account
}
```

## Consumed by

- `terraform/envs/dev/main.tf` — bindings only, no budget.
- `terraform/envs/staging/main.tf` — same.
- `terraform/envs/prod/main.tf` — budget guardrail enabled.
