"""Pydantic models for `deepcab-platform data clone-bq`.

One-shot cross-region copy of a public NYC TLC table into our EU dataset.
BigQuery refuses CREATE-TABLE-AS-SELECT across regions, so the operation
runs as three subprocess steps (export to GCS, gsutil cp, bq load) — all
inputs are validated at the boundary so a typo in --year or a malformed
table name fails before any cloud call.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class DataCloneBqInputs(BaseModel):
    model_config = {"extra": "forbid"}

    source_table: str = Field(
        default="nyc-tlc:yellow.trips",
        description="Public source in `<project>:<dataset>.<table>` or `<project>.<dataset>.<table>` form.",
    )
    target_project: str = "garassino-ml"
    target_dataset: str = "taxi"
    target_table: str = "yellow_trips_raw"
    target_location: str = "europe-west1"
    source_location: str = "US"  # nyc-tlc lives in US

    year: int = Field(default=2014, ge=2009, le=2026)
    staging_bucket_us: str = "garassino-ml-bq-staging-us"
    staging_bucket_eu: str = "garassino-ml-bq-staging-eu"

    cleanup_staging: bool = True

    @field_validator("source_table")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        # Allow both `project:dataset.table` and `project.dataset.table` forms.
        normalised = v.replace(":", ".", 1)
        if normalised.count(".") != 2:
            raise ValueError("source_table must be project[:|.]dataset.table")
        return v


class DataCloneBqResult(BaseModel):
    model_config = {"extra": "forbid"}

    qualified_table: str
    location: str
    rows_loaded: int | None = None
    skipped_extract: bool = False
    skipped_copy: bool = False
    skipped_load: bool = False
    staging_buckets_deleted: bool = False
