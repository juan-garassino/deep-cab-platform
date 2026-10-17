"""BootstrapService: WIF condition scoping (G-023) and create-vs-reuse idempotency."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from deepcab_platform.schemas.bootstrap import BootstrapInputs
from deepcab_platform.schemas.enums import PlatformEnv
from deepcab_platform.services import bootstrap as bootstrap_mod
from deepcab_platform.services.bootstrap import BootstrapService

_BILLING = "ABCDEF-012345-6789AB"


@dataclass
class _StubGcloud:
    exists: bool
    calls: list[list[str]] = field(default_factory=list)

    def run(self, args: list[str], *, check: bool = True) -> str:
        self.calls.append(args)
        if "describe" in args and "--format=value(projectNumber)" in args:
            return "123456\n"
        if "describe" in args and not self.exists:
            raise RuntimeError("NOT_FOUND")
        return ""


def _inputs(**kw: str) -> BootstrapInputs:
    return BootstrapInputs(env=PlatformEnv.DEV, billing_account=_BILLING, project_id="deepcab-dev-1", **kw)


@pytest.mark.parametrize(
    "field_, bad",
    [
        ("gh_owner", "x' || true || '"),
        ("gh_owner", ""),
        ("gh_owner", "-leading-dash"),
        ("gh_platform_repo", "repo/../other"),
        ("gh_platform_repo", "a b"),
        ("gh_platform_repo", ".."),
    ],
)
def test_github_identifiers_are_validated(field_: str, bad: str) -> None:
    with pytest.raises(ValidationError):
        _inputs(**{field_: bad})


def test_fresh_project_creates_everything_with_scoped_wif(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bootstrap_mod.time, "sleep", lambda _s: None)
    g = _StubGcloud(exists=False)
    res = BootstrapService(gcloud=g).bootstrap(_inputs(gh_owner="octo-org", gh_platform_repo="infra.repo"))

    verbs = [" ".join(c[:4]) for c in g.calls]
    assert any(v.startswith("projects create deepcab-dev-1") for v in verbs)
    assert any(v.startswith("storage buckets create") for v in verbs)
    oidc = next(c for c in g.calls if "create-oidc" in c)
    assert "--attribute-condition=assertion.repository_owner == 'octo-org'" in oidc
    wiu = next(c for c in g.calls if "--role=roles/iam.workloadIdentityUser" in c)
    assert any(a.endswith("/attribute.repository/octo-org/infra.repo") for a in wiu)
    assert res.project_number == "123456"
    assert res.wif_provider.startswith("projects/123456/")


def test_existing_project_reuses_resources() -> None:
    g = _StubGcloud(exists=True)
    BootstrapService(gcloud=g).bootstrap(_inputs())
    flat = [" ".join(c) for c in g.calls]
    assert not any(" create" in f.split("--")[0] for f in flat)
