# Artifact Registry repo holding all deepCab Docker images.
# The 001-deepCab-api and 003-deepCab-website CI workflows push here; the 002
# platform repo references the resulting URLs in the cloud_run / cloud_run_job
# / cloud_run_website modules. Image names: api, retrain, website.

resource "google_artifact_registry_repository" "deepcab" {
  project       = var.project_id
  location      = var.region
  repository_id = var.repo_id
  description   = var.description
  format        = "DOCKER"
  labels        = var.labels

  # Keep only a sane number of images / versions per env to avoid the unbounded
  # GAR storage cost that bites every team eventually.
  cleanup_policies {
    id     = "keep-tagged-recent"
    action = "KEEP"
    most_recent_versions {
      package_name_prefixes = ["api", "retrain", "website", "mlflow"]
      keep_count            = 10
    }
  }

  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "604800s" # 7 days
    }
  }
}
