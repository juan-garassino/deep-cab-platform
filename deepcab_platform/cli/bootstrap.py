"""`deepcab-platform bootstrap` — create GCP project + WIF + state bucket."""

from __future__ import annotations

import typer
from rich import print as rprint

from deepcab_platform.deps import get_bootstrap_service
from deepcab_platform.schemas.bootstrap import BootstrapInputs
from deepcab_platform.schemas.enums import GcpRegion, PlatformEnv, ProviderMode


def bootstrap_cmd(
    env: PlatformEnv = typer.Option(PlatformEnv.DEV, "--env", "-e", help="Target env"),
    billing_account: str = typer.Option(..., "--billing-account", "-b", help="Format: XXXXXX-XXXXXX-XXXXXX"),
    project_id: str = typer.Option(..., "--project-id", "-p", help="Globally unique GCP project ID"),
    region: GcpRegion = typer.Option(GcpRegion.US_CENTRAL1, "--region", "-r"),
    gh_owner: str = typer.Option("juan-garassino", "--gh-owner"),
    gh_platform_repo: str = typer.Option("deepCab-platform", "--gh-platform-repo"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print commands without executing"),
) -> None:
    """One-shot: create GCP project, link billing, enable APIs, create state bucket, set up WIF + terraform SA."""
    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    service = get_bootstrap_service(mode)
    inputs = BootstrapInputs(
        env=env, billing_account=billing_account, project_id=project_id,
        region=region, gh_owner=gh_owner, gh_platform_repo=gh_platform_repo,
    )
    result = service.bootstrap(inputs)
    rprint("\n[bold green]✓ bootstrap complete[/bold green]\n")
    rprint("Paste these into [cyan]scripts/gh-vars.env[/cyan]:")
    rprint(f"  GCP_PROJECT={result.project_id}")
    rprint(f"  GCP_PROJECT_NUMBER={result.project_number}")
    rprint(f"  GCP_REGION={result.region.value}")
    rprint(f"  GCP_WIF_PROVIDER={result.wif_provider}")
    rprint(f"  GCP_DEPLOYER_SA={result.deployer_sa_email}")
    rprint(
        f"\nThen [cyan]deepcab-platform sync-gh[/cyan] to upload to GitHub, then "
        f"[cyan]deepcab-platform tf apply -e {env.value}[/cyan] to provision the rest."
    )
