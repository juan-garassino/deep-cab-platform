# ----------------------------------------------------------------------------
# deepCab — Shared env_config lookup
#
# Single source of truth for per-environment values that previously lived
# duplicated across envs/{dev,staging,prod}/main.tf. Each env now reads
# `module.env_config.cfg` and threads the right slice into each downstream
# module call.
#
# This module is pure data — no resources, no providers — so it does NOT
# require its own `terraform init -upgrade` cycle when env files change.
# It is invoked as a local-path module from each env's main.tf:
#
#   module "env_config" {
#     source = "../_shared"
#     env    = local.env
#   }
#
#   locals { cfg = module.env_config.cfg }
#
# To change a per-env knob (Cloud SQL tier, scheduler paused, IAM role
# list, etc.) edit `env_configs` below — never the env main.tf files.
# Differences that are *truly* per-env (project IDs, project numbers,
# DNS zone names) stay in terraform.tfvars / variables.tf since they
# are operator-supplied, not infra-shape decisions.
# ----------------------------------------------------------------------------

variable "env" {
  description = "Environment short name (dev|staging|prod)."
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of: dev, staging, prod."
  }
}

locals {
  env_configs = {
    # ------------------------------------------------------------------------
    # DEV — smallest tier; public-IP Cloud SQL; no VPC, DNS, GKE, budget.
    # ------------------------------------------------------------------------
    dev = {
      cloud_sql = {
        tier                = "db-f1-micro"
        disk_size_gb        = 10
        deletion_protection = false
        use_private_ip      = false
        backup_enabled      = true
        # No public 0.0.0.0/0 (G-013): add your own /32 here, or use the
        # Cloud SQL Auth Proxy (works with an empty list).
        authorized_networks = []
      }

      cloud_run_api = {
        cpu                   = "1"
        memory                = "512Mi"
        min_instances         = 0
        max_instances         = 2
        container_concurrency = 40
        timeout_seconds       = 60
      }

      cloud_run_website = {
        cpu                   = "1"
        memory                = "256Mi"
        min_instances         = 0
        max_instances         = 2
        container_concurrency = 200
      }

      cloud_run_mlflow = {
        cpu           = "1"
        memory        = "1Gi"
        min_instances = 0
        max_instances = 2
      }

      cloud_run_status = {
        cpu           = "1"
        memory        = "512Mi"
        min_instances = 0
        max_instances = 1
      }

      cloud_run_job = {
        cpu                  = "2"
        memory               = "4Gi"
        task_timeout_seconds = 1800
        data_size            = "1k"
      }

      scheduler = {
        paused = true
      }

      # Empty lists => the wif module falls back to its own broad defaults.
      wif = {
        deployer_project_roles  = []
        terraform_project_roles = []
      }

      vpc = {
        enabled               = false
        subnet_cidr           = ""
        private_services_cidr = ""
        enable_nat            = false
      }

      dns = {
        enabled = false
      }

      gke = {
        enabled = false
      }

      iam = {
        budget_alert_email = ""
        budget_amount_usd  = 0
        billing_account    = ""
      }

      storage = {
        force_destroy = true
      }
    }

    # ------------------------------------------------------------------------
    # STAGING — mid-tier; private-IP Cloud SQL via VPC; DNS optional; no GKE.
    # ------------------------------------------------------------------------
    staging = {
      cloud_sql = {
        tier                = "db-g1-small"
        disk_size_gb        = 10
        deletion_protection = true
        use_private_ip      = true
        backup_enabled      = true
        authorized_networks = []
      }

      cloud_run_api = {
        cpu                   = "1"
        memory                = "1Gi"
        min_instances         = 0
        max_instances         = 4
        container_concurrency = 80
        timeout_seconds       = 60
      }

      cloud_run_website = {
        cpu                   = "1"
        memory                = "256Mi"
        min_instances         = 1
        max_instances         = 4
        container_concurrency = 200
      }

      # Staging today routes API to an external MLflow via var.mlflow_tracking_uri;
      # the cloud_run_mlflow module isn't instantiated, but we keep the slice for
      # symmetry / future expansion.
      cloud_run_mlflow = {
        cpu           = "1"
        memory        = "1Gi"
        min_instances = 0
        max_instances = 2
      }

      cloud_run_status = {
        cpu           = "1"
        memory        = "512Mi"
        min_instances = 0
        max_instances = 1
      }

      cloud_run_job = {
        cpu                  = "4"
        memory               = "8Gi"
        task_timeout_seconds = 3600
        data_size            = "10k"
      }

      scheduler = {
        paused = false
      }

      wif = {
        deployer_project_roles  = []
        terraform_project_roles = []
      }

      vpc = {
        enabled               = true
        subnet_cidr           = "10.40.0.0/20"
        private_services_cidr = "10.50.0.0/16"
        enable_nat            = true
      }

      dns = {
        enabled = true
      }

      gke = {
        enabled = false
      }

      iam = {
        budget_alert_email = ""
        budget_amount_usd  = 0
        billing_account    = ""
      }

      storage = {
        force_destroy = false
      }
    }

    # ------------------------------------------------------------------------
    # PROD — highest tier; private-IP HA Cloud SQL; DNS; GKE toggleable;
    # tightened WIF role lists; budget alert.
    # ------------------------------------------------------------------------
    prod = {
      cloud_sql = {
        tier                = "db-custom-2-4096"
        disk_size_gb        = 50
        deletion_protection = true
        use_private_ip      = true
        backup_enabled      = true
        authorized_networks = []
      }

      cloud_run_api = {
        cpu                   = "2"
        memory                = "2Gi"
        min_instances         = 1
        max_instances         = 10
        container_concurrency = 80
        timeout_seconds       = 60
      }

      cloud_run_website = {
        cpu                   = "1"
        memory                = "512Mi"
        min_instances         = 2
        max_instances         = 10
        container_concurrency = 200
      }

      cloud_run_mlflow = {
        cpu           = "2"
        memory        = "2Gi"
        min_instances = 1
        max_instances = 4
      }

      cloud_run_status = {
        cpu           = "1"
        memory        = "512Mi"
        min_instances = 1
        max_instances = 2
      }

      cloud_run_job = {
        cpu                  = "4"
        memory               = "8Gi"
        task_timeout_seconds = 3600
        data_size            = "full"
      }

      scheduler = {
        paused = false
      }

      # Prod tightens both lists. No roles/editor anywhere.
      wif = {
        deployer_project_roles = [
          "roles/run.developer",
          "roles/artifactregistry.writer",
          "roles/iam.serviceAccountUser",
          "roles/storage.objectAdmin",
        ]
        terraform_project_roles = [
          "roles/run.admin",
          "roles/cloudsql.admin",
          "roles/storage.admin",
          "roles/secretmanager.admin",
          "roles/artifactregistry.admin",
          "roles/iam.workloadIdentityPoolAdmin",
          "roles/iam.serviceAccountAdmin",
          "roles/resourcemanager.projectIamAdmin",
          "roles/compute.networkAdmin",
          "roles/cloudscheduler.admin",
          "roles/container.admin",
        ]
      }

      vpc = {
        enabled               = true
        subnet_cidr           = "10.60.0.0/20"
        private_services_cidr = "10.70.0.0/16"
        enable_nat            = true
      }

      dns = {
        enabled = true
      }

      # GKE provisioned only when the operator flips var.enable_gke. The
      # `available = true` bit here marks "this env may run GKE" — the env
      # main.tf still gates on var.enable_gke for the actual on/off.
      gke = {
        enabled = true
      }

      iam = {
        # Budget defaults are surfaced through variables.tf so an operator
        # can override without editing this file.
        budget_alert_email = ""
        budget_amount_usd  = 200
        billing_account    = ""
      }

      storage = {
        force_destroy = false
      }
    }
  }
}

output "cfg" {
  description = "Resolved env_config slice for var.env."
  value       = local.env_configs[var.env]
}
