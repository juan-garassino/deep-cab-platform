"""`terraform` CLI provider — Protocol + Real + DryRun impls."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from rich import print as rprint

from deepcab_platform.providers._subprocess import run_capture


@runtime_checkable
class TerraformProvider(Protocol):
    """Abstracts `terraform`. workdir scopes the command to an env directory."""

    def run(self, args: list[str], *, workdir: str, check: bool = True) -> str: ...


@dataclass
class RealTerraformProvider:
    binary: str = "terraform"

    def run(self, args: list[str], *, workdir: str, check: bool = True) -> str:
        if shutil.which(self.binary) is None:
            raise RuntimeError(f"`{self.binary}` not found on PATH")
        env = os.environ.copy()
        env.setdefault("TF_IN_AUTOMATION", "1")
        env.setdefault("TF_INPUT", "0")
        return run_capture([self.binary, *args], check=check, cwd=workdir, env=env)


@dataclass
class DryRunTerraformProvider:
    def run(self, args: list[str], *, workdir: str, check: bool = True) -> str:
        rprint(
            f"[dim]\\[dry-run terraform][/dim] [cyan](cd {workdir} && terraform "
            f"{' '.join(args)})[/cyan]"
        )
        return ""
