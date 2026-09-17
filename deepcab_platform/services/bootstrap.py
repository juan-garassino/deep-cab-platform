"""BootstrapService — create GCP project + link billing + state bucket + WIF.

Pure-Python port of `scripts/bootstrap-gcp.sh`. Idempotent: every step checks
first. Returns a `BootstrapResult` whose fields go straight into
`scripts/gh-vars.env` (which `SyncGhService` then uploads).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from deepcab_platform.providers.gcloud import GcloudProvider
from deepcab_platform.schemas.bootstrap import BootstrapInputs, BootstrapResult
from deepcab_platform.schemas.enums import GcpRegion


@dataclass
class BootstrapService:
    """Drives the 5-step bootstrap. All gcloud calls go through `gcloud`."""

    gcloud: GcloudProvider

    POOL_ID = "github-pool"
    PROVIDER_ID = "github-provider"
    DEPLOYER_SA = "deepcab-deployer"
    RUNTIME_SA = "deepcab-runtime"
    SCHEDULER_SA = "deepcab-scheduler"
    TERRAFORM_SA = "deepcab-terraform"

    REQUIRED_APIS = (
        "cloudresourcemanager.googleapis.com",
        "iam.googleapis.com",
        "iamcredentials.googleapis.com",
        "sts.googleapis.com",
        "artifactregistry.googleapis.com",
        "run.googleapis.com",
        "cloudbuild.googleapis.com",
        "storage.googleapis.com",
        "secretmanager.googleapis.com",
        "cloudscheduler.googleapis.com",
        "sqladmin.googleapis.com",
        "compute.googleapis.com",
        "serviceusage.googleapis.com",
        "cloudbilling.googleapis.com",
    )

    def bootstrap(self, inputs: BootstrapInputs) -> BootstrapResult:
        self._ensure_project(inputs.project_id, inputs.env.value)
        project_number = self._project_number(inputs.project_id)
        self._link_billing(inputs.project_id, inputs.billing_account)
        self._enable_apis(inputs.project_id)
        state_bucket = self._ensure_state_bucket(inputs.project_id, inputs.env.value, inputs.region)
        wif_provider = self._ensure_wif(
            inputs.project_id, project_number, inputs.gh_owner
        )
        self._ensure_terraform_sa(
            inputs.project_id, project_number, inputs.gh_owner, inputs.gh_platform_repo
        )
        return BootstrapResult(
            project_id=inputs.project_id,
            project_number=project_number,
            region=inputs.region,
            wif_provider=wif_provider,
            deployer_sa_email=f"{self.DEPLOYER_SA}@{inputs.project_id}.iam.gserviceaccount.com",
            runtime_sa_email=f"{self.RUNTIME_SA}@{inputs.project_id}.iam.gserviceaccount.com",
            scheduler_sa_email=f"{self.SCHEDULER_SA}@{inputs.project_id}.iam.gserviceaccount.com",
            terraform_sa_email=f"{self.TERRAFORM_SA}@{inputs.project_id}.iam.gserviceaccount.com",
            state_bucket=state_bucket,
        )

    def _ensure_project(self, project_id: str, env: str) -> None:
        try:
            self.gcloud.run(["projects", "describe", project_id, "--quiet"])
        except Exception:
            self.gcloud.run(["projects", "create", project_id, "--name", f"deepCab {env}"])

    def _project_number(self, project_id: str) -> str:
        out = self.gcloud.run(
            ["projects", "describe", project_id, "--format=value(projectNumber)"]
        )
        return out.strip()

    def _link_billing(self, project_id: str, billing_account: str) -> None:
        # `gcloud beta billing projects link` is idempotent.
        self.gcloud.run(
            ["beta", "billing", "projects", "link", project_id, f"--billing-account={billing_account}"]
        )

    def _enable_apis(self, project_id: str) -> None:
        self.gcloud.run(
            ["services", "enable", *self.REQUIRED_APIS, f"--project={project_id}"]
        )

    def _ensure_state_bucket(self, project_id: str, env: str, region: GcpRegion) -> str:
        bucket = f"deepcab-tfstate-{env}"
        try:
            self.gcloud.run(["storage", "buckets", "describe", f"gs://{bucket}", f"--project={project_id}"])
        except Exception:
            self.gcloud.run([
                "storage", "buckets", "create", f"gs://{bucket}",
                f"--project={project_id}", f"--location={region.value}",
                "--uniform-bucket-level-access",
            ])
            self.gcloud.run(["storage", "buckets", "update", f"gs://{bucket}", "--versioning"])
        return bucket

    def _ensure_wif(self, project_id: str, project_number: str, gh_owner: str) -> str:
        # Pool: active → no-op; soft-deleted → undelete; missing → create.
        self._ensure_wif_pool(project_id)
        # Provider: same logic, scoped to the pool.
        self._ensure_wif_provider(project_id, gh_owner)
        return (
            f"projects/{project_number}/locations/global/workloadIdentityPools/"
            f"{self.POOL_ID}/providers/{self.PROVIDER_ID}"
        )

    def _ensure_wif_pool(self, project_id: str) -> None:
        try:
            self.gcloud.run([
                "iam", "workload-identity-pools", "describe", self.POOL_ID,
                "--location=global", f"--project={project_id}",
            ])
            return  # active
        except Exception:
            pass
        # Check if soft-deleted (30-day window) — undelete is the right move.
        try:
            out = self.gcloud.run([
                "iam", "workload-identity-pools", "describe", self.POOL_ID,
                "--location=global", "--show-deleted", f"--project={project_id}",
            ])
            if "DELETED" in out:
                self.gcloud.run([
                    "iam", "workload-identity-pools", "undelete", self.POOL_ID,
                    "--location=global", f"--project={project_id}", "--quiet",
                ])
                return
        except Exception:
            pass
        # Truly absent — create.
        self.gcloud.run([
            "iam", "workload-identity-pools", "create", self.POOL_ID,
            "--location=global", "--display-name=GitHub Actions Pool",
            f"--project={project_id}",
        ])

    def _ensure_wif_provider(self, project_id: str, gh_owner: str) -> None:
        try:
            self.gcloud.run([
                "iam", "workload-identity-pools", "providers", "describe", self.PROVIDER_ID,
                f"--workload-identity-pool={self.POOL_ID}", "--location=global",
                f"--project={project_id}",
            ])
            return
        except Exception:
            pass
        try:
            out = self.gcloud.run([
                "iam", "workload-identity-pools", "providers", "describe", self.PROVIDER_ID,
                f"--workload-identity-pool={self.POOL_ID}", "--location=global",
                "--show-deleted", f"--project={project_id}",
            ])
            if "DELETED" in out:
                self.gcloud.run([
                    "iam", "workload-identity-pools", "providers", "undelete", self.PROVIDER_ID,
                    f"--workload-identity-pool={self.POOL_ID}", "--location=global",
                    f"--project={project_id}", "--quiet",
                ])
                return
        except Exception:
            pass
        self.gcloud.run([
            "iam", "workload-identity-pools", "providers", "create-oidc", self.PROVIDER_ID,
            f"--workload-identity-pool={self.POOL_ID}", "--location=global",
            "--display-name=GitHub Actions",
            "--attribute-mapping=google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref",
            f"--attribute-condition=assertion.repository_owner == '{gh_owner}'",
            "--issuer-uri=https://token.actions.githubusercontent.com",
            f"--project={project_id}",
        ])

    def _ensure_terraform_sa(
        self, project_id: str, project_number: str, gh_owner: str, gh_platform_repo: str
    ) -> None:
        sa_email = f"{self.TERRAFORM_SA}@{project_id}.iam.gserviceaccount.com"
        try:
            self.gcloud.run(["iam", "service-accounts", "describe", sa_email, f"--project={project_id}"])
        except Exception:
            self.gcloud.run([
                "iam", "service-accounts", "create", self.TERRAFORM_SA,
                f"--project={project_id}",
                "--display-name=deepCab platform terraform CI",
            ])
            # IAM is eventually consistent — wait for the SA before binding.
            for _ in range(6):
                try:
                    self.gcloud.run([
                        "iam", "service-accounts", "describe", sa_email, f"--project={project_id}"
                    ])
                    break
                except Exception:
                    time.sleep(5)

        for role in ("roles/editor", "roles/iam.securityAdmin", "roles/resourcemanager.projectIamAdmin"):
            self.gcloud.run([
                "projects", "add-iam-policy-binding", project_id,
                f"--member=serviceAccount:{sa_email}",
                f"--role={role}", "--condition=None", "--quiet",
            ])
        self.gcloud.run([
            "iam", "service-accounts", "add-iam-policy-binding", sa_email,
            "--role=roles/iam.workloadIdentityUser",
            f"--member=principalSet://iam.googleapis.com/projects/{project_number}/locations/global/workloadIdentityPools/{self.POOL_ID}/attribute.repository/{gh_owner}/{gh_platform_repo}",
            f"--project={project_id}", "--quiet",
        ])
