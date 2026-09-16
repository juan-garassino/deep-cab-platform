terraform {
  required_version = ">= 1.5.0"
  # No providers — this module is pure HCL (locals + outputs), no GCP resources.
}
