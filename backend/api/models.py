import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import storage
from backend.api.audit import actor_header, log_audit
from backend.api.cascade import cascade_from_model
from backend.api.deps import get_or_404
from backend.api.ws import broadcast
from backend.assurance.model import runtime
from backend.db.models import Contributor, Dataset, Model, iso, utcnow
from backend.db.session import get_db
from backend.sandbox.runner import SandboxError

router = APIRouter(prefix="/models", tags=["models"])


def detect_framework(filename: str) -> str:
    name = filename.lower()
    if name.endswith(".onnx"):
        return "onnx"
    if name.endswith((".pt", ".pth")):
        return "pytorch"
    if name.endswith(".safetensors"):
        return "safetensors"
    return "unknown"


async def inspect_model(path: Path, framework: str) -> tuple[str, dict]:
    """Topology fingerprint and graph summary, computed inside the sandbox."""
    if framework != "onnx":
        return "not-executable", {
            "error": f"{framework} checkpoints are hash-tracked only; pickle based formats are never loaded"
        }
    try:
        info = await runtime.inspect(path)
    except SandboxError as e:
        return "unparseable", {"error": str(e)}
    return info["arch_fingerprint"], {**info["graph"], "sandbox_guards": info.get("guards", [])}


class ByteDiff(BaseModel):
    bytes_changed: int
    first_offsets: list[int]
    size: int
    tensors_touched: list[str] = []


class ModelIntegrity(BaseModel):
    hash_match: bool
    arch_match: bool | None
    actual_arch_fingerprint: str | None
    byte_diff: ByteDiff | None


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
    integrity: ModelIntegrity | None = None
    invalidated_inferences: list[str] = []


def model_out(
    m: Model, integrity: ModelIntegrity | None = None, invalidated: list[str] | None = None
) -> ModelOut:
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
        integrity=integrity,
        invalidated_inferences=invalidated or [],
    )


def vault_copy(model: Model) -> Path:
    return storage.vault() / f"model-{model.sha256}"


def _byte_diff(pristine: Path, current: Path, regions: list[dict]) -> ByteDiff:
    a, b = pristine.read_bytes(), current.read_bytes()
    offsets = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
    touched = sorted(
        {r["tensor"] for r in regions for o in offsets if r["offset"] <= o < r["offset"] + r["length"]}
    )
    return ByteDiff(
        bytes_changed=len(offsets) + abs(len(a) - len(b)),
        first_offsets=offsets[:8],
        size=len(b),
        tensors_touched=touched,
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
    framework = detect_framework(file.filename or "")
    arch, summary = await inspect_model(dest, framework)

    model = Model(
        contributor_id=contributor_id,
        dataset_id=dataset_id or None,
        version=version,
        name=file.filename or "",
        framework=framework,
        sha256=sha,
        actual_sha256=sha,
        arch_fingerprint=arch,
        graph_summary=summary,
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
        after={"sha256": sha, "framework": framework, "arch_fingerprint": arch, "dataset_id": dataset_id},
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


async def check_model(model: Model) -> tuple[str | None, ModelIntegrity]:
    """Re-hash the stored checkpoint; on a mismatch, say what changed and whether the topology survived."""
    stored = storage.models() / model.sha256
    if not stored.exists():
        return None, ModelIntegrity(
            hash_match=False, arch_match=None, actual_arch_fingerprint=None, byte_diff=None
        )

    actual = await storage.sha256_file(stored)
    if actual == model.sha256:
        return actual, ModelIntegrity(
            hash_match=True, arch_match=True, actual_arch_fingerprint=model.arch_fingerprint, byte_diff=None
        )

    arch, _ = await inspect_model(stored, model.framework)
    pristine = vault_copy(model)
    regions = (model.graph_summary or {}).get("weight_regions") or []
    return actual, ModelIntegrity(
        hash_match=False,
        arch_match=arch == model.arch_fingerprint,
        actual_arch_fingerprint=arch,
        byte_diff=_byte_diff(pristine, stored, regions) if pristine.exists() else None,
    )


@router.post("/{model_id}/verify", response_model=ModelOut)
async def verify_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    """Re-hash the stored checkpoint and return the real disk digest alongside the registered one."""
    model = await get_or_404(db, Model, model_id)
    before = {"status": model.status, "actual_sha256": model.actual_sha256}

    actual, integrity = await check_model(model)
    invalidated: list[str] = []
    if integrity.hash_match:
        model.status = "suspicious" if model.status == "suspicious" else "verified"
    else:
        model.status = "tampered"
        invalidated = await cascade_from_model(db, model, actor)
    model.actual_sha256 = actual
    model.verified_at = utcnow()

    log_audit(
        db,
        actor=actor,
        action="model.verify",
        artifact_type="model",
        artifact_id=model.id,
        before=before,
        after={
            "status": model.status,
            "actual_sha256": actual,
            **integrity.model_dump(exclude={"byte_diff"}),
        },
    )
    await db.commit()
    await broadcast({"type": "node_status", "node_type": "model", "id": model.id, "status": model.status})

    if actual is None:
        raise HTTPException(status_code=422, detail="Model file missing, integrity broken")
    return model_out(model, integrity, invalidated)
