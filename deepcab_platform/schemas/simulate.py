"""Pydantic models for `deepcab-platform simulate run`.

Drives the 001-side `flow_v2/simulate.py` continuous-training loop.
The CLI is a thin shell around a `simulate_flow` subprocess call so the
flow keeps its own contract — these models exist to validate the time
window + execution target before we shell out.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from deepcab_platform.schemas.enums import BackendKind, DataSize, PlatformEnv


class SimulateRunInputs(BaseModel):
    model_config = {"extra": "forbid"}

    env: PlatformEnv = PlatformEnv.DEV
    backend: BackendKind = BackendKind.TORCH_MLP
    reference_data: DataSize = DataSize.S10K

    time_window_start: datetime = Field(
        ..., description="UTC ISO timestamp; inclusive start of the simulation window."
    )
    time_window_end: datetime = Field(
        ..., description="UTC ISO timestamp; exclusive end of the simulation window."
    )
    chunk_period_days: int = Field(default=7, ge=1, le=365)
    promotion_threshold: float = Field(default=0.05, ge=0.0, le=1.0)

    executor: str = Field(
        default="local",
        description="`local` (in-process) or `vm` (one GCE training VM per chunk).",
    )
    max_chunks: int | None = Field(
        default=None, ge=1,
        description="Hard cap on chunks fired; useful for cost-bounded demos.",
    )
    notify_every_chunk: bool = True

    @field_validator("executor")
    @classmethod
    def _valid_executor(cls, v: str) -> str:
        if v not in {"local", "vm"}:
            raise ValueError("executor must be 'local' or 'vm'")
        return v

    @field_validator("time_window_end")
    @classmethod
    def _end_after_start(cls, v: datetime, info) -> datetime:
        start = info.data.get("time_window_start")
        if start is not None and v <= start:
            raise ValueError("time_window_end must be > time_window_start")
        return v


class SimulateChunkSummary(BaseModel):
    chunk_index: int
    train_run_id: str | None
    challenger_metric: float
    promoted: bool
    reason: str
    new_champion_version: str | None


class SimulateRunResult(BaseModel):
    model_config = {"extra": "forbid"}

    backend: BackendKind
    chunks: list[SimulateChunkSummary]
    promotions: int
    final_champion_version: str | None
    mae_trajectory: list[float]
    estimated_total_cost_usd: float
