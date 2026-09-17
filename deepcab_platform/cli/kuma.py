"""`deepcab-platform kuma seed|check` — pre-configure Uptime Kuma monitors."""

from __future__ import annotations

import typer
from rich import print as rprint

from deepcab_platform.deps import get_kuma_service, settings
from deepcab_platform.schemas.enums import ProviderMode

kuma_app = typer.Typer(help="Uptime Kuma status-page seeder.", no_args_is_help=True)


@kuma_app.command("seed")
def seed(
    base_url: str = typer.Option(
        None, "--base-url",
        help="Uptime Kuma URL. Defaults to settings.kuma.base_url.",
    ),
    admin_password: str = typer.Option(
        None, "--admin-password",
        help="Defaults to settings.kuma.admin_password (read from KUMA_ADMIN_PASSWORD env var or Secret Manager).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Create admin (if needed) + POST every monitor from cloud-manifests/kuma/monitors.yaml."""
    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    service = get_kuma_service(mode)
    s = settings()
    url = base_url or s.kuma.base_url
    pw = admin_password or s.kuma.admin_password
    if not url:
        raise typer.BadParameter(
            "Kuma base URL not set. Pass --base-url or set KUMA_BASE_URL in your env file."
        )
    if not pw:
        raise typer.BadParameter(
            "Kuma admin password not set. Pass --admin-password or set KUMA_ADMIN_PASSWORD."
        )
    result = service.seed(url, pw)
    rprint(
        f"[bold green]✓ kuma seed[/bold green] "
        f"created={len(result.monitors_created)} skipped={len(result.monitors_skipped)} "
        f"@ [cyan]{result.base_url}[/cyan]"
    )


@kuma_app.command("check")
def check(
    base_url: str = typer.Option(None, "--base-url"),
) -> None:
    """Probe the Kuma instance for liveness."""
    service = get_kuma_service(ProviderMode.REAL)
    url = base_url or settings().kuma.base_url
    if not url:
        raise typer.BadParameter("Pass --base-url or set KUMA_BASE_URL.")
    ok = service.health(url)
    if ok:
        rprint(f"[bold green]✓[/bold green] {url} responsive")
    else:
        rprint(f"[bold red]✗[/bold red] {url} unreachable")
        raise typer.Exit(code=1)
