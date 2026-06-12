"""DI wiring — providers → services. Mirror of 001 `api/deps.py`.

Tests override via direct construction (e.g. `BootstrapService(gcloud=DryRunGcloudProvider())`).
The CLI uses `--dry-run` to switch every provider to its dry-run variant in one go.
"""

from __future__ import annotations

from functools import lru_cache

from deepcab_platform.providers.gcloud import (
    DryRunGcloudProvider,
    GcloudProvider,
    RealGcloudProvider,
)
from deepcab_platform.providers.gh import DryRunGhProvider, GhProvider, RealGhProvider
from deepcab_platform.providers.http import DryRunHttpProvider, HttpProvider, RealHttpProvider
from deepcab_platform.providers.kuma import (
    DryRunKumaApiProvider,
    KumaApiProvider,
    RealKumaApiProvider,
)
from deepcab_platform.providers.terraform import (
    DryRunTerraformProvider,
    RealTerraformProvider,
    TerraformProvider,
)
from deepcab_platform.schemas.enums import ProviderMode
from deepcab_platform.schemas.settings import PlatformSettings, get_settings
from deepcab_platform.services.bootstrap import BootstrapService
from deepcab_platform.services.cleanup import CleanupLegacyService
from deepcab_platform.services.data import DataCloneBqService
from deepcab_platform.services.kuma import KumaSeedService
from deepcab_platform.services.mlflow import MlflowMirrorService
from deepcab_platform.services.secrets import SecretsService
from deepcab_platform.services.showcase import ShowcaseService
from deepcab_platform.services.simulate import (
    DryRunSimulateRunner,
    SimulateService,
    SubprocessSimulateRunner,
)
from deepcab_platform.services.sync_gh import SyncGhService
from deepcab_platform.services.terraform import TerraformService
from deepcab_platform.services.train import TrainOnVmService


@lru_cache(maxsize=2)
def get_gcloud_provider(mode: ProviderMode = ProviderMode.REAL) -> GcloudProvider:
    return DryRunGcloudProvider() if mode == ProviderMode.DRY_RUN else RealGcloudProvider()


@lru_cache(maxsize=2)
def get_gh_provider(mode: ProviderMode = ProviderMode.REAL) -> GhProvider:
    return DryRunGhProvider() if mode == ProviderMode.DRY_RUN else RealGhProvider()


@lru_cache(maxsize=2)
def get_terraform_provider(mode: ProviderMode = ProviderMode.REAL) -> TerraformProvider:
    return DryRunTerraformProvider() if mode == ProviderMode.DRY_RUN else RealTerraformProvider()


@lru_cache(maxsize=2)
def get_http_provider(mode: ProviderMode = ProviderMode.REAL) -> HttpProvider:
    return DryRunHttpProvider() if mode == ProviderMode.DRY_RUN else RealHttpProvider()


@lru_cache(maxsize=2)
def get_kuma_api_provider(mode: ProviderMode = ProviderMode.REAL) -> KumaApiProvider:
    return DryRunKumaApiProvider() if mode == ProviderMode.DRY_RUN else RealKumaApiProvider()


def get_bootstrap_service(mode: ProviderMode = ProviderMode.REAL) -> BootstrapService:
    return BootstrapService(gcloud=get_gcloud_provider(mode))


def get_sync_gh_service(mode: ProviderMode = ProviderMode.REAL) -> SyncGhService:
    return SyncGhService(gh=get_gh_provider(mode))


def get_mlflow_service(mode: ProviderMode = ProviderMode.REAL) -> MlflowMirrorService:
    return MlflowMirrorService(gcloud=get_gcloud_provider(mode))


def get_terraform_service(mode: ProviderMode = ProviderMode.REAL) -> TerraformService:
    return TerraformService(terraform=get_terraform_provider(mode))


def get_showcase_service(mode: ProviderMode = ProviderMode.REAL) -> ShowcaseService:
    return ShowcaseService(
        terraform_service=get_terraform_service(mode),
        gcloud=get_gcloud_provider(mode),
        cleanup_service=get_cleanup_service(mode),
    )


def get_kuma_service(mode: ProviderMode = ProviderMode.REAL) -> KumaSeedService:
    return KumaSeedService(kuma=get_kuma_api_provider(mode))


def get_secrets_service(mode: ProviderMode = ProviderMode.REAL) -> SecretsService:
    return SecretsService(gcloud=get_gcloud_provider(mode))


def get_train_service(mode: ProviderMode = ProviderMode.REAL) -> TrainOnVmService:
    return TrainOnVmService(gcloud=get_gcloud_provider(mode))


def get_data_clone_service(mode: ProviderMode = ProviderMode.REAL) -> DataCloneBqService:
    return DataCloneBqService(gcloud=get_gcloud_provider(mode))


def get_simulate_service(mode: ProviderMode = ProviderMode.REAL) -> SimulateService:
    runner = DryRunSimulateRunner() if mode == ProviderMode.DRY_RUN else SubprocessSimulateRunner()
    return SimulateService(runner=runner)


def get_cleanup_service(mode: ProviderMode = ProviderMode.REAL) -> CleanupLegacyService:
    return CleanupLegacyService(
        terraform=get_terraform_provider(mode),
        gcloud=get_gcloud_provider(mode),
    )


def settings() -> PlatformSettings:
    return get_settings()
