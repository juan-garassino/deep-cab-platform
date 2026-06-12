"""CleanupLegacyService — verifies the allow-list scoping + idempotency.

Uses a stub TerraformProvider that replays canned outputs and a stub
GcloudProvider that records calls. No real subprocesses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from deepcab_platform.schemas.enums import PlatformEnv
from deepcab_platform.services.cleanup import CleanupLegacyService


@dataclass
class _StubTerraform:
    """Replays canned outputs based on the first arg of each call.

    Anything not in `replies` returns empty string. Records every call so
    tests can assert what state-rm addresses were forgotten.
    """

    replies: dict[tuple[str, ...], str] = field(default_factory=dict)
    calls: list[list[str]] = field(default_factory=list)

    def run(self, args: list[str], *, workdir: str, check: bool = True) -> str:
        self.calls.append(args)
        return self.replies.get(tuple(args), self.replies.get((args[0],), ""))


@dataclass
class _StubGcloud:
    described: dict[str, str] = field(default_factory=dict)
    calls: list[list[str]] = field(default_factory=list)

    def run(self, args: list[str], *, check: bool = True) -> str:
        self.calls.append(args)
        # `describe` calls: `sql instances describe <name> ...` or `secrets describe <id> ...`.
        # The describable name is the token right after "describe".
        if "describe" in args:
            i = args.index("describe")
            key = args[i + 1] if i + 1 < len(args) else ""
            return self.described.get(key, "")
        return ""


def _state_list_with_legacy() -> str:
    return "\n".join(
        [
            "module.bigquery.google_bigquery_dataset.taxi",
            "module.cloud_sql.google_sql_database_instance.this",
            "module.cloud_sql.google_sql_user.users[\"mlflow\"]",
            "module.gar.google_artifact_registry_repository.deepcab",
            "google_secret_manager_secret_version.mlflow_db_password",
            "module.wif.google_service_account.deployer",
        ]
    )


def test_cleanup_only_touches_allow_listed_addresses() -> None:
    tf = _StubTerraform(
        replies={
            ("state", "list"): _state_list_with_legacy(),
            ("output", "-raw", "project_id"): "garassino-ml",
            # plan returns no legacy lines after the cleanup
            ("plan", "-input=false", "-no-color", "-detailed-exitcode"): "Plan: 1 to add",
        }
    )
    gcloud = _StubGcloud(described={"deepcab-mlflow-dev": "deepcab-mlflow-dev", "mlflow-db-password": "mlflow-db-password"})
    svc = CleanupLegacyService(terraform=tf, gcloud=gcloud)

    result = svc.cleanup(PlatformEnv.DEV)

    # Allow-list scope: only the 3 legacy lines were rm'd; BigQuery, GAR, WIF untouched.
    assert sorted(result.state_addresses_removed) == sorted(
        [
            "module.cloud_sql.google_sql_database_instance.this",
            'module.cloud_sql.google_sql_user.users["mlflow"]',
            "google_secret_manager_secret_version.mlflow_db_password",
        ]
    )
    rm_args = [c for c in tf.calls if c[:2] == ["state", "rm"]]
    assert len(rm_args) == 3

    # Orphaned cloud SQL instance + obsolete secret get deleted via gcloud.
    assert result.cloud_sql_instance_deleted is True
    assert "mlflow-db-password" in result.secrets_deleted

    # plan_clean is True because the canned plan output has no legacy substrings.
    assert result.plan_clean is True


def test_cleanup_is_idempotent_when_state_is_clean() -> None:
    tf = _StubTerraform(
        replies={
            ("state", "list"): "module.bigquery.google_bigquery_dataset.taxi\nmodule.gar.google_artifact_registry_repository.deepcab\n",
            ("output", "-raw", "project_id"): "garassino-ml",
            ("plan", "-input=false", "-no-color", "-detailed-exitcode"): "No changes",
        }
    )
    # Nothing exists on the cloud side either.
    gcloud = _StubGcloud(described={})
    svc = CleanupLegacyService(terraform=tf, gcloud=gcloud)

    result = svc.cleanup(PlatformEnv.DEV)

    assert result.state_addresses_removed == []
    assert result.cloud_sql_instance_deleted is False
    assert result.cloud_sql_instance_skipped_reason == "instance already absent"
    assert result.secrets_deleted == []
    assert result.plan_clean is True
    # No `state rm` calls, no `instances delete` calls, no `secrets delete` calls.
    assert not any(c[:2] == ["state", "rm"] for c in tf.calls)
    assert not any("delete" in c for c in gcloud.calls)


def test_pre_flight_helper_returns_legacy_addresses() -> None:
    """ShowcaseService consumes `list_legacy_state_addresses` to abort UP
    when legacy resources are still in state — verify the helper alone."""
    tf = _StubTerraform(replies={("state", "list"): _state_list_with_legacy()})
    svc = CleanupLegacyService(terraform=tf, gcloud=_StubGcloud())

    addresses = svc.list_legacy_state_addresses(PlatformEnv.DEV)

    assert len(addresses) == 3
    assert all("cloud_sql" in a or "mlflow_db_password" in a for a in addresses)
