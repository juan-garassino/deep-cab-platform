"""Pydantic models for the GCP project bootstrap flow."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from deepcab_platform.schemas.enums import GcpRegion, PlatformEnv


class BootstrapInputs(BaseModel):
    """User-supplied inputs to `BootstrapService.bootstrap()`."""

    model_config = {"extra": "forbid"}

    env: PlatformEnv
    billing_account: str = Field(pattern=r"^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$")
    project_id: str = Field(min_length=6, max_length=30, pattern=r"^[a-z][a-z0-9-]+$")
    region: GcpRegion = GcpRegion.US_CENTRAL1
    # Interpolated into the WIF provider's CEL attribute-condition and the
    # principalSet member, so keep them to GitHub's own charsets (G-023).
    gh_owner: str = Field(default="juan-garassino", pattern=r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}$")
    gh_platform_repo: str = Field(default="deepCab-platform", pattern=r"^[A-Za-z0-9._-]{1,100}$")

    @field_validator("gh_platform_repo")
    @classmethod
    def _not_dot_path(cls, v: str) -> str:
        if v in {".", ".."}:
            raise ValueError("gh_platform_repo cannot be '.' or '..'")
        return v


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
