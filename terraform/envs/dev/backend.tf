terraform {
  required_version = ">= 1.5.0"

  # Migrated 2026-06-06: state now lives in the shared garassino-op control plane.
  # Create the bucket once: gsutil mb -p garassino-op -l europe-west1 -b on
  # gs://garassino-op-tf-state/ (versioning enabled).
  backend "gcs" {
    bucket = "garassino-op-tf-state"
    prefix = "deepcab/envs/dev"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
