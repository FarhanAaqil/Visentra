from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
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

app = FastAPI(
    title="VISENTRA",
    description="AI Integrity Assurance Platform — SIH26228",
    version="0.1.0",
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
