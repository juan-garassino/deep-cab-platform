"""DataCloneBqService — cross-region BQ table clone (US public → EU private).

Three-step pattern because BQ refuses CREATE-TABLE-AS-SELECT across
regions:

  1. ``bq query --location=US`` runs the rendered EXPORT DATA SQL from
     ``cloud-manifests/bq/yellow_trips_raw.export.sql`` into a US GCS
     staging bucket.
  2. ``gsutil -m cp -r`` moves the Parquet files from the US bucket to
     the EU bucket. Cross-region egress: ~€0.10/GB.
  3. ``bq load --location=europe-west1`` populates the EU table created
     by ``terraform/modules/bigquery``.

Idempotency: each step checks whether its output already exists. Re-runs
of the CLI skip completed steps so an interrupted clone can resume.
"""

from __future__ import annotations

import string
from dataclasses import dataclass
from pathlib import Path

from deepcab_platform.providers.gcloud import GcloudProvider
from deepcab_platform.schemas.data import DataCloneBqInputs, DataCloneBqResult


@dataclass
class DataCloneBqService:
    gcloud: GcloudProvider
    sql_template_path: Path = Path("cloud-manifests/bq/yellow_trips_raw.export.sql")

    def clone(self, inputs: DataCloneBqInputs) -> DataCloneBqResult:
        qualified = f"{inputs.target_project}.{inputs.target_dataset}.{inputs.target_table}"

        # Step 0: ensure staging buckets exist.
        self._ensure_bucket(inputs.staging_bucket_us, inputs.source_location)
        self._ensure_bucket(inputs.staging_bucket_eu, inputs.target_location)

        # Step 1: extract source → US bucket (skip if Parquet already present).
        us_prefix = f"gs://{inputs.staging_bucket_us}/yellow_trips_raw_{inputs.year}/"
        skipped_extract = self._gcs_prefix_has_parquet(us_prefix)
        if not skipped_extract:
            sql = self._render_export_sql(inputs)
            self.gcloud.run(
                [
                    "alpha", "bq", "query",
                    f"--project_id={inputs.target_project}",
                    f"--location={inputs.source_location}",
                    "--use_legacy_sql=false",
                    "--quiet",
                    "--nouse_cache",
                    sql,
                ],
            )

        # Step 2: cross-region copy → EU bucket.
        eu_prefix = f"gs://{inputs.staging_bucket_eu}/yellow_trips_raw_{inputs.year}/"
        skipped_copy = self._gcs_prefix_has_parquet(eu_prefix)
        if not skipped_copy:
            self.gcloud.run(
                [
                    "storage", "cp",
                    "--recursive",
                    f"{us_prefix}*",
                    eu_prefix,
                ],
            )

        # Step 3: load EU bucket → EU table (idempotent via --replace).
        rows = self._row_count(qualified, inputs.target_location)
        skipped_load = rows is not None and rows > 0
        if not skipped_load:
            self.gcloud.run(
                [
                    "alpha", "bq", "load",
                    f"--project_id={inputs.target_project}",
                    f"--location={inputs.target_location}",
                    "--source_format=PARQUET",
                    "--replace",
                    "--time_partitioning_field=pickup_datetime",
                    "--clustering_fields=pickup_datetime",
                    f"{inputs.target_project}:{inputs.target_dataset}.{inputs.target_table}",
                    f"{eu_prefix}*.parquet",
                ],
            )
            rows = self._row_count(qualified, inputs.target_location)

        # Step 4: optional cleanup of staging buckets.
        staging_deleted = False
        if inputs.cleanup_staging:
            self.gcloud.run(
                ["storage", "rm", "--recursive", f"{us_prefix}*"], check=False
            )
            self.gcloud.run(
                ["storage", "rm", "--recursive", f"{eu_prefix}*"], check=False
            )
            staging_deleted = True

        return DataCloneBqResult(
            qualified_table=qualified,
            location=inputs.target_location,
            rows_loaded=rows,
            skipped_extract=skipped_extract,
            skipped_copy=skipped_copy,
            skipped_load=skipped_load,
            staging_buckets_deleted=staging_deleted,
        )

    # ------------------------- internals --------------------------------------

    def _render_export_sql(self, inputs: DataCloneBqInputs) -> str:
        template = string.Template(self.sql_template_path.read_text())
        return template.safe_substitute(
            STAGING_BUCKET_US=inputs.staging_bucket_us,
            YEAR=str(inputs.year),
        )

    def _ensure_bucket(self, bucket: str, location: str) -> None:
        # `gcloud storage buckets create` returns non-zero when bucket exists;
        # check=False so we don't blow up on a benign re-create.
        self.gcloud.run(
            ["storage", "buckets", "create", f"gs://{bucket}", f"--location={location}"],
            check=False,
        )

    def _gcs_prefix_has_parquet(self, prefix: str) -> bool:
        out = self.gcloud.run(
            ["storage", "ls", f"{prefix}**.parquet"], check=False
        )
        return bool(out.strip())

    def _row_count(self, qualified: str, location: str) -> int | None:
        out = self.gcloud.run(
            [
                "alpha", "bq", "query",
                f"--location={location}",
                "--use_legacy_sql=false",
                "--format=value",
                "--quiet",
                f"SELECT COUNT(*) FROM `{qualified}`",
            ],
            check=False,
        )
        out = out.strip()
        if not out or not out.isdigit():
            return None
        return int(out)
