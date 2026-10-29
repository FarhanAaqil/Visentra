"""Dataset assurance (Pillar I) router.

POST /datasets/{id}/analyze                       near-duplicate + OOD screening of the dataset's samples
GET  /datasets/{id}/findings                      findings from the latest analysis
GET  /datasets/{id}/samples/{sample_id}/thumbnail compressed preview of one sample
"""

import asyncio
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from PIL import Image
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import storage
from backend.api.audit import actor_header, log_audit
from backend.api.datasets import dataset_samples
from backend.api.deps import get_or_404
from backend.api.ws import broadcast
from backend.assurance.data import dataset_checks as checks
from backend.db.models import Dataset, DatasetSample, Finding, iso, utcnow
from backend.db.session import get_db

router = APIRouter(tags=["dataset-assurance"])


class AnalysisOut(BaseModel):
    dataset_id: str
    status: str
    duplicate_pairs: int
    ood_flagged: int
    total_samples_checked: int
    embedder: str
    thresholds: dict
    findings: list[dict]
    scores: list[dict]


class FindingOut(BaseModel):
    id: str
    check_type: str
    evidence_json: dict | None
    severity: str
    created_at: str


def _run_checks(samples: list[tuple[str, Path]], phashes: dict[str, str], embeddings_path: Path):
    return checks.find_near_duplicates(samples, phashes), checks.score_ood(samples, save_to=embeddings_path)


@router.post("/datasets/{dataset_id}/analyze", response_model=AnalysisOut)
async def analyze_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    dataset = await get_or_404(db, Dataset, dataset_id)
    if dataset.status == "tampered":
        raise HTTPException(status_code=409, detail="Dataset failed its integrity check, restore it first")

    rows = await dataset_samples(db, dataset_id)
    samples = [(s.id, storage.resolve(s.path)) for s in rows]
    samples = [(sid, p) for sid, p in samples if p.exists()]
    phashes = {s.id: s.phash for s in rows if s.phash}
    embeddings_path = storage.sample_dir(dataset.sha256) / "embeddings.npy"

    dup_pairs, ood_scores = await asyncio.to_thread(_run_checks, samples, phashes, embeddings_path)
    names = {s.id: s.name for s in rows}
    for pair in dup_pairs:
        pair["image_a"], pair["image_b"] = names[pair["sample_a_id"]], names[pair["sample_b_id"]]
    for r in ood_scores:
        r["image"] = names[r["sample_id"]]
    ood_flagged = [r for r in ood_scores if r["flag"] == "ood"]

    # Re-running replaces the previous verdict instead of piling up duplicate findings.
    await db.execute(
        delete(Finding).where(Finding.artifact_type == "dataset", Finding.artifact_id == dataset_id)
    )

    flags: dict[str, set[str]] = {s.id: set() for s in rows}
    findings: list[dict] = []
    for pair in dup_pairs:
        flags[pair["sample_a_id"]].add("near_duplicate")
        flags[pair["sample_b_id"]].add("near_duplicate")
        findings.append({"check": "near_duplicate", **pair})
        db.add(
            Finding(
                artifact_type="dataset",
                artifact_id=dataset_id,
                check_type="near_duplicate",
                evidence_json=pair,
                severity=pair["severity"],
            )
        )
    for r in ood_flagged:
        flags[r["sample_id"]].add("ood")
        findings.append({"check": "ood_anomaly", **r})
        db.add(
            Finding(
                artifact_type="dataset",
                artifact_id=dataset_id,
                check_type="ood_anomaly",
                evidence_json=r,
                severity=r["severity"],
            )
        )

    embedder = checks.embedder_name()
    thresholds = {"hamming": checks.HAMMING_THRESHOLD, "ood": checks.OOD_THRESHOLD}
    summary = {
        "samples_checked": len(samples),
        "duplicate_pairs": len(dup_pairs),
        "ood_flagged": len(ood_flagged),
        "embedder": embedder,
        "thresholds": thresholds,
        "analyzed_at": iso(utcnow()),
    }
    db.add(
        Finding(
            artifact_type="dataset",
            artifact_id=dataset_id,
            check_type="analysis_summary",
            evidence_json=summary,
            severity="info",
        )
    )
    for row in rows:
        row.flags = sorted(flags[row.id])
        if embeddings_path.exists():
            row.embedding_ref = storage.relative(embeddings_path)

    before = {"status": dataset.status}
    dataset.status = "flagged" if (dup_pairs or ood_flagged) else "verified"
    log_audit(
        db,
        actor=actor,
        action="dataset.analyze",
        artifact_type="dataset",
        artifact_id=dataset_id,
        before=before,
        after={"status": dataset.status, **summary},
    )
    await db.commit()
    await broadcast(
        {"type": "node_status", "node_type": "dataset", "id": dataset_id, "status": dataset.status}
    )

    return AnalysisOut(
        dataset_id=dataset_id,
        status=dataset.status,
        duplicate_pairs=len(dup_pairs),
        ood_flagged=len(ood_flagged),
        total_samples_checked=len(samples),
        embedder=embedder,
        thresholds=thresholds,
        findings=findings,
        scores=ood_scores,
    )


@router.get("/datasets/{dataset_id}/findings", response_model=list[FindingOut])
async def get_dataset_findings(dataset_id: str, db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Finding)
        .where(Finding.artifact_type == "dataset", Finding.artifact_id == dataset_id)
        .order_by(Finding.created_at.desc())
    )
    return [
        FindingOut(
            id=f.id,
            check_type=f.check_type,
            evidence_json=f.evidence_json,
            severity=f.severity,
            created_at=iso(f.created_at),
        )
        for f in (await db.execute(stmt)).scalars().all()
    ]


@router.get("/datasets/{dataset_id}/samples/{sample_id}/thumbnail")
async def get_sample_thumbnail(
    dataset_id: str,
    sample_id: str,
    size: int = Query(default=128, ge=16, le=512),
    db: AsyncSession = Depends(get_db),
):
    """JPEG preview of a sample. Only files registered to this dataset can be served."""
    sample = await get_or_404(db, DatasetSample, sample_id, "Sample")
    if sample.dataset_id != dataset_id:
        raise HTTPException(status_code=404, detail="Sample not found")
    path = storage.resolve(sample.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample file missing from storage")

    def render() -> bytes:
        img = Image.open(path).convert("RGB")
        img.thumbnail((size, size), Image.Resampling.NEAREST if size >= 64 else Image.Resampling.LANCZOS)
        if img.size[0] < size:
            img = img.resize((size, size), Image.Resampling.NEAREST)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=88, optimize=True)
        return buf.getvalue()

    return Response(
        content=await asyncio.to_thread(render),
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )
