"""CleanupLegacyService — one-shot sweep of legacy Cloud SQL state.

Background: the 2026-06-07 migration dropped ``module.cloud_sql`` and
``google_secret_manager_secret_version.mlflow_db_password`` from the dev
composition (MLflow now reads from Neon via Secret Manager). Existing
tfstate still references both. Running ``terraform apply`` against that
state plans destroys for the old resources — Cloud SQL takes ~5 min to
drop and races MLflow's revision swap, sometimes leaving MLflow stuck
restarting against a dying SQL.

This service runs the cleanup deterministically:

  1. ``terraform state list`` → grep for legacy resource shapes
  2. ``terraform state rm`` each match (allow-list scoped — never sweeps
     anything outside the known shapes)
  3. ``gcloud sql instances delete`` for the orphaned Cloud SQL instance
  4. ``gcloud secrets delete`` for the obsolete ``mlflow-db-password``
  5. ``terraform plan`` → confirm no legacy lines remain

Idempotent: every step is a no-op on the second run.
"""

from __future__ import annotations

from dataclasses import dataclass

from deepcab_platform.providers.gcloud import GcloudProvider
from deepcab_platform.providers.terraform import TerraformProvider
from deepcab_platform.schemas.cleanup import CleanupLegacyResult
from deepcab_platform.schemas.enums import PlatformEnv

# Substrings that mark a state address as "legacy" — the cleanup only
# touches resources matching one of these. Conservative on purpose: adding
# a new entry here is a deliberate code change, not a runtime decision.
_LEGACY_SUBSTRINGS = ("module.cloud_sql", "mlflow_db_password", "mlflow-db-password")

_LEGACY_SECRET_IDS = ("mlflow-db-password",)


@dataclass
class CleanupLegacyService:
    terraform: TerraformProvider
    gcloud: GcloudProvider
    terraform_envs_dir: str = "terraform/envs"

    def cleanup(self, env: PlatformEnv) -> CleanupLegacyResult:
        workdir = f"{self.terraform_envs_dir}/{env.value}"

        # 1+2: state list → state rm.
        addresses = self._legacy_state_addresses(workdir)
        for addr in addresses:
            self.terraform.run(["state", "rm", addr], workdir=workdir, check=False)

        # 3: delete orphaned Cloud SQL instance.
        project_id = self._project_id(workdir)
        instance_name = f"deepcab-mlflow-{env.value}"
        sql_deleted, sql_skip_reason = self._delete_cloud_sql(project_id, instance_name)

        # 4: delete obsolete secret(s).
        secrets_deleted: list[str] = []
        for secret_id in _LEGACY_SECRET_IDS:
            if self._delete_secret(project_id, secret_id):
                secrets_deleted.append(secret_id)

        # 5: verify with `terraform plan`.
        plan_clean, legacy_lines = self._verify_plan_clean(workdir)

        return CleanupLegacyResult(
            state_addresses_removed=addresses,
            cloud_sql_instance_deleted=sql_deleted,
            cloud_sql_instance_skipped_reason=sql_skip_reason,
            secrets_deleted=secrets_deleted,
            plan_clean=plan_clean,
            plan_legacy_lines=legacy_lines,
        )

    # --- pre-flight helper consumed by ShowcaseService ---------------------

    def list_legacy_state_addresses(self, env: PlatformEnv) -> list[str]:
        return self._legacy_state_addresses(f"{self.terraform_envs_dir}/{env.value}")

    # --- internals --------------------------------------------------------

    def _legacy_state_addresses(self, workdir: str) -> list[str]:
        try:
            out = self.terraform.run(["state", "list"], workdir=workdir)
        except Exception:
            return []
        return [
            line.strip()
            for line in out.splitlines()
            if any(s in line for s in _LEGACY_SUBSTRINGS) and line.strip()
        ]

    def _project_id(self, workdir: str) -> str:
        try:
            out = self.terraform.run(
                ["output", "-raw", "project_id"], workdir=workdir, check=False
            )
            return out.strip().strip('"')
        except Exception:
            return ""

    def _delete_cloud_sql(self, project_id: str, instance_name: str) -> tuple[bool, str | None]:
        if not project_id:
            return False, "no project_id resolved from terraform output"
        # Describe first — silently skip if already gone.
        describe = self.gcloud.run(
            ["sql", "instances", "describe", instance_name, f"--project={project_id}", "--format=value(name)"],
            check=False,
        )
        if not describe.strip():
            return False, "instance already absent"
        self.gcloud.run(
            ["sql", "instances", "delete", instance_name, f"--project={project_id}", "--quiet"],
            check=False,
        )
        return True, None

    def _delete_secret(self, project_id: str, secret_id: str) -> bool:
        if not project_id:
            return False
        describe = self.gcloud.run(
            ["secrets", "describe", secret_id, f"--project={project_id}", "--format=value(name)"],
            check=False,
        )
        if not describe.strip():
            return False
        self.gcloud.run(
            ["secrets", "delete", secret_id, f"--project={project_id}", "--quiet"],
            check=False,
        )
        return True

    def _verify_plan_clean(self, workdir: str) -> tuple[bool, list[str]]:
        try:
            out = self.terraform.run(
                ["plan", "-input=false", "-no-color", "-detailed-exitcode"],
                workdir=workdir,
                check=False,
            )
        except Exception:
            return False, []
        legacy_lines = [
            line for line in out.splitlines() if any(s in line for s in _LEGACY_SUBSTRINGS)
        ]
        return not legacy_lines, legacy_lines
