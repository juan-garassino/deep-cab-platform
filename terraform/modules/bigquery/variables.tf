variable "project_id" {
  description = "GCP project hosting the BigQuery dataset (garassino-ml in dev)."
  type        = string
}

variable "location" {
  description = "BigQuery region. Must match where Cloud Run + GCS live so Polars/api reads don't egress cross-region."
  type        = string
  default     = "europe-west1"
}

variable "dataset_id" {
  description = "Dataset name. Tables live under this dataset (e.g. <project>.<dataset>.yellow_trips_raw)."
  type        = string
  default     = "taxi"
}

variable "table_id" {
  description = "Raw table name. Populated by the one-shot cross-region clone of nyc-tlc.yellow.trips."
  type        = string
  default     = "yellow_trips_raw"
}

variable "table_deletion_protection" {
  description = "Stop `terraform destroy` from wiping the multi-GB cloned table. Toggle off only before a one-off teardown."
  type        = bool
  default     = true
}

variable "labels" {
  description = "Labels propagated to the dataset for cost-allocation."
  type        = map(string)
  default     = {}
}
