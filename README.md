# VISENTRA

> **SIH26228 — "From Data to Decision, Proving AI Integrity"**

VISENTRA is a computer-vision AI assurance platform that verifies the integrity of the **data, model, and predictions** in a CV pipeline, and produces cryptographic evidence when something looks wrong.

The core UI is a live **lineage graph** — `Contributor → Dataset → Model → Inference → Assurance` — not a conventional dashboard.

---

## What it does

| Capability | Status |
|---|---|
| Dataset SHA-256 fingerprinting + versioning | ✅ Phase 0 |
| Model hash registration + tamper detection | ✅ Phase 1 |
| Black-box backdoor trigger-consistency scan | ✅ Phase 2 |
| Inference hash binding + evidence record | ✅ Phase 3 |
| Near-duplicate + OOD dataset screening | ✅ Phase 4 |
| Assurance report (0–100 score + limitations) | ✅ Phase 5 |
| Live WebSocket status propagation in graph | ✅ Phase 1+ |

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | React + TypeScript + Vite, React Flow, visx/D3 |
| Backend | Python + FastAPI + Pydantic, WebSocket |
| ML/CV | PyTorch, ONNXRuntime, OpenCV, scikit-learn, imagehash |
| Database | PostgreSQL + SQLAlchemy + Alembic |
| Storage | Local filesystem, content-addressed by SHA-256 |

---

## Project structure

```
visentra/
├── frontend/          # React + TypeScript + Vite app
│   └── src/
│       ├── graph/         # lineage graph (React Flow)
│       ├── inspector/     # dataset inspector
│       ├── interrogation/ # model interrogation / backdoor bench
│       ├── evidence/      # inference evidence record
│       ├── report/        # assurance report + export
│       └── shared/        # theme, api client, websocket hook
├── backend/           # FastAPI app
│   ├── api/           # routers
│   ├── assurance/     # data / model / inference checks
│   ├── db/            # SQLAlchemy models + Alembic migrations
│   ├── sandbox/       # isolated model execution subprocess
│   └── main.py
├── docs/
│   └── assurance-report-template.md
├── infra/
│   └── docker-compose.yml
└── VISENTRA_Implementation_Plan.md
```

---

## Getting started

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
# copy .env.example → .env and fill in DB URL
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Database

```bash
cd backend
alembic upgrade head
```

---

## Implementation plan

See [`VISENTRA_Implementation_Plan.md`](./VISENTRA_Implementation_Plan.md) for the full build roadmap (phases 0–5).

---

## License

MIT
