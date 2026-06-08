#!/usr/bin/env bash
# Build and run Mintlify docs in Docker. From repo root: ./docker-run-docs.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

export DOCS_PORT="${DOCS_PORT:-3005}"

docker compose up --build docs "$@"
