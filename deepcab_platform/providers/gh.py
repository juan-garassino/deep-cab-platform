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
    """Shells out to the `gh` CLI."""
    binary: str = "gh"

    def run(self, args: list[str], *, check: bool = True, input_text: str | None = None) -> str:
        """Run `gh <args>`, optionally piping `input_text` to stdin; return stdout."""
        if shutil.which(self.binary) is None:
            raise RuntimeError(f"`{self.binary}` not found on PATH")
        return run_capture([self.binary, *args], check=check, input_text=input_text)


@dataclass
class DryRunGhProvider:
    """Prints the `gh` command instead of executing it. Always returns an empty string."""
    def run(self, args: list[str], *, check: bool = True, input_text: str | None = None) -> str:
        """Print the gh command (and a stdin preview) and return an empty string."""
        suffix = f"  (stdin: {input_text[:40]!r}…)" if input_text else ""
        rprint(f"[dim]\\[dry-run gh][/dim] [cyan]gh {' '.join(args)}[/cyan]{suffix}")
        return ""
