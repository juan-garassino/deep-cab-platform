"""`deepcab-platform mlflow ...` — MLflow image lifecycle."""

from __future__ import annotations

import typer
from rich import print as rprint

from deepcab_platform.deps import get_mlflow_service, settings
from deepcab_platform.schemas.enums import ProviderMode

mlflow_app = typer.Typer(help="MLflow image lifecycle (mirror, deploy).", no_args_is_help=True)


@mlflow_app.command("mirror")
def mirror(
    project_id: str = typer.Option(
        None, "--project-id", "-p",
        help="GCP project hosting the GAR repo. Defaults to settings.gcp.project.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Mirror ghcr.io/mlflow/mlflow → europe-west1-docker.pkg.dev/.../mlflow:tag via Cloud Build."""
    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    service = get_mlflow_service(mode)
    pid = project_id or settings().gcp.project
    if not pid:
        raise typer.BadParameter("--project-id is required (or set GCP_PROJECT in your env file).")
    out = service.mirror(pid)
    rprint(f"[bold green]✓ mirror complete[/bold green]\n{out}")
