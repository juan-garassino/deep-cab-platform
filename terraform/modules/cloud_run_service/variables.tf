variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Region for the Cloud Run service."
  type        = string
}

variable "env" {
  description = "Environment short name (dev/staging/prod). Becomes a label."
  type        = string
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
}

variable "component" {
  description = "Short component name for labels (e.g. `cloud-run-api`, `cloud-run-mlflow`)."
  type        = string
}

variable "image" {
  description = "Docker image including tag. CI swaps this on releases — `lifecycle.ignore_changes` keeps TF from reverting."
  type        = string
}

variable "service_account_email" {
  description = "Runtime SA email."
  type        = string
}

variable "cpu" {
  description = "Container CPU."
  type        = string
  default     = "1"
}

variable "memory" {
  description = "Container memory."
  type        = string
  default     = "512Mi"
}

variable "min_instances" {
  description = "Minimum number of warm instances."
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of instances."
  type        = number
  default     = 4
}

variable "container_concurrency" {
  description = "Max in-flight requests per instance."
  type        = number
  default     = 80
}

variable "timeout_seconds" {
  description = "Per-request timeout."
  type        = number
  default     = 60
}

variable "container_port" {
  description = "Container port the service listens on."
  type        = number
  default     = 8000
}

variable "env_vars" {
  description = "Plain (non-secret) env vars."
  type        = map(string)
  default     = {}
}

variable "secret_env_vars" {
  description = "Env vars sourced from Secret Manager (`{ ENV_VAR = secret_id }`). Always uses the `latest` version."
  type        = map(string)
  default     = {}
}

variable "command" {
  description = "Optional container entrypoint override (list of strings, e.g. `[\"bash\", \"-c\"]`)."
  type        = list(string)
  default     = null
}

variable "args" {
  description = "Optional container args override (list of strings)."
  type        = list(string)
  default     = null
}

variable "volumes" {
  description = <<-EOT
    Optional list of volume specs. Each entry:
      - `name`             (string, required)
      - `type`             ("cloud_sql" | "gcs", required)
      - `cloud_sql_instances` (list(string), required when type == "cloud_sql")
      - `gcs_bucket`       (string, required when type == "gcs")
      - `gcs_read_only`    (bool, optional — defaults to false)
  EOT
  type = list(object({
    name                = string
    type                = string
    cloud_sql_instances = optional(list(string), [])
    gcs_bucket          = optional(string, "")
    gcs_read_only       = optional(bool, false)
  }))
  default = []
}

variable "volume_mounts" {
  description = "Optional list of `{ name, mount_path }` to mount the volumes above into the container."
  type = list(object({
    name       = string
    mount_path = string
  }))
  default = []
}

variable "startup_probe_path" {
  description = "HTTP path for the startup probe."
  type        = string
  default     = "/healthz"
}

variable "liveness_probe_path" {
  description = "HTTP path for the liveness probe."
  type        = string
  default     = "/healthz"
}

variable "startup_probe_initial_delay_seconds" {
  description = "Initial delay before the startup probe runs."
  type        = number
  default     = 5
}

variable "startup_probe_period_seconds" {
  description = "Seconds between startup probe attempts."
  type        = number
  default     = 2
}

variable "startup_probe_failure_threshold" {
  description = "Consecutive startup probe failures before the container is killed."
  type        = number
  default     = 30
}

variable "startup_probe_timeout_seconds" {
  description = "Per-attempt timeout for the startup probe."
  type        = number
  default     = 2
}

variable "liveness_probe_period_seconds" {
  description = "Seconds between liveness probe attempts."
  type        = number
  default     = 10
}

variable "liveness_probe_failure_threshold" {
  description = "Consecutive liveness probe failures before the container is killed."
  type        = number
  default     = 3
}

variable "liveness_probe_timeout_seconds" {
  description = "Per-attempt timeout for the liveness probe."
  type        = number
  default     = 2
}

variable "allow_unauthenticated" {
  description = "If true, grant `roles/run.invoker` to allUsers (public service)."
  type        = bool
  default     = true
}

variable "ingress" {
  description = "Cloud Run ingress (INGRESS_TRAFFIC_ALL | INGRESS_TRAFFIC_INTERNAL_ONLY | INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER)."
  type        = string
  default     = "INGRESS_TRAFFIC_ALL"
}

variable "labels" {
  description = "Labels applied to the service. Merged with `env`, `managed=terraform`, `component=<var.component>`."
  type        = map(string)
  default     = {}
}
