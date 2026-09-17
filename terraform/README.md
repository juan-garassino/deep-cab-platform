# `terraform/` — deepCab IaC

Layered Terraform tree that provisions the entire GCP shape of deepCab.
The 001 (API) repo never `gcloud`'s anything about service shape; it only
builds + pushes images and does `gcloud run services update --image=...`.
Every other knob lives here.

## Layout

```
terraform/
├── modules/         # reusable building blocks (provider versions pinned per module)
└── envs/
    ├── _shared/     # env_config.tf — canonical per-env config map (data-only)
    │                #   (tiers, CIDRs, role lists, instance counts, paused flags)
    ├── dev/         # composition: instantiates modules for this env
    ├── staging/
    └── prod/
```

`envs/_shared/env_config.tf` is the single source of truth for everything that
varies per env (Cloud SQL tier, scaling, IAM role lists, scheduler paused, VPC
CIDRs, DNS/GKE toggles, budget, storage force_destroy). It is a pure-data module
exposing `module.env_config.cfg`. The design intent is that each env's `main.tf`
reads `module "env_config" { source = "../_shared"; env = local.env }` and threads
`local.cfg.<module_key>.*` into each downstream module — the caller-supplied env
override lands last, so it wins.

> Note: the env `main.tf` files still carry inlined literals; rewiring each env to
> consume `local.cfg.*` is a deliberate follow-up (deferred so it wouldn't collide
> with the `cloud_run_service` module consolidation). Until then, treat
> `env_config.tf` as the intended source of truth and keep the two in sync when you
> touch a per-env value. Truly per-env operator-supplied values (project IDs,
> project numbers, DNS zone names, images) stay in `terraform.tfvars` /
> `variables.tf`.

## Modules

| Module | Resource(s) | Status |
|---|---|---|
| `_labels` | Shared `{env, managed, component}` label assembler (Wave 2 / S3) — no resources, pure HCL locals | helper (consumed by `storage`, `secret_manager`, ...) |
| `gar` | Artifact Registry repo (with cleanup policies) | always-on |
| `storage` | 3 GCS buckets (mlflow, models, tfstate) | always-on |
| `cloud_sql` | Cloud SQL Postgres + databases + users | always-on |
| `secret_manager` | Secret containers + accessor IAM | always-on |
| `wif` | Workload Identity Pool + Provider + 4 SAs + bindings | always-on |
| `cloud_run_service` | Generic `google_cloud_run_v2_service` (Wave 2 / S1) — instantiated once per workload: api, website, mlflow, status. Replaces the former `cloud_run`, `cloud_run_website`, `cloud_run_mlflow`, `cloud_run_status` quartet. | always-on |
| `cloud_run_job` | `deepcab-retrain` job (v2) | always-on |
| `scheduler` | Cloud Scheduler firing the job | always-on |
| `vpc` | VPC + Cloud NAT + private services connection | gated (`enabled = false` in dev) |
| `gke` | GKE Standard cluster + node pool | gated (`enabled = false` default) |
| `dns` | Managed zone records | gated (empty `zone_name` disables) |
| `iam` | Cross-cutting bindings + billing budget | always-on (mostly no-ops without inputs) |

Total: **13 modules** (12 resource-bearing + 1 `_labels` helper). All four
former `cloud_run_*` flavours now share the single `cloud_run_service`
module, each declared once per env in `envs/<env>/main.tf`.

## Envs

The canonical per-env values live in `envs/_shared/env_config.tf` (see above).
When changing a tier, instance count, or role list, update that map — and, until
the env `main.tf` files are rewired to read `local.cfg.*`, mirror the change in
the matching env `main.tf`.

| Env | API (Cloud Run) | Website (Cloud Run) | Cloud SQL | VPC | DNS | GKE | Budget |
|---|---|---|---|---|---|---|---|
| `dev` | cpu=1 mem=512Mi min=0 max=2 | cpu=1 mem=256Mi min=0 max=2 | db-f1-micro, public IP | disabled | disabled | disabled | none |
| `staging` | cpu=1 mem=1Gi min=0 max=4 | cpu=1 mem=256Mi min=1 max=4 | db-g1-small, private IP | enabled | optional | disabled | none |
| `prod` | cpu=2 mem=2Gi min=1 max=10 | cpu=1 mem=512Mi min=2 max=10 | db-custom-2-4096, HA + PITR | enabled | enabled | optional | $200/mo alert |

## Quickstart

```bash
# From repo root:
make ENV=dev plan
make ENV=dev apply

# Each env has its own state bucket — see RUNBOOK.md for the one-time
# bootstrap (chicken-and-egg: bucket must exist before `terraform init`).
```

## Editing modules

1. Make the change in `modules/<m>/`.
2. `make fmt` (terraform fmt -recursive).
3. `make validate` to verify each env still validates.
4. Open a PR — `.github/workflows/platform-plan.yml` posts the plan per env.
5. Merge to main — `.github/workflows/platform-apply.yml` applies in order
   dev → staging → prod (with manual approval gates).

## Editing envs

`envs/<env>/main.tf` composes the modules. `envs/<env>/terraform.tfvars` provides
the per-env values (project ID, project number, image tags, DNS zone, etc.).
Never commit real secrets here — those live in Secret Manager.
