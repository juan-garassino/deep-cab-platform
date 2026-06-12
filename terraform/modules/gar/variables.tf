variable "project_id" {
  description = "GCP project ID hosting the Artifact Registry repo."
  type        = string
}

variable "region" {
  description = "Region the Artifact Registry repo lives in (e.g. europe-west1)."
  type        = string
}

variable "repo_id" {
  description = "Artifact Registry repository ID. Forms the second path segment of the image URL."
  type        = string
  default     = "deepcab"
}

variable "description" {
  description = "Free-form description shown in the GCP console."
  type        = string
  default     = "deepCab container images (api, retrain job, website)"
}

variable "labels" {
  description = "Labels applied to the repository for cost-allocation."
  type        = map(string)
  default     = {}
}
