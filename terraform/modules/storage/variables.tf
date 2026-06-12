variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Bucket location (single region — e.g. europe-west1)."
  type        = string
}

variable "env" {
  description = "Environment short name (dev/staging/prod)."
  type        = string
}

variable "name_prefix" {
  description = "Prefix used to construct unique bucket names. Typically the project ID or org slug."
  type        = string
  default     = "deepcab"
}

variable "force_destroy" {
  description = "If true, allows `terraform destroy` to delete buckets that still contain objects. Use only in dev."
  type        = bool
  default     = false
}

variable "mlflow_artifacts_lifecycle_days" {
  description = "Days before mlflow artifacts are moved to NEARLINE."
  type        = number
  default     = 30
}

variable "models_archive_days" {
  description = "Days before model artifacts are archived (COLDLINE)."
  type        = number
  default     = 90
}

variable "labels" {
  description = "Labels applied to every bucket."
  type        = map(string)
  default     = {}
}
