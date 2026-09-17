"""gcloud CLI provider — Protocol + Real (shells out) + DryRun (prints) impls."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from rich import print as rprint

from deepcab_platform.providers._subprocess import run_capture


@runtime_checkable
class GcloudProvider(Protocol):
    """Abstracts the `gcloud` CLI. Returns stdout on success, raises on non-zero exit."""

    def run(self, args: list[str], *, check: bool = True) -> str: ...


@dataclass
class RealGcloudProvider:
    """Shells out to `gcloud`. Honors CLOUDSDK_PYTHON if set in env."""

    binary: str = "gcloud"
    extra_env: dict[str, str] | None = None

    def run(self, args: list[str], *, check: bool = True) -> str:
        if shutil.which(self.binary) is None:
            raise RuntimeError(f"`{self.binary}` not found on PATH")
        env = os.environ.copy()
        if self.extra_env:
            env.update(self.extra_env)
        # Default to system Python for the gcloud bundled-python protobuf bug
        env.setdefault("CLOUDSDK_PYTHON", "/usr/bin/python3")
        return run_capture([self.binary, *args], check=check, env=env)


@dataclass
class DryRunGcloudProvider:
    """Prints the command instead of executing. Always returns empty string."""

    def run(self, args: list[str], *, check: bool = True) -> str:
        rprint(f"[dim]\\[dry-run gcloud][/dim] [cyan]gcloud {' '.join(args)}[/cyan]")
        return ""
