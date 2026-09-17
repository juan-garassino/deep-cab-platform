# ----------------------------------------------------------------------------
# deepCab — STAGING environment composition
#
# Mid-tier. Private-IP Cloud SQL via VPC. DNS optional. No GKE.
# Budget target: ~$20-40/mo.
# ----------------------------------------------------------------------------

locals {
  env = "staging"

  common_labels = {
    env       = local.env
    managed   = "terraform"
    component = "deepcab-platform"
  }
}

module "gar" {
  source     = "../../modules/gar"
  project_id = var.project_id
  region     = var.region
  labels     = local.common_labels
}

module "storage" {
  source        = "../../modules/storage"
  project_id    = var.project_id
  region        = var.region
  env           = local.env
  force_destroy = false
  labels        = local.common_labels
}

module "wif" {
  source           = "../../modules/wif"
  project_id       = var.project_id
  project_number   = var.project_number
  gh_owner         = var.gh_owner
  gh_repo          = var.gh_api_repo
  platform_gh_repo = var.gh_platform_repo
  website_gh_repo  = var.gh_website_repo
  labels           = local.common_labels
}

module "secrets" {
  source           = "../../modules/secret_manager"
  project_id       = var.project_id
  region           = var.region
  env              = local.env
  runtime_sa_email = module.wif.runtime_sa_email
  labels           = local.common_labels
}

module "vpc" {
  source                = "../../modules/vpc"
  project_id            = var.project_id
  region                = var.region
  env                   = local.env
  enabled               = true
  subnet_cidr           = "10.40.0.0/20"
  private_services_cidr = "10.50.0.0/16"
  enable_nat            = true
}

module "cloud_sql" {
  source     = "../../modules/cloud_sql"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  tier                = "db-g1-small"
  deletion_protection = true
  use_private_ip      = true
  private_network     = module.vpc.network_self_link

  labels = local.common_labels

  depends_on = [module.vpc]
}

module "cloud_run_api" {
  source     = "../../modules/cloud_run_service"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  service_name          = "deepcab-api"
  component             = "cloud-run-api"
  image                 = var.api_image
  service_account_email = module.wif.runtime_sa_email

  cpu                   = "1"
  memory                = "1Gi"
  min_instances         = 0
  max_instances         = 4
  container_concurrency = 80
  container_port        = 8000
  allow_unauthenticated = true

  volumes = [
    {
      name                = "cloudsql"
      type                = "cloud_sql"
      cloud_sql_instances = [module.cloud_sql.connection_name]
    },
  ]

  volume_mounts = [
    { name = "cloudsql", mount_path = "/cloudsql" },
  ]

  env_vars = {
    APP_ENV             = "staging"
    PORT                = "8000"
    MLFLOW_TRACKING_URI = var.mlflow_tracking_uri
    MODEL_TARGET        = "gcs"
    GCP_PROJECT         = var.project_id
    REGISTRY_GCS_BUCKET = module.storage.models_bucket
  }

  secret_env_vars = {
    OPENAI_API_KEY     = "openai-api-key"
    DEEPCAB_API_KEY    = "deepcab-api-key"
    SLACK_WEBHOOK_URL  = "slack-webhook-url"
    MLFLOW_DB_PASSWORD = "mlflow-db-password"
  }

  labels = local.common_labels

  depends_on = [module.secrets, module.gar]
}

moved {
  from = module.cloud_run.google_cloud_run_v2_service.this
  to   = module.cloud_run_api.google_cloud_run_v2_service.this
}

moved {
  from = module.cloud_run.google_cloud_run_v2_service_iam_member.public
  to   = module.cloud_run_api.google_cloud_run_v2_service_iam_member.public
}

module "cloud_run_website" {
  source     = "../../modules/cloud_run_service"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  service_name          = "deepcab-website"
  component             = "cloud-run-website"
  image                 = var.website_image
  service_account_email = module.wif.runtime_sa_email

  cpu                   = "1"
  memory                = "256Mi"
  min_instances         = 1
  max_instances         = 4
  container_concurrency = 200
  timeout_seconds       = 30
  container_port        = 80
  allow_unauthenticated = true

  startup_probe_path                  = "/"
  liveness_probe_path                 = "/"
  startup_probe_initial_delay_seconds = 1
  startup_probe_failure_threshold     = 10
  liveness_probe_period_seconds       = 30

  labels = local.common_labels

  depends_on = [module.gar]
}

module "cloud_run_job" {
  source     = "../../modules/cloud_run_job"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  image                 = var.retrain_image
  service_account_email = module.wif.runtime_sa_email
  scheduler_sa_email    = module.wif.scheduler_sa_email

  cpu                  = "4"
  memory               = "8Gi"
  task_timeout_seconds = 3600

  args = [
    "-m",
    "deepCab.training.train",
    "backend=tf_mlp",
    "data=10k",
  ]

  cloudsql_instances = [module.cloud_sql.connection_name]

  env_vars = {
    APP_ENV             = "staging"
    MLFLOW_TRACKING_URI = var.mlflow_tracking_uri
    MODEL_TARGET        = "gcs"
    GCP_PROJECT         = var.project_id
    REGISTRY_GCS_BUCKET = module.storage.models_bucket
  }

  secret_env_vars = {
    MLFLOW_DB_PASSWORD = "mlflow-db-password"
  }

  labels = local.common_labels

  depends_on = [module.secrets]
}

module "scheduler" {
  source     = "../../modules/scheduler"
  project_id = var.project_id
  region     = var.region
  env        = local.env

  target_uri            = module.cloud_run_job.execute_uri
  service_account_email = module.wif.scheduler_sa_email
  paused                = false
}

module "dns" {
  source     = "../../modules/dns"
  project_id = var.project_id
  env        = local.env

  enabled     = var.dns_zone_name != ""
  zone_name   = var.dns_zone_name
  dns_name    = var.dns_name
  create_zone = false

  records = var.dns_zone_name == "" ? {} : {
    "api.staging" = {
      type    = "CNAME"
      ttl     = 300
      rrdatas = ["ghs.googlehosted.com."]
    }
  }
}

module "gke" {
  source     = "../../modules/gke"
  project_id = var.project_id
  region     = var.region
  env        = local.env
  enabled    = false
}

module "iam" {
  source     = "../../modules/iam"
  project_id = var.project_id
  env        = local.env
}
