# Module: `_labels`

Trivial helper module that assembles the canonical deepCab label block:

```hcl
{
  env       = var.env
  managed   = "terraform"
  component = var.component
}
```

`extra_labels` (default `{}`) is merged in **first**, so the canonical three keys
always win on collision — preserving the historical semantics of every
`merge(var.labels, { env = ..., managed = "terraform", component = "..." })`
block that lived inline in every resource module.

## Why a module for three lines?

Because that same three-line `merge(...)` was duplicated across `storage`,
`secret_manager`, and (in spirit) every Cloud Run module. One source of truth
means: change the canonical schema once, every resource picks it up.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `env` | `string` | — | dev/staging/prod. Becomes the `env` label. |
| `component` | `string` | — | Component slug (e.g. `deepcab-platform`). Becomes the `component` label. |
| `extra_labels` | `map(string)` | `{}` | Caller-supplied labels merged underneath the canonical three. |

## Outputs

| Name | Description |
|---|---|
| `labels` | Final merged label map, ready to drop onto any GCP resource that accepts `labels`. |

## Usage

```hcl
module "labels" {
  source       = "../_labels"
  env          = var.env
  component    = "deepcab-platform"
  extra_labels = var.labels
}

resource "google_storage_bucket" "x" {
  # ...
  labels = module.labels.labels
}
```

## Why underscore-prefixed?

`_labels` sorts before all resource modules in `ls`, signalling "internal
helper, not a resource". The Terraform Registry naming convention for such
helpers (e.g. terraform-aws-modules) commonly uses the underscore prefix.
