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
  value = module.wif.provider_name
}

output "deployer_sa_email" {
  value = module.wif.deployer_sa_email
}

output "terraform_sa_email" {
  value = module.wif.terraform_sa_email
}

output "runtime_sa_email" {
  value = module.wif.runtime_sa_email
}

output "api_service_url" {
  value = module.cloud_run_api.service_url
}

output "retrain_job_name" {
  value = module.cloud_run_job.job_name
}

output "cloud_sql_connection_name" {
  value = module.cloud_sql.connection_name
}

output "gke_enabled" {
  value = module.gke.enabled
}

output "gke_cluster_name" {
  value = module.gke.cluster_name
}
