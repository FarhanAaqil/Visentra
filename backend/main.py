import sys
from pathlib import Path
from contextlib import asynccontextmanager

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from sqlalchemy import select
from backend.db.session import engine, AsyncSessionLocal
from backend.db.models import Base, Contributor
from backend.api.contributors import router as contributors_router
from backend.api.datasets import router as datasets_router
from backend.api.models import router as models_router
from backend.api.chain import router as chain_router
from backend.api.demo import router as demo_router
from backend.api.backdoor import router as backdoor_router
from backend.api.inference import router as inference_router
from backend.api.dataset_assurance import router as dataset_assurance_router
from backend.api.report import router as report_router
from backend.api.ws import router as ws_router

import logging
logger = logging.getLogger("uvicorn.error")

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Automatically seed demo data if database is empty
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Contributor))
            contributors = result.scalars().all()
            is_empty = len(contributors) == 0
            has_demo = any(c.name == "VISENTRA Demo" for c in contributors)

        if is_empty and not has_demo:
            logger.info("Database is empty — automatically seeding VISENTRA demo data...")
            from scripts.seed_demo import seed_demo_data
            await seed_demo_data(app=app)
            logger.info("Demo data successfully seeded on startup.")
    except Exception as e:
        logger.warning("Auto-seed check encountered an error: %s", e)

    yield

app = FastAPI(
    title="VISENTRA",
    description="AI Integrity Assurance Platform — SIH26228",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(contributors_router)
app.include_router(datasets_router)
app.include_router(models_router)
app.include_router(chain_router)
app.include_router(ws_router)
app.include_router(demo_router)
app.include_router(backdoor_router)
app.include_router(inference_router)
app.include_router(dataset_assurance_router)
app.include_router(report_router)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "visentra"}
