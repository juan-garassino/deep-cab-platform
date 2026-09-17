# Module: `scheduler`

Cloud Scheduler HTTP job that fires the `cloud_run_job` retrain on a cron. Uses OAuth-token auth against the Cloud Run Job's `:run` endpoint; the SA used must already hold `roles/run.invoker` on the target Job (the `cloud_run_job` module grants this automatically when given the scheduler SA email).

Replaces `001/infra/gcp/scheduler/bootstrap.sh`.

## Cross-repo contract

None directly. The scheduler is purely an internal-to-platform timer. The job it fires is the same image that 001-deepCab-api CI built and pushed.

## Inputs (key)

| Name | Type | Default | Description |
| --- | --- | --- | --- |
| `project_id` | `string` | — | GCP project ID. |
| `region` | `string` | — | Region — typically same as the target Job. |
| `env` | `string` | — | Environment short name. |
| `target_uri` | `string` | — | HTTP URI to call — typically `module.cloud_run_job.execute_uri`. |
| `service_account_email` | `string` | — | Scheduler SA — mints the OAuth token. |
| `schedule_name` | `string` | `deepcab-retrain-daily` | Cloud Scheduler job name. |
| `cron_schedule` | `string` | `0 2 * * *` | Cron expression. |
| `time_zone` | `string` | `Etc/UTC` | IANA timezone. |
| `attempt_deadline` | `string` | `1800s` | Per-attempt deadline. |
| `retry_count` | `number` | `0` | Scheduler retries (on top of Job's own `max_retries`). |
| `paused` | `bool` | `false` | If true, the schedule is created but paused (dev default). |

## Outputs

| Name | Description |
| --- | --- |
| `schedule_name` | Cloud Scheduler job name. |
| `schedule_id` | Full resource ID of the schedule. |
| `next_run_estimate` | Cron expression — actual next-run timestamp must be queried via API. |

## Example usage

```hcl
module "scheduler" {
  source     = "../../modules/scheduler"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  target_uri            = module.cloud_run_job.execute_uri
  service_account_email = module.wif.scheduler_sa_email
  paused                = true   # dev — fire manually only
}
```

## Consumed by

- `terraform/envs/dev/main.tf` — paused; fire manually via `gcloud scheduler jobs run`.
- `terraform/envs/staging/main.tf` — active.
- `terraform/envs/prod/main.tf` — active; 02:00 UTC daily.
