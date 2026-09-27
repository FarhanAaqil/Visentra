import hashlib
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.db.session import get_db
from backend.db.models import Dataset, Contributor
from backend.api.ws import broadcast

router = APIRouter(prefix="/datasets", tags=["datasets"])

STORAGE = Path(settings.storage_root) / "datasets"

async def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    async with aiofiles.open(path, "rb") as f:
        while chunk := await f.read(65536):
            h.update(chunk)
    return h.hexdigest()

class DatasetOut(BaseModel):
    id: str
    contributor_id: str
    version: str
    sha256: str
    status: str
    created_at: str

@router.post("", response_model=DatasetOut, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    contributor_id: str = Form(...),
    version: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Contributor).where(Contributor.id == contributor_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Contributor not found")

    STORAGE.mkdir(parents=True, exist_ok=True)
    file_id = str(uuid.uuid4())
    dest = STORAGE / file_id

    async with aiofiles.open(dest, "wb") as out:
        while chunk := await file.read(65536):
            await out.write(chunk)

    sha = await _sha256_file(dest)

    dataset = Dataset(
        contributor_id=contributor_id,
        version=version,
        sha256=sha,
        status="verified",
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)

    dest.rename(STORAGE / sha)

    await broadcast({"type": "node_status", "node_type": "dataset", "id": dataset.id, "status": "verified"})

    return DatasetOut(
        id=dataset.id,
        contributor_id=dataset.contributor_id,
        version=dataset.version,
        sha256=dataset.sha256,
        status=dataset.status,
        created_at=dataset.created_at.isoformat(),
    )

@router.get("/{dataset_id}", response_model=DatasetOut)
async def get_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetOut(
        id=dataset.id,
        contributor_id=dataset.contributor_id,
        version=dataset.version,
        sha256=dataset.sha256,
        status=dataset.status,
        created_at=dataset.created_at.isoformat(),
    )

@router.post("/{dataset_id}/verify", response_model=DatasetOut)
async def verify_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    """Re-check the stored file's SHA-256 against the registered hash."""
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    stored = STORAGE / dataset.sha256
    if not stored.exists():
        dataset.status = "tampered"
        await db.commit()
        await broadcast({"type": "node_status", "node_type": "dataset", "id": dataset_id, "status": "tampered"})
        raise HTTPException(status_code=422, detail="Stored file missing — dataset integrity broken")

    actual = await _sha256_file(stored)
    if actual != dataset.sha256:
        dataset.status = "tampered"
        new_status = "tampered"
    else:
        dataset.status = "verified"
        new_status = "verified"

    await db.commit()
    await broadcast({"type": "node_status", "node_type": "dataset", "id": dataset_id, "status": new_status})

    return DatasetOut(
        id=dataset.id,
        contributor_id=dataset.contributor_id,
        version=dataset.version,
        sha256=dataset.sha256,
        status=dataset.status,
        created_at=dataset.created_at.isoformat(),
    )
