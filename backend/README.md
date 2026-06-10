# ISO Robot — backend

FastAPI service: document registry,jobs, and future Azure Document Intelligence / Azure OpenAI pipelines.

## Setup

```bash
cd backend
python3 -m venv ../venv   # or use existing repo-root venv
source ../venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `backend/.env`, or keep a single `.env` at the **repository root** (recommended if you already use it). Settings load `backend/.env` first, then repo-root `.env` (later file wins on duplicate keys).

## Run

From the `backend` directory (required so `PYTHONPATH=src` resolves to `backend/src`):

```bash
source ../.venv/bin/activate   # or ../venv
export PYTHONPATH=src
uvicorn iso_robot.main:app --reload --host 0.0.0.0 --port 8000
```

Or from the repo root: `./run-api.sh` (or `./backend/run.sh`).

Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Docker

Build and run from the **repository root** (same layout as local dev — SQLite and uploads live under `backend/data/`):

```bash
cp .env.docker.example .env   # optional; add Azure keys / JWT secret
./docker-run.sh               # first run seeds demo users (RUN_SEED_DEMO=true)
```

Or manually:

```bash
mkdir -p backend/data all-docs
docker compose up --build
```

API: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Health: `GET /health`.

**VM deploy:** copy the whole repo (including `backend/data/` if you already have a DB), install Docker, create `.env`, then `docker compose up -d --build`. Data persists in mounted volumes (`backend/data`, `data`, `all-docs`).

| Variable | Docker default |
|----------|----------------|
| `DATABASE_PATH` | `/app/backend/data/db.sqlite` |
| `DOCUMENTS_DIR` | `/app/all-docs` |
| `RUN_SEED_DEMO` | `false` (`true` in `./docker-run.sh` for first boot) |
| `API_PORT` | host port mapped to container `8000` |

Notable **API v1** routes:

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/summary` | Dashboard counts |
| POST | `/documents/scan` | Register PDFs/HTML from disk |
| GET | `/controls` | List controls (`document_id` filter) |
| POST | `/controls/extract` | Queue Document Intelligence + OpenAI extraction job |
| POST | `/issues/seed-from-poc` | Load Risk Sources sheet into DB + synthetic issues |
| GET | `/issues` | List issues (`include_classification`) |
| POST | `/issues/classify` | Queue Azure OpenAI classification job |
| GET | `/issues/{id}/classification` | Latest classification JSON |
| POST | `/risk-library/seed-from-poc` | Seed library + write `data/curated/risk_library_seed.csv` |
| GET | `/risk-library` | List catalog |
| POST | `/risk-discovery/run` | Queue BM25 + LLM discovery + matching job |
| GET | `/candidate-risks` | Candidates with latest match metadata |
| GET | `/discovery-export` | Full JSON export |
| POST | `/jobs` | Create job (`extract_controls`, `classify_issues`, `risk_discovery`, …) |

## Defaults

| Variable | Default |
|----------|---------|
| `DATABASE_PATH` | `<backend>/data/db.sqlite` |
| `DOCUMENTS_DIR` | `<repo>/all-docs` |

Override with env or `.env` when needed.

## Layout

| Path | Role |
|------|------|
| `src/iso_robot/` | Application package |
| `src/iso_robot/handlers/` | HTTP handlers |
| `src/iso_robot/domain/` | Business logic |
| `src/iso_robot/repositories/` | SQLite access |
| `src/iso_robot/integrations/` | Azure clients |
| `src/iso_robot/helpers/` | Utilities |
| `src/iso_robot/config/` | Settings |
