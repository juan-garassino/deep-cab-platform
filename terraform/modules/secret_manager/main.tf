# Secret Manager — declares the secret containers, NOT their values.
#
# Values are populated out-of-band after first apply:
#
#   gcloud secrets versions add slack-webhook-url --data-file=- <<< "$URL"
#
# Rationale: secret values should never live in Terraform state (state is
# stored in GCS and read by CI). Declaring the containers in TF is enough to
# enforce IAM and lifecycle.

module "labels" {
  source       = "../_labels"
  env          = var.env
  component    = "deepcab-platform"
  extra_labels = var.labels
}

locals {
  secret_set = toset(var.secret_ids)
}

resource "google_secret_manager_secret" "this" {
  for_each  = local.secret_set
  project   = var.project_id
  secret_id = each.value
  labels    = module.labels.labels

  replication {
    user_managed {
      replicas {
        location = var.region
      }
    }
  }
}

# Runtime SA can read every secret.
resource "google_secret_manager_secret_iam_member" "runtime_accessor" {
  for_each  = local.secret_set
  project   = var.project_id
  secret_id = google_secret_manager_secret.this[each.value].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${var.runtime_sa_email}"
}
