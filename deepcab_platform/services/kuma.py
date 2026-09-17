"""KumaSeedService — first-boot admin creation + monitor pre-seeding.

Wave 4. Wave 4-fix (2026-06-06): switched from HTTP REST to Kuma's socket.io
API via the `uptime-kuma-api` PyPI wrapper. Kuma's monitor management is not
exposed over REST; that was the root cause of the original 404s.

Flow on first run:
1. Connect to Kuma's socket.io server.
2. If needs_setup() → setup(admin, password). Otherwise login(admin, password).
3. Fetch existing monitors via list_monitors(); skip any with names that
   already exist (idempotent re-seed).
4. For each monitor in monitors.yaml, add_monitor(**kuma_payload).
5. Disconnect.

Returns a KumaSeedResult — created vs skipped names + base_url.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from rich import print as rprint

from deepcab_platform.providers.kuma import KumaApiProvider
from deepcab_platform.schemas.kuma import KumaMonitor, KumaSeedConfig, KumaSeedResult


@dataclass
class KumaSeedService:
    kuma: KumaApiProvider
    config_path: Path = Path("cloud-manifests/kuma/monitors.yaml")

    def load_config(self) -> KumaSeedConfig:
        raw = yaml.safe_load(self.config_path.read_text())
        return KumaSeedConfig.model_validate(raw)

    def seed(
        self,
        base_url: str,
        admin_password: str,
        *,
        config: KumaSeedConfig | None = None,
    ) -> KumaSeedResult:
        cfg = config or self.load_config()
        base = base_url.rstrip("/")
        self.kuma.connect(base)
        try:
            admin_created = False
            if self.kuma.needs_setup():
                self.kuma.setup(cfg.admin_user, admin_password)
                admin_created = True
            self.kuma.login(cfg.admin_user, admin_password)

            existing_names = {m.get("name") for m in self.kuma.list_monitors()}
            created: list[str] = []
            skipped: list[str] = []

            for monitor in cfg.monitors:
                if monitor.name in existing_names:
                    skipped.append(monitor.name)
                    continue
                try:
                    self.kuma.add_monitor(**self._to_kuma_payload(monitor))
                    created.append(monitor.name)
                except Exception as exc:
                    rprint(f"[yellow]monitor {monitor.name!r} failed: {exc}[/yellow]")
                    skipped.append(monitor.name)

            return KumaSeedResult(
                admin_created=admin_created,
                monitors_created=created,
                monitors_skipped=skipped,
                base_url=base,
            )
        finally:
            self.kuma.disconnect()

    @staticmethod
    def _to_kuma_payload(monitor: KumaMonitor) -> dict:
        return {
            "type": monitor.type,
            "name": monitor.name,
            "url": str(monitor.url),
            "interval": monitor.interval_seconds,
            "retryInterval": monitor.retry_interval_seconds,
            "maxretries": monitor.max_retries,
            "accepted_statuscodes": monitor.accepted_status_codes,
            "description": monitor.description,
        }

    def health(self, base_url: str) -> bool:
        """Connect-only check. Returns True if Kuma's socket.io handshake succeeds."""
        try:
            self.kuma.connect(base_url.rstrip("/"))
            return True
        except Exception:
            return False
        finally:
            self.kuma.disconnect()
