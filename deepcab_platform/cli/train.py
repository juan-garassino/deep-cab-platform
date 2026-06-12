"""`deepcab-platform train-on-vm` — fire off a GCE training job."""

from __future__ import annotations

import os

import typer
from rich import print as rprint

from deepcab_platform.deps import get_train_service, settings
from deepcab_platform.schemas.enums import BackendKind, DataSize, GpuType, PlatformEnv, ProviderMode
from deepcab_platform.schemas.train import TrainOnVmInputs


def train_on_vm_cmd(
    env: PlatformEnv = typer.Option(PlatformEnv.DEV, "--env", "-e"),
    backend: BackendKind = typer.Option(BackendKind.TORCH_MLP, "--backend", "-b"),
    data: DataSize = typer.Option(DataSize.S100K, "--data", "-d"),
    machine_type: str = typer.Option("n1-standard-4", "--machine"),
    zone: str = typer.Option("europe-west1-b", "--zone"),
    gpu: GpuType = typer.Option(GpuType.T4, "--gpu", help="`none` runs CPU on COS"),
    spot: bool = typer.Option(True, "--spot/--standard"),
    auto_delete: bool = typer.Option(True, "--auto-delete/--keep-alive"),
    max_runtime: str = typer.Option("6h", "--max-runtime", help="Belt-and-suspenders GCE timeout"),
    image_tag: str = typer.Option("v1.0", "--image-tag"),
    project_id: str = typer.Option(None, "--project-id", "-p"),
    extra_env: list[str] = typer.Option(
        None, "--extra-env", "-E",
        help="KEY=VAL passed as `-e KEY=value` to the in-VM `docker run`. Repeatable.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Launch a one-shot training VM. Self-destructs on completion or `--max-runtime` timeout.

    Default config: torch_mlp on a 100k slice with 1× T4 spot ≈ $0.14/hr ≈ $0.05 for a 20-minute run.
    Falls back to CPU on Container-Optimized OS with `--gpu none`.
    """
    mode = ProviderMode.DRY_RUN if dry_run else ProviderMode.REAL
    svc = get_train_service(mode)
    s = settings()
    pid = project_id or s.gcp.project
    if not pid:
        raise typer.BadParameter("--project-id required (or set GCP_PROJECT in env).")

    extra_env_dict: dict[str, str] = {}
    for pair in extra_env or []:
        if "=" not in pair:
            raise typer.BadParameter(f"--extra-env expects KEY=VAL; got {pair!r}")
        k, v = pair.split("=", 1)
        extra_env_dict[k] = v

    inputs = TrainOnVmInputs(
        env=env, backend=backend, data=data,
        machine_type=machine_type, zone=zone, gpu=gpu,
        spot=spot, auto_delete=auto_delete, max_runtime=max_runtime,
        image_tag=image_tag, extra_env=extra_env_dict,
    )

    # Pull MLflow URL + models bucket from settings/env (or fall back to standard naming).
    mlflow_url = os.environ.get("MLFLOW_URL", "")
    models_bucket = os.environ.get("GCP_MODELS_BUCKET", f"deepcab-models-{env.value}")
    telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")

    if not mlflow_url:
        rprint(
            "[yellow]MLFLOW_URL not set in env. Training will still run but won't log to MLflow.[/yellow]"
        )

    result = svc.launch(
        inputs,
        project_id=pid,
        models_bucket=models_bucket,
        mlflow_url=mlflow_url,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
    )

    rprint(f"[bold green]✓ training VM launched[/bold green] [cyan]{result.instance_name}[/cyan]")
    rprint(f"  machine:  {result.machine_type} · gpu={result.gpu.value} · spot={result.spot}")
    rprint(f"  image:    {result.image}")
    rprint(f"  est. cost: ${result.estimated_cost_per_hour:.2f}/hr")
    rprint(f"  console:  {result.monitoring_url}")
    rprint(f"  serial:   {result.serial_console_url}")
    rprint(
        "\n[dim]The VM will self-destruct on training completion or after "
        f"{inputs.max_runtime} (whichever comes first). Tail progress with:[/dim]\n"
        f"  [cyan]gcloud compute instances get-serial-port-output {result.instance_name} "
        f"--zone={result.zone} --project={pid}[/cyan]"
    )
