# Deploy deepCab from scratch — no-friction runbook

> **Pre-migration doc (2026-06-07):** GCP project `deepcab-dev` cold-deleted; canonical config is now `garassino-ml` / `europe-west1` (root `CLAUDE.md` § "GCP architecture"). Project IDs and regions below describe pre-migration state — body kept as historical narrative.

Two sections:

- **A. Bootstrap** — one-time per GCP project (you do this once per env).
- **B. Deploy** — every release (tag + push, fully automatic after bootstrap).

Real reproduction of the 2026-06-05 first bootstrap is interleaved as
"the exact errors you'll hit and what to do." Skip if you don't care.

---

## 0. One-time laptop setup

```bash
brew install terraform google-cloud-sdk gh
gcloud auth login
gcloud auth application-default login
gh auth login                                   # SSH protocol, `repo` scope minimum

# Fix the bundled-Python protobuf bug (real, happens on every new gcloud install)
echo 'export CLOUDSDK_PYTHON=/usr/bin/python3' >> ~/.zshrc
export CLOUDSDK_PYTHON=/usr/bin/python3         # current shell

# On your default GCP project (whatever `gcloud config get-value project` returns),
# enable the two metadata APIs needed to even list/create projects. Free, no charges.
DEFAULT_PROJECT=$(gcloud config get-value project)
gcloud services enable \
  cloudresourcemanager.googleapis.com \
  cloudbilling.googleapis.com \
  --project="$DEFAULT_PROJECT"
```

After this, `gcloud billing accounts list` and `gcloud projects list` work.

---

## A. Bootstrap a new env (one-time per GCP project)

### A.1. Pick your billing account

```bash
gcloud billing accounts list
# ACCOUNT_ID            NAME                OPEN
# 01B30C-8DE544-29E214  garassino-billing   True       <-- the OPEN one
```

### A.2. Run the bootstrap CLI

```bash
cd 002-deepCab-platform
uv sync --extra dev                                            # one-time

# `--env` controls the state-bucket name (gs://deepcab-tfstate-<env>) and labels.
# `--project-id` must be globally unique on GCP.
uv run deepcab-platform bootstrap \
  --env dev \
  --billing-account 01B30C-8DE544-29E214 \
  --project-id deepcab-dev
```

(Or the Makefile alias: `BILLING_ACCOUNT=… PROJECT_ID=deepcab-dev ENV=dev make bootstrap_gcp`.)

Add `--dry-run` to see every `gcloud` call without executing — useful for code
review or pre-flight sanity.

This does (idempotent — safe to re-run):

1. `gcloud projects create deepcab-dev`
2. `gcloud beta billing projects link` to your billing account
3. Enable 14 required APIs on the new project
4. Create `gs://deepcab-tfstate-dev` (versioned) for terraform state
5. Create the Workload Identity Pool + GitHub provider
6. Create the `deepcab-terraform` SA bound to the platform GH repo

Output prints the values you need for the next step. Capture them.
See [`docs/CLI.md`](./CLI.md) for the full subcommand reference.

### A.3. Fill in the dotenv files

```bash
cd 002-deepCab-platform/scripts

cp gh-vars.env.example          gh-vars.env
cp gh-vars.api.env.example      gh-vars.api.env
cp gh-vars.website.env.example  gh-vars.website.env
cp gh-vars.platform.env.example gh-vars.platform.env
cp gh-secrets.env.example       gh-secrets.env

# Edit each with the values bootstrap_gcp printed.
$EDITOR gh-vars.env gh-vars.platform.env gh-secrets.env
```

For now `gh-vars.api.env` / `gh-vars.website.env` defaults are fine; tune later.

### A.4. Push secrets/vars to all 3 GitHub repos

```bash
cd 002-deepCab-platform
uv run deepcab-platform sync-gh           # or: make sync_gh
```

Wraps `gh variable set -f` + `gh secret set -f` and uploads to all of
`juan-garassino/deepCab`, `juan-garassino/deepCab-platform`,
`juan-garassino/deepCab-website`. Renders a Rich table with the per-repo
results. Secrets with empty values are skipped (so partial `.env` files are
safe).

### A.5. First terraform apply (creates everything else)

```bash
cd 002-deepCab-platform
uv run deepcab-platform tf apply --env dev      # or: make ENV=dev apply
```

(Auto-runs `terraform init` if `.terraform/` is missing. `--dry-run` prints
the would-be command without invoking terraform.)

This creates: GAR, deployer SA, runtime SA, scheduler SA, Cloud SQL,
Cloud Run services (api, website, mlflow, status — all four spun up from
the consolidated `cloud_run_service` module), Cloud Run Job (retrain),
Cloud Scheduler (paused in dev), Secret Manager containers, GCS buckets,
IAM bindings. Takes ~5 minutes.

### A.6. Populate the Secret Manager containers (TF only declares them)

```bash
echo -n "<your-openai-key>"   | gcloud secrets versions add openai-api-key   --data-file=- --project=deepcab-dev
echo -n "<your-deepcab-key>"  | gcloud secrets versions add deepcab-api-key  --data-file=- --project=deepcab-dev
echo -n "<slack-or-discord>"  | gcloud secrets versions add slack-webhook-url --data-file=- --project=deepcab-dev
echo -n "<db-password>"       | gcloud secrets versions add mlflow-db-password --data-file=- --project=deepcab-dev
echo -n "<kuma-admin-pw>"     | gcloud secrets versions add kuma-admin-password --data-file=- --project=deepcab-dev
```

### A.7. Pre-seed Uptime Kuma monitors (Wave 4)

The status page (`deepcab-status` Cloud Run service, running
`louislam/uptime-kuma:1`) boots with a blank UI on first deploy. Seed it
from `cloud-manifests/kuma/monitors.yaml`:

```bash
cd 002-deepCab-platform

# Point KUMA_BASE_URL at the status service URL terraform just emitted
export KUMA_BASE_URL=$(uv run deepcab-platform tf output --env dev | grep status_page_url | awk -F\" '{print $2}')
export KUMA_ADMIN_PASSWORD=$(gcloud secrets versions access latest --secret=kuma-admin-password --project=deepcab-dev)

uv run deepcab-platform kuma seed         # or: make kuma_seed
```

What it does:

1. POST `/api/setup` to create the admin user (no-op if it exists).
2. POST `/api/login` to grab a JWT.
3. For each monitor in `cloud-manifests/kuma/monitors.yaml`, POST
   `/api/monitor`. Existing monitors with the same name are skipped (the
   seeder is idempotent).

Validate the seed config without hitting the network:

```bash
uv run deepcab-platform kuma check --base-url $KUMA_BASE_URL
```

To add a new monitor later, edit `cloud-manifests/kuma/monitors.yaml` and
re-run `kuma seed` — see [`docs/RUNBOOK.md`](./RUNBOOK.md) §6.

Bootstrap complete. Section A never runs again for this env.

---

## B. Deploy (every release)

After bootstrap, the entire deploy chain is GitHub Actions. You touch one thing
per release: a git tag.

### B.1. Deploy the API

```bash
cd 001-deepCab-api
git checkout master
git pull
git tag v0.2.0                  # any v* tag fires deploy-cloud-run.yml
git push origin v0.2.0
```

CI does: build api image -> push to GAR -> `gcloud run services update
deepcab-api --image=...`. ~3 minutes. Watch with `gh run watch --repo juan-garassino/deepCab`.

### B.2. Deploy the website

```bash
cd 003-deepCab-website
git checkout master
git pull
git tag v0.2.0
git push origin v0.2.0
```

Same shape. Image: `deepcab/website:v0.2.0`. Service: `deepcab-website`.

### B.3. Update infrastructure shape

Anything beyond "swap the image" (CPU/memory/scale/IAM/env vars/secrets/
add a new service) goes through Terraform in 002:

```bash
cd 002-deepCab-platform
git checkout develop
# edit terraform/modules/* or terraform/envs/<env>/main.tf
git add -A && git commit -m "feat: bump prod api memory to 2Gi"
git push origin develop
# Open PR develop -> master. platform-plan.yml posts the plan as a PR comment.
# Merge to master. platform-apply.yml runs `terraform apply` on dev, staging, prod.
```

### B.4. Schedule retrain

The Cloud Scheduler is paused in dev. To fire the retrain Job manually:

```bash
gcloud run jobs execute deepcab-retrain --region=us-central1 --project=deepcab-dev
```

To un-pause for staging/prod, edit `terraform/envs/<env>/main.tf` → set
`module.scheduler { paused = false }`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `gcloud failed to load. ... MessageMapContainer` | Bundled Python broken. `export CLOUDSDK_PYTHON=/usr/bin/python3` (one-time in zshrc). |
| `Cloud Billing API has not been used in project X` | Enable it: `gcloud services enable cloudbilling.googleapis.com --project=X`. Same for cloudresourcemanager. |
| `gcloud projects create` blocked by Claude Code | Auto-mode classifier requires explicit user authorization of high-severity infra. Run the create command yourself in `!` block, or pre-approve in `~/.claude/settings.json`. |
| `gh secret set` fails with 401 | `gh auth refresh -s repo` (or `admin:repo` for org-level secrets later). |
| `terraform apply` says "bucket gs://deepcab-tfstate-dev does not exist" | The bootstrap step skipped or failed. Re-run `make bootstrap_gcp`. |
| Deploy succeeded but `/healthz` 404 | TF placeholder image still serving. Tag + push from 001 to fire a real image build. |
| Discord/Telegram instead of Slack | Discord webhooks have a Slack-compat endpoint — append `/slack` to the webhook URL, paste it into `SLACK_WEBHOOK_URL` secret. Telegram needs a workflow rewrite. |

---

## What lives where (cheat sheet)

| Want to change... | Edit... | Goes live via... |
|---|---|---|
| api code | 001-deepCab-api/deepCab/ | tag v* in 001 |
| api Dockerfile | 001-deepCab-api/infra/docker/Dockerfile | tag v* in 001 |
| website UI | 003-deepCab-website/src/ | tag v* in 003 |
| Cloud Run shape (cpu/mem/scale) | 002-deepCab-platform/terraform/modules/cloud_run_service/ | merge to master in 002 |
| Per-env knobs | 002-deepCab-platform/terraform/envs/<env>/main.tf | merge to master in 002 |
| Secret values | `gcloud secrets versions add` | next deploy or `gcloud run services update` |
| GitHub repo vars/secrets | 002-deepCab-platform/scripts/gh-*.env | `deepcab-platform sync-gh` (or `make sync_gh`) |
| Status-page monitors | 002-deepCab-platform/cloud-manifests/kuma/monitors.yaml | `deepcab-platform kuma seed` |
| Branching policy | this doc + parent CLAUDE.md "Branching" section | n/a |
