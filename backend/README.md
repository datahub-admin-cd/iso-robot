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
| POST | `/chatbot/query` | **SSE** chat over the caller's org knowledge (events: `retrieval` → `message` → `done`/`error`) |
| POST | `/chatbot/reindex` | Queue a full Milvus reindex for the caller's org (admins may target any org) |
| GET | `/chatbot/status` | Milvus/embedding readiness + the org's indexed chunk count |

## Chatbot & vector search (Milvus)

The chatbot answers questions **only** from the logged-in user's organisation data
(`client_org_id` from the JWT), using Retrieval-Augmented Generation over a
[Milvus](https://milvus.io) vector index. The DB stays the source of truth; Milvus
is a per-org read index kept in sync by the **Indexing Service**
(`domain/indexing_service.py`), which is called after each successful write and via
the `reindex` backfill job.

Layering mirrors the rest of the app: `routers/v1.py` → `handlers/chatbot.py` →
`domain/{retrieval,chat,indexing,embedding}_service.py` →
`repositories/vector_repository.py` → `integrations/milvus_client.py`.

**Tenant isolation:** every Milvus search is pinned to `client_org_id ==` the
caller's org (a Milvus partition key), so one org can never see another's chunks.

**Graceful degradation:** if `MILVUS_URI` is unreachable or the embedding
deployment is unset, indexing becomes a no-op and chat returns a "no information"
answer — the rest of the API keeps working.

Required configuration:

| Variable | Default | Purpose |
|----------|---------|---------|
| `MILVUS_URI` | `http://localhost:19530` (compose: `http://milvus-standalone:19530`) | Milvus gRPC endpoint |
| `MILVUS_TOKEN` | _(empty)_ | Auth token for managed/secured Milvus (e.g. Zilliz Cloud) |
| `MILVUS_DB_NAME` | `default` | Milvus database |
| `MILVUS_COLLECTION` | `iso_robot_knowledge` | Collection holding all org chunks |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | _(empty, **required for chat**)_ | Azure embedding deployment, e.g. `text-embedding-3-small` |
| `AZURE_OPENAI_EMBEDDING_DIM` | `1536` | Embedding dim (must match deployment + collection) |
| `CHATBOT_TOP_K` | `8` | Chunks retrieved per question |
| `CHATBOT_MAX_CONTEXT_CHARS` | `12000` | Max context characters sent to the chat model |

Chat completions reuse the existing `AZURE_OPENAI_*` deployment (`stream=True`).

**Consuming the SSE stream** (native `EventSource` cannot send an `Authorization`
header, so use `fetch`):

```js
const res = await fetch("/api/v1/chatbot/query", {
  method: "POST",
  headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
  body: JSON.stringify({ question: "What are my highest rated risks?" }),
});
const reader = res.body.getReader();
// parse `event:`/`data:` frames: retrieval (sources) → message (deltas) → done (citations)
```

First seed the index after data exists: `POST /api/v1/chatbot/reindex`, then poll
`GET /api/v1/jobs/{job_id}` until completed.

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
