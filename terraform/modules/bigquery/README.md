# bigquery module

Provisions the BigQuery dataset + raw taxi-trip table that backs the
continuous-training simulation loop.

The table is **populated out-of-band** via
`deepcab-platform data clone-bq` (cross-region export-load pattern;
BigQuery doesn't allow CREATE-TABLE-AS-SELECT across regions). Terraform
owns the empty shape so the IAM roles + schema + partitioning are
declarative; data lives across `make destroy` cycles thanks to
`deletion_protection = true` on the table itself.

## Usage

```hcl
module "bigquery" {
  source     = "../../modules/bigquery"
  project_id = var.project_id
  location   = var.region          # europe-west1
  labels     = local.common_labels
}
```

## Where the data comes from

| Step | Cmd |
| --- | --- |
| 1 — extract source slice (US) | `bq query --location=US ... < cloud-manifests/bq/yellow_trips_raw.export.sql` |
| 2 — cross-region copy        | `gsutil -m cp -r gs://...-staging-us/ gs://...-staging-eu/` |
| 3 — load into EU table       | `bq load --location=europe-west1 ... <table> gs://...-staging-eu/*.parquet` |

All three steps are wrapped (idempotently) by:

```bash
uv run deepcab-platform data clone-bq --year 2014
```

## Why deletion_protection on the table

Re-pulling the slice costs ~€3 of cross-region egress + ~10 min of wall
clock. Show-and-destroy stacks blow away IAM + Cloud Run + Cloud SQL each
cycle; this table is one of two pieces we deliberately keep (the other is
GAR images). Toggle `table_deletion_protection = false` only when you
genuinely want to wipe and re-pull.
