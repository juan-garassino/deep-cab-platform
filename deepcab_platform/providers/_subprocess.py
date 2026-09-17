"""Shared subprocess helper for the Real* providers.

Each Real provider (gcloud, gh, terraform) needs the same error-handling:
- capture stdout + stderr so dry-run mode and tests can inspect them
- on non-zero exit, surface BOTH streams to the user (rich+capture hides them
  otherwise; the original CalledProcessError traceback obscures the real cause)
- re-raise CalledProcessError so callers can decide whether to bubble up

This helper does exactly that. Callers pass the args list; we return stdout
and raise on failure (with the messages already streamed to the user).
"""

from __future__ import annotations

import subprocess
import sys


def run_capture(
    args: list[str],
    *,
    check: bool = True,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> str:
    """Run a subprocess; on failure write stdout+stderr through and raise."""
    result = subprocess.run(
        args,
        check=False,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        input=input_text,
    )
    if result.returncode != 0:
        if result.stdout:
            sys.stdout.write(result.stdout)
        if result.stderr:
            sys.stderr.write(result.stderr)
        if check:
            raise subprocess.CalledProcessError(
                result.returncode, args, output=result.stdout, stderr=result.stderr
            )
    return result.stdout
