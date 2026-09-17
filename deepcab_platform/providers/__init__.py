"""Provider Protocols + Real / DryRun implementations.

Mirrors 001's `deepCab/api/providers.py`: every external system (gcloud CLI,
gh CLI, terraform CLI, HTTP API) is fronted by a `Protocol` + a `Real` impl
that actually executes + a `DryRun` impl that prints what would happen. Tests
and the CLI's --dry-run flag inject DryRun impls.
"""
