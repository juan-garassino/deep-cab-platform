# ----------------------------------------------------------------------------
# deepCab — DEV environment composition
#
# Smallest tier everywhere. No VPC (public-IP Cloud SQL). No DNS. No GKE.
# Budget target: ~$5-15/mo idle.
# ----------------------------------------------------------------------------

locals {
  env = "dev"

  common_labels = {
    env       = local.env
    managed   = "terraform"
    component = "deepcab-platform"
  }
}

# 1. Artifact Registry (must exist before Cloud Run can reference images)
module "gar" {
  source     = "../../modules/gar"
  project_id = var.project_id
  region     = var.region
  labels     = local.common_labels
}

# 2. Storage buckets (mlflow artifacts, models, tfstate)
# name_prefix override: the old `deepcab-*-dev` bucket names from the deleted
# deepcab-dev project are still in GCS-global-namespace cooldown. Use
# project-id-scoped names to guarantee uniqueness. Pattern matches the
# garassino-ml convention from root CLAUDE.md.
module "storage" {
  source      = "../../modules/storage"
  project_id  = var.project_id
  region      = var.region
  env         = local.env
  name_prefix = "garassino-deepcab"

  # dev: allow destroy with objects present so iteration is painless
  force_destroy = true

  labels = local.common_labels
}

# 3. WIF + service accounts
module "wif" {
  source           = "../../modules/wif"
  project_id       = var.project_id
  project_number   = var.project_number
  gh_owner         = var.gh_owner
  gh_repo          = var.gh_api_repo
  platform_gh_repo = var.gh_platform_repo
  website_gh_repo  = var.gh_website_repo

  labels = local.common_labels
}

# 4. Secret Manager
module "secrets" {
  source           = "../../modules/secret_manager"
  project_id       = var.project_id
  region           = var.region
  env              = local.env
  runtime_sa_email = module.wif.runtime_sa_email

  labels = local.common_labels
}

# 5. VPC disabled in dev — Cloud SQL uses public IP with our office network only.
module "vpc" {
  source     = "../../modules/vpc"
  project_id = var.project_id
  region     = var.region
  env        = local.env
  enabled    = false
}

# 6. MLflow tracking backend is now Neon (free tier) instead of Cloud SQL.
# DSN is in Secret Manager as `neon-deepcab-dsn` (populated manually after
# one-time Neon project provisioning — see docs/RUNBOOK.md §1.7 + §F).
# Persists across `make destroy` cycles, which Cloud SQL did not.
#
# The cloud_sql module + random_password.mlflow_db + mlflow_db_password
# secret version were removed 2026-06-07. Existing dev state needs:
#   terraform state rm module.cloud_sql
#   terraform state rm random_password.kuma_admin_legacy  # if present
# then `terraform apply` to converge.

# 7. Cloud Run service — deepcab-api (minimal scale)
module "cloud_run_api" {
  source     = "../../modules/cloud_run_service"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  service_name          = "deepcab-api"
  component             = "cloud-run-api"
  image                 = var.api_image
  service_account_email = module.wif.runtime_sa_email

  cpu                   = "1"
  memory                = "512Mi"
  min_instances         = 0
  max_instances         = 2
  container_concurrency = 40
  container_port        = 8000
  allow_unauthenticated = true

  env_vars = {
    APP_ENV             = "dev"
    MLFLOW_TRACKING_URI = module.cloud_run_mlflow.service_url
    MODEL_TARGET        = "gcs"
    GCP_PROJECT         = var.project_id
    REGISTRY_GCS_BUCKET = module.storage.models_bucket
  }

  secret_env_vars = {
    OPENAI_API_KEY    = "openai-api-key"
    DEEPCAB_API_KEY   = "deepcab-api-key"
    SLACK_WEBHOOK_URL = "slack-webhook-url"
  }

  labels = local.common_labels

  depends_on = [
    module.secrets,
    module.gar,
  ]
}

moved {
  from = module.cloud_run.google_cloud_run_v2_service.this
  to   = module.cloud_run_api.google_cloud_run_v2_service.this
}

moved {
  from = module.cloud_run.google_cloud_run_v2_service_iam_member.public
  to   = module.cloud_run_api.google_cloud_run_v2_service_iam_member.public
}

# MLflow's tracking backend secret (`neon-deepcab-dsn`) is user-supplied;
# push the value once after Neon is provisioned:
#
#   echo -n 'postgresql+psycopg2://...neon.tech/.../deepcab-mlflow?sslmode=require' \
#     | gcloud secrets versions add neon-deepcab-dsn --data-file=-
#
# The runtime SA already has secretAccessor via the secret_manager module —
# nothing else to do here.

# Uptime Kuma admin password — auto-generated, stored in Secret Manager.
# Read by `deepcab-platform kuma seed` to create the admin account on first
# boot. To rotate: `gcloud secrets versions add kuma-admin-password --data-file=-`.
resource "random_password" "kuma_admin" {
  length  = 32
  special = false
}

resource "google_secret_manager_secret_version" "kuma_admin_password" {
  secret      = "projects/${var.project_id}/secrets/kuma-admin-password"
  secret_data = random_password.kuma_admin.result

  depends_on = [module.secrets]
}

# 7a. Cloud Run service — MLflow tracking server.
# Backend is Neon free tier (postgres) instead of Cloud SQL — persists across
# `make destroy` cycles and costs €0/mo. DSN is `neon-deepcab-dsn` in Secret
# Manager (populated manually after one-time Neon project creation; see
# docs/RUNBOOK.md §1.7).
#
# Image: GAR-mirrored MLflow (ghcr.io is rejected by Cloud Run). To refresh:
#   gcloud builds submit --config=cloud-manifests/mlflow/mirror.yaml --no-source
#
# Quirk: ghcr.io/mlflow/mlflow ships without psycopg2. Install it on boot, then
# exec mlflow server. Same hack as local docker-compose; swap for a custom
# image baked from this base + `pip install psycopg2-binary` when cold-start
# time becomes a real cost.
module "cloud_run_mlflow" {
  source     = "../../modules/cloud_run_service"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  service_name          = "deepcab-mlflow"
  component             = "cloud-run-mlflow"
  image                 = "europe-west1-docker.pkg.dev/garassino-ml/deepcab/mlflow:v2.16.2"
  service_account_email = module.wif.runtime_sa_email

  cpu                   = "1"
  memory                = "1Gi"
  min_instances         = 0
  max_instances         = 2
  container_concurrency = 40
  container_port        = 5000

  command = ["bash", "-c"]
  args = [
    "pip install --no-cache-dir psycopg2-binary && exec mlflow server --host 0.0.0.0 --port 5000 --backend-store-uri \"$${DEEPCAB_NEON_DSN}\" --default-artifact-root 'gs://${module.storage.mlflow_artifacts_bucket}/' --serve-artifacts"
  ]

  env_vars = {
    MLFLOW_TRACKING_URI = "http://0.0.0.0:5000"
  }

  secret_env_vars = {
    DEEPCAB_NEON_DSN = "neon-deepcab-dsn"
  }

  startup_probe_path             = "/"
  liveness_probe_path            = "/"
  startup_probe_period_seconds   = 3
  startup_probe_timeout_seconds  = 3
  liveness_probe_period_seconds  = 30
  liveness_probe_timeout_seconds = 3

  labels = local.common_labels

  depends_on = [module.secrets, module.storage]
}

# Uptime Kuma needs read+write on its gcsfuse-mounted state bucket
# (writes SQLite, error.log, uploads). Runtime SA only has objectViewer
# project-wide; grant objectAdmin on this one bucket explicitly.
resource "google_storage_bucket_iam_member" "status_bucket_admin" {
  bucket = module.storage.status_state_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.wif.runtime_sa_email}"
}

# Same for MLflow artifacts bucket (MLflow writes run artifacts there).
resource "google_storage_bucket_iam_member" "mlflow_artifacts_admin" {
  bucket = module.storage.mlflow_artifacts_bucket
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.wif.runtime_sa_email}"
}

# 7c. Cloud Run service — Uptime Kuma status page (statuspage.io look).
# Persistence: SQLite at /app/data/kuma.db on a gcsfuse-mounted bucket so
# probe history survives revisions.
module "cloud_run_status" {
  source     = "../../modules/cloud_run_service"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  service_name          = "deepcab-status"
  component             = "cloud-run-status"
  image                 = "docker.io/louislam/uptime-kuma:1"
  service_account_email = module.wif.runtime_sa_email

  cpu                   = "1"
  memory                = "512Mi"
  min_instances         = var.showcase_mode ? 1 : 0
  max_instances         = 1
  container_concurrency = 80
  timeout_seconds       = 30
  container_port        = 3001

  volumes = [
    {
      name          = "kuma-data"
      type          = "gcs"
      gcs_bucket    = module.storage.status_state_bucket
      gcs_read_only = false
    },
  ]

  volume_mounts = [
    { name = "kuma-data", mount_path = "/app/data" },
  ]

  startup_probe_path             = "/"
  liveness_probe_path            = "/"
  startup_probe_period_seconds   = 5
  startup_probe_timeout_seconds  = 3
  liveness_probe_period_seconds  = 60
  liveness_probe_timeout_seconds = 5

  labels = local.common_labels

  depends_on = [module.storage]
}

# 7b. Cloud Run service — static SPA (Vite+React+nginx)
module "cloud_run_website" {
  source     = "../../modules/cloud_run_service"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  service_name          = "deepcab-website"
  component             = "cloud-run-website"
  image                 = var.website_image
  service_account_email = module.wif.runtime_sa_email

  cpu                   = "1"
  memory                = "256Mi"
  min_instances         = 0
  max_instances         = 2
  container_concurrency = 200
  timeout_seconds       = 30
  container_port        = 80
  allow_unauthenticated = true

  startup_probe_path                  = "/"
  liveness_probe_path                 = "/"
  startup_probe_initial_delay_seconds = 1
  startup_probe_failure_threshold     = 10
  liveness_probe_period_seconds       = 30

  labels = local.common_labels

  depends_on = [module.gar]
}

# 8. Cloud Run Job (retrain)
module "cloud_run_job" {
  source     = "../../modules/cloud_run_job"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  image                 = var.retrain_image
  service_account_email = module.wif.runtime_sa_email
  scheduler_sa_email    = module.wif.scheduler_sa_email

  cpu                  = "2"
  memory               = "4Gi"
  task_timeout_seconds = 1800

  args = [
    "-m",
    "deepCab.training.train",
    "backend=tf_mlp",
    "data=1k",
  ]

  env_vars = {
    APP_ENV             = "dev"
    MLFLOW_TRACKING_URI = module.cloud_run_mlflow.service_url
    MODEL_TARGET        = "gcs"
    GCP_PROJECT         = var.project_id
    REGISTRY_GCS_BUCKET = module.storage.models_bucket
  }

  # No secrets needed for the retrain Job — MLflow tracking server fronts the
  # Neon DSN; the Job only talks to the MLflow URL.
  secret_env_vars = {}

  labels = local.common_labels

  depends_on = [module.secrets]
}

# 9. Cloud Scheduler (paused in dev — fires manually only)
module "scheduler" {
  source     = "../../modules/scheduler"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  target_uri            = module.cloud_run_job.execute_uri
  service_account_email = module.wif.scheduler_sa_email
  paused                = true
}

# 10. DNS disabled in dev
module "dns" {
  source     = "../../modules/dns"
  project_id = var.project_id
  env        = local.env
  enabled    = false
}

# 11. GKE disabled in dev
module "gke" {
  source     = "../../modules/gke"
  project_id = var.project_id
  region     = var.region
  env        = local.env
  enabled    = false
}

# 12. Cross-cutting IAM (no budget in dev)
module "iam" {
  source     = "../../modules/iam"
  project_id = var.project_id
  env        = local.env
}

# 13. BigQuery — dataset + raw taxi-trip table for the simulation loop.
# Populated out-of-band by `deepcab-platform data clone-bq`; table has
# deletion_protection so make destroy keeps the cloned slice.
module "bigquery" {
  source     = "../../modules/bigquery"
  project_id = var.project_id
  location   = var.region
  labels     = local.common_labels
}
