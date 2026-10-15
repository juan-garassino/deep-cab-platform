"""SyncGhService must not crash with KeyError on a repo outside the known map."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from deepcab_platform.services.sync_gh import SyncGhService


@dataclass
class _StubGh:
    calls: list[list[str]] = field(default_factory=list)

    def run(self, args: list[str], *, check: bool = True, input_text: str | None = None) -> str:
        self.calls.append(args)
        return ""


def test_sync_unknown_repo_uses_shared_files_only(tmp_path: Path) -> None:
    (tmp_path / "gh-vars.env").write_text("GCP_REGION=europe-west1\n")
    (tmp_path / "gh-secrets.env").write_text("OPENAI_API_KEY=\n")
    gh = _StubGh()
    svc = SyncGhService(gh=gh, scripts_dir=tmp_path)

    result = svc.sync(["someone/other-repo"])

    assert result.vars_set["someone/other-repo"] == ["GCP_REGION"]
    assert result.secrets_skipped["someone/other-repo"] == ["OPENAI_API_KEY"]
    assert len(gh.calls) == 1
