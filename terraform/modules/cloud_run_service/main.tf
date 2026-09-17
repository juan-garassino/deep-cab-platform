# Generic Cloud Run v2 service.
#
# Consolidates the previous deepcab-api, deepcab-website, deepcab-mlflow, and
# deepcab-status modules into one. Each caller passes the variant-specific
# image, env, command/args, and volumes.
#
# Cross-repo contract (api + website):
#   001/003 CI runs `gcloud run services update --image=...` to swap the
#   container image; it never replaces the spec. That means
#   `lifecycle.ignore_changes` MUST cover the container image — otherwise TF
#   would revert every CI image push.
#
# Mlflow + status have no CI image swap; image is updated in-place via TF.
# The ignore_changes on the image is still safe for them (it just means the
# image is only changed when the value in TF changes, which is true anyway).

locals {
  service_labels = merge(
    var.labels,
    {
      env       = var.env
      managed   = "terraform"
      component = var.component
    }
  )
}

resource "google_cloud_run_v2_service" "this" {
  project  = var.project_id
  name     = var.service_name
  location = var.region
  ingress  = var.ingress
  labels   = local.service_labels

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    max_instance_request_concurrency = var.container_concurrency
    timeout                          = "${var.timeout_seconds}s"

    dynamic "volumes" {
      for_each = var.volumes
      content {
        name = volumes.value.name

        dynamic "cloud_sql_instance" {
          for_each = volumes.value.type == "cloud_sql" ? [1] : []
          content {
            instances = volumes.value.cloud_sql_instances
          }
        }

        dynamic "gcs" {
          for_each = volumes.value.type == "gcs" ? [1] : []
          content {
            bucket    = volumes.value.gcs_bucket
            read_only = volumes.value.gcs_read_only
          }
        }
      }
    }

    containers {
      image   = var.image
      command = var.command
      args    = var.args

      ports {
        name           = "http1"
        container_port = var.container_port
      }

      resources {
        limits = {
          cpu    = var.cpu
          memory = var.memory
        }
        cpu_idle          = var.min_instances == 0
        startup_cpu_boost = true
      }

      dynamic "env" {
        for_each = var.env_vars
        content {
          name  = env.key
          value = env.value
        }
      }

      dynamic "env" {
        for_each = var.secret_env_vars
        content {
          name = env.key
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }

      dynamic "volume_mounts" {
        for_each = var.volume_mounts
        content {
          name       = volume_mounts.value.name
          mount_path = volume_mounts.value.mount_path
        }
      }

      startup_probe {
        http_get {
          path = var.startup_probe_path
          port = var.container_port
        }
        initial_delay_seconds = var.startup_probe_initial_delay_seconds
        period_seconds        = var.startup_probe_period_seconds
        failure_threshold     = var.startup_probe_failure_threshold
        timeout_seconds       = var.startup_probe_timeout_seconds
      }

      liveness_probe {
        http_get {
          path = var.liveness_probe_path
          port = var.container_port
        }
        period_seconds    = var.liveness_probe_period_seconds
        failure_threshold = var.liveness_probe_failure_threshold
        timeout_seconds   = var.liveness_probe_timeout_seconds
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  lifecycle {
    # CI updates the image via `gcloud run services update --image=...` for
    # api+website. Ignoring here keeps TF from reverting that on next plan.
    # Safe no-op for mlflow/status (image only changes when TF value changes).
    ignore_changes = [
      template[0].containers[0].image,
      client,
      client_version,
    ]
  }
}

# Allow unauthenticated invocations when desired (toggle per env).
resource "google_cloud_run_v2_service_iam_member" "public" {
  count    = var.allow_unauthenticated ? 1 : 0
  project  = var.project_id
  location = google_cloud_run_v2_service.this.location
  name     = google_cloud_run_v2_service.this.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
