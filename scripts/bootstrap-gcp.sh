#!/usr/bin/env bash
# Thin wrapper around the Python CLI. The real logic lives in
# deepcab_platform/services/bootstrap.py (Pydantic-typed, idempotent, with
# DryRun providers for testing).
#
# Kept for shell-only callers. New scripts should call:
#   uv run deepcab-platform bootstrap --env <env> --billing-account <id> --project-id <id>
exec uv run deepcab-platform bootstrap \
  --env "${ENV:-dev}" \
  --billing-account "${BILLING_ACCOUNT:?BILLING_ACCOUNT required}" \
  --project-id "${PROJECT_ID:?PROJECT_ID required}" \
  "$@"
