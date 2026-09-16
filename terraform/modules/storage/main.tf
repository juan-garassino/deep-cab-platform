# GCS buckets backing the deepCab stack.
#
# Shared defaults (project, location, storage_class, UBLA, force_destroy, labels)
# live in `local.bucket_defaults`. Each `google_storage_bucket` resource is kept
# as a distinct named address — state-stable — and only spells out the fields
# that diverge from the defaults plus its lifecycle/versioning blocks.
#
# - mlflow-artifacts: artifact store for MLflow runs (referenced by MLFLOW_ARTIFACT_URI)
# - models:           trained-model artifacts written by the retrain job / registry.dispatcher
# - status_state:     gcsfuse-mounted into the Uptime Kuma container (SQLite live-rewrites,
#                     so no versioning, no lifecycle)
# - tfstate:          remote state bucket. CHICKEN-AND-EGG — created manually first
#                     (see RUNBOOK.md), then imported. force_destroy hard-pinned to false.

module "labels" {
  source       = "../_labels"
  env          = var.env
  component    = "deepcab-platform"
  extra_labels = var.labels
}

locals {
  bucket_defaults = {
    project                     = var.project_id
    location                    = var.region
    storage_class               = "STANDARD"
    uniform_bucket_level_access = true
    force_destroy               = var.force_destroy
    labels                      = module.labels.labels
  }
}

resource "google_storage_bucket" "mlflow_artifacts" {
  name                        = "${var.name_prefix}-mlflow-artifacts-${var.env}"
  project                     = local.bucket_defaults.project
  location                    = local.bucket_defaults.location
  storage_class               = local.bucket_defaults.storage_class
  uniform_bucket_level_access = local.bucket_defaults.uniform_bucket_level_access
  force_destroy               = local.bucket_defaults.force_destroy
  labels                      = local.bucket_defaults.labels

  versioning { enabled = true }

  lifecycle_rule {
    condition { age = var.mlflow_artifacts_lifecycle_days }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
  lifecycle_rule {
    condition { num_newer_versions = 5 }
    action { type = "Delete" }
  }
}

resource "google_storage_bucket" "models" {
  name                        = "${var.name_prefix}-models-${var.env}"
  project                     = local.bucket_defaults.project
  location                    = local.bucket_defaults.location
  storage_class               = local.bucket_defaults.storage_class
  uniform_bucket_level_access = local.bucket_defaults.uniform_bucket_level_access
  force_destroy               = local.bucket_defaults.force_destroy
  labels                      = local.bucket_defaults.labels

  versioning { enabled = true }

  lifecycle_rule {
    condition { age = var.models_archive_days }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }
}

resource "google_storage_bucket" "status_state" {
  # gcsfuse-mounted at /app/data inside cloud_run_status. SQLite rewrites in place;
  # no versioning needed.
  name                        = "${var.name_prefix}-status-${var.env}"
  project                     = local.bucket_defaults.project
  location                    = local.bucket_defaults.location
  storage_class               = local.bucket_defaults.storage_class
  uniform_bucket_level_access = local.bucket_defaults.uniform_bucket_level_access
  force_destroy               = local.bucket_defaults.force_destroy
  labels                      = local.bucket_defaults.labels
}

resource "google_storage_bucket" "tfstate" {
  # Bootstrapped manually, then imported. force_destroy override stays false in
  # every env — state buckets must never be auto-deleted.
  name                        = "${var.name_prefix}-tfstate-${var.env}"
  project                     = local.bucket_defaults.project
  location                    = local.bucket_defaults.location
  storage_class               = local.bucket_defaults.storage_class
  uniform_bucket_level_access = local.bucket_defaults.uniform_bucket_level_access
  force_destroy               = false # explicit override
  labels                      = local.bucket_defaults.labels

  versioning { enabled = true }

  lifecycle_rule {
    condition {
      num_newer_versions = 30
      age                = 30
    }
    action { type = "Delete" }
  }
}
