#!/usr/bin/env bash
# Start the FastAPI backend. Run from repo root: ./run-api.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/backend"

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
elif [[ -f "$ROOT/venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/venv/bin/activate"
fi

export PYTHONPATH=src
exec uvicorn iso_robot.main:app --reload --host 0.0.0.0 --port "${PORT:-8000}" "$@"
