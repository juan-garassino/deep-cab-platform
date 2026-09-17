"""HTTP provider — Protocol + Real (requests) + DryRun impls. Used by the Kuma seeder."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import requests
from rich import print as rprint


@runtime_checkable
class HttpProvider(Protocol):
    """Minimal HTTP surface — just what the Kuma seeder needs."""

    def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> Any: ...
    def get(self, url: str, *, headers: dict | None = None) -> Any: ...


@dataclass
class RealHttpProvider:
    timeout_seconds: float = 15.0

    def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> Any:
        response = requests.post(url, json=json, headers=headers, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json() if response.content else {}

    def get(self, url: str, *, headers: dict | None = None) -> Any:
        response = requests.get(url, headers=headers, timeout=self.timeout_seconds)
        response.raise_for_status()
        return response.json() if response.content else {}


@dataclass
class DryRunHttpProvider:
    """Records what would be sent without hitting the network."""

    posts: list[dict] = field(default_factory=list)
    gets: list[dict] = field(default_factory=list)

    def post(self, url: str, *, json: dict | None = None, headers: dict | None = None) -> Any:
        rprint(f"[dim]\\[dry-run POST][/dim] [cyan]{url}[/cyan] body={json}")
        self.posts.append({"url": url, "json": json, "headers": headers})
        return {}

    def get(self, url: str, *, headers: dict | None = None) -> Any:
        rprint(f"[dim]\\[dry-run GET][/dim] [cyan]{url}[/cyan]")
        self.gets.append({"url": url, "headers": headers})
        return {}
