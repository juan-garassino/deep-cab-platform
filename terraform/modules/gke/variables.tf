variable "enabled" {
  description = "Module is a no-op when false. Default false — Cloud Run covers everything for now."
  type        = bool
  default     = false
}

variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "region" {
  description = "Region for the regional cluster."
  type        = string
}

variable "env" {
  description = "Environment short name."
  type        = string
}

variable "cluster_name" {
  description = "GKE cluster name."
  type        = string
  default     = "deepcab-gke"
}

variable "network" {
  description = "VPC self_link. Required when enabled."
  type        = string
  default     = ""
}

variable "subnet" {
  description = "Subnetwork ID. Required when enabled."
  type        = string
  default     = ""
}

variable "release_channel" {
  description = "GKE release channel."
  type        = string
  default     = "REGULAR"
}

variable "node_machine_type" {
  description = "Node pool machine type."
  type        = string
  default     = "e2-standard-2"
}

variable "min_node_count" {
  description = "Minimum nodes per zone."
  type        = number
  default     = 1
}

variable "max_node_count" {
  description = "Maximum nodes per zone."
  type        = number
  default     = 3
}

variable "runtime_sa_email" {
  description = "Runtime SA — bound to the GKE workload identity for pods."
  type        = string
  default     = ""
}

variable "enable_workload_identity" {
  description = "Enable GKE Workload Identity (recommended)."
  type        = bool
  default     = true
}

variable "labels" {
  description = "Labels applied to the cluster."
  type        = map(string)
  default     = {}
}

variable "master_authorized_cidrs" {
  description = "CIDRs allowed to reach the GKE control plane. Empty = no external access. Never use 0.0.0.0/0."
  type = list(object({
    name = string
    cidr = string
  }))
  default = []

  validation {
    condition     = alltrue([for c in var.master_authorized_cidrs : c.cidr != "0.0.0.0/0"])
    error_message = "0.0.0.0/0 is not allowed for the GKE control plane."
  }
}
