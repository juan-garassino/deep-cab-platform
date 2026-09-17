"""`deepcab-platform showcase up|down` — cost toggle for the dev env."""

from __future__ import annotations

import typer
from rich import print as rprint

from deepcab_platform.deps import get_showcase_service
from deepcab_platform.schemas.enums import PlatformEnv, ProviderMode, ShowcaseMode

showcase_app = typer.Typer(help="Showcase stack up/down toggle.", no_args_is_help=True)


@showcase_app.command("up")
def up(
    env: PlatformEnv = typer.Option(PlatformEnv.DEV, "--env", "-e"),
    ignore_legacy: bool = typer.Option(
        False, "--ignore-legacy",
        help="Skip the pre-flight check for legacy Cloud SQL state. Use only if you've vetted the apply plan.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Bring the stack live: Cloud SQL ALWAYS, Uptime Kuma min=1 (~$15/mo)."""
    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    out = get_showcase_service(mode).set_mode(env, ShowcaseMode.UP, ignore_legacy=ignore_legacy)
    rprint("[bold green]✓ showcase up[/bold green]")
    rprint(out)


@showcase_app.command("down")
def down(
    env: PlatformEnv = typer.Option(PlatformEnv.DEV, "--env", "-e"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Stop Cloud SQL + scale Uptime Kuma to zero (~$1/mo idle)."""
    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    out = get_showcase_service(mode).set_mode(env, ShowcaseMode.DOWN)
    rprint("[bold green]✓ showcase down[/bold green]")
    rprint(out)
