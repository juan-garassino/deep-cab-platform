#!/usr/bin/env bash
# Thin wrapper. Logic in deepcab_platform/services/sync_gh.py.
exec uv run deepcab-platform sync-gh "$@"
