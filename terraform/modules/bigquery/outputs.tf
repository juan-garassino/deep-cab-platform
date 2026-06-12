output "dataset_id" {
  description = "Bare dataset ID (e.g. \"taxi\")."
  value       = google_bigquery_dataset.taxi.dataset_id
}

output "table_id" {
  description = "Bare table ID (e.g. \"yellow_trips_raw\")."
  value       = google_bigquery_table.yellow_trips_raw.table_id
}

output "qualified_table" {
  description = "Fully-qualified table reference for queries: project.dataset.table."
  value       = "${var.project_id}.${google_bigquery_dataset.taxi.dataset_id}.${google_bigquery_table.yellow_trips_raw.table_id}"
}

output "location" {
  description = "BigQuery region — must match GCS bucket + Cloud Run region."
  value       = google_bigquery_dataset.taxi.location
}
