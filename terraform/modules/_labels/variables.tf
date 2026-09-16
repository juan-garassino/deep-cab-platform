variable "env" {
  description = "Environment short name (dev/staging/prod). Becomes the `env` label."
  type        = string
}

variable "component" {
  description = "Component slug (e.g. `deepcab-platform`, `deepcab-mlflow`). Becomes the `component` label."
  type        = string
}

variable "extra_labels" {
  description = "Caller-supplied labels merged on top of the canonical {env, managed, component} block. Later keys win on collision."
  type        = map(string)
  default     = {}
}
