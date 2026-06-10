#!/usr/bin/env bash
# Build and run the backend in Docker. From repo root: ./docker-run.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  if [[ -f .env.docker.example ]]; then
    cp .env.docker.example .env
    echo "Created .env from .env.docker.example — edit Azure keys / JWT secret as needed."
  else
    touch .env
  fi
fi

mkdir -p backend/data all-docs

export RUN_SEED_DEMO="${RUN_SEED_DEMO:-true}"
export API_PORT="${API_PORT:-8000}"

docker compose up --build "$@"
