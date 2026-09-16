output "labels" {
  description = "Merged label map: {env, managed=\"terraform\", component} overlaid by extra_labels."
  value       = local.labels
}
