"""
Demo-only endpoint — swaps the stored model/dataset file with random bytes
to simulate a tamper attack. Calling /verify afterwards will flip the node red.
This endpoint exists purely for the 5-minute demo script and should be
removed or gated behind a flag before any real deployment.
"""
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.db.session import get_db
from backend.db.models import Model, Dataset

router = APIRouter(prefix="/demo", tags=["demo"])

MODEL_STORE = Path(settings.storage_root) / "models"
DATASET_STORE = Path(settings.storage_root) / "datasets"

@router.post("/models/{model_id}/tamper")
async def tamper_model(model_id: str, db: AsyncSession = Depends(get_db)):
    """Overwrite the stored model file with random bytes. Call /models/{id}/verify after to see the node go red."""
    result = await db.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    stored = MODEL_STORE / model.sha256
    if not stored.exists():
        raise HTTPException(status_code=404, detail="Stored model file not found")

    stored.write_bytes(os.urandom(1024))
    model.status = "tampered"
    await db.commit()

    from backend.api.ws import broadcast
    await broadcast({"type": "node_status", "node_type": "model", "id": model_id, "status": "tampered"})

    return {"detail": "Model file tampered. Digest divergence broadcast to live listeners."}

@router.post("/datasets/{dataset_id}/tamper")
async def tamper_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    """Overwrite the stored dataset archive with random bytes."""
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    stored = DATASET_STORE / dataset.sha256
    if not stored.exists():
        raise HTTPException(status_code=404, detail="Stored dataset file not found")

    stored.write_bytes(os.urandom(1024))

    return {"detail": "Dataset file tampered. Call /datasets/{id}/verify to detect the change."}

@router.post("/models/{model_id}/restore")
async def restore_model(model_id: str, db: AsyncSession = Depends(get_db)):
    """
    Reset demo state — delete the tampered file so the next upload starts clean.
    (A real restore would re-fetch from a trusted backup; here we just remove it
    so the verify endpoint flags 'file missing'.)
    """
    result = await db.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    stored = MODEL_STORE / model.sha256
    if stored.exists():
        stored.unlink()

    model.status = "pending"
    await db.commit()

    return {"detail": "Demo state reset. Re-upload the model to restore a verified state."}
