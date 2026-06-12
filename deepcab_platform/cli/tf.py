"""`deepcab-platform tf <action>` — thin terraform wrapper scoped to envs/<env>/."""

from __future__ import annotations

import typer
from rich import print as rprint

from deepcab_platform.deps import get_cleanup_service, get_terraform_service
from deepcab_platform.schemas.enums import PlatformEnv, ProviderMode, TerraformAction

tf_app = typer.Typer(help="Terraform plan/apply/destroy/output for a target env.", no_args_is_help=True)


def _run(action: TerraformAction, env: PlatformEnv, auto_approve: bool, dry_run: bool) -> None:
    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    out = get_terraform_service(mode).run_action(action, env, auto_approve=auto_approve)
    rprint(out)


@tf_app.command("plan")
def plan(env: PlatformEnv = typer.Option(PlatformEnv.DEV, "--env", "-e"),
         dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    _run(TerraformAction.PLAN, env, auto_approve=False, dry_run=dry_run)


@tf_app.command("apply")
def apply(env: PlatformEnv = typer.Option(PlatformEnv.DEV, "--env", "-e"),
          auto_approve: bool = typer.Option(False, "--auto-approve", "-y"),
          dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    _run(TerraformAction.APPLY, env, auto_approve=auto_approve, dry_run=dry_run)


@tf_app.command("destroy")
def destroy(env: PlatformEnv = typer.Option(PlatformEnv.DEV, "--env", "-e"),
            auto_approve: bool = typer.Option(False, "--auto-approve", "-y"),
            dry_run: bool = typer.Option(False, "--dry-run")) -> None:
    _run(TerraformAction.DESTROY, env, auto_approve=auto_approve, dry_run=dry_run)


@tf_app.command("output")
def output(env: PlatformEnv = typer.Option(PlatformEnv.DEV, "--env", "-e")) -> None:
    _run(TerraformAction.OUTPUT, env, auto_approve=False, dry_run=False)


@tf_app.command("validate")
def validate(env: PlatformEnv = typer.Option(PlatformEnv.DEV, "--env", "-e")) -> None:
    _run(TerraformAction.VALIDATE, env, auto_approve=False, dry_run=False)


@tf_app.command("cleanup-legacy")
def cleanup_legacy(
    env: PlatformEnv = typer.Option(PlatformEnv.DEV, "--env", "-e"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the Cloud SQL delete confirmation."),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """One-shot sweep of legacy Cloud SQL + mlflow-db-password state.

    Run this once before `make showcase_up` on an env whose tfstate predates
    the Cloud SQL → Neon migration. Idempotent — second call is a no-op.
    """
    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    svc = get_cleanup_service(mode)

    if not dry_run and not yes:
        addresses = svc.list_legacy_state_addresses(env)
        if addresses:
            rprint(
                f"[yellow]About to forget {len(addresses)} legacy resource(s) from state "
                f"and delete the orphaned Cloud SQL instance.[/yellow]"
            )
            for addr in addresses:
                rprint(f"  - {addr}")
            if not typer.confirm("Proceed?", default=False):
                raise typer.Abort()

    result = svc.cleanup(env)

    rprint(f"[bold green]✓ cleanup-legacy done[/bold green] env=[cyan]{env.value}[/cyan]")
    rprint(f"  state rm'd:     {len(result.state_addresses_removed)} address(es)")
    for addr in result.state_addresses_removed:
        rprint(f"    · {addr}")
    if result.cloud_sql_instance_deleted:
        rprint("  cloud SQL:      [green]deleted[/green]")
    elif result.cloud_sql_instance_skipped_reason:
        rprint(f"  cloud SQL:      [dim]skipped — {result.cloud_sql_instance_skipped_reason}[/dim]")
    if result.secrets_deleted:
        rprint(f"  secrets deleted: {', '.join(result.secrets_deleted)}")
    if result.plan_clean:
        rprint("  plan:           [green]clean[/green]")
    else:
        rprint("  plan:           [yellow]still references legacy:[/yellow]")
        for line in result.plan_legacy_lines[:10]:
            rprint(f"    {line}")
