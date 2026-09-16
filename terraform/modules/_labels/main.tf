# Dead-simple label assembler — single source of truth for the
# `{env, managed, component}` block that every other module used to inline as:
#
#   locals {
#     foo_labels = merge(var.labels, { env = var.env, managed = "terraform", component = "..." })
#   }
#
# No conditional logic, no data sources, no provider. Pure HCL.

locals {
  labels = merge(
    var.extra_labels,
    {
      env       = var.env
      managed   = "terraform"
      component = var.component
    },
  )
}
