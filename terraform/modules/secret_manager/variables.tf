variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Region for the user-managed replica policy."
  type        = string
}

variable "env" {
  description = "Environment short name."
  type        = string
}

variable "runtime_sa_email" {
  description = "Runtime SA email — granted secretAccessor on each secret."
  type        = string
}

variable "secret_ids" {
  description = "Secret IDs to provision (no initial value — populate via `gcloud secrets versions add`)."
  type        = list(string)
  default = [
    "slack-webhook-url",
    "openai-api-key",
    "deepcab-api-key",
    "kuma-admin-password",
    # MLflow tracking backend DSN (Neon free tier, populated manually after
    # one-time Neon provisioning). Replaces the deprecated mlflow-db-password
    # that paired with Cloud SQL.
    "neon-deepcab-dsn",
  ]
}

variable "labels" {
  description = "Labels applied to each secret."
  type        = map(string)
  default     = {}
}
