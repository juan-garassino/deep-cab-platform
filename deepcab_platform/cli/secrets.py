"""`deepcab-platform secrets rotate` — push new secret version + bump consumers."""

from __future__ import annotations

import sys

import typer
from rich import print as rprint

from deepcab_platform.deps import get_secrets_service, settings
from deepcab_platform.schemas.enums import ProviderMode

secrets_app = typer.Typer(help="Secret Manager rotations.", no_args_is_help=True)


@secrets_app.command("rotate")
def rotate(
    secret_id: str = typer.Argument(..., help="e.g. openai-api-key"),
    from_stdin: bool = typer.Option(False, "--from-stdin", help="Read value from stdin"),
    from_env: str = typer.Option(
        None, "--from-env",
        help="Read value from the named env var (e.g. OPENAI_API_KEY)",
    ),
    project_id: str = typer.Option(
        None, "--project-id", "-p",
        help="GCP project. Defaults to settings.gcp.project.",
    ),
    region: str = typer.Option("europe-west1", "--region", "-r"),
    service: list[str] = typer.Option(
        None, "--service", "-s",
        help="Cloud Run service(s) to bump. Repeatable. Defaults to known consumers.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Push a new secret version and bump every Cloud Run service that consumes it."""
    if from_stdin == bool(from_env):
        raise typer.BadParameter("Provide exactly one of --from-stdin or --from-env <VAR>.")
    if from_stdin:
        value = sys.stdin.read().rstrip("\n")
    else:
        import os
        value = os.environ.get(from_env, "")
    if not value:
        raise typer.BadParameter(f"Empty value (from {'stdin' if from_stdin else from_env}).")

    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    svc = get_secrets_service(mode)
    pid = project_id or settings().gcp.project
    if not pid:
        raise typer.BadParameter("--project-id required (or set GCP_PROJECT in env).")

    result = svc.rotate(
        secret_id, value, project_id=pid, region=region,
        services=service if service else None,
    )
    rprint(
        f"[bold green]✓ rotated[/bold green] {result['secret']} → version "
        f"{result['new_version']!r}; bumped: {result['services_bumped'] or '(none)'}"
    )
