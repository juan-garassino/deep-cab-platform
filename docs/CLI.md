# `deepcab-platform` CLI

> **Pre-migration doc (2026-06-07):** GCP project `deepcab-dev` cold-deleted; canonical config is now `garassino-ml` / `europe-west1` (root `CLAUDE.md` § "GCP architecture"). Project IDs and regions below describe pre-migration state — body kept as historical narrative.

Pythonic alternative to the bash scripts under `scripts/`. Same Typer + Pydantic
+ services/providers pattern as the 001 deepCab CLI — every subcommand wraps a
service, every service consumes a provider Protocol, and every provider has
both a `Real` and a `DryRun` implementation.

Shipped in **Wave 3** of the platform refactor. The bash scripts
(`scripts/bootstrap-gcp.sh`, `scripts/sync-gh-secrets.sh`, ...) still exist as
thin backwards-compat shims, but the Makefile targets now route through the
Typer CLI.

---

## Install + invoke

```bash
cd 002-deepCab-platform
uv sync --extra dev                  # one-time — installs the package + pytest/ruff/mypy
uv run deepcab-platform --help       # see subcommands
```

Or via the Makefile (which calls the CLI under the hood):

```bash
make cli                             # → uv run deepcab-platform --help
make status                          # → uv run deepcab-platform status
make bootstrap_gcp ENV=dev           # → uv run deepcab-platform bootstrap ...
make sync_gh                         # → uv run deepcab-platform sync-gh
make mlflow_mirror                   # → uv run deepcab-platform mlflow mirror
make showcase_up / showcase_down     # → uv run deepcab-platform showcase up|down
make kuma_seed                       # → uv run deepcab-platform kuma seed
```

`secrets rotate` has no Makefile alias by design — it's interactive (reads
the new value from stdin or an env var), so calling the CLI directly is
cleaner.

Every subcommand respects `DEEPCAB_ENV` (or legacy `APP_ENV`). See
[`docs/CONFIG.md`](./CONFIG.md) for the full environment model.

---

## Subcommands

### `bootstrap`

One-shot GCP project bootstrap: create the project, link billing, enable APIs,
create the Terraform state bucket, set up Workload Identity Federation + the
`deepcab-terraform` SA. Idempotent — every step probes first and skips if the
resource already exists. Pure-Python port of `scripts/bootstrap-gcp.sh`.

```bash
uv run deepcab-platform bootstrap \
  --env dev \
  --billing-account 01B30C-8DE544-29E214 \
  --project-id deepcab-dev \
  [--region us-central1] \
  [--gh-owner juan-garassino] \
  [--gh-platform-repo deepCab-platform] \
  [--dry-run]
```

What it does (in order):

1. `gcloud projects create <project-id>` (skipped if exists).
2. `gcloud beta billing projects link` to your billing account.
3. Enable 14 required APIs (`run.googleapis.com`, `sqladmin.googleapis.com`,
   `secretmanager.googleapis.com`, …).
4. Create `gs://deepcab-tfstate-<env>` (versioned, uniform access).
5. Create the WIF pool + GitHub OIDC provider.
6. Create the `deepcab-terraform` SA + grant
   `roles/{editor, iam.securityAdmin, resourcemanager.projectIamAdmin}` +
   bind it to the platform GH repo via `roles/iam.workloadIdentityUser`.

On success prints the values you paste into `scripts/gh-vars.env` for the
next step (`sync-gh`).

Source: `deepcab_platform/cli/bootstrap.py` → `services/bootstrap.py`.

---

### `sync-gh`

Bulk-upload GitHub Actions variables + secrets to all three deepCab repos
(`deepCab`, `deepCab-platform`, `deepCab-website`). Reads:

| Dotenv file | Uploaded to |
|---|---|
| `scripts/gh-vars.env` | All 3 repos (shared infra vars) |
| `scripts/gh-vars.api.env` | `deepCab` only |
| `scripts/gh-vars.platform.env` | `deepCab-platform` only |
| `scripts/gh-vars.website.env` | `deepCab-website` only |
| `scripts/gh-secrets.env` | All 3 repos (skipped if empty values) |

```bash
uv run deepcab-platform sync-gh [--dry-run]
```

Renders a Rich table summarising vars/secrets set per repo. Backwards-compatible
with `scripts/sync-gh-secrets.sh` (same dotenv contract).

Source: `deepcab_platform/cli/sync_gh.py` → `services/sync_gh.py`.

---

### `mlflow mirror`

Mirrors `ghcr.io/mlflow/mlflow:<tag>` → `us-central1-docker.pkg.dev/<project>/deepcab/mlflow:<tag>`
via a Cloud Build job. Cloud Run cannot pull images from ghcr.io directly, so
we re-tag into our own Artifact Registry repo.

```bash
uv run deepcab-platform mlflow mirror \
  [--project-id deepcab-dev] \
  [--dry-run]
```

Defaults to `settings.gcp.project` if `--project-id` is omitted. The Cloud
Build config is `cloud-manifests/mlflow/mirror.yaml`.

Source: `deepcab_platform/cli/mlflow.py` → `services/mlflow.py`.

---

### `showcase up` / `showcase down`

Toggle the dev env between "live demo" (~$15/mo) and "idle" (~$1/mo) without a
manual TF edit. Wraps `terraform apply -var=showcase_mode=true|false`.

```bash
uv run deepcab-platform showcase up   [--env dev] [--ignore-legacy] [--dry-run]
uv run deepcab-platform showcase down [--env dev] [--dry-run]
```

| State | MLflow backend | Uptime Kuma | Monthly |
|---|---|---|---|
| `up` | Neon free tier | `min_instances=1` | ~€1 (Kuma) |
| `down` | Neon free tier | `min_instances=0` | ~€0 idle |

`showcase up` runs a pre-flight check for legacy Cloud SQL / `mlflow_db_password`
resources in tfstate (leftovers from the pre-2026-06-07 architecture).
If found, aborts with a red banner pointing at `tf cleanup-legacy`. Pass
`--ignore-legacy` to override after eyeballing the apply plan.

Source: `deepcab_platform/cli/showcase.py` → `services/showcase.py`
→ `services/terraform.py` + `services/cleanup.py`.

---

### `train-on-vm`

Fire a one-shot GCE training VM. Renders `cloud-manifests/train/startup.sh.tmpl`
with per-call params + an optional `--extra-env`/`-E` set of `KEY=VAL` pairs
that land as `-e KEY=value` flags on the in-VM `docker run`. Used by the
simulation flow's `VmTrainExecutor` to pass the chunk's BQ WHERE clause and
a deterministic `MLFLOW_RUN_NAME`.

```bash
uv run deepcab-platform train-on-vm \
  --backend torch_mlp --data 100k --gpu t4 --spot \
  -E DATA_SOURCE=query \
  -E "DATA_BQ_WHERE=pickup_datetime >= TIMESTAMP('2014-01-01') AND pickup_datetime < TIMESTAMP('2014-01-08')" \
  -E MLFLOW_RUN_NAME=smoke-G
```

Keys must match `[A-Z_][A-Z0-9_]*` (shell-safe); values are `shlex.quote`'d
at render time so datetime literals + spaces survive bash array expansion
intact. Empty `--extra-env` set collapses to no-op (no leaked tokens in
the rendered script).

Source: `deepcab_platform/cli/train.py` → `services/train.py` →
`cloud-manifests/train/startup.sh.tmpl`.

---

### `kuma seed` / `kuma check`

`kuma seed` — Pre-populate the Uptime Kuma status page from
`cloud-manifests/kuma/monitors.yaml`. Creates the admin user (no-op if exists),
logs in, POSTs each monitor via the Kuma REST API. Existing monitors with the
same name are skipped (idempotent).

```bash
uv run deepcab-platform kuma seed \
  [--base-url https://kuma.deepcab.io] \
  [--admin-password ...] \
  [--dry-run]
```

Defaults: `--base-url` ← `settings.kuma.base_url`, `--admin-password` ←
`settings.kuma.admin_password` (read from `KUMA_ADMIN_PASSWORD` env var or
the `kuma-admin-password` Secret Manager secret in cloud envs).

`kuma check` — Liveness probe; non-zero exit if Kuma is unreachable.

```bash
uv run deepcab-platform kuma check [--base-url ...]
```

Monitor definitions are validated against
`deepcab_platform.schemas.kuma.KumaSeedConfig` — extra keys fail loudly. See
[`docs/RUNBOOK.md`](./RUNBOOK.md) for the "add a monitor" workflow.

Source: `deepcab_platform/cli/kuma.py` → `services/kuma.py`.

---

### `tf plan|apply|destroy|output|validate|cleanup-legacy`

Thin wrapper around `terraform <action>` scoped to `terraform/envs/<env>/`.
Auto-runs `terraform init` if `.terraform/` is missing.

```bash
uv run deepcab-platform tf plan           --env dev
uv run deepcab-platform tf apply          --env staging --auto-approve --dry-run
uv run deepcab-platform tf destroy        --env dev    --auto-approve
uv run deepcab-platform tf output         --env prod
uv run deepcab-platform tf validate       --env dev
uv run deepcab-platform tf cleanup-legacy --env dev    --dry-run
```

`--dry-run` (where supported) prints the would-be `terraform` invocation
without executing.

#### `cleanup-legacy`

One-shot sweep of the legacy `module.cloud_sql` + `mlflow-db-password`
state left over from the 2026-06-07 Cloud SQL → Neon migration. See
[RUNBOOK §F](RUNBOOK.md#f-migrating-cloud-sql--neon). Idempotent.
Flags: `--dry-run` (preview), `--yes` / `-y` (skip Cloud SQL delete
confirmation).

Source: `deepcab_platform/cli/tf.py` → `services/terraform.py` + `services/cleanup.py`.

---

### `secrets rotate`

Push a new version of a Secret Manager secret AND bump every Cloud Run
service that consumes it. Cloud Run binds secret env vars at *revision
creation* time, so adding a secret version alone doesn't update the
running service — this command handles both halves.

```bash
# from stdin (so the value never lands in shell history or argv)
echo "$NEW_OPENAI_KEY" | uv run deepcab-platform secrets rotate openai-api-key \
  --from-stdin --project-id deepcab-dev

# or from an env var
uv run deepcab-platform secrets rotate openai-api-key \
  --from-env OPENAI_API_KEY --project-id deepcab-dev

# scope the consumers explicitly (default = the consumers map in services/secrets.py)
uv run deepcab-platform secrets rotate slack-webhook-url \
  --from-env SLACK_WEBHOOK --service deepcab-api --service deepcab-mlflow
```

Add `--dry-run` to see the gcloud calls without executing them.

Source: `deepcab_platform/services/secrets.py` (`SecretsService.rotate`) +
`deepcab_platform/cli/secrets.py`.

### `status`

Print the resolved settings tree — what `DEEPCAB_ENV` is, which GCP project +
region the CLI will hit, which GitHub repos `sync-gh` will target, the Kuma
base URL, the current showcase mode.

```bash
uv run deepcab-platform status
```

Run this first when something feels off. If `gcp.project` is `(unset)`, your
`.env.<env>` file is missing or `DEEPCAB_ENV` points to the wrong value.

Source: `deepcab_platform/cli/status.py` → `deps.settings()`.

---

## Architecture

Same three-layer pattern as the 001 deepCab API (`api/services/` +
`api/providers.py`):

```
┌─────────────────────────────────────────────────────────┐
│  cli/<subcmd>.py     ── Typer surface, --dry-run flag,  │
│                         Rich rendering of results       │
└─────────────────────────┬───────────────────────────────┘
                          │ calls
                          ▼
┌─────────────────────────────────────────────────────────┐
│  services/<concern>.py ── @dataclass with provider DI,  │
│                            one method per business op   │
│                            (no I/O of its own)          │
└─────────────────────────┬───────────────────────────────┘
                          │ calls
                          ▼
┌─────────────────────────────────────────────────────────┐
│  providers/<tool>.py   ── Protocol + RealImpl (executes │
│                            via subprocess / requests)   │
│                            + DryRunImpl (prints + stubs)│
└─────────────────────────────────────────────────────────┘
```

Wiring lives in `deepcab_platform/deps.py` — `lru_cache`'d factory functions
return either the Real or DryRun provider based on `ProviderMode`. Tests
override services directly (e.g. `BootstrapService(gcloud=DryRunGcloudProvider())`).

Module map:

| Path | Purpose |
|---|---|
| `deepcab_platform/cli/` | 7 Typer files — `bootstrap`, `sync_gh`, `mlflow`, `showcase`, `kuma`, `tf`, `status` |
| `deepcab_platform/services/` | 6 dataclasses — one per concern, dependency-injected |
| `deepcab_platform/providers/` | 4 Protocols — `GcloudProvider`, `GhProvider`, `TerraformProvider`, `HttpProvider` (each with Real + DryRun) |
| `deepcab_platform/schemas/` | Pydantic + str-Enums — `BootstrapInputs/Result`, `KumaSeedConfig`, `GhSyncResult`, `PlatformSettings`, `PlatformEnv/ShowcaseMode/TerraformAction/...` |
| `deepcab_platform/deps.py` | DI wiring: `get_<service>_service(mode)` factory functions |
| `deepcab_platform/__main__.py` | Re-export so `python -m deepcab_platform` works |

---

## `--dry-run` flag

Every subcommand that touches GCP, GitHub, Terraform, or HTTP supports
`--dry-run`. It swaps the underlying provider for its `DryRun` impl, which
prints the command that *would* run and returns a stub response. Used by:

- The test suite (no real GCP credentials needed in CI).
- Sanity-checking a change before burning real GCP money.
- Generating reproducible "what would happen" reports for code review.

Example:

```bash
$ uv run deepcab-platform bootstrap --env dev \
    --billing-account 01B30C-8DE544-29E214 \
    --project-id deepcab-dev \
    --dry-run

[DRY-RUN gcloud] projects describe deepcab-dev --quiet
[DRY-RUN gcloud] beta billing projects link deepcab-dev --billing-account=01B30C-8DE544-29E214
[DRY-RUN gcloud] services enable cloudresourcemanager.googleapis.com ... --project=deepcab-dev
...
✓ bootstrap complete (dry-run; no resources created)
```

---

## Environment

Reads `DEEPCAB_ENV` (preferred) or legacy `APP_ENV`. Loads
`.env.<env>` via pydantic-settings. Sub-settings are prefix-grouped:

| Prefix | Settings class | Keys |
|---|---|---|
| `GCP_` | `GcpSettings` | `project`, `project_number`, `region`, `billing_account`, `deployer_sa`, `runtime_sa`, `terraform_sa`, `wif_provider` |
| `GH_` | `GhSettings` | `owner`, `api_repo`, `platform_repo`, `website_repo` |
| `KUMA_` | `KumaSettings` | `admin_user`, `admin_password`, `base_url` |
| `SHOWCASE_` | `ShowcaseSettings` | `mode` (`up` / `down`) |

See [`docs/CONFIG.md`](./CONFIG.md) for the full env model and precedence
rules.

---

## See also

- [`docs/DEPLOY-FROM-SCRATCH.md`](./DEPLOY-FROM-SCRATCH.md) — end-to-end bootstrap walkthrough using the CLI
- [`docs/RUNBOOK.md`](./RUNBOOK.md) — day-2 ops (secret rotation, drift, monitor management)
- [`docs/ARCHITECTURE.md`](./ARCHITECTURE.md) — cross-repo split + CLI layer diagram
- [`docs/CONFIG.md`](./CONFIG.md) — `DEEPCAB_ENV` model
- 001's `deepCab/cli/` — the reference implementation this package mirrors
