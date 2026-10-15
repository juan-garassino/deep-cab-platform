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
    """Shells out to `terraform` inside `workdir`, with `TF_IN_AUTOMATION=1` and `TF_INPUT=0` defaulted."""
    binary: str = "terraform"

    def run(self, args: list[str], *, workdir: str, check: bool = True) -> str:
        """Run `terraform <args>` in `workdir` and return stdout."""
        if shutil.which(self.binary) is None:
            raise RuntimeError(f"`{self.binary}` not found on PATH")
        env = os.environ.copy()
        env.setdefault("TF_IN_AUTOMATION", "1")
        env.setdefault("TF_INPUT", "0")
        return run_capture([self.binary, *args], check=check, cwd=workdir, env=env)


@dataclass
class DryRunTerraformProvider:
    """Prints the terraform command instead of executing it. Always returns an empty string."""
    def run(self, args: list[str], *, workdir: str, check: bool = True) -> str:
        """Print the terraform command and return an empty string."""
        rprint(
            f"[dim]\\[dry-run terraform][/dim] [cyan](cd {workdir} && terraform "
            f"{' '.join(args)})[/cyan]"
        )
        return ""
