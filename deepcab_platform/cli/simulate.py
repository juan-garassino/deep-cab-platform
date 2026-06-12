"""`deepcab-platform simulate run` — drives the continuous-training loop."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich import print as rprint
from rich.table import Table

from deepcab_platform.deps import get_simulate_service
from deepcab_platform.schemas.enums import (
    BackendKind,
    DataSize,
    PlatformEnv,
    ProviderMode,
)
from deepcab_platform.schemas.simulate import SimulateRunInputs

simulate_app = typer.Typer(help="Continuous-training simulation loop.", no_args_is_help=True)


@simulate_app.command("run")
def run(
    env: PlatformEnv = typer.Option(PlatformEnv.DEV, "--env", "-e"),
    backend: BackendKind = typer.Option(BackendKind.TORCH_MLP, "--backend", "-b"),
    reference_data: DataSize = typer.Option(DataSize.S10K, "--reference-data"),
    time_window_start: datetime = typer.Option(..., "--time-window-start"),
    time_window_end: datetime = typer.Option(..., "--time-window-end"),
    chunk_period_days: int = typer.Option(7, "--chunk-period-days", min=1, max=365),
    promotion_threshold: float = typer.Option(0.05, "--promotion-threshold", min=0.0, max=1.0),
    executor: str = typer.Option("local", "--executor", help="'local' or 'vm'."),
    max_chunks: int = typer.Option(None, "--max-chunks", help="Hard cap on chunks."),
    notify_only_on_success: bool = typer.Option(
        False, "--success-only/--notify-every-chunk",
        help="If set, Telegram/Slack pings fire only on promotions, not per chunk.",
    ),
    api_dir: Path = typer.Option(
        Path("../001-deepCab-api"),
        "--api-dir",
        help="Path to 001-deepCab-api (where `uv run python -m deepCab.flow_v2.simulate` is invoked).",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Walk the BQ time window in chunks; retrain + auto-promote per chunk.

    Default executor `local` runs in-process for fast dev iteration. Pass
    `--executor vm` to fire a fresh T4 spot VM per chunk (~€0.05/chunk).
    """
    inputs = SimulateRunInputs(
        env=env,
        backend=backend,
        reference_data=reference_data,
        time_window_start=time_window_start,
        time_window_end=time_window_end,
        chunk_period_days=chunk_period_days,
        promotion_threshold=promotion_threshold,
        executor=executor,
        max_chunks=max_chunks,
        notify_every_chunk=not notify_only_on_success,
    )
    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    svc = get_simulate_service(mode)
    result = svc.run(inputs, api_dir=str(api_dir.expanduser().resolve()))

    table = Table(title=f"simulate run · {result.backend.value} · {len(result.chunks)} chunks")
    table.add_column("#", justify="right")
    table.add_column("run_id")
    table.add_column("mae", justify="right")
    table.add_column("promoted", justify="center")
    table.add_column("reason")
    table.add_column("champion v", justify="right")
    for c in result.chunks:
        table.add_row(
            str(c.chunk_index),
            c.train_run_id or "-",
            f"{c.challenger_metric:.3f}",
            "✓" if c.promoted else " ",
            c.reason,
            c.new_champion_version or "-",
        )
    rprint(table)
    rprint(
        f"[bold]Promotions:[/bold] {result.promotions}/{len(result.chunks)} · "
        f"[bold]Final champion:[/bold] {result.final_champion_version or '-'} · "
        f"[bold]Est. cost:[/bold] ${result.estimated_total_cost_usd:.2f}"
    )
