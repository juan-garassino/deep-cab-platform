"""G-011 / G-019: the rendered VM startup script must not leak secrets or allow injection.

The startup script is stored as plaintext instance metadata (readable by anyone
with compute.instances.get) and runs as root, so: no bot token in it, and every
rendered value must reach bash as a single literal word.
"""

from __future__ import annotations

import shlex
import subprocess  # nosec B404 - runs `bash -n` on a test fixture only

import pytest

from deepcab_platform.schemas.train import TrainOnVmInputs
from tests.services.test_train_extra_env import _service


def _render(**kw: str) -> str:
    svc, gcloud = _service()
    base = {"project_id": "p", "models_bucket": "b", "mlflow_url": "https://m"}
    base.update(kw)
    svc.launch(TrainOnVmInputs(), **base)  # type: ignore[arg-type]
    return gcloud.captured_script


def test_bot_token_is_never_rendered_into_metadata() -> None:
    script = _render(telegram_bot_token_secret="telegram-bot-token", telegram_chat_id="42")
    assert "TG_BOT_SECRET=telegram-bot-token" in script
    assert "gcloud secrets versions access latest" in script
    assert "@@{" not in script  # every placeholder rendered
    subprocess.run(["bash", "-n"], input=script, text=True, check=True)  # nosec B603 B607


def test_launch_rejects_plaintext_token_argument() -> None:
    svc, _ = _service()
    with pytest.raises(TypeError):
        svc.launch(  # type: ignore[call-arg]
            TrainOnVmInputs(), project_id="p", models_bucket="b",
            mlflow_url="https://m", telegram_bot_token="123:abc",
        )


def test_rendered_values_are_shell_quoted() -> None:
    evil = 'https://m"; touch /tmp/pwned; echo "$(id)'
    script = _render(mlflow_url=evil)
    assert f"MLFLOW_URL={shlex.quote(evil)}" in script
    # The script must still parse.
    subprocess.run(["bash", "-n"], input=script, text=True, check=True)  # nosec B603 B607


def test_invalid_secret_name_rejected() -> None:
    with pytest.raises(ValueError, match="secret"):
        _render(telegram_bot_token_secret="x; rm -rf /")
