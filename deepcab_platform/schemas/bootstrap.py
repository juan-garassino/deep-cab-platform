"""Pydantic models for the GCP project bootstrap flow."""

from __future__ import annotations

from pydantic import BaseModel, Field

from deepcab_platform.schemas.enums import GcpRegion, PlatformEnv


class BootstrapInputs(BaseModel):
    """User-supplied inputs to `BootstrapService.bootstrap()`."""

    model_config = {"extra": "forbid"}

    env: PlatformEnv
    billing_account: str = Field(pattern=r"^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$")
    project_id: str = Field(min_length=6, max_length=30, pattern=r"^[a-z][a-z0-9-]+$")
    region: GcpRegion = GcpRegion.US_CENTRAL1
    gh_owner: str = "juan-garassino"
    gh_platform_repo: str = "deepCab-platform"


class BootstrapResult(BaseModel):
    """What `BootstrapService.bootstrap()` returns when done. Goes into gh-vars.env."""

    model_config = {"extra": "forbid"}

    project_id: str
    project_number: str
    region: GcpRegion
    wif_provider: str  # projects/<num>/locations/global/workloadIdentityPools/.../providers/...
    deployer_sa_email: str
    runtime_sa_email: str
    scheduler_sa_email: str
    terraform_sa_email: str
    state_bucket: str  # gs://deepcab-tfstate-<env>
