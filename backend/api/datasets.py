import asyncio
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
from backend.assurance.data.archive import ArchiveError, extract_images
from backend.assurance.data.dataset_checks import compute_merkle_root, compute_phash
from backend.db.models import Contributor, Dataset, DatasetSample, iso, utcnow
from backend.db.session import get_db

router = APIRouter(prefix="/datasets", tags=["datasets"])


class IntegrityOut(BaseModel):
    archive_match: bool
    merkle_match: bool
    recomputed_merkle_root: str | None
    changed_samples: list[str]
    missing_samples: list[str]


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
    integrity: IntegrityOut | None = None


class SampleOut(BaseModel):
    id: str
    name: str
    sha256: str | None
    phash: str | None
    flags: list[str]


def dataset_out(d: Dataset, integrity: IntegrityOut | None = None) -> DatasetOut:
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
        integrity=integrity,
    )


async def dataset_samples(db: AsyncSession, dataset_id: str) -> list[DatasetSample]:
    stmt = select(DatasetSample).where(DatasetSample.dataset_id == dataset_id).order_by(DatasetSample.name)
    return list((await db.execute(stmt)).scalars().all())


async def check_integrity(dataset: Dataset, samples: list[DatasetSample]) -> tuple[str | None, IntegrityOut]:
    """Re-hash the archive and every sample, then rebuild the Merkle root."""
    archive = storage.datasets() / dataset.sha256
    actual = await storage.sha256_file(archive) if archive.exists() else None

    changed, missing, leaves = [], [], []
    for s in samples:
        path = storage.resolve(s.path)
        if not path.exists():
            missing.append(s.id)
            continue
        digest = await storage.sha256_file(path)
        leaves.append(digest)
        if digest != s.sha256:
            changed.append(s.id)

    recomputed = compute_merkle_root(leaves) if samples else None
    integrity = IntegrityOut(
        archive_match=actual == dataset.sha256,
        merkle_match=(recomputed == dataset.merkle_root) if samples else True,
        recomputed_merkle_root=recomputed,
        changed_samples=changed,
        missing_samples=missing,
    )
    return actual, integrity


@router.post("", response_model=DatasetOut, status_code=201)
async def upload_dataset(
    file: UploadFile = File(...),
    contributor_id: str = Form(...),
    version: str = Form(...),
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    """Store the archive, unpack its images into content-addressed samples and seal a Merkle root."""
    await get_or_404(db, Contributor, contributor_id)

    tmp = storage.datasets() / f".upload-{uuid.uuid4()}"
    async with aiofiles.open(tmp, "wb") as out:
        while chunk := await file.read(storage.CHUNK):
            await out.write(chunk)

    sha = await storage.sha256_file(tmp)
    archive = storage.datasets() / sha
    tmp.replace(archive)

    try:
        extracted = await asyncio.to_thread(
            extract_images, archive, storage.sample_dir(sha), file.filename or ""
        )
    except (ArchiveError, OSError) as e:
        raise HTTPException(status_code=422, detail=f"Could not unpack dataset: {e}") from e

    phashes = await asyncio.to_thread(lambda: [compute_phash(s.path) for s in extracted])
    dataset = Dataset(
        contributor_id=contributor_id,
        version=version,
        name=file.filename or "",
        sha256=sha,
        actual_sha256=sha,
        merkle_root=compute_merkle_root([s.sha256 for s in extracted]) if extracted else None,
        sample_count=len(extracted),
        status="verified",
        verified_at=utcnow(),
    )
    db.add(dataset)
    await db.flush()
    for sample, phash in zip(extracted, phashes, strict=True):
        db.add(
            DatasetSample(
                dataset_id=dataset.id,
                name=sample.name,
                path=storage.relative(sample.path),
                sha256=sample.sha256,
                phash=phash,
                flags=[],
            )
        )
    log_audit(
        db,
        actor=actor,
        action="dataset.upload",
        artifact_type="dataset",
        artifact_id=dataset.id,
        after={
            "sha256": sha,
            "merkle_root": dataset.merkle_root,
            "sample_count": len(extracted),
            "version": version,
        },
    )
    await db.commit()
    await db.refresh(dataset)

    await broadcast({"type": "node_status", "node_type": "dataset", "id": dataset.id, "status": "verified"})
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


@router.get("/{dataset_id}/samples", response_model=list[SampleOut])
async def list_samples(dataset_id: str, db: AsyncSession = Depends(get_db)):
    await get_or_404(db, Dataset, dataset_id)
    return [
        SampleOut(id=s.id, name=s.name or "", sha256=s.sha256, phash=s.phash, flags=list(s.flags or []))
        for s in await dataset_samples(db, dataset_id)
    ]


@router.post("/{dataset_id}/verify", response_model=DatasetOut)
async def verify_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    """Re-hash the archive and each sample; any divergence marks the dataset tampered."""
    dataset = await get_or_404(db, Dataset, dataset_id)
    before = {"status": dataset.status, "actual_sha256": dataset.actual_sha256}

    actual, integrity = await check_integrity(dataset, await dataset_samples(db, dataset_id))
    intact = integrity.archive_match and integrity.merkle_match and not integrity.missing_samples
    if intact:
        # A flagged dataset keeps its hygiene verdict; only the hash state is re-checked here.
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
        after={"status": dataset.status, "actual_sha256": actual, **integrity.model_dump()},
    )
    await db.commit()
    await broadcast(
        {"type": "node_status", "node_type": "dataset", "id": dataset.id, "status": dataset.status}
    )
    return dataset_out(dataset, integrity)
