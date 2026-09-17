output "service_name" {
  description = "Cloud Run service name (input to `gcloud run services update --image=...`)."
  value       = google_cloud_run_v2_service.this.name
}

output "service_url" {
  description = "Stable HTTPS URL of the service."
  value       = google_cloud_run_v2_service.this.uri
}

output "location" {
  description = "Region the service lives in."
  value       = google_cloud_run_v2_service.this.location
}

output "latest_revision" {
  description = "Name of the latest revision."
  value       = google_cloud_run_v2_service.this.latest_created_revision
}
