"""SecretsService — rotate a Secret Manager secret + bounce Cloud Run revisions.

Cloud Run binds secret env vars at revision creation time. Pushing a new
version of `openai-api-key` does NOT update the running api — you need to
trigger a new revision. This service does both: pushes the new version
*and* fires `gcloud run services update --update-secrets=...` (a spec change
that creates a fresh revision picking up `:latest`).
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field

from deepcab_platform.providers.gcloud import GcloudProvider


def _default_consumers() -> dict[str, list[str]]:
    """Which Cloud Run services consume which secrets. Tests override directly."""
    return {
        "openai-api-key": ["deepcab-api"],
        "deepcab-api-key": ["deepcab-api"],
        "slack-webhook-url": ["deepcab-api"],
        "mlflow-db-password": ["deepcab-api", "deepcab-mlflow"],
        # kuma-admin-password is read by the seeder, not the kuma service itself.
    }


@dataclass
class SecretsService:
    gcloud: GcloudProvider
    secret_consumers: dict[str, list[str]] = field(default_factory=_default_consumers)

    def rotate(
        self,
        secret_id: str,
        value: str,
        *,
        project_id: str,
        region: str = "europe-west1",
        services: list[str] | None = None,
    ) -> dict:
        new_version = self._add_version(secret_id, value, project_id)
        targets = services if services is not None else self.secret_consumers.get(secret_id, [])
        for service in targets:
            self._bump_service(service, secret_id, project_id, region)
        return {"secret": secret_id, "new_version": new_version, "services_bumped": targets}

    def _add_version(self, secret_id: str, value: str, project_id: str) -> str:
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            f.write(value)
            path = f.name
        try:
            out = self.gcloud.run([
                "secrets", "versions", "add", secret_id,
                f"--data-file={path}", f"--project={project_id}",
                "--format=value(name)",
            ])
            return out.strip()
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _bump_service(self, service: str, secret_id: str, project_id: str, region: str) -> None:
        # env-var name = SECRET_ID uppercased with dashes → underscores
        # (matches the convention in cloud_run_service.secret_env_vars).
        env_var = secret_id.upper().replace("-", "_")
        self.gcloud.run([
            "run", "services", "update", service,
            f"--region={region}", f"--project={project_id}",
            f"--update-secrets={env_var}={secret_id}:latest",
            "--quiet",
        ])
