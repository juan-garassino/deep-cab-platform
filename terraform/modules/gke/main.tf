# GKE module — gated behind var.enabled, default false.
#
# Minimal regional autopilot-adjacent cluster:
#   - regional control plane in var.region
#   - separately-managed node pool (no default-node-pool) so we can tune autoscaling
#   - workload identity enabled by default
#   - private nodes, public endpoint (override per env if needed)

locals {
  enabled = var.enabled
}

resource "google_container_cluster" "this" {
  count    = local.enabled ? 1 : 0
  project  = var.project_id
  name     = "${var.cluster_name}-${var.env}"
  location = var.region

  network    = var.network
  subnetwork = var.subnet

  remove_default_node_pool = true
  initial_node_count       = 1

  release_channel {
    channel = var.release_channel
  }

  workload_identity_config {
    workload_pool = var.enable_workload_identity ? "${var.project_id}.svc.id.goog" : null
  }

  networking_mode = "VPC_NATIVE"

  ip_allocation_policy {
    # Use auto-derived secondary ranges
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  # Closed by default (G-012): the control plane is reachable only from the
  # CIDRs passed in var.master_authorized_cidrs (e.g. your office / VPN).
  master_authorized_networks_config {
    dynamic "cidr_blocks" {
      for_each = var.master_authorized_cidrs
      content {
        display_name = cidr_blocks.value.name
        cidr_block   = cidr_blocks.value.cidr
      }
    }
  }

  resource_labels = merge(
    var.labels,
    {
      env       = var.env
      managed   = "terraform"
      component = "gke"
    }
  )

  deletion_protection = var.env == "prod"
}

resource "google_container_node_pool" "default" {
  count    = local.enabled ? 1 : 0
  project  = var.project_id
  name     = "default-pool"
  location = var.region
  cluster  = google_container_cluster.this[0].name

  autoscaling {
    min_node_count = var.min_node_count
    max_node_count = var.max_node_count
  }

  node_config {
    machine_type = var.node_machine_type
    disk_size_gb = 50
    disk_type    = "pd-standard"

    service_account = var.runtime_sa_email != "" ? var.runtime_sa_email : null
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]

    workload_metadata_config {
      mode = var.enable_workload_identity ? "GKE_METADATA" : "MODE_UNSPECIFIED"
    }

    shielded_instance_config {
      enable_secure_boot          = true
      enable_integrity_monitoring = true
    }

    labels = {
      env  = var.env
      pool = "default"
    }
  }

  management {
    auto_repair  = true
    auto_upgrade = true
  }
}
