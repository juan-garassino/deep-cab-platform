variable "project_id" {
  description = "GCP project ID for staging."
  type        = string
}

variable "project_number" {
  description = "GCP project number."
  type        = string
}

variable "region" {
  description = "Primary region."
  type        = string
  default     = "europe-west1"
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
  default = "https://mlflow.staging.deepcab.com"
}

variable "dns_zone_name" {
  description = "Cloud DNS managed zone (e.g. `deepcab-com`). Empty disables DNS."
  type        = string
  default     = ""
}

variable "dns_name" {
  description = "DNS zone name with trailing dot."
  type        = string
  default     = ""
}
