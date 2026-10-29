import uuid

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import storage
from backend.api.audit import actor_header, log_audit
from backend.api.deps import get_or_404
from backend.api.ws import broadcast
from backend.db.models import Contributor, Dataset, iso, utcnow
from backend.db.session import get_db

router = APIRouter(prefix="/datasets", tags=["datasets"])


class DatasetOut(BaseModel):
    id: str
    contributor_id: str
    version: str
    name: str | None
    sha256: str
    actual_sha256: str | None
    merkle_root: str | None
    sample_count: int
    status: str
    created_at: str
    verified_at: str | None


def dataset_out(d: Dataset) -> DatasetOut:
    return DatasetOut(
        id=d.id,
        contributor_id=d.contributor_id,
        version=d.version,
        name=d.name,
        sha256=d.sha256,
        actual_sha256=d.actual_sha256,
        merkle_root=d.merkle_root,
        sample_count=d.sample_count or 0,
        status=d.status,
        created_at=iso(d.created_at),
        verified_at=iso(d.verified_at) or None,
    )


@router.post("", response_model=DatasetOut, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    contributor_id: str = Form(...),
    version: str = Form(...),
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    await get_or_404(db, Contributor, contributor_id)

    tmp = storage.datasets() / f".upload-{uuid.uuid4()}"
    async with aiofiles.open(tmp, "wb") as out:
        while chunk := await file.read(storage.CHUNK):
            await out.write(chunk)

    sha = await storage.sha256_file(tmp)
    dest = storage.datasets() / sha
    tmp.replace(dest)

    dataset = Dataset(
        contributor_id=contributor_id,
        version=version,
        name=file.filename or "",
        sha256=sha,
        actual_sha256=sha,
        status="verified",
        verified_at=utcnow(),
    )
    db.add(dataset)
    await db.flush()
    log_audit(
        db,
        actor=actor,
        action="dataset.upload",
        artifact_type="dataset",
        artifact_id=dataset.id,
        after={"sha256": sha, "version": version, "name": dataset.name},
    )
    await db.commit()
    await db.refresh(dataset)

    await broadcast(
        {"type": "node_status", "node_type": "dataset", "id": dataset.id, "status": dataset.status}
    )
    return dataset_out(dataset)


@router.get("", response_model=list[DatasetOut])
async def list_datasets(contributor_id: str | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Dataset).order_by(Dataset.created_at.desc())
    if contributor_id:
        stmt = stmt.where(Dataset.contributor_id == contributor_id)
    return [dataset_out(d) for d in (await db.execute(stmt)).scalars().all()]


@router.get("/{dataset_id}", response_model=DatasetOut)
async def get_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    return dataset_out(await get_or_404(db, Dataset, dataset_id))


@router.post("/{dataset_id}/verify", response_model=DatasetOut)
async def verify_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    """Re-hash the stored archive and compare it with the registered digest."""
    dataset = await get_or_404(db, Dataset, dataset_id)
    before = {"status": dataset.status, "actual_sha256": dataset.actual_sha256}

    stored = storage.datasets() / dataset.sha256
    actual = await storage.sha256_file(stored) if stored.exists() else None

    if actual == dataset.sha256:
        # A flagged dataset keeps its hygiene verdict; only hash state changes here.
        dataset.status = "flagged" if dataset.status == "flagged" else "verified"
    else:
        dataset.status = "tampered"
    dataset.actual_sha256 = actual
    dataset.verified_at = utcnow()

    log_audit(
        db,
        actor=actor,
        action="dataset.verify",
        artifact_type="dataset",
        artifact_id=dataset.id,
        before=before,
        after={"status": dataset.status, "actual_sha256": actual},
    )
    await db.commit()
    await broadcast(
        {"type": "node_status", "node_type": "dataset", "id": dataset.id, "status": dataset.status}
    )

    if actual is None:
        raise HTTPException(status_code=422, detail="Stored archive missing, dataset integrity broken")
    return dataset_out(dataset)
