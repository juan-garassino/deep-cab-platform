"""TrainOnVmService — provision a one-shot training VM on GCE.

The whole story: render the startup script template, write it to a tempfile,
call `gcloud compute instances create` with the tempfile as metadata, pass
back URLs the CLI can render for the user. Self-cleanup is the VM's job —
this service is fire-and-forget.

Why VM at all when we have a Cloud Run Job already? GPU. Cloud Run doesn't
support GPUs (as of 2026). For CPU training under 24h, `gcloud run jobs
execute deepcab-retrain` is strictly the better path.
"""

from __future__ import annotations

import os
import shlex
import string
import tempfile
from dataclasses import dataclass
from pathlib import Path

from deepcab_platform.providers.gcloud import GcloudProvider
from deepcab_platform.schemas.enums import GpuType
from deepcab_platform.schemas.train import TrainOnVmInputs, TrainOnVmResult

# Static cost table (USD/hour). Rough — uses Iowa spot pricing as of 2026-Q1.
# Used only for the CLI to print a "this will cost about X" hint.
HOURLY_COST_USD = {
    ("e2-standard-2", GpuType.NONE): 0.03,
    ("e2-standard-4", GpuType.NONE): 0.05,
    ("e2-standard-8", GpuType.NONE): 0.11,
    ("n1-standard-4", GpuType.NONE): 0.05,
    ("n1-standard-4", GpuType.T4): 0.14,
    ("n1-standard-8", GpuType.T4): 0.20,
    ("n1-standard-4", GpuType.L4): 0.32,
    ("n1-standard-8", GpuType.A100): 1.10,
}


@dataclass
class TrainOnVmService:
    gcloud: GcloudProvider
    template_path: Path = Path("cloud-manifests/train/startup.sh.tmpl")

    def launch(
        self,
        inputs: TrainOnVmInputs,
        *,
        project_id: str,
        models_bucket: str,
        mlflow_url: str,
        telegram_bot_token: str = "",
        telegram_chat_id: str = "",
    ) -> TrainOnVmResult:
        instance_name = self._instance_name(inputs)
        image_uri = (
            f"europe-west1-docker.pkg.dev/{project_id}/deepcab/api:{inputs.image_tag}"
        )
        startup_script = self._render_startup(
            inputs=inputs,
            project_id=project_id,
            image_uri=image_uri,
            models_bucket=models_bucket,
            mlflow_url=mlflow_url,
            telegram_bot_token=telegram_bot_token,
            telegram_chat_id=telegram_chat_id,
        )

        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as f:
            f.write(startup_script)
            startup_path = f.name

        try:
            args = self._gcloud_create_args(
                instance_name=instance_name,
                inputs=inputs,
                project_id=project_id,
                startup_script_path=startup_path,
                image_uri=image_uri,
            )
            self.gcloud.run(args)
        finally:
            try:
                os.unlink(startup_path)
            except OSError:
                pass

        return TrainOnVmResult(
            instance_name=instance_name,
            zone=inputs.zone,
            project_id=project_id,
            image=image_uri,
            machine_type=inputs.machine_type,
            gpu=inputs.gpu,
            spot=inputs.spot,
            serial_console_url=(
                f"https://console.cloud.google.com/compute/instancesDetail/zones/"
                f"{inputs.zone}/instances/{instance_name}/serialPort?project={project_id}"
            ),
            monitoring_url=(
                f"https://console.cloud.google.com/compute/instancesDetail/zones/"
                f"{inputs.zone}/instances/{instance_name}?project={project_id}"
            ),
            estimated_cost_per_hour=HOURLY_COST_USD.get((inputs.machine_type, inputs.gpu), 0.0),
        )

    # ------------------------- internals --------------------------------------

    @staticmethod
    def _instance_name(inputs: TrainOnVmInputs) -> str:
        import datetime
        ts = datetime.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        # GCE instance names: lowercase letters/digits/hyphens, ≤63 chars.
        return f"deepcab-train-{inputs.backend.value.replace('_', '-')}-{ts}"

    def _render_startup(
        self,
        *,
        inputs: TrainOnVmInputs,
        project_id: str,
        image_uri: str,
        models_bucket: str,
        mlflow_url: str,
        telegram_bot_token: str,
        telegram_chat_id: str,
    ) -> str:
        template = string.Template(self.template_path.read_text())
        return template.safe_substitute(
            PROJECT_ID=project_id,
            BACKEND=inputs.backend.value,
            DATA=inputs.data.value,
            IMAGE=image_uri,
            MODELS_BUCKET=models_bucket,
            MLFLOW_URL=mlflow_url,
            TG_BOT=telegram_bot_token,
            TG_CHAT=telegram_chat_id,
            AUTO_DELETE="true" if inputs.auto_delete else "false",
            GPU=inputs.gpu.value,
            EXTRA_DOCKER_ENV=self._render_extra_docker_env(inputs.extra_env),
        )

    @staticmethod
    def _render_extra_docker_env(extra: dict[str, str]) -> str:
        """Render extra env dict as space-separated `-e KEY='value'` flags.

        Keys are guaranteed shell-safe by the Pydantic validator; values get
        shlex.quote()'d so datetime literals + spaces survive the bash array
        expansion intact. Empty dict → empty string (placeholder collapses).
        """
        if not extra:
            return ""
        return " ".join(f"-e {k}={shlex.quote(v)}" for k, v in sorted(extra.items()))

    @staticmethod
    def _gcloud_create_args(
        *,
        instance_name: str,
        inputs: TrainOnVmInputs,
        project_id: str,
        startup_script_path: str,
        image_uri: str,
    ) -> list[str]:
        # GPU path uses Google's Deep Learning VM image (CUDA pre-installed).
        # CPU path uses Container-Optimized OS (smaller, faster boot).
        if inputs.gpu == GpuType.NONE:
            image_family = "cos-stable"
            image_project = "cos-cloud"
        else:
            image_family = "common-cu121-debian-11"
            image_project = "deeplearning-platform-release"

        sa_email = f"deepcab-runtime@{project_id}.iam.gserviceaccount.com"
        args = [
            "compute", "instances", "create", instance_name,
            f"--project={project_id}",
            f"--zone={inputs.zone}",
            f"--machine-type={inputs.machine_type}",
            f"--image-family={image_family}",
            f"--image-project={image_project}",
            f"--service-account={sa_email}",
            "--scopes=https://www.googleapis.com/auth/cloud-platform",
            f"--metadata-from-file=startup-script={startup_script_path}",
            f"--max-run-duration={inputs.max_runtime}",
            "--instance-termination-action=DELETE",
            "--boot-disk-size=100GB",
        ]
        if inputs.spot:
            args.append("--provisioning-model=SPOT")
        if inputs.gpu != GpuType.NONE:
            args.append(f"--accelerator=count=1,type={inputs.gpu.value}")
            args.append("--maintenance-policy=TERMINATE")  # required for GPU
            args.append("--metadata=install-nvidia-driver=True")
        return args
