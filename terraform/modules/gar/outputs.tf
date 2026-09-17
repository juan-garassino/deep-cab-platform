output "repo_id" {
  description = "Artifact Registry repository ID (short name)."
  value       = google_artifact_registry_repository.deepcab.repository_id
}

output "repo_url" {
  description = "Docker image URL prefix, e.g. europe-west1-docker.pkg.dev/PROJECT/deepcab."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.deepcab.repository_id}"
}

output "repo_name" {
  description = "Fully-qualified GAR resource name (projects/.../locations/.../repositories/...)."
  value       = google_artifact_registry_repository.deepcab.name
}
