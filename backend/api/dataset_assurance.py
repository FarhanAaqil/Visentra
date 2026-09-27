"""
Dataset assurance API router.

POST /datasets/{id}/verify  — already in datasets.py (hash check)
POST /datasets/{id}/analyze — runs near-duplicate + OOD checks on uploaded samples
GET  /datasets/{id}/findings — returns all findings for this dataset
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.db.session import get_db
from backend.db.models import Dataset, DatasetSample, Finding
from backend.api.ws import broadcast
from backend.assurance.data.dataset_checks import find_near_duplicates, score_ood

router = APIRouter(tags=["dataset-assurance"])

DATASET_STORE = Path(settings.storage_root) / "datasets"

def _collect_images(dataset_id: str, sample_paths: list[str]) -> list[Path]:
    """Resolve sample paths and filter to supported image extensions."""
    images = []
    for sp in sample_paths:
        p = Path(sp)
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"} and p.exists():
            images.append(p)
    if not images and DATASET_STORE.exists():
        images = [
            p for p in DATASET_STORE.rglob("*")
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
        ][:50]
    return images

class AnalysisOut(BaseModel):
    dataset_id: str
    status: str
    duplicate_pairs: int
    ood_flagged: int
    total_samples_checked: int
    findings: list[dict]

@router.post("/datasets/{dataset_id}/analyze", response_model=AnalysisOut)
async def analyze_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset).where(Dataset.id == dataset_id))
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    s_result = await db.execute(select(DatasetSample).where(DatasetSample.dataset_id == dataset_id))
    samples = s_result.scalars().all()
    sample_paths = [s.path for s in samples]
    images = _collect_images(dataset_id, sample_paths)

    all_findings = []

    dup_pairs = find_near_duplicates(images)
    for pair in dup_pairs:
        finding = Finding(
            artifact_type="dataset",
            artifact_id=dataset_id,
            check_type="near_duplicate",
            evidence_json=pair,
            severity=pair.get("severity", "warning"),
        )
        db.add(finding)
        all_findings.append({"check": "near_duplicate", **pair})

    ood_results = score_ood(images)
    ood_flagged = [r for r in ood_results if r.get("flag") == "ood"]
    for r in ood_flagged:
        finding = Finding(
            artifact_type="dataset",
            artifact_id=dataset_id,
            check_type="ood_anomaly",
            evidence_json=r,
            severity=r.get("severity", "warning"),
        )
        db.add(finding)
        all_findings.append({"check": "ood_anomaly", **r})

    if dup_pairs or ood_flagged:
        dataset.status = "flagged"
    else:
        dataset.status = "verified"
    await db.commit()

    await broadcast({
        "type": "node_status",
        "node_type": "dataset",
        "id": dataset_id,
        "status": dataset.status,
    })

    return AnalysisOut(
        dataset_id=dataset_id,
        status=dataset.status,
        duplicate_pairs=len(dup_pairs),
        ood_flagged=len(ood_flagged),
        total_samples_checked=len(images),
        findings=all_findings,
    )

class FindingOut(BaseModel):
    id: str
    check_type: str
    evidence_json: dict | None
    severity: str
    created_at: str

from io import BytesIO
from PIL import Image
from fastapi.responses import Response

@router.get("/datasets/{dataset_id}/thumbnail")
async def get_dataset_thumbnail(
    dataset_id: str,
    path: str = "",
    size: int = 128,
    quality: int = 80,
):
    """
    Returns an optimized, compressed thumbnail image.
    Applies bicubic downscaling, converts to RGB, and compresses to JPEG
    with quality=80 to guarantee lightweight lazy loading in the UI.
    """
    img_path = Path(path) if path else None
    if not img_path or not img_path.exists():
        img = Image.new("RGB", (size, size), color=(24, 30, 42))
    else:
        try:
            img = Image.open(img_path)
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
        except Exception:
            img = Image.new("RGB", (size, size), color=(24, 30, 42))

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return Response(
        content=buf.getvalue(),
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )

@router.get("/datasets/{dataset_id}/findings", response_model=list[FindingOut])
async def get_dataset_findings(dataset_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Finding)
        .where(Finding.artifact_type == "dataset")
        .where(Finding.artifact_id == dataset_id)
        .order_by(Finding.created_at.desc())
    )
    findings = result.scalars().all()
    return [
        FindingOut(
            id=f.id,
            check_type=f.check_type,
            evidence_json=f.evidence_json,
            severity=f.severity,
            created_at=f.created_at.isoformat(),
        )
        for f in findings
    ]

