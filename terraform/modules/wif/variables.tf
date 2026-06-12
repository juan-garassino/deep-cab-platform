variable "project_id" {
  description = "GCP project ID."
  type        = string
}

variable "project_number" {
  description = "GCP project number (numeric — used in principalSet identifiers)."
  type        = string
}

variable "gh_owner" {
  description = "GitHub org/user that hosts the API repo (e.g. juan-garassino)."
  type        = string
}

variable "gh_repo" {
  description = "GitHub repo name allowed to impersonate the deployer SA (e.g. deepCab)."
  type        = string
}

variable "platform_gh_repo" {
  description = "GitHub repo name of THIS platform repo, allowed to run terraform plan/apply."
  type        = string
  default     = "deepCab-platform"
}

variable "website_gh_repo" {
  description = "GitHub repo name of the website repo (003), also allowed to impersonate the deployer SA for image builds + Cloud Run image swaps."
  type        = string
  default     = "deepCab-website"
}

variable "pool_id" {
  description = "Workload Identity Pool ID."
  type        = string
  default     = "github-pool"
}

variable "provider_id" {
  description = "Workload Identity Pool Provider ID."
  type        = string
  default     = "github-provider"
}

variable "deployer_sa_id" {
  description = "Account ID for the deployer SA (used by 001 CI to push images + image-only updates)."
  type        = string
  default     = "deepcab-deployer"
}

variable "runtime_sa_id" {
  description = "Account ID for the runtime SA (impersonated by Cloud Run/GKE workloads)."
  type        = string
  default     = "deepcab-runtime"
}

variable "scheduler_sa_id" {
  description = "Account ID for the Cloud Scheduler SA (invokes the retrain Job)."
  type        = string
  default     = "deepcab-scheduler"
}

variable "terraform_sa_id" {
  description = "Account ID for the Terraform planner/applier SA (used by THIS platform repo's CI)."
  type        = string
  default     = "deepcab-terraform"
}

variable "deployer_project_roles" {
  description = "Project-level roles granted to the deployer SA. Trimmed and audited per environment."
  type        = list(string)
  default = [
    "roles/run.developer",
    "roles/run.admin",
    "roles/artifactregistry.writer",
    "roles/iam.serviceAccountUser",
    "roles/storage.objectAdmin",
    "roles/container.admin",
  ]
}

variable "runtime_project_roles" {
  description = "Project-level roles granted to the runtime SA."
  type        = list(string)
  default = [
    "roles/storage.objectViewer",
    "roles/secretmanager.secretAccessor",
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
    "roles/cloudsql.client",
    # train-on-vm: VM self-destructs at end of training run.
    "roles/compute.instanceAdmin.v1",
    # Continuous-training simulation: scan garassino-ml.taxi.yellow_trips_raw
    # from BigQuery + run queries via the BQ job runner. dataEditor is needed
    # by `data clone-bq` for the final `bq load` step into the EU table.
    "roles/bigquery.dataViewer",
    "roles/bigquery.dataEditor",
    "roles/bigquery.jobUser",
  ]
}

variable "terraform_project_roles" {
  description = "Project-level roles granted to the terraform SA. Broad — only used by CI from the platform repo."
  type        = list(string)
  default = [
    "roles/editor",
    "roles/iam.securityAdmin",
    "roles/resourcemanager.projectIamAdmin",
  ]
}

variable "labels" {
  description = "Labels applied to each SA where supported."
  type        = map(string)
  default     = {}
}
