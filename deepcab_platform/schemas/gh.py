"""Pydantic models for the GitHub Actions variable + secret sync."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GhVar(BaseModel):
    """One Actions variable (non-secret, visible in logs)."""

    model_config = {"extra": "forbid"}

    name: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    value: str


class GhSecret(BaseModel):
    """One Actions secret (never logged)."""

    model_config = {"extra": "forbid"}

    name: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    value: str = Field(repr=False)  # don't leak via repr/print


class GhSyncResult(BaseModel):
    """Returned by `SyncGhService.sync()` for the CLI to render."""

    model_config = {"extra": "forbid"}

    vars_set: dict[str, list[str]]  # repo -> [var_name, ...]
    secrets_set: dict[str, list[str]]
    secrets_skipped: dict[str, list[str]]  # values were empty
