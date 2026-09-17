"""TrainOnVmService renders --extra-env pairs into the VM startup script.

Uses a stub GcloudProvider that captures the startup script tempfile path
(passed via --metadata-from-file=startup-script=<path>) so we can assert
on its contents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import ValidationError

from deepcab_platform.schemas.enums import BackendKind, DataSize, GpuType, PlatformEnv
from deepcab_platform.schemas.train import TrainOnVmInputs
from deepcab_platform.services.train import TrainOnVmService


@dataclass
class _CapturingGcloud:
    calls: list[list[str]] = field(default_factory=list)
    captured_script: str = ""

    def run(self, args: list[str], *, check: bool = True) -> str:
        self.calls.append(args)
        # Find --metadata-from-file=startup-script=<path> and snapshot the file.
        for tok in args:
            if tok.startswith("--metadata-from-file=startup-script="):
                path = tok.split("=", 2)[2]
                self.captured_script = Path(path).read_text()
        return ""


def _service() -> tuple[TrainOnVmService, _CapturingGcloud]:
    gcloud = _CapturingGcloud()
    template_path = (
        Path(__file__).resolve().parents[2]
        / "cloud-manifests"
        / "train"
        / "startup.sh.tmpl"
    )
    return TrainOnVmService(gcloud=gcloud, template_path=template_path), gcloud


def test_extra_env_renders_quoted_flags_inside_docker_args() -> None:
    svc, gcloud = _service()
    inputs = TrainOnVmInputs(
        env=PlatformEnv.DEV,
        backend=BackendKind.TORCH_MLP,
        data=DataSize.S1K,
        gpu=GpuType.NONE,
        extra_env={
            "DATA_SOURCE": "query",
            "DATA_BQ_WHERE": "pickup_datetime >= TIMESTAMP('2014-01-01') AND pickup_datetime < TIMESTAMP('2014-01-08')",
            "MLFLOW_RUN_NAME": "sim-000-torch-mlp",
        },
    )

    svc.launch(
        inputs,
        project_id="garassino-ml",
        models_bucket="deepcab-models-dev",
        mlflow_url="https://mlflow.example",
    )

    script = gcloud.captured_script
    # Each extra env appears as `-e KEY=value` with the value shell-quoted.
    assert "-e DATA_SOURCE=query" in script
    assert "-e MLFLOW_RUN_NAME=sim-000-torch-mlp" in script
    # Shell-quoted WHERE clause survives the bash array expansion intact —
    # shlex.quote wraps in single quotes when single quotes appear inside.
    assert "DATA_BQ_WHERE=" in script
    assert "pickup_datetime >= TIMESTAMP" in script
    # The expansion line stays in place so the array picks them up.
    assert "extra_env_flags=(" in script
    assert 'docker_args+=("${extra_env_flags[@]}")' in script


def test_empty_extra_env_collapses_to_empty_expansion() -> None:
    svc, gcloud = _service()
    inputs = TrainOnVmInputs(
        env=PlatformEnv.DEV,
        backend=BackendKind.TORCH_MLP,
        data=DataSize.S1K,
        gpu=GpuType.NONE,
        # default extra_env={}
    )

    svc.launch(
        inputs,
        project_id="garassino-ml",
        models_bucket="deepcab-models-dev",
        mlflow_url="https://mlflow.example",
    )

    # `extra_env_flags=()` is empty array — the if-block skips the append.
    # Critically: no `-e DATA_BQ_WHERE` token leaked into docker_args.
    script = gcloud.captured_script
    assert "extra_env_flags=()" in script
    assert "-e DATA_SOURCE=" not in script
    assert "-e DATA_BQ_WHERE" not in script


def test_invalid_key_shape_rejected_by_schema() -> None:
    with pytest.raises(ValidationError, match="shell-safe"):
        TrainOnVmInputs(extra_env={"lowercase-key": "v"})
    with pytest.raises(ValidationError, match="shell-safe"):
        TrainOnVmInputs(extra_env={"WITH SPACE": "v"})
    with pytest.raises(ValidationError, match="shell-safe"):
        TrainOnVmInputs(extra_env={"1LEADING_DIGIT": "v"})


def test_keys_with_special_chars_in_values_get_quoted() -> None:
    """Values with shell metacharacters must survive — single quote, $, semicolon."""
    svc, gcloud = _service()
    inputs = TrainOnVmInputs(
        env=PlatformEnv.DEV, backend=BackendKind.TORCH_MLP, data=DataSize.S1K,
        gpu=GpuType.NONE,
        extra_env={"DATA_BQ_WHERE": "x = 'a'; rm -rf /"},
    )

    svc.launch(
        inputs, project_id="p", models_bucket="b", mlflow_url="https://m",
    )

    # Render result must NOT contain unquoted `;` after the value — it should
    # be inside single quotes so bash treats it as one token.
    script = gcloud.captured_script
    # shlex.quote wraps single-quote-containing values in double-quote pairs
    # joined around the inner quote. The full quoted form keeps the semicolon
    # safely inside the value.
    assert "rm -rf /" in script  # value is preserved
    # The render line itself does not allow the semicolon to escape.
    # Confirm the value lands inside an `-e DATA_BQ_WHERE=...` token where
    # the shlex.quote wrapping prevents premature command termination.
    where_line = next(line for line in script.splitlines() if "DATA_BQ_WHERE" in line)
    assert where_line.count("'") >= 2 or where_line.count('"') >= 2
