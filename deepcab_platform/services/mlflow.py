"""MlflowMirrorService — mirror ghcr.io/mlflow/mlflow to GAR via Cloud Build.

Cloud Run rejects ghcr.io images directly. This service submits a Cloud Build
job that pulls from ghcr and re-tags into our Artifact Registry. Wrapper
around `gcloud builds submit --config=cloud-manifests/mlflow/mirror.yaml`.
"""

from __future__ import annotations

from dataclasses import dataclass

from deepcab_platform.providers.gcloud import GcloudProvider


@dataclass
class MlflowMirrorService:
    gcloud: GcloudProvider
    config_path: str = "cloud-manifests/mlflow/mirror.yaml"

    def mirror(self, project_id: str) -> str:
        return self.gcloud.run([
            "builds", "submit",
            f"--config={self.config_path}",
            "--no-source",
            f"--project={project_id}",
        ])
