"""Pydantic result models for `deepcab-platform tf cleanup-legacy`.

The cleanup operation is purposefully narrow — only removes resources we
know are legacy from the 2026-06-07 Cloud SQL → Neon migration. No
inputs schema is needed (env is the only knob and it's a CLI arg).
"""

from __future__ import annotations

from pydantic import BaseModel


class CleanupLegacyResult(BaseModel):
    """Outcome of one `cleanup-legacy` run: what was removed and whether the follow-up plan is clean."""
    model_config = {"extra": "forbid"}

    state_addresses_removed: list[str]
    cloud_sql_instance_deleted: bool
    cloud_sql_instance_skipped_reason: str | None = None
    secrets_deleted: list[str]
    plan_clean: bool
    plan_legacy_lines: list[str] = []
