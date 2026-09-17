output "project_id" {
  value = var.project_id
}

output "region" {
  value = var.region
}

output "gar_repo_url" {
  value = module.gar.repo_url
}

output "models_bucket" {
  value = module.storage.models_bucket
}

output "mlflow_artifacts_bucket" {
  value = module.storage.mlflow_artifacts_bucket
}

output "wif_provider_name" {
  description = "Pass to GitHub Actions as `workload_identity_provider`."
  value       = module.wif.provider_name
}

output "deployer_sa_email" {
  description = "Pass to GitHub Actions as `service_account`."
  value       = module.wif.deployer_sa_email
}

output "terraform_sa_email" {
  description = "SA used by THIS repo's platform-plan / platform-apply workflows."
  value       = module.wif.terraform_sa_email
}

output "runtime_sa_email" {
  value = module.wif.runtime_sa_email
}

output "api_service_url" {
  description = "Cloud Run URL of the deepcab-api service."
  value       = module.cloud_run_api.service_url
}

output "website_service_url" {
  description = "Cloud Run URL of the deepcab-website SPA."
  value       = module.cloud_run_website.service_url
}

output "mlflow_service_url" {
  description = "Cloud Run URL of the deepcab-mlflow tracking server."
  value       = module.cloud_run_mlflow.service_url
}

output "status_page_url" {
  description = "Public Uptime Kuma status page."
  value       = module.cloud_run_status.service_url
}

output "retrain_job_name" {
  value = module.cloud_run_job.job_name
}

# cloud_sql_connection_name output removed 2026-06-07 alongside the cloud_sql
# module — MLflow now uses Neon, not Cloud SQL.

output "bq_qualified_table" {
  description = "Fully-qualified BQ table for the simulation loop (project.dataset.table)."
  value       = module.bigquery.qualified_table
}

output "bq_dataset_id" {
  value = module.bigquery.dataset_id
}

output "bq_location" {
  value = module.bigquery.location
}
