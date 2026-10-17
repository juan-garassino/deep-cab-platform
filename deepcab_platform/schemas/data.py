"""Pydantic models for `deepcab-platform data clone-bq`.

One-shot cross-region copy of a public NYC TLC table into our EU dataset.
BigQuery refuses CREATE-TABLE-AS-SELECT across regions, so the operation
runs as three subprocess steps (export to GCS, gsutil cp, bq load) — all
inputs are validated at the boundary so a typo in --year or a malformed
table name fails before any cloud call.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

_BUCKET = r"^[a-z0-9][a-z0-9_.-]{1,61}[a-z0-9]$"
_SOURCE_TABLE = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9][.:][A-Za-z0-9_]{1,1024}\.[A-Za-z0-9_-]{1,1024}")


class DataCloneBqInputs(BaseModel):
    model_config = {"extra": "forbid"}

    source_table: str = Field(
        default="nyc-tlc:yellow.trips",
        description="Public source in `<project>:<dataset>.<table>` or `<project>.<dataset>.<table>` form.",
    )
    # Identifier patterns: these are interpolated into a backtick-quoted BQ SQL
    # string and gs:// URIs, so reject anything outside the documented charsets.
    target_project: str = Field(default="garassino-ml", pattern=r"^[a-z][a-z0-9-]{4,28}[a-z0-9]$")
    target_dataset: str = Field(default="taxi", pattern=r"^[A-Za-z0-9_]{1,1024}$")
    target_table: str = Field(default="yellow_trips_raw", pattern=r"^[A-Za-z0-9_-]{1,1024}$")
    target_location: str = "europe-west1"
    source_location: str = "US"  # nyc-tlc lives in US

    year: int = Field(default=2014, ge=2009, le=2026)
    staging_bucket_us: str = Field(default="garassino-ml-bq-staging-us", pattern=_BUCKET)
    staging_bucket_eu: str = Field(default="garassino-ml-bq-staging-eu", pattern=_BUCKET)

    cleanup_staging: bool = True

    @field_validator("source_table")
    @classmethod
    def _valid_source(cls, v: str) -> str:
        # Allow both `project:dataset.table` and `project.dataset.table` forms.
        # The value is spliced into backtick-quoted SQL, so the charset is strict.
        if not _SOURCE_TABLE.fullmatch(v):
            raise ValueError("source_table must be project[:|.]dataset.table")
        return v

    @property
    def source_table_sql(self) -> str:
        """`project.dataset.table` form, as used inside a backtick-quoted SQL identifier."""
        return self.source_table.replace(":", ".", 1)


class DataCloneBqResult(BaseModel):
    model_config = {"extra": "forbid"}

    qualified_table: str
    location: str
    rows_loaded: int | None = None
    skipped_extract: bool = False
    skipped_copy: bool = False
    skipped_load: bool = False
    staging_buckets_deleted: bool = False
