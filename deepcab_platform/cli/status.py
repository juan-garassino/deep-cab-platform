"""`deepcab-platform status` — show resolved settings + recent state."""

from __future__ import annotations

from rich import print as rprint
from rich.table import Table

from deepcab_platform.deps import settings


def status_cmd() -> None:
    """Print resolved settings (env, project, gh repos, kuma URL)."""
    s = settings()
    table = Table(title="deepcab-platform settings", show_header=True)
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("env (DEEPCAB_ENV)", s.env.value)
    table.add_row("gcp.project", s.gcp.project or "(unset)")
    table.add_row("gcp.project_number", s.gcp.project_number or "(unset)")
    table.add_row("gcp.region", s.gcp.region.value)
    table.add_row("gh.owner", s.gh.owner)
    table.add_row("gh.api_repo", s.gh.api_repo)
    table.add_row("gh.platform_repo", s.gh.platform_repo)
    table.add_row("gh.website_repo", s.gh.website_repo)
    table.add_row("kuma.base_url", s.kuma.base_url or "(unset)")
    table.add_row("showcase.mode", s.showcase.mode.value)
    rprint(table)
