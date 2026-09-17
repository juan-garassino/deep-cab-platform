"""String-valued enums shared across schemas, services, and the CLI.

Mirrors the convention in 001's `deepCab/schemas/enums.py`: every enum inherits
from `(str, Enum)` so JSON serialization through Pydantic v2 stays
byte-for-byte identical to plain `Literal[...]` annotations. Pydantic accepts
both the enum member and its `.value` string for parsing.
"""

from __future__ import annotations

from enum import Enum


class PlatformEnv(str, Enum):
    """The four deployment environments — selects `.env.<env>` + GCP project."""

    LOCAL = "local"
    DEV = "dev"
    STAGING = "staging"
    PROD = "prod"


class ShowcaseMode(str, Enum):
    """Cost toggle for the showcase stack."""

    UP = "up"
    DOWN = "down"


class WorkloadType(str, Enum):
    """Routing label for Cloud Run service variants (used by `cloud_run_service` module callers)."""

    API = "api"
    WEBSITE = "website"
    MLFLOW = "mlflow"
    STATUS = "status"
    JOB = "job"


class GcpRegion(str, Enum):
    """Regions we currently support. Extend as needed."""

    US_CENTRAL1 = "us-central1"
    US_EAST1 = "us-east1"
    EUROPE_WEST1 = "europe-west1"
    ASIA_SOUTHEAST1 = "asia-southeast1"


class TerraformAction(str, Enum):
    """`deepcab-platform tf <action>` subcommands."""

    PLAN = "plan"
    APPLY = "apply"
    DESTROY = "destroy"
    IMPORT = "import"
    OUTPUT = "output"
    VALIDATE = "validate"


class ApiHealthStatus(str, Enum):
    """Surfaced by `deepcab-platform kuma check` and the Uptime Kuma seeder."""

    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OUTAGE = "outage"
    UNKNOWN = "unknown"


class ProviderMode(str, Enum):
    """Selects between real GCP/gh/terraform calls and dry-run/stub impls."""

    REAL = "real"
    DRY_RUN = "dry_run"


class BackendKind(str, Enum):
    """Subset of 001's BackendKind we wire as Hydra `backend=` overrides."""

    TF_MLP = "tf_mlp"
    TORCH_MLP = "torch_mlp"
    XGB = "xgb"
    LGBM = "lgbm"
    CATBOOST = "catboost"
    FT_TRANSFORMER = "ft_transformer"


class DataSize(str, Enum):
    """Subset of 001's DataSize. Passed as Hydra `data=` override."""

    S1K = "1k"
    S10K = "10k"
    S100K = "100k"
    S500K = "500k"
    FULL = "full"


class GpuType(str, Enum):
    """GPU accelerators we support on training VMs (spot-priced where available)."""

    NONE = "none"
    T4 = "nvidia-tesla-t4"
    L4 = "nvidia-l4"
    A100 = "nvidia-tesla-a100"
