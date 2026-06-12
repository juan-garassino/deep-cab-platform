# CONFIG — environment model

> **Pre-migration doc (2026-06-07):** GCP project `deepcab-dev` cold-deleted; canonical config is now `garassino-ml` / `europe-west1` (root `CLAUDE.md` § "GCP architecture"). Project IDs and regions below describe pre-migration state — body kept as historical narrative.

deepCab uses one environment variable, `DEEPCAB_ENV`, to switch every layer
between local development and the three GCP environments. This doc is the
canonical reference for that model.

## The four values

| `DEEPCAB_ENV` | Purpose | Cost when idle |
|---|---|---|
| `local` | docker-compose stack on your laptop. No GCP. | $0 |
| `dev` | `deepcab-dev` GCP project. Cheap, ephemeral. | ~$1/mo with showcase_down, ~$15/mo with showcase_up |
| `staging` | `deepcab-staging` GCP project (not yet provisioned). Pre-prod soak. | ~$30/mo |
| `prod` | `deepcab-prod` GCP project (not yet provisioned). User-facing. | ~$100+/mo |

## What `DEEPCAB_ENV` actually changes, layer by layer

| Layer | How it reads `DEEPCAB_ENV` | What changes |
|---|---|---|
| **001 api** (FastAPI) | `deepCab/schemas/settings.py` `_env_file()` returns `.env.<env>` | All Settings sub-classes (Data, Registry, GCP, MLflow, OBS, OpenAI) load from that file. MLflow URI, GCS bucket names, OTLP endpoint, etc., all flip. |
| **001 cli** (`deepcab` Typer) | Same `settings.py` | `uv run deepcab status` prints the env-resolved values. |
| **003 website** (Vite SPA) | Build-time only via `VITE_API_BASE_URL` build-arg | Each tagged release builds against one env's api URL. Re-tag to re-deploy. |
| **infra/compose/docker-compose.yml** | `DEEPCAB_ENV: ${DEEPCAB_ENV:-local}` | `local` is the default; override via `infra/compose/.env` (gitignored) or shell export. Mostly only `local` makes sense here. |
| **002 platform Terraform** | Selected via directory: `terraform/envs/<env>/` | Each env is its own composition. `make ENV=<env> plan/apply` scopes the work. |
| **002 deepcab-platform CLI** | `deepcab_platform/schemas/settings.py` (mirrors 001) | Every subcommand (`bootstrap`, `sync-gh`, `kuma seed`, `showcase up`) reads the env and routes to the right GCP project. |
| **CI / GitHub Actions** | Per-env variables (`GCP_WIF_PROVIDER_DEV` etc.) + workflow `env:` blocks | The `platform-apply.yml` matrix applies dev → staging → prod sequentially with manual approval gates. |

## Precedence (when conflicting values exist)

001 / 002 Python:
1. `DEEPCAB_ENV` env var
2. `APP_ENV` env var (legacy alias, still accepted)
3. Default = `dev` (legacy default, will move to `local` once Wave 1 lands)

Pydantic-settings then picks `.env.<env>` and overlays per-prefix env vars on top of file values:
- File values < process env values < explicit `Settings(...)` kwargs.

## Adding a new env

1. **001 api**: copy `.env.dev.sample` → `.env.<new-env>.sample`. Add `AppEnv.<NEW> = "new"` in `deepCab/schemas/enums.py`.
2. **002 platform Terraform**: copy `terraform/envs/dev/` → `terraform/envs/<new-env>/`. Update `terraform.tfvars` with the new project ID + number.
3. **002 platform CLI** (after Wave 3): add `PlatformEnv.<NEW>` in `deepcab_platform/schemas/enums.py`.
4. **GitHub Actions**: add `GCP_WIF_PROVIDER_<NEW>` + `GCP_TERRAFORM_SA_<NEW>` vars to the platform repo. Re-run `make sync_gh`.
5. **Bootstrap the GCP project**: `BILLING_ACCOUNT=… PROJECT_ID=deepcab-<new> ENV=<new> make bootstrap_gcp`. Then `make ENV=<new> apply`.

## Things that intentionally don't follow `DEEPCAB_ENV`

- **MLflow image version**: pinned in TF (`cloud_run_mlflow.image`), refreshed via `make mlflow_mirror` independent of env.
- **Uptime Kuma version**: pinned in `cloud_run_status` TF module.
- **gh repo names**: hardcoded as defaults (`deepCab`, `deepCab-platform`, `deepCab-website`) — overridable per env if you ever fork.

## Rotating secrets

Secret values aren't read from `.env.<env>` files — those only hold the
*identifiers* (which Cloud Run service uses which Secret Manager secret).
The values live in Secret Manager, populated either by Terraform
(`mlflow-db-password`, `kuma-admin-password`) or manually after the first
apply (`openai-api-key`, `deepcab-api-key`, `slack-webhook-url`).

To rotate one in-place:

```bash
echo "$NEW_VALUE" | uv run deepcab-platform secrets rotate <secret-id> \
  --from-stdin --project-id $(uv run deepcab-platform tf output --env dev | grep project_id | awk -F\" '{print $2}')
```

That command pushes a new version AND triggers a Cloud Run revision swap on
every service that consumes the secret (the mapping is in
`services/secrets.py::_default_consumers`). Without the revision swap, the
running container keeps reading the old value — Cloud Run binds secret env
vars at revision-creation time, not at request time.

## CI notifications (Slack + Telegram)

Every deploy/apply workflow fires notification steps per outcome
(starting / success / failure) to each configured channel. Both Slack and
Telegram run in parallel — set zero, one, or both of:

| Secret | What | How to get it |
| --- | --- | --- |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL. Discord works too — append `/slack` to a Discord webhook URL. | Slack app settings → Incoming Webhooks. |
| `TELEGRAM_BOT_TOKEN` | Bot token | Message **@BotFather** in Telegram → `/newbot` → copy the token. |
| `TELEGRAM_CHAT_ID` | Where the bot sends messages | Message your new bot once, then `curl https://api.telegram.org/bot<TOKEN>/getUpdates` and parse `result[0].message.chat.id`. |

Each step has `continue-on-error: true` and a `[ -z "$TG_BOT" ] && exit 0`
guard, so missing secrets just no-op — they never fail a deploy. Set both
sets and you get a Slack ping AND a Telegram ping for every event.

Push values into the 3 repos via `make sync_gh` after filling
`scripts/gh-secrets.env`.

## Things `DEEPCAB_ENV` does NOT replace

- `APP_ENV` is the legacy name. It still works. Don't remove it from existing `.env` files.
- The TF `var.env` in `terraform/envs/<env>/main.tf` is set per directory, not from `DEEPCAB_ENV` — they're conceptually the same but mechanically separate.

## See also

- `001-deepCab/CLAUDE.md` → "Environments" section
- `001-deepCab-api/CLAUDE.md` → "Required environment" section
- `002-deepCab-platform/docs/CLI.md` (Wave 5) — every `deepcab-platform` subcommand respects `DEEPCAB_ENV`
- `002-deepCab-platform/docs/DEPLOY-FROM-SCRATCH.md` — end-to-end bootstrap for any env
