"""Pydantic models for `deepcab-platform train-on-vm`.

The training VM is provisioned ad-hoc, runs `python -m deepCab.training.train`
inside our `deepcab/api` image, uploads the run artifacts to GCS, logs the
run to MLflow, and self-destructs. Inputs are Pydantic-validated so a typo
in `--backend` or `--data` fails before the gcloud call.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, field_validator

from deepcab_platform.schemas.enums import BackendKind, DataSize, GpuType, PlatformEnv

# Shell-safe env-var key shape. Pydantic rejects anything else so the rendered
# `-e KEY=value` in the VM startup script can't carry an injection vector.
_ENV_KEY_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


class TrainOnVmInputs(BaseModel):
    """User-supplied inputs to `TrainOnVmService.launch()`."""

    model_config = {"extra": "forbid"}

    env: PlatformEnv = PlatformEnv.DEV
    backend: BackendKind = BackendKind.TORCH_MLP
    data: DataSize = DataSize.S100K
    machine_type: str = "n1-standard-4"
    zone: str = "europe-west1-b"
    gpu: GpuType = GpuType.T4
    spot: bool = True
    max_runtime: str = "6h"  # GCP `--max-run-duration` value
    auto_delete: bool = True
    image_tag: str = "v1.0"
    tail: bool = False  # stream serial console after create
    # Extra env vars rendered as `-e KEY=value` on the in-VM `docker run`.
    # Used by the simulation flow's VmTrainExecutor to pass the chunk's BQ
    # WHERE clause + deterministic MLFLOW_RUN_NAME. Keys are validated to
    # be shell-safe; values get shlex.quote'd at render time.
    extra_env: dict[str, str] = Field(default_factory=dict)

    @field_validator("extra_env")
    @classmethod
    def _shell_safe_keys(cls, v: dict[str, str]) -> dict[str, str]:
        for k in v:
            if not _ENV_KEY_PATTERN.match(k):
                raise ValueError(
                    f"extra_env key {k!r} must match [A-Z_][A-Z0-9_]* (shell-safe)"
                )
        return v


class TrainOnVmResult(BaseModel):
    """What `launch()` returns. Goes back to the CLI for rendering."""

    model_config = {"extra": "forbid"}

    instance_name: str
    zone: str
    project_id: str
    image: str
    machine_type: str
    gpu: GpuType
    spot: bool
    serial_console_url: str
    monitoring_url: str
    estimated_cost_per_hour: float = Field(ge=0)
