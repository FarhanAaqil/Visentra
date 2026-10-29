"""Demo-only endpoints that simulate supply-chain attacks.

Gated behind settings.enable_demo so a real deployment can switch them off.
"""

import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend import storage
from backend.api.audit import actor_header, log_audit
from backend.api.deps import get_or_404, require_demo
from backend.api.ws import broadcast
from backend.db.models import Dataset, Model
from backend.db.session import get_db

router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(require_demo)])


@router.post("/models/{model_id}/tamper")
async def tamper_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    model = await get_or_404(db, Model, model_id)
    stored = storage.models() / model.sha256
    if not stored.exists():
        raise HTTPException(status_code=404, detail="Stored model file not found")

    stored.write_bytes(os.urandom(1024))
    before = {"status": model.status}
    model.status = "tampered"
    log_audit(
        db,
        actor=actor,
        action="model.tamper",
        artifact_type="model",
        artifact_id=model.id,
        before=before,
        after={"status": "tampered"},
    )
    await db.commit()
    await broadcast({"type": "node_status", "node_type": "model", "id": model_id, "status": "tampered"})
    return {"detail": "Model file tampered. Digest divergence broadcast to live listeners."}


@router.post("/datasets/{dataset_id}/tamper")
async def tamper_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    dataset = await get_or_404(db, Dataset, dataset_id)
    stored = storage.datasets() / dataset.sha256
    if not stored.exists():
        raise HTTPException(status_code=404, detail="Stored dataset file not found")

    stored.write_bytes(os.urandom(1024))
    log_audit(db, actor=actor, action="dataset.tamper", artifact_type="dataset", artifact_id=dataset.id)
    await db.commit()
    return {"detail": "Dataset file tampered. Call /datasets/{id}/verify to detect the change."}


@router.post("/models/{model_id}/restore")
async def restore_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    model = await get_or_404(db, Model, model_id)
    stored = storage.models() / model.sha256
    if stored.exists():
        stored.unlink()

    before = {"status": model.status}
    model.status = "pending"
    log_audit(
        db,
        actor=actor,
        action="model.restore",
        artifact_type="model",
        artifact_id=model.id,
        before=before,
        after={"status": "pending"},
    )
    await db.commit()
    return {"detail": "Demo state reset. Re-upload the model to restore a verified state."}
