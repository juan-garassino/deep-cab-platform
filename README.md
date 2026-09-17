# deepCab-platform

> **GCP migration note (2026-06-07):** Live GCP project `deepcab-dev` was cold-deleted. This stack now targets **`garassino-ml`** (region **`europe-west1`**) in show-and-destroy mode under the €25/mo workspace cost cap. Terraform state moved to `gs://garassino-op-tf-state/deepcab/`. The `dev` env is the only funded tier; `staging` / `prod` env directories are marked DEPRECATED and kept as reference. Refs to `deepcab-dev` / `us-central1` elsewhere in this README and `docs/` describe **pre-migration state** — canonical config in workspace root `CLAUDE.md` § "GCP architecture".

GCP infrastructure-as-code for the deepCab learning project. Real Terraform, real CI,
multi-env (dev / staging / prod). Sibling repo to [`deepCab`](https://github.com/juan-garassino/deepCab)
(the API). The split:

| Repo | Owns |
|---|---|
| `deepCab` | source code + Dockerfile + image build + `gcloud run services update --image=...` |
| `deepCab-platform` *(this repo)* | every GCP resource — service shape, IAM, networking, storage, secrets, scheduler, … |

The static landing page (`index.html`, `CNAME`, `images/`, `script.js`, `style.css`)
is also published from this repo via GitHub Pages, but it is **not** the focus.
Platform content lives under `terraform/`, `cloud-manifests/`, `docs/`, `.github/`.

---

## What's here

```
.
├── index.html, CNAME, images/, script.js, style.css   # GitHub Pages landing
│
├── deepcab_platform/           # Python CLI (Wave 3) — mirrors 001's deepCab/{cli,services,providers,schemas}
│   ├── cli/                    #   8 Typer subcommands (bootstrap, sync-gh, mlflow, showcase, kuma, secrets, tf, status)
│   ├── services/               #   7 @dataclass services with provider DI
│   ├── providers/              #   5 Protocols × {Real, DryRun} impls (gcloud, gh, terraform, http, kuma) + shared _subprocess helper
│   ├── schemas/                #   Pydantic models + str-Enums + pydantic-settings
│   └── deps.py                 #   wires providers → services → cli
│
├── terraform/                  # Layered Terraform (modules + per-env composition)
│   ├── modules/                #   13 reusable modules (Wave 2: 4 cloud_run_* → cloud_run_service, _labels extracted)
│   ├── envs/{dev,staging,prod} #   per-env wiring + tfvars
│   └── README.md
│
├── cloud-manifests/            # Declarative side-cars + legacy YAML
│   ├── kuma/                   #   Wave 4 — Uptime Kuma seed config (monitors.yaml, validated by KumaSeedConfig)
│   ├── mlflow/                 #   Cloud Build config for the MLflow image mirror
│   ├── cloud-run/              #   legacy YAML preserved for reference / diff
│   ├── cloud-run-jobs/
│   ├── scheduler/
│   ├── gke/
│   └── workload-identity/
│
├── scripts/                    # Bash shims preserved for backwards-compat (sync-gh-secrets.sh, bootstrap-gcp.sh)
│
├── .github/workflows/
│   ├── platform-plan.yml       # PR → `terraform plan` per env → PR comment
│   └── platform-apply.yml      # main → apply dev → staging → prod (gated)
│
├── docs/
│   ├── ARCHITECTURE.md         # diagrams, cross-repo split, CLI layer, module consolidation
│   ├── CLI.md                  # `deepcab-platform` subcommand reference (Wave 3)
│   ├── CONFIG.md               # DEEPCAB_ENV model (Wave 3)
│   ├── ENVIRONMENTS.md         # per-env table (sizes, URLs, who can deploy)
│   ├── COSTS.md                # monthly cost back-of-napkin per env
│   ├── DEPLOY-FROM-SCRATCH.md  # end-to-end bootstrap walkthrough
│   └── RUNBOOK.md              # day-2 ops (secret rotation, drift, status-page monitors)
│
├── pyproject.toml              # uv-managed Python package (Typer + Pydantic)
└── Makefile                    # env-scoped wrappers (plan / apply / fmt / validate / lint / CLI shortcuts)
```

## 5-minute quickstart

Prerequisites: `terraform`, `gcloud`, `gh`, `uv` installed; you own a GCP project and a billing account.

```bash
# 1. Clone the repo + install the CLI
git clone https://github.com/juan-garassino/deepCab-platform.git
cd deepCab-platform
uv sync --extra dev                                     # installs deepcab-platform Typer CLI

# 2. Local sanity (no GCP access needed)
make fmt                                                # terraform fmt -recursive
make validate                                           # init -backend=false + validate, per env
uv run deepcab-platform --help                          # see all subcommands

# 3. Bootstrap your first env (full walkthrough in docs/DEPLOY-FROM-SCRATCH.md)
uv run deepcab-platform bootstrap \
  --env dev \
  --billing-account 01B30C-8DE544-29E214 \
  --project-id deepcab-dev                              # idempotent; add --dry-run to preview

# 4. Push GitHub Actions vars + secrets to all 3 repos
uv run deepcab-platform sync-gh

# 5. First terraform apply (auto-init under the hood)
uv run deepcab-platform tf apply --env dev

# 6. Populate secrets (TF declares containers, NOT values)
#    Use `secrets rotate` so the consuming Cloud Run services get a new
#    revision automatically. Bare `gcloud secrets versions add` works too
#    but you'd then have to bump every service by hand.
echo "https://hooks.slack.com/..."  | uv run deepcab-platform secrets rotate slack-webhook-url --from-stdin --project-id deepcab-dev
echo "sk-..."                        | uv run deepcab-platform secrets rotate openai-api-key   --from-stdin --project-id deepcab-dev

# 7. Pre-seed the Uptime Kuma status page from cloud-manifests/kuma/monitors.yaml
export KUMA_BASE_URL=$(uv run deepcab-platform tf output --env dev | grep status_page_url | awk -F\" '{print $2}')
export KUMA_ADMIN_PASSWORD=$(gcloud secrets versions access latest --secret=kuma-admin-password)
uv run deepcab-platform kuma seed

# 8. Trigger the first image build from 001-deepCab-api (tag a release)

# 9. Hit it
#    Note: /healthz is intercepted by Google Frontend on Cloud Run; use
#    /readyz for external probes. /docs and / also reach the container.
URL=$(uv run deepcab-platform tf output --env dev | grep api_service_url | awk -F\" '{print $2}')
curl -fsS ${URL}/readyz
```

## Layered Terraform — how it composes

```
envs/dev/main.tf   ──┐
envs/staging/.../   ─┼──>   modules/{_labels, gar, storage, wif, secret_manager, cloud_sql,
envs/prod/.../     ──┘                vpc, cloud_run_service, cloud_run_job,
                                      scheduler, gke, dns, iam}
```

`cloud_run_service` (Wave 2 consolidation) is instantiated once per workload
(api / website / mlflow / status), replacing four specialized modules.
`_labels` (Wave 2 extraction) is a shared helper consumed by `storage`,
`secret_manager`, and future modules.

Each `envs/<env>/` composes the same set of modules with env-specific knobs.
There is no DRY tax — repetition makes diffs obvious during code review.

See `terraform/README.md` for the module reference table and `docs/ARCHITECTURE.md`
for the dependency graph.

## How the cross-repo split works

```
┌──────────────────────────┐
│ deepCab (001) — API repo │
│                          │
│  push v0.1.0 tag         │
│       │                  │
│       ▼                  │
│  docker build + push     │   ┌────────────────────────────────────┐
│  to GAR                  │   │ deepCab-platform (002) — THIS REPO │
│       │                  │   │                                    │
│       ▼                  │   │  TF defines the Cloud Run service  │
│  gcloud run services     │   │  spec (CPU/mem/scale/env/IAM)      │
│  update --image=…        │◀──┤  TF defines the GAR repo, IAM, ... │
│       │                  │   │                                    │
│       ▼                  │   │  Image updates from 001 do NOT     │
│  service rolls forward   │   │  trigger TF drift                  │
└──────────────────────────┘   │  (`lifecycle.ignore_changes`)      │
                               └────────────────────────────────────┘
```

Concretely: `terraform/modules/cloud_run_service/main.tf` has

```hcl
lifecycle {
  ignore_changes = [
    template[0].containers[0].image,
    client,
    client_version,
  ]
}
```

so TF owns the spec and 001 owns the image, with no fight.

## CI workflows

| Workflow | Trigger | Effect |
|---|---|---|
| `platform-plan.yml` | PR touching `terraform/**` | Matrix over [dev, staging, prod] — `terraform plan` → PR comment |
| `platform-apply.yml` | push to `main` touching `terraform/**` (or manual) | Sequential apply dev → staging → prod with `environment:` approval gates + Slack notify |

Both auth via Workload Identity Federation (zero JSON keys).

## Local development

The Terraform tree assumes you have `terraform >= 1.5` and a Google Cloud SDK
authenticated as a project owner. For everything else (running the API,
docker-compose, MLflow locally) you want the **001 repo**, not this one.

## Pointers

- `docs/DEPLOY-FROM-SCRATCH.md` — end-to-end first-bootstrap walkthrough
- `docs/CLI.md` — `deepcab-platform` subcommand reference (Wave 3)
- `docs/CONFIG.md` — `DEEPCAB_ENV` environment model
- `docs/RUNBOOK.md` — day-2 ops: secret rotation, drift recovery, status-page monitors
- `docs/ARCHITECTURE.md` — cross-repo split + CLI layer + module consolidation
- `docs/ENVIRONMENTS.md` — per-env table (sizes, URLs, deploy permissions)
- `docs/COSTS.md` — back-of-napkin monthly cost estimates
- `terraform/README.md` — module reference

## License

Same as the parent project: MIT (or as specified in the API repo).
