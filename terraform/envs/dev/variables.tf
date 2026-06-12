variable "project_id" {
  description = "GCP project ID for the dev environment."
  type        = string
}

variable "project_number" {
  description = "GCP project number (used in WIF principalSet identifiers)."
  type        = string
}

variable "region" {
  description = "Primary region."
  type        = string
  default     = "europe-west1"
}

variable "gh_owner" {
  description = "GitHub owner (org/user) of both deepCab repos."
  type        = string
  default     = "juan-garassino"
}

variable "gh_api_repo" {
  description = "Name of the API repo (image builder)."
  type        = string
  default     = "deepCab"
}

variable "gh_platform_repo" {
  description = "Name of THIS platform repo."
  type        = string
  default     = "deepCab-platform"
}

variable "gh_website_repo" {
  description = "Name of the website repo (003), allowed to push images + image-only Cloud Run updates."
  type        = string
  default     = "deepCab-website"
}

variable "api_image" {
  description = "Initial API container image. Default = bootstrap placeholder; first real image lands after 001 CI runs."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "retrain_image" {
  description = "Initial retrain container image."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "website_image" {
  description = "Initial website (static SPA) container image. Real image lands after 003 CI runs."
  type        = string
  default     = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "showcase_mode" {
  description = <<-EOT
    Cost toggle for the dev environment.
      false (default, ~$0/mo idle): Cloud SQL stopped, Uptime Kuma min=0.
      true  (~$15/mo):              Cloud SQL ALWAYS, Uptime Kuma min=1.
    Flip via `make showcase_up` / `make showcase_down`.
  EOT
  type        = bool
  default     = false
}

variable "mlflow_tracking_uri" {
  description = "URL of the MLflow tracking server reachable from Cloud Run."
  type        = string
  default     = "http://mlflow.dev.deepcab.com:5000"
}
