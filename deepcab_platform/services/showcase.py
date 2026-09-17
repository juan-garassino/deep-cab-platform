"""ShowcaseService — up/down with readiness wait + Kuma warm-up.

`up` flips Cloud SQL to ALWAYS and Uptime Kuma to min=1 via TF. Apply alone
takes ~30-60s longer than Cloud SQL needs to enter RUNNABLE state. Without a
wait, the MLflow Cloud Run revision starts first, can't connect to Postgres,
returns 5xx for the first ~60s. We poll the Cloud SQL state until RUNNABLE,
then optionally curl Kuma to dodge the min=0 cold-start on first visit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests
from rich import print as rprint

from deepcab_platform.providers.gcloud import GcloudProvider
from deepcab_platform.schemas.enums import PlatformEnv, ShowcaseMode, TerraformAction
from deepcab_platform.services.cleanup import CleanupLegacyService
from deepcab_platform.services.terraform import TerraformService


class LegacyStateDetected(RuntimeError):
    """Raised when showcase pre-flight finds Cloud SQL / mlflow_db_password
    references still in tfstate. Caller can catch + suppress via --ignore-legacy."""


@dataclass
class ShowcaseService:
    terraform_service: TerraformService
    gcloud: GcloudProvider | None = None
    cleanup_service: CleanupLegacyService | None = None
    cloud_sql_ready_timeout_seconds: int = 300

    def set_mode(
        self,
        env: PlatformEnv,
        mode: ShowcaseMode,
        *,
        ignore_legacy: bool = False,
    ) -> str:
        if mode == ShowcaseMode.UP:
            self._check_legacy_state(env, ignore_legacy=ignore_legacy)

        showcase_var = "true" if mode == ShowcaseMode.UP else "false"
        out = self.terraform_service.run_action(
            TerraformAction.APPLY,
            env,
            auto_approve=True,
            extra_args=[f"-var=showcase_mode={showcase_var}"],
        )
        if mode == ShowcaseMode.UP:
            self._wait_for_cloud_sql(env)
            self._warm_kuma(env)
        return out

    # ------------------------- pre-flight ------------------------------------

    def _check_legacy_state(self, env: PlatformEnv, *, ignore_legacy: bool) -> None:
        """Abort apply if tfstate still holds the dropped cloud_sql / mlflow_db_password
        resources — they cause a destroy race against the MLflow revision swap.
        Falls back to a non-fatal warning when the state lookup itself fails."""
        if self.cleanup_service is None:
            return
        try:
            addresses = self.cleanup_service.list_legacy_state_addresses(env)
        except Exception as exc:
            rprint(f"[yellow]Could not check tfstate for legacy resources ({exc}); proceeding.[/yellow]")
            return
        if not addresses:
            return
        msg = (
            f"Legacy resources still in tfstate for env={env.value}:\n  - "
            + "\n  - ".join(addresses)
            + "\n\nRun `deepcab-platform tf cleanup-legacy --env "
            + env.value
            + "` first."
        )
        if ignore_legacy:
            rprint(f"[yellow]{msg}\n(--ignore-legacy set; proceeding anyway)[/yellow]")
            return
        rprint(f"[red]{msg}[/red]")
        raise LegacyStateDetected(msg)

    # ------------------------- readiness helpers -----------------------------

    def _wait_for_cloud_sql(self, env: PlatformEnv) -> None:
        """Poll the Cloud SQL instance state until RUNNABLE (or timeout)."""
        if self.gcloud is None:
            return  # skip silently in tests
        project_id = self._terraform_output(env, "project_id")
        if not project_id:
            return
        instance = f"deepcab-mlflow-{env.value}"
        rprint(f"[dim]waiting for Cloud SQL [cyan]{instance}[/cyan] to be RUNNABLE…[/dim]")
        deadline = time.monotonic() + self.cloud_sql_ready_timeout_seconds
        last_state = ""
        while time.monotonic() < deadline:
            try:
                out = self.gcloud.run([
                    "sql", "instances", "describe", instance,
                    f"--project={project_id}", "--format=value(state)",
                ])
                last_state = out.strip()
                if last_state == "RUNNABLE":
                    rprint(f"[green]✓[/green] Cloud SQL [cyan]{instance}[/cyan] RUNNABLE")
                    return
            except Exception as exc:
                last_state = f"<error: {exc}>"
            time.sleep(5)
        rprint(
            f"[yellow]Cloud SQL not RUNNABLE within {self.cloud_sql_ready_timeout_seconds}s "
            f"(last state: {last_state!r}). Continuing anyway; MLflow may still be warming.[/yellow]"
        )

    def _warm_kuma(self, env: PlatformEnv) -> None:
        url = self._terraform_output(env, "status_page_url")
        if not url:
            return
        try:
            requests.get(url, timeout=15, allow_redirects=False)
            rprint(f"[green]✓[/green] Kuma warmed at [cyan]{url}[/cyan]")
        except Exception as exc:
            rprint(f"[yellow]Kuma warm-up GET failed (non-fatal): {exc}[/yellow]")

    def _terraform_output(self, env: PlatformEnv, name: str) -> str:
        try:
            out = self.terraform_service.run_action(
                TerraformAction.OUTPUT, env, extra_args=["-raw", name]
            )
            return out.strip().strip('"')
        except Exception:
            return ""
