"""G-021: the simulate time window mixes naive and tz-aware ISO timestamps.

Both fields are documented as UTC; a naive value must be treated as UTC
instead of crashing the validator with a raw TypeError.
"""

from __future__ import annotations

from datetime import timezone

import pytest
from pydantic import ValidationError

from deepcab_platform.schemas.simulate import SimulateRunInputs


def test_naive_and_aware_bounds_are_both_utc() -> None:
    inputs = SimulateRunInputs(
        time_window_start="2014-01-01T00:00:00",
        time_window_end="2014-02-01T00:00:00Z",
    )
    assert inputs.time_window_start.tzinfo is not None
    assert inputs.time_window_start.utcoffset() == inputs.time_window_end.utcoffset()
    assert inputs.time_window_start.astimezone(timezone.utc).isoformat() == "2014-01-01T00:00:00+00:00"


def test_end_before_start_is_a_validation_error_even_when_mixed() -> None:
    with pytest.raises(ValidationError, match="time_window_end"):
        SimulateRunInputs(
            time_window_start="2014-02-01T00:00:00Z",
            time_window_end="2014-01-01T00:00:00",
        )
