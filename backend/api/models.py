import hashlib
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import storage
from backend.api.audit import actor_header, log_audit
from backend.api.deps import get_or_404
from backend.api.ws import broadcast
from backend.db.models import Contributor, Dataset, Model, iso, utcnow
from backend.db.session import get_db

router = APIRouter(prefix="/models", tags=["models"])


def _detect_framework(filename: str) -> str:
    if filename.endswith(".onnx"):
        return "onnx"
    if filename.endswith((".pt", ".pth")):
        return "pytorch"
    if filename.endswith(".safetensors"):
        return "safetensors"
    return "unknown"


def _arch_fingerprint(path: Path, framework: str) -> str:
    try:
        if framework == "onnx":
            import onnx

            model = onnx.load(str(path))
            names = sorted(n.name for n in model.graph.node)
            return hashlib.sha256("|".join(names).encode()).hexdigest()[:32]
    except Exception:
        pass
    return "unknown"


class ModelOut(BaseModel):
    id: str
    contributor_id: str
    dataset_id: str | None
    version: str
    name: str | None
    framework: str
    sha256: str
    actual_sha256: str | None
    arch_fingerprint: str | None
    graph_summary: dict | None
    status: str
    created_at: str
    verified_at: str | None


def model_out(m: Model) -> ModelOut:
    return ModelOut(
        id=m.id,
        contributor_id=m.contributor_id,
        dataset_id=m.dataset_id,
        version=m.version,
        name=m.name,
        framework=m.framework,
        sha256=m.sha256,
        actual_sha256=m.actual_sha256,
        arch_fingerprint=m.arch_fingerprint,
        graph_summary=m.graph_summary,
        status=m.status,
        created_at=iso(m.created_at),
        verified_at=iso(m.verified_at) or None,
    )


@router.post("", response_model=ModelOut, status_code=201)
async def upload_model(
    file: UploadFile = File(...),
    contributor_id: str = Form(...),
    version: str = Form(...),
    dataset_id: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    await get_or_404(db, Contributor, contributor_id)
    if dataset_id:
        await get_or_404(db, Dataset, dataset_id)

    tmp = storage.models() / f".upload-{uuid.uuid4()}"
    async with aiofiles.open(tmp, "wb") as out:
        while chunk := await file.read(storage.CHUNK):
            await out.write(chunk)

    sha = await storage.sha256_file(tmp)
    dest = storage.models() / sha
    tmp.replace(dest)
    framework = _detect_framework(file.filename or "")

    model = Model(
        contributor_id=contributor_id,
        dataset_id=dataset_id or None,
        version=version,
        name=file.filename or "",
        framework=framework,
        sha256=sha,
        actual_sha256=sha,
        arch_fingerprint=_arch_fingerprint(dest, framework),
        status="verified",
        verified_at=utcnow(),
    )
    db.add(model)
    await db.flush()
    log_audit(
        db,
        actor=actor,
        action="model.upload",
        artifact_type="model",
        artifact_id=model.id,
        after={"sha256": sha, "framework": framework, "dataset_id": dataset_id},
    )
    await db.commit()
    await db.refresh(model)

    await broadcast({"type": "node_status", "node_type": "model", "id": model.id, "status": model.status})
    return model_out(model)


@router.get("", response_model=list[ModelOut])
async def list_models(contributor_id: str | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Model).order_by(Model.created_at.desc())
    if contributor_id:
        stmt = stmt.where(Model.contributor_id == contributor_id)
    return [model_out(m) for m in (await db.execute(stmt)).scalars().all()]


@router.get("/{model_id}", response_model=ModelOut)
async def get_model(model_id: str, db: AsyncSession = Depends(get_db)):
    return model_out(await get_or_404(db, Model, model_id))


@router.post("/{model_id}/verify", response_model=ModelOut)
async def verify_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    """Re-hash the stored checkpoint and compare it with the registered SHA-256."""
    model = await get_or_404(db, Model, model_id)
    before = {"status": model.status, "actual_sha256": model.actual_sha256}

    stored = storage.models() / model.sha256
    actual = await storage.sha256_file(stored) if stored.exists() else None

    if actual == model.sha256:
        model.status = "suspicious" if model.status == "suspicious" else "verified"
    else:
        model.status = "tampered"
    model.actual_sha256 = actual
    model.verified_at = utcnow()

    log_audit(
        db,
        actor=actor,
        action="model.verify",
        artifact_type="model",
        artifact_id=model.id,
        before=before,
        after={"status": model.status, "actual_sha256": actual},
    )
    await db.commit()
    await broadcast({"type": "node_status", "node_type": "model", "id": model.id, "status": model.status})

    if actual is None:
        raise HTTPException(status_code=422, detail="Model file missing, integrity broken")
    return model_out(model)
