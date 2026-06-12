# Runbook

> **Pre-migration doc (2026-06-07):** GCP project `deepcab-dev` cold-deleted; canonical config is now `garassino-ml` / `europe-west1` (root `CLAUDE.md` § "GCP architecture"). Project IDs and regions below describe pre-migration state — body kept as historical narrative.

Operational playbook for the deepCab platform. Read this end-to-end before
your first apply.

---

## 0. Prerequisites

On your laptop:

```bash
brew install terraform google-cloud-sdk
gcloud auth login
gcloud auth application-default login
```

You should have **billing-account owner** access on the GCP org that will host
the deepCab projects, and **admin** access on the GitHub repos `deepCab` and
`deepCab-platform`.

---

## 1. Bootstrap a new environment

### 1.1 Create the GCP project

```bash
ENV=dev   # or staging / prod
gcloud projects create deepcab-${ENV} --name="deepCab ${ENV}"
gcloud beta billing projects link deepcab-${ENV} \
  --billing-account=$BILLING_ACCOUNT     # 0X0X0X-0X0X0X-0X0X0X
gcloud config set project deepcab-${ENV}
```

Capture the project number — you need it for `terraform.tfvars`:

```bash
gcloud projects describe deepcab-${ENV} --format='value(projectNumber)'
```

### 1.2 Create the Terraform state bucket (chicken-and-egg)

```bash
gcloud storage buckets create gs://deepcab-tfstate-${ENV} \
  --project=deepcab-${ENV} \
  --location=us-central1 \
  --uniform-bucket-level-access
gcloud storage buckets update gs://deepcab-tfstate-${ENV} --versioning
```

> The bucket name **must** match the literal in `terraform/envs/${ENV}/backend.tf`.

### 1.3 Bootstrap APIs + WIF manually (one-time, breaks the second chicken-and-egg)

Terraform can manage the rest, but to run `terraform apply` from CI via WIF
you first need WIF itself. Run the existing imperative bootstrap once:

```bash
export PROJECT=deepcab-${ENV}
export PROJECT_NUMBER=$(gcloud projects describe $PROJECT --format='value(projectNumber)')
export GH_OWNER=juan-garassino
export GH_REPO=deepCab-platform     # bootstrap WIF for THIS repo first
export REGION=us-central1
./cloud-manifests/workload-identity/bootstrap.sh
```

Then create the `deepcab-terraform` SA with broad-but-bounded roles so it can
run `terraform apply` from CI:

```bash
gcloud iam service-accounts create deepcab-terraform \
  --project=$PROJECT \
  --display-name="deepCab platform terraform CI"

for ROLE in roles/editor roles/iam.securityAdmin roles/resourcemanager.projectIamAdmin; do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member="serviceAccount:deepcab-terraform@$PROJECT.iam.gserviceaccount.com" \
    --role=$ROLE --condition=None >/dev/null
done

gcloud iam service-accounts add-iam-policy-binding \
  deepcab-terraform@$PROJECT.iam.gserviceaccount.com \
  --project=$PROJECT \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/attribute.repository/$GH_OWNER/deepCab-platform"
```

> After the first successful `terraform apply` the **TF-managed** `wif` module
> replaces all of these bindings. The bootstrap is just enough to let TF take over.

### 1.4 Set GitHub variables for this env

```bash
ENV_UPPER=$(echo $ENV | tr '[:lower:]' '[:upper:]')

gh variable set GCP_PROJECT_${ENV_UPPER}         --body "deepcab-${ENV}"
gh variable set GCP_PROJECT_NUMBER_${ENV_UPPER}  --body "$PROJECT_NUMBER"
gh variable set GCP_REGION_${ENV_UPPER}          --body "us-central1"
gh variable set GCP_WIF_PROVIDER_${ENV_UPPER}    --body "projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
gh variable set GCP_TERRAFORM_SA_${ENV_UPPER}    --body "deepcab-terraform@deepcab-${ENV}.iam.gserviceaccount.com"
gh variable set GCP_DEPLOYER_SA_${ENV_UPPER}     --body "deepcab-deployer@deepcab-${ENV}.iam.gserviceaccount.com"

gh secret set SLACK_WEBHOOK_URL                  # paste the URL when prompted
```

Also configure each env in repo Settings → Environments → Required reviewers.

### 1.5 Edit the env's tfvars

Edit `terraform/envs/${ENV}/terraform.tfvars`:

- `project_id` = `deepcab-${ENV}`
- `project_number` = the value from 1.1
- `gh_owner` / `gh_api_repo` / `gh_platform_repo` if defaults don't match

Commit + push (these are not secrets).

### 1.6 First apply

```bash
make ENV=${ENV} plan
make ENV=${ENV} apply
```

This provisions: WIF (full TF-managed replacement), GAR, GCS, Cloud SQL,
Cloud Run + Job (with the `gcr.io/cloudrun/hello` placeholder image),
Cloud Scheduler. ~5-10 minutes.

### 1.7 Populate secrets

```bash
gcloud config set project garassino-ml

# Slack
echo -n "https://hooks.slack.com/..."                 | gcloud secrets versions add slack-webhook-url  --data-file=-
# OpenAI key (for the agent)
echo -n "sk-..."                                       | gcloud secrets versions add openai-api-key    --data-file=-
# Internal API key (X-API-Key for /train and /agent/improve)
openssl rand -hex 32 | tr -d '\n'                      | gcloud secrets versions add deepcab-api-key   --data-file=-
# MLflow tracking backend DSN (one-time, from Neon — see below)
echo -n "postgresql+psycopg2://...neon.tech/.../deepcab-mlflow?sslmode=require" \
  | gcloud secrets versions add neon-deepcab-dsn --data-file=-
```

#### Neon free-tier provisioning (one-time)

MLflow's tracking backend lives on a Neon (`neon.tech`) Postgres instead of
Cloud SQL — €0/mo idle, survives `make destroy` cycles, no Cloud SQL Proxy
volume to wire. Pre-requisites for the DSN above:

1. Sign in to `https://neon.tech` (GitHub SSO).
2. Create a new project `deepcab-mlflow` in the `aws-eu-central-1` region
   (closest to GCP `europe-west1`).
3. Create a database `deepcab-mlflow` inside that project (the schema MLflow
   needs is auto-created on first server boot).
4. Copy the **pooled** connection string (psycopg2 form). Strip the leading
   `psql ` if present and prefix the dialect:
   `postgresql+psycopg2://<user>:<password>@<host>/<db>?sslmode=require`.
5. Push it as the `neon-deepcab-dsn` secret value (command above).

Neon free tier sleeps after 5 min idle — the first MLflow call after a quiet
window adds ~3 s. For demos, warm it up before running the simulation loop:
`curl -fsS "$mlflow_url" >/dev/null`.

### 1.8 First image lands

Trigger the 001 image build (typically by tagging `v0.1.0`):

```bash
cd ../001-deepCab-api
git tag v0.1.0
git push origin v0.1.0
```

The 001 `release.yml` workflow builds + pushes to GAR, then runs
`gcloud run services update --image=...` to swap the placeholder image for the
real one. TF's `lifecycle.ignore_changes` keeps the next `terraform plan` from
reverting that image change.

### 1.9 Smoke test

```bash
URL=$(cd ../002-deepCab-platform/terraform/envs/${ENV} && terraform output -raw api_service_url)
# Note: /healthz is intercepted by Google Frontend on Cloud Run before reaching the container.
# Use /readyz (or /version, /docs) for external smoke tests.
curl -fsS ${URL}/readyz
curl -fsS ${URL}/version
```

---

## 2. Secret rotation

Use the CLI — it pushes the new version AND triggers a Cloud Run revision
swap on every consuming service in one call:

```bash
echo "$NEW_VALUE" | uv run deepcab-platform secrets rotate openai-api-key \
  --from-stdin --project-id deepcab-dev
```

The mapping of secret → consuming services lives in
`deepcab_platform/services/secrets.py` (`_default_consumers`). Override per
call with `--service deepcab-api`.

Manual fallback (bypasses the consumer map):

```bash
gcloud secrets versions add slack-webhook-url --data-file=- <<< "https://hooks.slack.com/NEW"
gcloud run services update deepcab-api --region=us-central1 \
  --update-secrets=SLACK_WEBHOOK_URL=slack-webhook-url:latest
```

For `mlflow-db-password` rotation: see step 1.7.

---

## 3. Destroying an env

```bash
make ENV=dev destroy
```

Cloud SQL has `deletion_protection = true` in staging/prod. To destroy a
production-like env you must first:

```bash
cd terraform/envs/<env>
terraform apply -var='deletion_protection=false'   # update tfvars and re-apply
make ENV=<env> destroy
```

The `tfstate` bucket has `force_destroy = false` and survives `terraform destroy`
on purpose — delete it manually if you really mean it.

> **Migrating an old tfstate from Cloud SQL?** Run [§F](#f-migrating-cloud-sql--neon)
> first; otherwise `make showcase_up` will plan a destroy of `module.cloud_sql`
> that races MLflow's revision swap.

### 3.1 Re-bootstrapping within 30 days (WIF soft-delete window)

When you destroy + rebuild the same env quickly, the WIF pool + provider sit
in GCP's `DELETED` state for 30 days. A naive create returns
`ALREADY_EXISTS in DELETED state`. The bootstrap CLI handles this:
`BootstrapService._ensure_wif_pool` and `_ensure_wif_provider` first probe
`--show-deleted` and call `undelete` instead of `create` when the resource
is soft-deleted. Same with `gcloud iam service-accounts undelete` if you
ever destroy a SA you want back.

If you're operating outside the CLI (e.g. clicking in console), the manual
recovery is:

```bash
gcloud iam workload-identity-pools undelete github-pool \
  --location=global --project=$PROJECT_ID
gcloud iam workload-identity-pools providers undelete github-provider \
  --workload-identity-pool=github-pool --location=global \
  --project=$PROJECT_ID
# then `terraform import` both back into state and re-apply.
```

### 3.2 The showcase up/down toggle (cheaper than destroy)

If you just want the stack idle without losing data, use the showcase
toggle instead of destroying. `showcase down` flips Cloud SQL to
`activation_policy = NEVER` (storage-only cost, ~$1/mo for 10 GB) and
scales Uptime Kuma to `min_instances = 0` ($0). Cloud Run services stay
provisioned but cost nothing while idle. `showcase up` flips both back —
`ShowcaseService` polls the Cloud SQL state until `RUNNABLE` so MLflow
isn't 5xx-ing while Postgres warms up.

```bash
make showcase_down            # ~$1/mo idle, services preserved
# … hours/days later …
make showcase_up              # back to ~$15/mo, MLflow ready when this returns
```

---

## 4. Drift recovery

If someone clicks in the Cloud Console and changes a service spec:

```bash
make ENV=<env> plan       # shows the drift
make ENV=<env> apply      # reconciles to TF
```

If the change should be preserved, copy it into the TF code instead.

---

## 5. Common failure modes

| Error | Cause | Fix |
|---|---|---|
| `Backend initialization required` | tfstate bucket missing | Run step 1.2 |
| `Permission 'iam.serviceAccounts.getAccessToken' denied` | WIF binding missing | Re-run step 1.3 |
| `Error 409: artifact registry 'deepcab' already exists` | Previous bootstrap-script artifact | `terraform import module.gar.google_artifact_registry_repository.deepcab projects/.../locations/.../repositories/deepcab` |
| Cloud Run revision stuck in `Provisioning` | Bad image | `gcloud run revisions list` + roll back |
| `cloud-sql-proxy unauthorized` | Runtime SA missing `roles/cloudsql.client` | Already in `wif` defaults — re-apply if missing |

---

## 6. How to add a monitor to the status page

The Uptime Kuma status page (`deepcab-status` Cloud Run service) is seeded
declaratively from `cloud-manifests/kuma/monitors.yaml`. Adding or editing a
monitor is a 2-step loop — no clicking around the Kuma UI.

### 6.1 Edit the YAML

```bash
$EDITOR cloud-manifests/kuma/monitors.yaml
```

Add an entry to the `monitors:` list:

```yaml
- name: deepcab-grafana                       # unique, max 64 chars
  type: http                                  # http | keyword | ping | port | dns
  url: https://grafana.deepcab.io/api/health
  interval_seconds: 60                        # 20-3600
  retry_interval_seconds: 60
  max_retries: 2                              # 0-10
  accepted_status_codes: ["200-299"]
  description: Grafana dashboard health endpoint.
  tags: [observability]
```

The file is validated against `deepcab_platform.schemas.kuma.KumaSeedConfig`
on every `kuma seed` call — extra keys, missing fields, or out-of-range
values fail loudly before any HTTP call is made.

### 6.2 Re-run the seeder

```bash
export KUMA_BASE_URL=$(uv run deepcab-platform tf output --env <env> | grep status_page_url | awk -F\" '{print $2}')
export KUMA_ADMIN_PASSWORD=$(gcloud secrets versions access latest --secret=kuma-admin-password --project=deepcab-<env>)

uv run deepcab-platform kuma seed          # or: make kuma_seed
```

Output reports `created=N skipped=M`. **Existing monitors with the same name
are skipped** (idempotent — re-running is safe). To force-update an existing
monitor, delete it from the Kuma UI first, then re-seed.

### 6.3 Verify

```bash
uv run deepcab-platform kuma check --base-url $KUMA_BASE_URL
# ✓ https://... responsive
```

Open the status page in a browser to see the new monitor in the list. The
first probe runs within `interval_seconds` of creation.

---

## 7. Train on a GCE VM (one-shot)

For CPU training under 24h, `gcloud run jobs execute deepcab-retrain` is
strictly better — faster spin-up, no IAM to manage. The VM path exists for
**GPU training** and **interactive SSH debugging** of training crashes.

### 7.1 Launch

```bash
# Default: torch_mlp on a 100k slice with 1× T4 spot ≈ $0.14/hr ≈ $0.05/run
uv run deepcab-platform train-on-vm --project-id deepcab-dev

# CPU variant (Container-Optimized OS, e2-standard-4 spot)
uv run deepcab-platform train-on-vm --gpu none --machine e2-standard-4 \
  --project-id deepcab-dev

# Keep the VM alive after training for SSH debugging
uv run deepcab-platform train-on-vm --keep-alive --project-id deepcab-dev

# Different backend + bigger slice
uv run deepcab-platform train-on-vm --backend xgb --data 500k \
  --machine n1-standard-8 --project-id deepcab-dev
```

What happens:
1. Renders `cloud-manifests/train/startup.sh.tmpl` with your inputs.
2. `gcloud compute instances create` with the script as metadata,
   `--max-run-duration` as the belt-and-suspenders auto-destruct.
3. VM pulls the `deepcab/api:<tag>` image from GAR.
4. Runs `python -m deepCab.training.train backend=X data=Y` inside the
   container with `REGISTRY_TARGET=gcs` so the model lands in
   `gs://deepcab-models-<env>/runs/<run_id>/`.
5. Logs the run to MLflow at the URL you set in `MLFLOW_URL`.
6. Sends Telegram start/success/failure pings (no-op when
   `TELEGRAM_BOT_TOKEN` is empty).
7. Self-destructs when training is done (unless `--keep-alive`).

### 7.2 Watch progress

```bash
# Serial console = boot + script stdout in real time
gcloud compute instances get-serial-port-output \
  deepcab-train-<backend>-<ts> --zone=us-central1-a --project=deepcab-dev

# Or MLflow once the run is registered
open https://deepcab-mlflow-vkj76snh3q-uc.a.run.app/#/experiments
```

### 7.3 Required IAM (handled by TF)

The `deepcab-runtime` SA needs `roles/compute.instanceAdmin.v1` (project-
level) so the VM can `gcloud compute instances delete` itself. This is in
the `wif` module's `runtime_project_roles` default. After bumping the
module, `make ENV=dev apply` to land the IAM binding before first use.

### 7.4 Cost

| Shape | Hourly (Iowa spot) | Typical 20-min run |
| --- | --- | --- |
| e2-standard-4 (CPU) | ~$0.05 | ~$0.02 |
| n1-standard-4 + T4 | ~$0.14 | ~$0.05 |
| n1-standard-8 + L4 | ~$0.32 | ~$0.11 |
| n1-standard-8 + A100 | ~$1.10 | ~$0.37 |

The `--spot` default can be preempted by GCP — fine for one-shot training,
not for production-critical workloads. Add `--standard` to opt out.

## 8. Continuous-training simulation

The simulation loop walks a sliding time-window over our EU BigQuery copy
of `nyc-tlc.yellow.trips`, retrains per chunk, and auto-promotes
`@challenger` → `@champion` (old champion becomes `@legacy`) whenever the
new model beats the live one by `--promotion-threshold` on a fixed
reference slice. Detailed design: `~/.claude/plans/now-please-ultrathik-how-enumerated-star.md`.

### 8.1 One-time setup — clone the BQ table (~10 min, ~€3)

BigQuery refuses CREATE-TABLE-AS-SELECT across regions, so we use the
export-to-GCS-then-load pattern. Wrapped by:

```bash
uv run deepcab-platform data clone-bq \
  --source-table nyc-tlc:yellow.trips \
  --target-project garassino-ml \
  --target-dataset taxi \
  --target-table yellow_trips_raw \
  --target-location europe-west1 \
  --year 2014
```

What it does:

1. `bq query --location=US` against the rendered template at
   `cloud-manifests/bq/yellow_trips_raw.export.sql` → writes Parquet to a
   temp US staging bucket.
2. `gsutil -m cp -r` between staging buckets (US → EU). ~30 GB egress for
   the full 2014 slice.
3. `bq load --location=europe-west1` from the EU staging bucket into the
   TF-managed `garassino-ml.taxi.yellow_trips_raw` table.
4. Deletes both staging buckets.

The table itself has `deletion_protection = true` (see
`terraform/modules/bigquery/main.tf`) so `make destroy` doesn't wipe the
loaded data. Re-running `data clone-bq` is idempotent — it skips steps
whose outputs already exist.

### 8.2 Smoke (dry-run the loop without firing VMs)

```bash
uv run deepcab-platform simulate run \
  --env dev --backend torch_mlp \
  --time-window-start 2014-01-01 --time-window-end 2014-01-31 \
  --chunk-period 7d --reference-data 10k --dry-run
```

Expect 4 dry-run `gcloud compute instances create` lines (4 weeks in Jan)
+ 4 polled MLflow run lookups + 4 promote decisions. Nothing fires.

### 8.3 Real run (cost-bounded, ~€0.20)

```bash
make showcase_up                           # ~3 min — brings up MLflow on Neon
uv run deepcab-platform simulate run \
  --env dev --backend torch_mlp \
  --time-window-start 2014-01-01 --time-window-end 2014-01-28 \
  --chunk-period 7d --reference-data 10k --promotion-threshold 0.05
# 4 T4-spot VMs sequentially (~5 min each) — Telegram per chunk + per promotion
make showcase_down                         # back to ~€0/mo idle
```

### 8.4 What gets promoted, when

`PromotionService.maybe_promote()` flips aliases iff
`challenger_metric < champion_metric * (1 - promotion_threshold)` on the
held-out reference slice. Default threshold is 5%. The old champion gets
`@legacy` for one-flag rollback (`mlflow alias set @champion legacy_version`).

### 8.5 Required IAM (TF-managed)

The runtime SA needs `roles/bigquery.dataViewer`, `roles/bigquery.dataEditor`,
and `roles/bigquery.jobUser` — all in `terraform/modules/wif/variables.tf`'s
`runtime_project_roles` default. After bumping the module, `make ENV=dev apply`
to land the bindings before first run.

## F. Migrating Cloud SQL → Neon

The 2026-06-07 architecture move dropped `module.cloud_sql` and the
`mlflow-db-password` secret in favour of Neon free tier (see §1.7). An
env whose tfstate predates that change still references both — running
`terraform apply` plans destroys for them, and Cloud SQL takes ~5 min to
drop, racing the MLflow Cloud Run revision swap.

One-shot fix, idempotent:

```bash
uv run deepcab-platform tf cleanup-legacy --env dev
```

What it does:

1. `terraform state rm` every legacy address (allow-listed: only matches
   `module.cloud_sql*` and `*mlflow_db_password*`).
2. `gcloud sql instances delete deepcab-mlflow-dev` (orphan after step 1).
3. `gcloud secrets delete mlflow-db-password` (no longer referenced).
4. `terraform plan` → confirms nothing legacy remains.

`make showcase_up` runs a pre-flight check for legacy state and aborts
with a red banner if found. Override with `--ignore-legacy` only after
you've eyeballed the apply plan.

Dry-run first if unsure:

```bash
uv run deepcab-platform tf cleanup-legacy --env dev --dry-run
```
