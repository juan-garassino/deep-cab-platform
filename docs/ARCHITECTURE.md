# Architecture

## Cross-repo split

```
┌────────────────────────────────────────────┐         ┌────────────────────────────────────────────┐
│ 001-deepCab-api                            │         │ 002-deepCab-platform   (THIS REPO)         │
│ ─────────────────                          │         │ ───────────────────────                    │
│ Owns: Dockerfile, source code, image build │   gcloud│ Owns: GCP shape (Terraform)                │
│                                            │ run     │       - Artifact Registry repo             │
│ CI:                                        │ services│       - Cloud Run service spec             │
│   build → push to Artifact Registry        │ update  │       - Cloud Run Job spec                 │
│   gcloud run services update --image=…  ───┼────────▶│       - Cloud Scheduler                    │
│   gcloud run jobs update --image=…         │         │       - Cloud SQL                          │
│                                            │         │       - GCS buckets                        │
│ Local: docker-compose, pytest              │         │       - Secret Manager containers          │
│                                            │         │       - WIF Pool + Provider + 4 SAs        │
│                                            │         │       - VPC, DNS, GKE (gated)              │
│                                            │         │ CI: terraform plan (PR) + apply (main)     │
└────────────────────────────────────────────┘         └────────────────────────────────────────────┘
```

The 001 repo's CI pipeline is **image-only updates**. It never replaces a Cloud
Run service spec from YAML, never creates IAM bindings, never provisions GCS
buckets. That work is all in Terraform here in 002.

## Why split?

1. **Different blast radius** — touching app code shouldn't be able to corrupt cloud shape.
2. **Different change rate** — app changes ship multiple times per day; cloud shape
   changes once a week or less.
3. **Different reviewer set** — app PRs need a backend reviewer; platform PRs
   need an SRE/platform reviewer who reads TF plans.
4. **Different secret scope** — the deployer SA used by 001 has narrow roles
   (run.developer + artifactregistry.writer); the terraform SA used by 002 has
   broad admin roles. Keeping them in separate repos limits the attack surface
   of either compromise.

## Data flow

```
┌──────────────┐    POST /predict     ┌──────────────────┐
│  client      │ ───────────────────▶│  Cloud Run        │
└──────────────┘                     │  deepcab-api      │
                                     │  (env vars +      │
                                     │   secret mounts)  │
                                     └─────┬────────┬────┘
                                           │        │
                          model load       │        │ mlflow track
                                           ▼        ▼
                                ┌──────────┐  ┌───────────────────┐
                                │  GCS     │  │  Cloud SQL        │
                                │  models  │  │  Postgres (mlflow)│
                                └──────────┘  └───────────────────┘

   Cloud Scheduler (02:00 UTC)
        │ POST /apis/run.googleapis.com/.../jobs/deepcab-retrain:run
        ▼
   Cloud Run Job  ───▶ trains model ───▶ writes to gs://${models_bucket}
                                  └────▶ logs run to MLflow (Cloud SQL)
```

## CI/CD flow

```
┌─────────────────────┐
│ Developer opens PR  │
│ to 002 (terraform)  │
└─────────┬───────────┘
          │ paths: terraform/**
          ▼
┌─────────────────────────────────┐
│ platform-plan.yml               │
│   matrix [dev, staging, prod]   │
│   → terraform init + plan       │
│   → post plan as PR comment     │
└─────────┬───────────────────────┘
          │ merge to main
          ▼
┌─────────────────────────────────┐
│ platform-apply.yml              │
│   apply-dev      (env: dev)     │
│     ↓ (manual approval)         │
│   apply-staging  (env: staging) │
│     ↓ (manual approval)         │
│   apply-prod     (env: prod)    │
│   → Slack notify                │
└─────────────────────────────────┘
```

## Bootstrap dependency graph (one-time per env)

```
deepcab-platform bootstrap --env <env>       (creates project + billing + state bucket + WIF + terraform SA)
    ↓
deepcab-platform sync-gh                      (uploads GitHub Actions vars + secrets)
    ↓
deepcab-platform tf apply --env <env>         (auto-init; provisions:
                                                wif → gar → storage → secret_manager →
                                                vpc → cloud_sql →
                                                cloud_run_service ×4 (api, website, mlflow, status) →
                                                cloud_run_job → scheduler)
    ↓
manual: populate secrets via `gcloud secrets versions add …`
    ↓
deepcab-platform kuma seed                    (Wave 4 — pre-populates the status page from monitors.yaml)
    ↓
manual: push first v0.1.0 tag in 001 → api image lands in GAR; push first v0.1.0 tag in 003 → website image lands in GAR
    ↓
deepcab-platform tf apply --env <env>         (Cloud Run services pick up real images; idempotent re-run)
    ↓
manual: hit Cloud Run URLs (api + website + mlflow + status) → done
```

## The `deepcab-platform` CLI layer

Wave 3 introduced a Python CLI that wraps every step of the bootstrap +
day-2 ops flow. Same three-layer pattern as 001's `api/services/` +
`api/providers.py`:

```
┌────────────────────────────────────────────────────────────────┐
│  deepcab_platform/cli/         Typer surface; --dry-run flag   │
│   bootstrap.py  sync_gh.py  mlflow.py  showcase.py             │
│   kuma.py       tf.py        status.py                         │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               ▼  (DI via deepcab_platform/deps.py)
┌────────────────────────────────────────────────────────────────┐
│  deepcab_platform/services/   @dataclass services; no I/O      │
│   BootstrapService    SyncGhService    MlflowMirrorService     │
│   ShowcaseService     KumaSeedService  TerraformService        │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────┐
│  deepcab_platform/providers/  Protocol + Real + DryRun impls   │
│   GcloudProvider  GhProvider  TerraformProvider  HttpProvider  │
└────────────────────────────────────────────────────────────────┘
```

- Every subcommand is env-aware via `DEEPCAB_ENV` (or legacy `APP_ENV`),
  read by `deepcab_platform/schemas/settings.py` (pydantic-settings).
- `ProviderMode.DRY_RUN` swaps every Real impl for its DryRun counterpart
  in one go — tests and `--dry-run` use the same machinery.
- Pydantic-typed inputs/outputs (`BootstrapInputs`, `BootstrapResult`,
  `KumaSeedConfig`, `GhSyncResult`) catch malformed configs before any
  external call.

See [`docs/CLI.md`](./CLI.md) for the per-subcommand reference.

## Terraform module consolidation (Waves 1–2)

The module tree was simplified twice during the polish pass:

- **Wave 2 / S1**: the four specialized Cloud Run modules
  (`cloud_run`, `cloud_run_website`, `cloud_run_mlflow`, `cloud_run_status`)
  were collapsed into a single generic `terraform/modules/cloud_run_service/`,
  instantiated once per workload (api / website / mlflow / status). Same
  `lifecycle.ignore_changes = [template[0].containers[0].image]` contract
  applies to all four.
- **Wave 2 / S3**: the `{env, managed, component}` label block that every
  module used to inline is now a shared `terraform/modules/_labels/` —
  consumed by `storage`, `secret_manager`, and (going forward) every new
  module.

Net module count: 12 (v1) → 15 (after mlflow + status + website) → **13**
(after consolidation; `_labels` added but 4 cloud_run flavours collapsed).
