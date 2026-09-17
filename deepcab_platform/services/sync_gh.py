"""SyncGhService — bulk-upload GitHub Actions vars + secrets to N repos.

Python port of `scripts/sync-gh-secrets.sh`. Reads the same dotenv files
(`scripts/gh-vars.env`, `scripts/gh-vars.<repo>.env`, `scripts/gh-secrets.env`)
so the surface is backwards-compatible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from rich import print as rprint

from deepcab_platform.providers.gh import GhProvider
from deepcab_platform.schemas.gh import GhSyncResult


@dataclass
class SyncGhService:
    gh: GhProvider
    scripts_dir: Path = field(default_factory=lambda: Path("scripts"))

    REPO_VARS_FILE = {
        "juan-garassino/deepCab": "gh-vars.api.env",
        "juan-garassino/deepCab-platform": "gh-vars.platform.env",
        "juan-garassino/deepCab-website": "gh-vars.website.env",
    }

    def sync(self, repos: list[str] | None = None) -> GhSyncResult:
        repos = repos or list(self.REPO_VARS_FILE)
        shared_vars = self.scripts_dir / "gh-vars.env"
        shared_secrets = self.scripts_dir / "gh-secrets.env"
        if not shared_vars.exists():
            raise FileNotFoundError(f"Missing {shared_vars} — copy {shared_vars.name}.example")
        if not shared_secrets.exists():
            raise FileNotFoundError(f"Missing {shared_secrets} — copy {shared_secrets.name}.example")

        result = GhSyncResult(vars_set={}, secrets_set={}, secrets_skipped={})

        for repo in repos:
            rprint(f"[bold cyan]→ {repo}[/bold cyan]")
            # Shared vars
            self.gh.run(["variable", "set", "--repo", repo, "-f", str(shared_vars)])
            shared_names = self._parse_names(shared_vars)
            # Per-repo vars (if file exists)
            per_repo = self.scripts_dir / self.REPO_VARS_FILE[repo]
            per_repo_names: list[str] = []
            if per_repo.exists():
                self.gh.run(["variable", "set", "--repo", repo, "-f", str(per_repo)])
                per_repo_names = self._parse_names(per_repo)
            result.vars_set[repo] = shared_names + per_repo_names

            # Secrets — skip if all values empty
            if self._has_nonempty_values(shared_secrets):
                self.gh.run(["secret", "set", "--repo", repo, "-f", str(shared_secrets)])
                result.secrets_set[repo] = self._parse_names(shared_secrets)
            else:
                result.secrets_skipped[repo] = self._parse_names(shared_secrets)
        return result

    @staticmethod
    def _parse_names(path: Path) -> list[str]:
        names: list[str] = []
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            names.append(stripped.split("=", 1)[0])
        return names

    @staticmethod
    def _has_nonempty_values(path: Path) -> bool:
        pattern = re.compile(r"^[A-Z_]+=.+$")
        return any(pattern.match(line.strip()) for line in path.read_text().splitlines())
