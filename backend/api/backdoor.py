"""
Backdoor scan router.

POST /models/{id}/backdoor-scan   — kick off a scan (runs synchronously for now, async in Phase 5 polish)
GET  /models/{id}/backdoor-scan/{scan_id} — retrieve evidence detail
"""
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.db.session import get_db
from backend.db.models import Model, BackdoorFinding
from backend.api.ws import broadcast
from backend.assurance.model.backdoor import run_backdoor_scan

router = APIRouter(tags=["backdoor"])

MODEL_STORE = Path(settings.storage_root) / "models"
EVIDENCE_STORE = Path(settings.storage_root) / "evidence"

class ScanResult(BaseModel):
    scan_id: str
    model_id: str
    status: str
    findings: list[dict]
    top_confidence: float

class FindingOut(BaseModel):
    id: str
    model_id: str
    trigger_type: str | None
    target_class: int | None
    consistency_rate: float | None
    anomaly_index: float | None
    cluster_score: float | None
    confidence: float | None
    evidence_ref: str | None
    created_at: str

@router.post("/models/{model_id}/backdoor-scan", response_model=ScanResult)
async def start_backdoor_scan(model_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    model_path = MODEL_STORE / model.sha256

    dataset_store = Path(settings.storage_root) / "datasets"
    sample_images: list[Path] = []
    if dataset_store.exists():
        sample_images = [
            p for p in dataset_store.rglob("*")
            if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}
        ][:20]

    try:
        findings_raw = run_backdoor_scan(model_path, sample_images)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scan error: {e}")

    EVIDENCE_STORE.mkdir(parents=True, exist_ok=True)
    scan_id = str(uuid.uuid4())
    top_confidence = max((f["confidence"] for f in findings_raw), default=0.0)

    for f in findings_raw:
        evidence_path = EVIDENCE_STORE / f"{scan_id}_{f['trigger_type']}.json"
        evidence_path.write_text(json.dumps(f["evidence"], indent=2))

        finding = BackdoorFinding(
            model_id=model_id,
            trigger_type=f["trigger_type"],
            target_class=f.get("target_class"),
            consistency_rate=f.get("consistency_rate"),
            anomaly_index=f.get("anomaly_index"),
            cluster_score=f.get("cluster_score"),
            confidence=f.get("confidence"),
            evidence_ref=str(evidence_path),
        )
        db.add(finding)

    new_status = "suspicious" if top_confidence >= 0.3 else "verified"
    model.status = new_status
    await db.commit()

    await broadcast({
        "type": "node_status",
        "node_type": "model",
        "id": model_id,
        "status": new_status,
        "scan_id": scan_id,
        "top_confidence": top_confidence,
    })

    return ScanResult(
        scan_id=scan_id,
        model_id=model_id,
        status="suspicious" if top_confidence >= 0.3 else "clean",
        findings=findings_raw,
        top_confidence=top_confidence,
    )

@router.get("/models/{model_id}/backdoor-findings", response_model=list[FindingOut])
async def get_backdoor_findings(model_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BackdoorFinding)
        .where(BackdoorFinding.model_id == model_id)
        .order_by(BackdoorFinding.created_at.desc())
    )
    findings = result.scalars().all()
    return [
        FindingOut(
            id=f.id,
            model_id=f.model_id,
            trigger_type=f.trigger_type,
            target_class=f.target_class,
            consistency_rate=f.consistency_rate,
            anomaly_index=f.anomaly_index,
            cluster_score=f.cluster_score,
            confidence=f.confidence,
            evidence_ref=f.evidence_ref,
            created_at=f.created_at.isoformat(),
        )
        for f in findings
    ]
