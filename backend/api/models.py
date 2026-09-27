import hashlib
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.db.session import get_db
from backend.db.models import Model, Contributor
from backend.api.ws import broadcast

router = APIRouter(prefix="/models", tags=["models"])

STORAGE = Path(settings.storage_root) / "models"


async def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    async with aiofiles.open(path, "rb") as f:
        while chunk := await f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def _detect_framework(filename: str) -> str:
    if filename.endswith(".onnx"):
        return "onnx"
    if filename.endswith((".pt", ".pth")):
        return "pytorch"
    return "unknown"


def _arch_fingerprint(path: Path, framework: str) -> str:
    """Lightweight architecture fingerprint — layer names hash for ONNX, state_dict key hash for PyTorch."""
    try:
        if framework == "onnx":
            import onnx
            model = onnx.load(str(path))
            names = sorted(n.name for n in model.graph.node)
            return hashlib.sha256("|".join(names).encode()).hexdigest()[:32]
        if framework == "pytorch":
            import torch
            sd = torch.load(str(path), map_location="cpu")
            keys = sorted(sd.keys()) if isinstance(sd, dict) else []
            return hashlib.sha256("|".join(keys).encode()).hexdigest()[:32]
    except Exception:
        pass
    return "unknown"


class ModelOut(BaseModel):
    id: str
    contributor_id: str
    version: str
    framework: str
    sha256: str
    arch_fingerprint: str | None
    status: str
    created_at: str


@router.post("", response_model=ModelOut, status_code=201)
async def upload_model(
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
    framework = _detect_framework(file.filename or "")
    arch_fp = _arch_fingerprint(dest, framework)

    model = Model(
        contributor_id=contributor_id,
        version=version,
        framework=framework,
        sha256=sha,
        arch_fingerprint=arch_fp,
        status="verified",
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)

    dest.rename(STORAGE / sha)

    await broadcast({"type": "node_status", "node_type": "model", "id": model.id, "status": "verified"})

    return ModelOut(
        id=model.id,
        contributor_id=model.contributor_id,
        version=model.version,
        framework=model.framework,
        sha256=model.sha256,
        arch_fingerprint=model.arch_fingerprint,
        status=model.status,
        created_at=model.created_at.isoformat(),
    )


@router.get("/{model_id}", response_model=ModelOut)
async def get_model(model_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return ModelOut(
        id=model.id,
        contributor_id=model.contributor_id,
        version=model.version,
        framework=model.framework,
        sha256=model.sha256,
        arch_fingerprint=model.arch_fingerprint,
        status=model.status,
        created_at=model.created_at.isoformat(),
    )


@router.post("/{model_id}/verify", response_model=ModelOut)
async def verify_model(model_id: str, db: AsyncSession = Depends(get_db)):
    """Re-hash the stored model file and compare against the registered SHA-256."""
    result = await db.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    stored = STORAGE / model.sha256
    if not stored.exists():
        model.status = "tampered"
        await db.commit()
        await broadcast({"type": "node_status", "node_type": "model", "id": model_id, "status": "tampered"})
        raise HTTPException(status_code=422, detail="Model file missing — integrity broken")

    actual = await _sha256_file(stored)
    new_status = "verified" if actual == model.sha256 else "tampered"
    model.status = new_status
    await db.commit()

    await broadcast({"type": "node_status", "node_type": "model", "id": model_id, "status": new_status})

    return ModelOut(
        id=model.id,
        contributor_id=model.contributor_id,
        version=model.version,
        framework=model.framework,
        sha256=model.sha256,
        arch_fingerprint=model.arch_fingerprint,
        status=model.status,
        created_at=model.created_at.isoformat(),
    )
