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
        """Open a socket.io connection to the Kuma instance at `base_url`."""
        from uptime_kuma_api import UptimeKumaApi
        self._client = UptimeKumaApi(base_url)

    def needs_setup(self) -> bool:
        """Return True if Kuma has not been initialised with an admin user yet."""
        return bool(self._client.need_setup())

    def setup(self, username: str, password: str, language: str = "en") -> None:
        # uptime-kuma-api 1.2: setup(username, password). language is configured later.
        """Create the initial admin user. `language` is accepted for interface parity but unused by uptime-kuma-api 1.2."""
        self._client.setup(username, password)

    def login(self, username: str, password: str) -> None:
        """Authenticate as `username`."""
        self._client.login(username, password)

    def list_monitors(self) -> list[dict]:
        """Return existing monitors, or an empty list if the lookup fails."""
        try:
            return list(self._client.get_monitors())
        except Exception:
            return []

    def add_monitor(self, **kwargs: Any) -> dict:
        """Create a monitor from `kwargs` and return the API response."""
        return self._client.add_monitor(**kwargs)

    def disconnect(self) -> None:
        """Close the connection; errors on close are ignored."""
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
        """Record the connect call."""
        self.calls.append(("connect", {"base_url": base_url}))
        rprint(f"[dim]\\[dry-run kuma][/dim] connect [cyan]{base_url}[/cyan]")

    def needs_setup(self) -> bool:
        """Return True until `setup` has been called."""
        self.calls.append(("needs_setup", {}))
        return self._needs_setup

    def setup(self, username: str, password: str, language: str = "en") -> None:
        """Record the setup call and mark Kuma as initialised."""
        self.calls.append(("setup", {"username": username, "language": language}))
        rprint(f"[dim]\\[dry-run kuma][/dim] setup admin=[cyan]{username}[/cyan]")
        self._needs_setup = False

    def login(self, username: str, password: str) -> None:
        """Record the login call."""
        self.calls.append(("login", {"username": username}))
        rprint(f"[dim]\\[dry-run kuma][/dim] login as [cyan]{username}[/cyan]")

    def list_monitors(self) -> list[dict]:
        """Return the monitors added so far in this dry run."""
        return list(self._monitors)

    def add_monitor(self, **kwargs: Any) -> dict:
        """Record the monitor, assign it a sequential `monitorID`, and return it."""
        self.calls.append(("add_monitor", dict(kwargs)))
        rprint(f"[dim]\\[dry-run kuma][/dim] add_monitor name=[cyan]{kwargs.get('name')}[/cyan]")
        result = {"monitorID": len(self._monitors) + 1, **kwargs}
        self._monitors.append(result)
        return result

    def disconnect(self) -> None:
        """Record the disconnect call."""
        self.calls.append(("disconnect", {}))
