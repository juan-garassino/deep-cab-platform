"""TerraformService — thin wrapper around `terraform plan/apply/destroy`.

Scopes commands to `terraform/envs/<env>/`. Auto-handles `terraform init` if
the .terraform/ dir is missing. Reads `DEEPCAB_ENV` to pick the env unless
overridden explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from deepcab_platform.providers.terraform import TerraformProvider
from deepcab_platform.schemas.enums import PlatformEnv, TerraformAction


@dataclass
class TerraformService:
    """Runs Terraform actions scoped to `terraform/envs/<env>`."""
    terraform: TerraformProvider
    terraform_dir: Path = Path("terraform")

    def envs_dir(self, env: PlatformEnv) -> str:
        """Return the working directory for `env`."""
        return str(self.terraform_dir / "envs" / env.value)

    def init(self, env: PlatformEnv) -> str:
        """Run `terraform init -input=false` for `env`."""
        return self.terraform.run(["init", "-input=false"], workdir=self.envs_dir(env))

    def run_action(
        self,
        action: TerraformAction,
        env: PlatformEnv,
        *,
        auto_approve: bool = False,
        extra_args: list[str] | None = None,
    ) -> str:
        """Run `terraform <action>` for `env` with `-input=false -no-color`.

        `-auto-approve` is added only for apply/destroy when `auto_approve` is set;
        `extra_args` are appended after it.
        """
        args = [action.value, "-input=false", "-no-color"]
        if action in (TerraformAction.APPLY, TerraformAction.DESTROY) and auto_approve:
            args.append("-auto-approve")
        if extra_args:
            args.extend(extra_args)
        return self.terraform.run(args, workdir=self.envs_dir(env))
