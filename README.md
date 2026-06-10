# ISO-Robot

Monorepo for ISO Robot ERM / risk-discovery work: data assets, offline UI prototype, **FastAPI backend** ([`backend/`](backend/)), and **Vite + React** UI ([`frontend/`](frontend/)).

## Backend

See [`backend/README.md`](backend/README.md) for install, `.env`, and `uvicorn` commands.

**From repo root** (uses `.venv` or `venv` if present):

```bash
source .venv/bin/activate
./run-api.sh
```

**Or from `backend/`** (recommended):

```bash
cd backend
source ../.venv/bin/activate   # or ../venv
export PYTHONPATH=src
uvicorn iso_robot.main:app --reload --host 0.0.0.0 --port 8000
```

If you stay at the repo root without `cd backend`, set `PYTHONPATH=backend/src` (not `src` alone).

API base: `http://127.0.0.1:8000/api/v1` — OpenAPI at `/docs`.

## Frontend

See [`frontend/README.md`](frontend/README.md).

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). CORS allows this origin to the backend.

## High-level layout

```
ISO-Robot/
├── backend/                 # FastAPI app (`iso_robot`)
│   └── src/iso_robot/
├── frontend/                # React + Vite UI
├── data/
│   └── curated/             # `risk_library_seed.csv` (written when seeding the library)
├── all-docs/                # Optional PDF/HTML scan folder (default `DOCUMENTS_DIR`)
├── ISO ROBOT RISK POC.xlsx  # POC workbook (risk sources + risk table templates)
└── README.md
```

## Security

Do not commit `.env` or API keys. `.env` may live at the repo root or under `backend/` (see backend README).

## Azure (integration)

Control extraction (Document Intelligence + OpenAI JSON chat), issue classification, candidate risk synthesis, and library matching require configured Azure endpoints and keys. These calls were not integration-tested in CI without live credentials.
