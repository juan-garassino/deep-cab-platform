# BigQuery dataset + raw taxi-trip table.
#
# Holds the cross-region clone of `nyc-tlc.yellow.trips` (US, public) used by
# the continuous-training simulation loop. The clone itself is performed
# manually via `deepcab-platform data clone-bq` (export-to-GCS-then-load
# pattern; BQ doesn't allow cross-region CTAS).
#
# Why the table has `deletion_protection`:
#   - The cloned slice is ~30 GB and costs ~€3 of egress to re-pull. We don't
#     want a `make destroy` of the show-and-destroy stack to wipe it.
#   - Dataset itself stays destroyable; only the populated table is protected.
#
# Schema mirrors the columns selected by cloud-manifests/bq/yellow_trips_raw.export.sql.

resource "google_bigquery_dataset" "taxi" {
  project    = var.project_id
  dataset_id = var.dataset_id
  location   = var.location
  labels     = var.labels

  description = "Continuous-training simulation source. One-shot clone of nyc-tlc.yellow.trips (lat/lon)."

  # Dataset is cheap to recreate (no data lives at the dataset level), so we
  # don't protect it. The TABLE underneath is what holds the rows.
  delete_contents_on_destroy = false
}

resource "google_bigquery_table" "yellow_trips_raw" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.taxi.dataset_id
  table_id   = var.table_id
  labels     = var.labels

  deletion_protection = var.table_deletion_protection

  description = "Raw taxi trips cloned from nyc-tlc.yellow.trips. Time-partitioned on pickup_datetime."

  time_partitioning {
    type  = "DAY"
    field = "pickup_datetime"
  }

  clustering = ["pickup_datetime"]

  schema = jsonencode([
    { name = "vendor_id", type = "STRING", mode = "NULLABLE" },
    { name = "pickup_datetime", type = "TIMESTAMP", mode = "REQUIRED" },
    { name = "dropoff_datetime", type = "TIMESTAMP", mode = "NULLABLE" },
    { name = "pickup_longitude", type = "FLOAT64", mode = "NULLABLE" },
    { name = "pickup_latitude", type = "FLOAT64", mode = "NULLABLE" },
    { name = "dropoff_longitude", type = "FLOAT64", mode = "NULLABLE" },
    { name = "dropoff_latitude", type = "FLOAT64", mode = "NULLABLE" },
    { name = "passenger_count", type = "INT64", mode = "NULLABLE" },
    { name = "trip_distance", type = "FLOAT64", mode = "NULLABLE" },
    { name = "fare_amount", type = "FLOAT64", mode = "NULLABLE" },
    { name = "total_amount", type = "FLOAT64", mode = "NULLABLE" },
  ])
}
