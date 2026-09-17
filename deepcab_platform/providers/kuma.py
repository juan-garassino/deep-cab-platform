"""Uptime Kuma API provider — Protocol + Real (uptime-kuma-api) + DryRun impls.

Kuma's monitor management is socket.io, not REST. The community library
`uptime-kuma-api` (PyPI) wraps the socket protocol with Pythonic methods.
This module abstracts the bits we need so `KumaSeedService` keeps the same
clean architecture as the other services (Protocol + Real/DryRun).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from rich import print as rprint


@runtime_checkable
class KumaApiProvider(Protocol):
    """Subset of Kuma's socket.io API used by the seeder."""

    def connect(self, base_url: str) -> None: ...
    def needs_setup(self) -> bool: ...
    def setup(self, username: str, password: str, language: str = "en") -> None: ...
    def login(self, username: str, password: str) -> None: ...
    def list_monitors(self) -> list[dict]: ...
    def add_monitor(self, **kwargs: Any) -> dict: ...
    def disconnect(self) -> None: ...


@dataclass
class RealKumaApiProvider:
    """Wraps `uptime_kuma_api.UptimeKumaApi`. Lazy import keeps the dep
    optional for callers that only need the dry-run path."""

    _client: Any = None

    def connect(self, base_url: str) -> None:
        from uptime_kuma_api import UptimeKumaApi
        self._client = UptimeKumaApi(base_url)

    def needs_setup(self) -> bool:
        return bool(self._client.need_setup())

    def setup(self, username: str, password: str, language: str = "en") -> None:
        # uptime-kuma-api 1.2: setup(username, password). language is configured later.
        self._client.setup(username, password)

    def login(self, username: str, password: str) -> None:
        self._client.login(username, password)

    def list_monitors(self) -> list[dict]:
        try:
            return list(self._client.get_monitors())
        except Exception:
            return []

    def add_monitor(self, **kwargs: Any) -> dict:
        return self._client.add_monitor(**kwargs)

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None


@dataclass
class DryRunKumaApiProvider:
    """Records calls without touching the network."""

    calls: list[tuple[str, dict]] = field(default_factory=list)
    _monitors: list[dict] = field(default_factory=list)
    _needs_setup: bool = True

    def connect(self, base_url: str) -> None:
        self.calls.append(("connect", {"base_url": base_url}))
        rprint(f"[dim]\\[dry-run kuma][/dim] connect [cyan]{base_url}[/cyan]")

    def needs_setup(self) -> bool:
        self.calls.append(("needs_setup", {}))
        return self._needs_setup

    def setup(self, username: str, password: str, language: str = "en") -> None:
        self.calls.append(("setup", {"username": username, "language": language}))
        rprint(f"[dim]\\[dry-run kuma][/dim] setup admin=[cyan]{username}[/cyan]")
        self._needs_setup = False

    def login(self, username: str, password: str) -> None:
        self.calls.append(("login", {"username": username}))
        rprint(f"[dim]\\[dry-run kuma][/dim] login as [cyan]{username}[/cyan]")

    def list_monitors(self) -> list[dict]:
        return list(self._monitors)

    def add_monitor(self, **kwargs: Any) -> dict:
        self.calls.append(("add_monitor", dict(kwargs)))
        rprint(f"[dim]\\[dry-run kuma][/dim] add_monitor name=[cyan]{kwargs.get('name')}[/cyan]")
        result = {"monitorID": len(self._monitors) + 1, **kwargs}
        self._monitors.append(result)
        return result

    def disconnect(self) -> None:
        self.calls.append(("disconnect", {}))
