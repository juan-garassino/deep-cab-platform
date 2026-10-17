"""SecretsService.rotate never puts the secret value on argv and cleans up its tempfile."""

from __future__ import annotations

import os
from dataclasses import dataclass, field

from deepcab_platform.services.secrets import SecretsService

_VALUE = "not-a-real-secret-value"


@dataclass
class _StubGcloud:
    calls: list[list[str]] = field(default_factory=list)
    seen: dict[str, object] = field(default_factory=dict)

    def run(self, args: list[str], *, check: bool = True) -> str:
        self.calls.append(args)
        for a in args:
            if a.startswith("--data-file="):
                path = a.split("=", 1)[1]
                self.seen["path"] = path
                self.seen["mode"] = os.stat(path).st_mode & 0o777
                with open(path) as f:
                    self.seen["content"] = f.read()
                return "projects/p/secrets/s/versions/3\n"
        return ""


def test_rotate_passes_value_by_private_file_and_bumps_consumers() -> None:
    g = _StubGcloud()
    out = SecretsService(gcloud=g).rotate("openai-api-key", _VALUE, project_id="p")

    assert all(_VALUE not in a for call in g.calls for a in call)
    assert g.seen["content"] == _VALUE
    assert g.seen["mode"] == 0o600
    assert not os.path.exists(str(g.seen["path"]))
    assert out["new_version"] == "projects/p/secrets/s/versions/3"
    bump = g.calls[1]
    assert bump[:4] == ["run", "services", "update", "deepcab-api"]
    assert "--update-secrets=OPENAI_API_KEY=openai-api-key:latest" in bump


def test_rotate_unknown_secret_bumps_nothing() -> None:
    g = _StubGcloud()
    out = SecretsService(gcloud=g).rotate("unknown", _VALUE, project_id="p")
    assert out["services_bumped"] == [] and len(g.calls) == 1
