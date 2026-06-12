variable "project_id" {
  description = "GCP project ID for prod."
  type        = string
}

variable "project_number" {
  description = "GCP project number."
  type        = string
}

variable "region" {
  type    = string
  default = "europe-west1"
}

variable "gh_owner" {
  type    = string
  default = "juan-garassino"
}

variable "gh_api_repo" {
  type    = string
  default = "deepCab"
}

variable "gh_platform_repo" {
  type    = string
  default = "deepCab-platform"
}

variable "gh_website_repo" {
  type    = string
  default = "deepCab-website"
}

variable "api_image" {
  type    = string
  default = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "retrain_image" {
  type    = string
  default = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "website_image" {
  type    = string
  default = "us-docker.pkg.dev/cloudrun/container/hello"
}

variable "mlflow_tracking_uri" {
  type    = string
  default = "https://mlflow.deepcab.com"
}

variable "dns_zone_name" {
  description = "Cloud DNS zone name (empty disables)."
  type        = string
  default     = ""
}

variable "dns_name" {
  description = "DNS zone name with trailing dot."
  type        = string
  default     = ""
}

variable "enable_gke" {
  description = "Toggle GKE provisioning on/off in prod."
  type        = bool
  default     = false
}

variable "budget_alert_email" {
  description = "Recipient for the prod budget alert. Empty disables the budget."
  type        = string
  default     = ""
}

variable "budget_amount_usd" {
  type    = number
  default = 200
}

variable "billing_account" {
  description = "GCP billing account ID (required when budget_alert_email is set)."
  type        = string
  default     = ""
}
