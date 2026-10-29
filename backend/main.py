import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

from backend.api.audit import router as audit_router  # noqa: E402
from backend.api.backdoor import router as backdoor_router  # noqa: E402
from backend.api.chain import router as chain_router  # noqa: E402
from backend.api.contributors import router as contributors_router  # noqa: E402
from backend.api.dataset_assurance import router as dataset_assurance_router  # noqa: E402
from backend.api.datasets import router as datasets_router  # noqa: E402
from backend.api.demo import router as demo_router  # noqa: E402
from backend.api.inference import router as inference_router  # noqa: E402
from backend.api.models import router as models_router  # noqa: E402
from backend.api.report import router as report_router  # noqa: E402
from backend.api.ws import router as ws_router  # noqa: E402
from backend.config import settings  # noqa: E402
from backend.db.models import Base, Contributor  # noqa: E402
from backend.db.session import AsyncSessionLocal, engine  # noqa: E402

logger = logging.getLogger("uvicorn.error")

VERSION = "1.0.0"


async def _seed_if_empty(app: FastAPI) -> None:
    async with AsyncSessionLocal() as session:
        count = (await session.execute(select(func.count(Contributor.id)))).scalar_one()
    if count:
        return
    logger.info("Database is empty, seeding the VISENTRA demo pipeline")
    from scripts.seed_demo import seed_demo_data

    await seed_demo_data(app=app)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if settings.auto_seed:
        try:
            await _seed_if_empty(app)
        except Exception as e:  # seeding is a convenience, never block startup
            logger.warning("Auto-seed failed: %s", e)

    yield


app = FastAPI(
    title="VISENTRA",
    description="Cryptographic provenance and behavioural assurance for CV supply chains (SIH26228)",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (
    contributors_router,
    datasets_router,
    models_router,
    chain_router,
    ws_router,
    demo_router,
    backdoor_router,
    inference_router,
    dataset_assurance_router,
    report_router,
    audit_router,
):
    app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "visentra", "version": VERSION, "demo": settings.enable_demo}
