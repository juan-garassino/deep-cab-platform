"""Pydantic models for Uptime Kuma seed configs.

`monitors.yaml` is parsed into `KumaSeedConfig`, then `KumaSeedService` POSTs each
`KumaMonitor` via the Kuma REST API to pre-populate the status page.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class KumaMonitor(BaseModel):
    """One monitored endpoint on the status page."""

    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=64)
    type: str = Field(default="http", pattern="^(http|keyword|ping|port|dns)$")
    url: HttpUrl
    interval_seconds: int = Field(default=60, ge=20, le=3600)
    retry_interval_seconds: int = Field(default=60, ge=20, le=3600)
    max_retries: int = Field(default=2, ge=0, le=10)
    accepted_status_codes: list[str] = Field(default_factory=lambda: ["200-299"])
    description: str = ""
    tags: list[str] = Field(default_factory=list)


class KumaSeedConfig(BaseModel):
    """The full monitors.yaml document."""

    model_config = {"extra": "forbid"}

    admin_user: str = "admin"
    admin_password_env_var: str = "KUMA_ADMIN_PASSWORD"
    monitors: list[KumaMonitor]


class KumaSeedResult(BaseModel):
    """Returned by `KumaSeedService.seed()` for the CLI to render."""

    model_config = {"extra": "forbid"}

    admin_created: bool
    monitors_created: list[str]
    monitors_skipped: list[str]  # already-existing monitors with the same name
    base_url: str
