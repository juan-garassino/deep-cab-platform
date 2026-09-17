"""`gh` CLI provider — Protocol + Real + DryRun impls."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from rich import print as rprint

from deepcab_platform.providers._subprocess import run_capture


@runtime_checkable
class GhProvider(Protocol):
    """Abstracts the `gh` CLI. Returns stdout; raises on non-zero by default."""

    def run(self, args: list[str], *, check: bool = True, input_text: str | None = None) -> str: ...


@dataclass
class RealGhProvider:
    binary: str = "gh"

    def run(self, args: list[str], *, check: bool = True, input_text: str | None = None) -> str:
        if shutil.which(self.binary) is None:
            raise RuntimeError(f"`{self.binary}` not found on PATH")
        return run_capture([self.binary, *args], check=check, input_text=input_text)


@dataclass
class DryRunGhProvider:
    def run(self, args: list[str], *, check: bool = True, input_text: str | None = None) -> str:
        suffix = f"  (stdin: {input_text[:40]!r}…)" if input_text else ""
        rprint(f"[dim]\\[dry-run gh][/dim] [cyan]gh {' '.join(args)}[/cyan]{suffix}")
        return ""
