# GUARDIAN

Automated security and bug sweep for `deep-cab-platform`. It runs on branch `claude/guardian`.
Every 4th run is a meta-review run (count the entries under **Log**). The next one is run 4 (run 2 done 2026-10-17).

## Checks

| Area | Command / rule |
|---|---|
| Deps (PyPI) | `uv export --frozen --no-hashes --all-extras --no-emit-project > req.txt && pip-audit -r req.txt --no-deps --disable-pip` |
| Deps (deployed images) | `pip-audit` on the versions pinned in `cloud-manifests/mlflow/mirror.yaml` and any `pip install` in Terraform container `args` |
| Deps (OSV) | `osv-scanner -r .`: **did not run** (osv.dev API returned 403 from the sandbox) |
| Code | `bandit -r deepcab_platform -q` |
| Code (grep) | `eval(`, `exec(`, `pickle`, `yaml.load`, `shell=True`, `os.system`, `verify=False`, `0.0.0.0`, SQL built with f-strings or format, values interpolated into the rendered VM startup script |
| Secrets | `gitleaks detect --source . --redact -v` (full history), `gitleaks detect --no-git --redact`, `detect-secrets scan --all-files`, each hit triaged by hand |
| Actions | Actions pinned to a SHA? `permissions:` minimal? Is `${{ github.event.* }}` interpolated into `run:`? Do the step `if:` conditions work? |
| Docker | No Dockerfiles in the repo |
| Terraform | `terraform fmt -check -recursive terraform` (registry is blocked from the sandbox, so `validate` cannot init providers). Manual review of `0.0.0.0/0`, `allUsers` / `allow_unauthenticated`, and secrets in `secret_env_vars` |
| Tests / lint | `uv sync --extra dev`, `uv run pytest -q --cov=deepcab_platform`, `uv run ruff check .`, `uv run mypy deepcab_platform` |

## Findings ledger

| id | severity | type | file | status | date |
|---|---|---|---|---|---|
| G-001 | med | vuln-dep: urllib3 2.7.0 (PYSEC-2026-4175/4176/4177) | uv.lock | fixed (2.8.0) | 2026-10-15 |
| G-002 | low | vuln-dep: pydantic-settings 2.14.1 (CVE-2026-58203, secrets_dir symlink) | uv.lock | fixed (>=2.15) | 2026-10-15 |
| G-003 | med | injection: `image_tag`/`zone`/`machine_type`/`max_runtime` were not validated and reach the root bash startup script / gcloud argv | deepcab_platform/schemas/train.py | fixed | 2026-10-15 |
| G-004 | med | SQL built by string (bandit B608): BQ identifiers and bucket names were not validated | deepcab_platform/schemas/data.py | fixed | 2026-10-15 |
| G-005 | low | bug: `sync-gh` raised `KeyError` for a repo outside `REPO_VARS_FILE` | deepcab_platform/services/sync_gh.py | fixed | 2026-10-15 |
| G-006 | med | supply chain: GitHub Actions were pinned to mutable tags | .github/workflows/*.yml | open (patch ready; push needs `workflow` scope) | 2026-10-15 |
| G-007 | low | `${{ github.event.inputs.env }}` interpolated into `run:` | .github/workflows/platform-plan.yml | open (patch ready) | 2026-10-15 |
| G-008 | low | bug: the Slack notify step `if: env.SLACK_WEBHOOK_URL != ''` read step env, so it was always false and Slack never fired | .github/workflows/platform-apply.yml | open (patch ready) | 2026-10-15 |
| G-009 | low | `.gitignore` did not cover the `.env.<env>` files that settings load | .gitignore | fixed | 2026-10-15 |
| G-010 | low | lint: unused import (ruff F401) | deepcab_platform/services/simulate.py | fixed | 2026-10-15 |
| G-011 | med | Telegram bot token rendered in plaintext into the VM startup-script metadata | deepcab_platform/services/train.py, cloud-manifests/train/startup.sh.tmpl | fixed (VM reads it from Secret Manager) | 2026-10-17 |
| G-012 | med | GKE master authorized networks set to `0.0.0.0/0` | terraform/modules/gke/main.tf | fixed (`master_authorized_cidrs`, default closed, 0.0.0.0/0 rejected) | 2026-10-17 |
| G-013 | low | dev `cloud_sql.authorized_networks` set to `0.0.0.0/0` (module not used in dev today) | terraform/envs/_shared/env_config.tf | fixed (`[]`, same as staging/prod) | 2026-10-17 |
| G-014 | low | secret-scan hit, see the URGENT note below (re-confirmed 2026-10-17; low-impact client-side token type) | n/a | open (owner) | 2026-10-15 |
| G-015 | low | `platform-plan` "Skip if dispatch" step `exit 0` does not skip the steps after it | .github/workflows/platform-plan.yml | open | 2026-10-15 |
| G-016 | low | MLflow container runs `pip install psycopg2-binary` unpinned at every boot | terraform/envs/dev/main.tf | fixed (pinned `==2.9.10`, `--only-binary=:all:`) | 2026-10-17 |
| G-017 | low | mypy: 3 errors (missing yaml / uptime_kuma stubs, pydantic Annotated default) | pyproject.toml | fixed (types-PyYAML, pydantic mypy plugin, override) | 2026-10-17 |
| G-019 | med | injection: `MLFLOW_URL`, `GCP_MODELS_BUCKET`, `TELEGRAM_CHAT_ID` (env) were spliced raw into double-quoted assignments in the root startup script; `string.Template` also rendered the script's own bash `$VAR`s | deepcab_platform/services/train.py, startup.sh.tmpl | fixed (`@@{}` delimiter + `shlex.quote`) | 2026-10-17 |
| G-020 | high | vuln-dep: the deployed MLflow server image `v2.16.2` has 62 known advisories (pip-audit) and the dev Cloud Run service is public (`allow_unauthenticated` defaults to true) | cloud-manifests/mlflow/mirror.yaml, terraform/envs/dev/main.tf | open (owner: needs mirror rebuild + `mlflow db upgrade`) | 2026-10-17 |
| G-021 | low | bug: `simulate run` crashed with a raw `TypeError` when one bound was naive and the other tz-aware | deepcab_platform/schemas/simulate.py | fixed | 2026-10-17 |
| G-022 | low | bug: `data clone-bq --source-table` was validated then ignored (SQL hardcoded the source); its validator also let backticks / `;` through into SQL. Row-count query ran in the default gcloud project. | deepcab_platform/schemas/data.py, services/data.py, export.sql | fixed | 2026-10-17 |
| G-023 | med | injection: `gh_owner` / `gh_platform_repo` unvalidated but spliced into the WIF provider CEL `attribute-condition` and principalSet (e.g. `x' \|\| true \|\| '` would trust any GitHub owner) | deepcab_platform/schemas/bootstrap.py | fixed | 2026-10-17 |
| G-024 | low | bandit B404/B603/B608 on vetted sites | providers/_subprocess.py, services/data.py | annotated `# nosec` with reason | 2026-10-17 |
| G-018 | low | bandit B110 try/except/pass (5 sites; best-effort probes on purpose) | services/bootstrap.py, providers/kuma.py | wontfix | 2026-10-15 |

URGENT: possible credential exposure, see the owner's private run summary.

Triaged as false positives: the gitleaks `hashicorp-tf-password` hits and the detect-secrets "Secret Keyword" hits in `terraform/**`. They are Secret Manager secret *names* or references, not values. The base64 hits in `index.html` are SRI hashes.

## Metrics

| Metric | Run 1 before | Run 2 before | Run 2 after |
|---|---|---|---|
| Open vulns crit/high/med/low | 0 / 0 / 6 / 7 | 0 / 0 / 3 / 4 | 0 / 1 / 1 / 2 (+1 wontfix) |
| Known-vulnerable deps, lockfile (pip-audit) | 4 advisories in 2 pkgs | 0 | 0 |
| Known-vulnerable deployed images | not checked | 62 (mlflow 2.16.2) | 62 (owner action, G-020) |
| Bugs open | 3 | 2 (G-008, G-015) | 2 (both workflow-only) |
| Failing tests | 0 | 0 | 0 |
| Test count | 7 | 21 | 27 (pass 2: 44) |
| Coverage (line) | 18% | 26% | 29% (pass 2: 44%) |
| ruff errors | 1 | 0 | 0 |
| mypy errors | 3 | 3 | 0 |

The open counts above: high = G-020; med = G-006; low = G-007, G-014 (G-008/G-015 are workflow bugs, counted under Bugs).

## Backlog (prioritized)

0. G-020 (owner): bump the mirrored MLflow image to `v3.17.1` (0 known advisories at 2026-10-17; `v3.15.2` has 1). Do it in `cloud-manifests/mlflow/mirror.yaml` and the `image` in `terraform/envs/dev/main.tf`, run `mlflow db upgrade "$DEEPCAB_NEON_DSN"` against a Neon branch first, then apply. Also consider `allow_unauthenticated = false` or IAP for MLflow.
1. G-006, G-007, G-008, G-015 (workflow edits): the guardian's token lacks the GitHub `workflow` scope, so it cannot push changes under `.github/workflows/`. The owner should apply these edits by hand:
   - pin `actions/checkout@11d5960a326750d5838078e36cf38b85af677262` (v4), `hashicorp/setup-terraform@b9cd54a3c349d3f38e8881555d616ced269862dd` (v3), `google-github-actions/auth@c200f3691d83b41bf9bbd8638997a462592937ed` (v2), `actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b` (v7);
   - in `platform-apply.yml`, replace `if: success()/failure() && env.SLACK_WEBHOOK_URL != ''` with `if: success()/failure()` + `continue-on-error: true` and start each `run:` with `[ -z "$SLACK_WEBHOOK_URL" ] && exit 0`;
   - in `platform-plan.yml`, pass `github.event.inputs.env` / `matrix.env` to the skip step through `env:` instead of `${{ }}` in `run:`, and gate the later steps on a step output (G-015);
   - add a small CI job: `uv sync --extra dev && uv run pytest -q && uv run ruff check . && uv run mypy deepcab_platform` (mypy is clean now).
2. G-011 follow-up (owner): create the `telegram-bot-token` secret, grant `roles/secretmanager.secretAccessor` on it to `deepcab-runtime@`, and export `TELEGRAM_BOT_TOKEN_SECRET=telegram-bot-token`. Ideally manage that secret and binding in Terraform `secret_manager`.
3. G-012 follow-up: if GKE is ever enabled, pass `master_authorized_cidrs` from the env compositions.
4. G-014: owner action. See the private summary.
5. Tests for `services/showcase.py`, `services/kuma.py`, `providers/kuma.py`, `deps.py` (still 0%). bootstrap/data/secrets were covered in run 2 pass 2.
6. Get `terraform validate` working: cache providers, or run it in CI.

## Learnings

- Values rendered into `startup.sh.tmpl` through `string.Template` are spliced into a root bash script. Only `extra_env` was protected (`shlex.quote`). Every other user-controlled field needs a strict pattern at the pydantic boundary.
- In GitHub Actions, a step's own `env:` is not available in that step's `if:`. Conditions like that silently become false.
- `uv lock --upgrade-package` also bumped the lockfile format (revision 1 to 3), which makes the diff large. The package changes are only pydantic-settings and urllib3.

- `string.Template` substitutes bare `$NAME`, not just `${NAME}`. A bash template rendered with it has *every* bash variable reference rewritten at render time. Use a subclass with its own delimiter (`@@`) for shell templates.
- Lockfile audits miss what is actually deployed. Container images pinned in Terraform/Cloud Build carry their own (here: much worse) vulnerability surface.
- pydantic-core regexes are Rust `regex`: no look-around. Use a `field_validator` for exclusions.
- A pydantic `field_validator` that raises `TypeError` surfaces as a raw exception, not a `ValidationError`. Normalize inputs (e.g. tz) in an earlier validator.

Ideas for future checks:
1. Add a grep rule that flags every `string.Template` placeholder fed from CLI or env input that lacks a validator.
2. Run actionlint / zizmor over `.github/workflows` to catch dead `if:` conditions and injection.
3. Run tfsec / checkov over `terraform/` for open CIDRs, public IAM, and missing deletion protection.
4. Every run, pip-audit each container image version referenced in Terraform and Cloud Build, not only `uv.lock`.
5. Add a test that renders the startup script with hostile values for *every* placeholder and runs `bash -n`.
6. Flag Terraform module variables whose defaults are insecure (e.g. `allow_unauthenticated = true`) and list which callers rely on that default.

## Log

- Run 1 (2026-10-15): First sweep. Fixed 2 vulnerable deps, 2 input-validation injection vectors, 1 bug (sync-gh KeyError), `.gitignore` for env files, and 1 lint error. Added 14 tests. The workflow fixes (G-006/7/8) were written but could not be pushed (token lacks `workflow` scope), so they are listed in the Backlog for the owner. 10 items remain open. osv-scanner was unavailable (403).
- Run 2 (2026-10-17): Fixed G-011: the Telegram token now comes from Secret Manager on the VM and is no longer in metadata. Fixed G-019: startup-script injection through env-sourced values, plus the template rendering bash's own `$VAR`s. Also fixed G-012 and G-013 (closed the `0.0.0.0/0` networks), G-016 (pinned psycopg2), G-017 (mypy 3 to 0) and G-021 (simulate tz crash). Added 6 tests (21 to 27). New HIGH G-020: the public dev MLflow runs image v2.16.2, which has 62 advisories. That needs an owner-driven migration, so it was not auto-changed. Terraform was only checked with `fmt` (the registry is blocked). Not a meta-review run.
- Run 2, pass 2 (2026-10-17): Added tests for the riskiest 0%-coverage modules: bootstrap, data clone, secrets rotate (27 to 44 tests, coverage 29% to 44%). They found and fixed G-023 (med, CEL injection into the WIF provider condition via `gh_owner`) and G-022 (`--source-table` ignored + unsafe charset; row-count project scope). Bandit is down to the 5 wontfix B110 sites: vetted sites were annotated with `# nosec` + reason (G-024). MLflow (G-020) was left for the owner, as instructed.
