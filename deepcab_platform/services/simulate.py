"""SimulateService — thin wrapper around 001's `flow_v2.simulate.simulate_flow`.

The 002 platform repo shouldn't import 001's Python (different package
boundary), so we shell out to the simulate flow via `python -m`. The flow
itself returns a SimulateResult dataclass; we re-parse the JSON it prints
back into our Pydantic ``SimulateRunResult`` for the CLI to render.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol, runtime_checkable

from rich import print as rprint

from deepcab_platform.providers._subprocess import run_capture
from deepcab_platform.schemas.simulate import (
    SimulateChunkSummary,
    SimulateRunInputs,
    SimulateRunResult,
)


@runtime_checkable
class SimulateRunner(Protocol):
    """Pluggable runner so tests can avoid shelling out to a Python subprocess."""

    def invoke(self, inputs: SimulateRunInputs, *, api_dir: str) -> dict: ...


@dataclass
class SubprocessSimulateRunner:
    """Invokes 001's simulate_flow in a subprocess.

    Args list mirrors what the 001-side `python -m deepCab.flow_v2.simulate`
    entrypoint expects. JSON is printed on the final line by that entrypoint
    so we just parse the last non-empty line.
    """

    def invoke(self, inputs: SimulateRunInputs, *, api_dir: str) -> dict:
        cmd = [
            "uv", "run", "python", "-m", "deepCab.flow_v2.simulate",
            "--backend", inputs.backend.value,
            "--reference-size", inputs.reference_data.value,
            "--start", inputs.time_window_start.isoformat(),
            "--end", inputs.time_window_end.isoformat(),
            "--chunk-days", str(inputs.chunk_period_days),
            "--threshold", str(inputs.promotion_threshold),
            "--executor", inputs.executor,
        ]
        if inputs.max_chunks is not None:
            cmd.extend(["--max-chunks", str(inputs.max_chunks)])
        if not inputs.notify_every_chunk:
            cmd.append("--success-only")

        out = run_capture(cmd, cwd=api_dir, env=os.environ.copy())
        # Last non-empty line should be the JSON payload.
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                return json.loads(line)
        raise RuntimeError(f"simulate_flow produced no JSON output. tail:\n{out[-2000:]}")


@dataclass
class DryRunSimulateRunner:
    """Prints what would run, returns a single-chunk synthetic result."""

    def invoke(self, inputs: SimulateRunInputs, *, api_dir: str) -> dict:
        n_chunks = max(
            1,
            (inputs.time_window_end - inputs.time_window_start)
            // timedelta(days=inputs.chunk_period_days),
        )
        if inputs.max_chunks is not None:
            n_chunks = min(n_chunks, inputs.max_chunks)
        rprint(
            f"[dim]\\[dry-run simulate][/dim] executor=[cyan]{inputs.executor}[/cyan] "
            f"chunks=[cyan]{n_chunks}[/cyan] backend=[cyan]{inputs.backend.value}[/cyan]"
        )
        return {
            "backend": inputs.backend.value,
            "chunks": [
                {
                    "chunk_index": i,
                    "train_run_id": f"dry-{i}",
                    "challenger_metric": 2.5,
                    "promoted": False,
                    "reason": "dry-run",
                    "new_champion_version": None,
                }
                for i in range(n_chunks)
            ],
            "promotions": 0,
            "final_champion_version": None,
            "mae_trajectory": [2.5] * n_chunks,
            "estimated_total_cost_usd": 0.0,
        }


@dataclass
class SimulateService:
    runner: SimulateRunner

    def run(self, inputs: SimulateRunInputs, *, api_dir: str) -> SimulateRunResult:
        payload = self.runner.invoke(inputs, api_dir=api_dir)
        return SimulateRunResult(
            backend=inputs.backend,
            chunks=[SimulateChunkSummary(**c) for c in payload.get("chunks", [])],
            promotions=payload.get("promotions", 0),
            final_champion_version=payload.get("final_champion_version"),
            mae_trajectory=payload.get("mae_trajectory", []),
            estimated_total_cost_usd=payload.get("estimated_total_cost_usd", 0.0),
        )
