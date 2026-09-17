"""pydantic-settings — single source of truth for runtime configuration.

Mirrors 001's `deepCab/schemas/settings.py`:
- Prefix-grouped sub-Settings (`GCP_`, `GH_`, `KUMA_`, `SHOWCASE_`)
- `DEEPCAB_ENV` (with `APP_ENV` as legacy alias) selects which `.env.<env>` file loads
- `@lru_cache` singleton via `get_settings()`
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Annotated

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from deepcab_platform.schemas.enums import GcpRegion, PlatformEnv, ShowcaseMode


def _env_file() -> str:
    env = os.environ.get("DEEPCAB_ENV") or os.environ.get("APP_ENV") or "local"
    return f".env.{env}"


class GcpSettings(BaseSettings):
    """GCP project + region + identity context."""

    model_config = SettingsConfigDict(env_prefix="GCP_", env_file=_env_file(), extra="ignore")

    project: str = ""
    project_number: str = ""
    region: GcpRegion = GcpRegion.US_CENTRAL1
    billing_account: str = ""
    deployer_sa: str = ""
    runtime_sa: str = ""
    terraform_sa: str = ""
    wif_provider: str = ""


class GhSettings(BaseSettings):
    """GitHub OIDC + repo identifiers used by the WIF + sync-gh flows."""

    model_config = SettingsConfigDict(env_prefix="GH_", env_file=_env_file(), extra="ignore")

    owner: str = "juan-garassino"
    api_repo: str = "deepCab"
    platform_repo: str = "deepCab-platform"
    website_repo: str = "deepCab-website"


class KumaSettings(BaseSettings):
    """Uptime Kuma admin credentials + base URL for the seeder."""

    model_config = SettingsConfigDict(env_prefix="KUMA_", env_file=_env_file(), extra="ignore")

    admin_user: str = "admin"
    admin_password: str = ""  # Read from Secret Manager (kuma-admin-password) in cloud envs
    base_url: str = ""  # Filled at runtime from terraform output `status_page_url`


class ShowcaseSettings(BaseSettings):
    """Showcase up/down toggle state."""

    model_config = SettingsConfigDict(env_prefix="SHOWCASE_", env_file=_env_file(), extra="ignore")

    mode: ShowcaseMode = ShowcaseMode.DOWN


class PlatformSettings(BaseSettings):
    """Composite root. Sub-settings hold their own env prefixes."""

    model_config = SettingsConfigDict(env_file=_env_file(), extra="ignore")

    env: Annotated[
        PlatformEnv,
        Field(default=PlatformEnv.LOCAL, validation_alias=AliasChoices("DEEPCAB_ENV", "APP_ENV")),
    ]

    gcp: GcpSettings = Field(default_factory=GcpSettings)
    gh: GhSettings = Field(default_factory=GhSettings)
    kuma: KumaSettings = Field(default_factory=KumaSettings)
    showcase: ShowcaseSettings = Field(default_factory=ShowcaseSettings)


@lru_cache(maxsize=1)
def get_settings() -> PlatformSettings:
    """Singleton accessor. Cleared between tests via `get_settings.cache_clear()`."""
    return PlatformSettings()
