"""DataCloneBqService: SQL rendering, idempotency and project scoping (G-022)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import ValidationError

from deepcab_platform.schemas.data import DataCloneBqInputs
from deepcab_platform.services.data import DataCloneBqService

_SQL = Path(__file__).resolve().parents[2] / "cloud-manifests" / "bq" / "yellow_trips_raw.export.sql"


@dataclass
class _StubGcloud:
    parquet_present: bool = False
    row_count: str = ""
    calls: list[list[str]] = field(default_factory=list)

    def run(self, args: list[str], *, check: bool = True) -> str:
        self.calls.append(args)
        if args[:2] == ["storage", "ls"]:
            return "gs://x/a.parquet\n" if self.parquet_present else ""
        if args[:3] == ["alpha", "bq", "query"] and args[-1].startswith("SELECT COUNT"):
            return self.row_count
        return ""


def _svc(**kw: object) -> tuple[DataCloneBqService, _StubGcloud]:
    g = _StubGcloud(**kw)  # type: ignore[arg-type]
    return DataCloneBqService(gcloud=g, sql_template_path=_SQL), g


def _export_sql(g: _StubGcloud) -> str:
    return next(c[-1] for c in g.calls if c[:3] == ["alpha", "bq", "query"] and "EXPORT DATA" in c[-1])


def test_source_table_is_used_in_export_sql() -> None:
    svc, g = _svc()
    svc.clone(DataCloneBqInputs(source_table="bigquery-public-data:new_york.tlc_yellow_trips_2014"))
    sql = _export_sql(g)
    assert "FROM `bigquery-public-data.new_york.tlc_yellow_trips_2014`" in sql
    assert "${" not in sql


@pytest.mark.parametrize(
    "bad",
    ["a-proj.ds.t` UNION ALL SELECT 1 --", "proj.ds.t;drop", "proj.ds.t\nx", "Pr0j.ds.t"],
)
def test_source_table_rejects_sql_metacharacters(bad: str) -> None:
    with pytest.raises(ValidationError):
        DataCloneBqInputs(source_table=bad)


def test_completed_steps_are_skipped_on_rerun() -> None:
    svc, g = _svc(parquet_present=True, row_count="42\n")
    res = svc.clone(DataCloneBqInputs(cleanup_staging=False))
    assert (res.skipped_extract, res.skipped_copy, res.skipped_load) == (True, True, True)
    assert res.rows_loaded == 42
    assert not any("EXPORT DATA" in c[-1] for c in g.calls)
    assert not any(c[:3] == ["alpha", "bq", "load"] for c in g.calls)


def test_row_count_query_is_scoped_to_target_project() -> None:
    svc, g = _svc(parquet_present=True, row_count="7")
    svc.clone(DataCloneBqInputs(target_project="other-proj", cleanup_staging=False))
    count = next(c for c in g.calls if c[-1].startswith("SELECT COUNT"))
    assert "--project_id=other-proj" in count
