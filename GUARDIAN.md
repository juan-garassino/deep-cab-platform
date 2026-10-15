# GUARDIAN

Automated security and bug sweep for `deep-cab-platform`. It runs on branch `claude/guardian`.
Every 4th run is a meta-review run (count the entries under **Log**). The next one is run 4.

## Checks

| Area | Command / rule |
|---|---|
| Deps (PyPI) | `uv export --frozen --no-hashes --all-extras --no-emit-project > req.txt && pip-audit -r req.txt --no-deps --disable-pip` |
| Deps (OSV) | `osv-scanner -r .`: **did not run** (osv.dev API returned 403 from the sandbox) |
| Code | `bandit -r deepcab_platform -q` |
| Code (grep) | `eval(`, `exec(`, `pickle`, `yaml.load`, `shell=True`, `os.system`, `verify=False`, `0.0.0.0`, SQL built with f-strings or format, values interpolated into the rendered VM startup script |
| Secrets | `gitleaks detect --source . --redact -v` (full history), `gitleaks detect --no-git --redact`, `detect-secrets scan --all-files`, each hit triaged by hand |
| Actions | Actions pinned to a SHA? `permissions:` minimal? Is `${{ github.event.* }}` interpolated into `run:`? Do the step `if:` conditions work? |
| Docker | No Dockerfiles in the repo |
| Terraform | Manual review of `0.0.0.0/0`, `allUsers` / `allow_unauthenticated`, and secrets in `secret_env_vars` |
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
| G-011 | med | Telegram bot token rendered in plaintext into the VM startup-script metadata | deepcab_platform/services/train.py, cloud-manifests/train/startup.sh.tmpl | open | 2026-10-15 |
| G-012 | med | GKE master authorized networks set to `0.0.0.0/0` | terraform/modules/gke/main.tf | open | 2026-10-15 |
| G-013 | low | dev `cloud_sql.authorized_networks` set to `0.0.0.0/0` (module not used in dev today) | terraform/envs/_shared/env_config.tf | open | 2026-10-15 |
| G-014 | low | secret-scan hit, see the URGENT note below | n/a | open | 2026-10-15 |
| G-015 | low | `platform-plan` "Skip if dispatch" step `exit 0` does not skip the steps after it | .github/workflows/platform-plan.yml | open | 2026-10-15 |
| G-016 | low | MLflow container runs `pip install psycopg2-binary` unpinned at every boot | terraform/envs/dev/main.tf | open | 2026-10-15 |
| G-017 | low | mypy: 3 errors (missing yaml / uptime_kuma stubs, pydantic Annotated default) | various | open | 2026-10-15 |
| G-018 | low | bandit B110 try/except/pass (5 sites; best-effort probes on purpose) | services/bootstrap.py, providers/kuma.py | wontfix | 2026-10-15 |

URGENT: possible credential exposure, see the owner's private run summary.

Triaged as false positives: the gitleaks `hashicorp-tf-password` hits and the detect-secrets "Secret Keyword" hits in `terraform/**`. They are Secret Manager secret *names* or references, not values. The base64 hits in `index.html` are SRI hashes.

## Metrics

| Metric | Before | After |
|---|---|---|
| Open vulns crit/high/med/low | 0 / 0 / 6 / 7 | 0 / 0 / 3 / 4 (+1 wontfix) |
| Known-vulnerable deps (pip-audit) | 4 advisories in 2 pkgs | 0 |
| Bugs open | 3 (G-005, G-008, G-015) | 2 (G-008, G-015) |
| Failing tests | 0 | 0 |
| Test count | 7 | 21 |
| Coverage (line) | 18% | 26% |
| ruff errors | 1 | 0 |
| mypy errors | 3 | 3 |

## Backlog (prioritized)

0. G-006, G-007, G-008 (workflow edits): the guardian's token lacks the GitHub `workflow` scope, so it cannot push changes under `.github/workflows/`. The owner should apply these edits by hand:
   - pin `actions/checkout@11d5960a326750d5838078e36cf38b85af677262` (v4), `hashicorp/setup-terraform@b9cd54a3c349d3f38e8881555d616ced269862dd` (v3), `google-github-actions/auth@c200f3691d83b41bf9bbd8638997a462592937ed` (v2), `actions/github-script@f28e40c7f34bde8b3046d885e986cb6290c5673b` (v7);
   - in `platform-apply.yml`, replace `if: success()/failure() && env.SLACK_WEBHOOK_URL != ''` with `if: success()/failure()` + `continue-on-error: true` and start each `run:` with `[ -z "$SLACK_WEBHOOK_URL" ] && exit 0`;
   - in `platform-plan.yml`, pass `github.event.inputs.env` / `matrix.env` to the skip step through `env:` instead of `${{ }}` in `run:`.
1. G-011: stop embedding `TELEGRAM_BOT_TOKEN` in instance metadata. Have the startup script read it from Secret Manager with the VM's service account.
2. G-012: restrict GKE `master_authorized_networks` to known CIDRs, or use a private endpoint.
3. G-014: owner action. See the private summary.
4. G-015: make the dispatch-skip work by gating each later step with `if:` or a step output.
5. G-016: bake `psycopg2-binary` into the mirrored MLflow image with a pinned version. Also check the MLflow `v2.16.2` image against current advisories.
6. G-013: drop the `0.0.0.0/0` Cloud SQL authorized network from the dev config.
7. G-017: add `types-PyYAML` to dev deps and the pydantic mypy plugin, then add mypy to CI.
8. There is no CI that runs pytest or ruff. Add a small workflow.

## Learnings

- Values rendered into `startup.sh.tmpl` through `string.Template` are spliced into a root bash script. Only `extra_env` was protected (`shlex.quote`). Every other user-controlled field needs a strict pattern at the pydantic boundary.
- In GitHub Actions, a step's own `env:` is not available in that step's `if:`. Conditions like that silently become false.
- `uv lock --upgrade-package` also bumped the lockfile format (revision 1 to 3), which makes the diff large. The package changes are only pydantic-settings and urllib3.

Ideas for future checks:
1. Add a grep rule that flags every `string.Template` placeholder fed from CLI or env input that lacks a validator.
2. Run actionlint / zizmor over `.github/workflows` to catch dead `if:` conditions and injection.
3. Run tfsec / checkov over `terraform/` for open CIDRs, public IAM, and missing deletion protection.

## Log

- Run 1 (2026-10-15): First sweep. Fixed 2 vulnerable deps, 2 input-validation injection vectors, 1 bug (sync-gh KeyError), `.gitignore` for env files, and 1 lint error. Added 14 tests. The workflow fixes (G-006/7/8) were written but could not be pushed (token lacks `workflow` scope), so they are listed in the Backlog for the owner. 10 items remain open. osv-scanner was unavailable (403).
