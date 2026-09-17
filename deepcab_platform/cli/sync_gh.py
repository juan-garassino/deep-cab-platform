"""`deepcab-platform sync-gh` — upload variables + secrets to all 3 GitHub repos."""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.table import Table

from deepcab_platform.deps import get_sync_gh_service
from deepcab_platform.schemas.enums import ProviderMode


def sync_gh_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="Print gh calls without executing"),
) -> None:
    """Bulk-upload gh-vars*.env + gh-secrets.env to deepCab, deepCab-platform, deepCab-website."""
    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    service = get_sync_gh_service(mode)
    result = service.sync()

    table = Table(title="GitHub Actions sync — results")
    table.add_column("Repo", style="cyan")
    table.add_column("Vars set", style="green")
    table.add_column("Secrets", style="yellow")
    for repo in result.vars_set:
        vars_count = len(result.vars_set.get(repo, []))
        secrets_status = (
            f"{len(result.secrets_set.get(repo, []))} set"
            if repo in result.secrets_set
            else f"{len(result.secrets_skipped.get(repo, []))} skipped (empty values)"
        )
        table.add_row(repo, str(vars_count), secrets_status)
    rprint(table)
