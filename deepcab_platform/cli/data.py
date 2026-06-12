"""`deepcab-platform data clone-bq` — one-shot cross-region BQ table clone."""

from __future__ import annotations

import typer
from rich import print as rprint

from deepcab_platform.deps import get_data_clone_service
from deepcab_platform.schemas.data import DataCloneBqInputs
from deepcab_platform.schemas.enums import ProviderMode

data_app = typer.Typer(help="BigQuery data operations.", no_args_is_help=True)


@data_app.command("clone-bq")
def clone_bq(
    source_table: str = typer.Option("nyc-tlc:yellow.trips", "--source-table"),
    target_project: str = typer.Option("garassino-ml", "--target-project"),
    target_dataset: str = typer.Option("taxi", "--target-dataset"),
    target_table: str = typer.Option("yellow_trips_raw", "--target-table"),
    target_location: str = typer.Option("europe-west1", "--target-location"),
    source_location: str = typer.Option("US", "--source-location"),
    year: int = typer.Option(2014, "--year", min=2009, max=2026),
    staging_bucket_us: str = typer.Option("garassino-ml-bq-staging-us", "--staging-us"),
    staging_bucket_eu: str = typer.Option("garassino-ml-bq-staging-eu", "--staging-eu"),
    cleanup_staging: bool = typer.Option(True, "--cleanup/--keep-staging"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Three-step cross-region clone: extract (US) → gsutil cp → load (EU).

    Idempotent — re-runs skip steps whose outputs already exist. After the
    first successful clone, re-running is cheap and only verifies the EU
    table still has rows.
    """
    inputs = DataCloneBqInputs(
        source_table=source_table,
        target_project=target_project,
        target_dataset=target_dataset,
        target_table=target_table,
        target_location=target_location,
        source_location=source_location,
        year=year,
        staging_bucket_us=staging_bucket_us,
        staging_bucket_eu=staging_bucket_eu,
        cleanup_staging=cleanup_staging,
    )
    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    svc = get_data_clone_service(mode)
    result = svc.clone(inputs)

    rprint(f"[bold green]✓ clone-bq done[/bold green] table=[cyan]{result.qualified_table}[/cyan] location={result.location}")
    rprint(
        f"  steps:  extract={'skipped' if result.skipped_extract else 'ran'} · "
        f"copy={'skipped' if result.skipped_copy else 'ran'} · "
        f"load={'skipped' if result.skipped_load else 'ran'}"
    )
    if result.rows_loaded is not None:
        rprint(f"  rows:   [cyan]{result.rows_loaded:,}[/cyan]")
    if result.staging_buckets_deleted:
        rprint("  cleanup: staging buckets emptied")
