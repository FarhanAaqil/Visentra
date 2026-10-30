"""Backdoor interrogation router (Pillar III).

POST /models/{id}/backdoor-scan         run the two-stage scan and store its evidence
GET  /models/{id}/backdoor-findings     per-trigger findings from the latest scan
GET  /models/{id}/backdoor-scans/latest full evidence report of the latest scan
"""

import json
import uuid

import cv2
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import storage
from backend.api.audit import actor_header, log_audit
from backend.api.datasets import dataset_samples
from backend.api.deps import get_or_404
from backend.api.ws import broadcast
from backend.assurance import synthetic
from backend.assurance.model.backdoor import MAX_SAMPLES, run_backdoor_scan
from backend.db.models import BackdoorFinding, Dataset, Model, iso, utcnow
from backend.db.session import get_db
from backend.sandbox.runner import SandboxError

router = APIRouter(tags=["backdoor"])


class FindingOut(BaseModel):
    id: str
    model_id: str
    scan_id: str | None
    trigger_type: str | None
    target_class: int | None
    consistency_rate: float | None
    anomaly_index: float | None
    cluster_score: float | None
    confidence: float | None
    evidence_ref: str | None
    created_at: str


async def clean_probe_set(db: AsyncSession, model: Model) -> tuple[list, list[str], str]:
    """Clean samples from the model's own dataset (skipping flagged ones), else procedural probes."""
    if model.dataset_id:
        dataset = await get_or_404(db, Dataset, model.dataset_id)
        if dataset.status == "tampered":
            raise HTTPException(status_code=409, detail="The model's dataset failed its integrity check")
        images, names = [], []
        for s in await dataset_samples(db, dataset.id):
            if s.flags:
                continue
            img = cv2.imread(str(storage.resolve(s.path)))
            if img is not None:
                images.append(img)
                names.append(s.name)
        if len(images) >= 2:
            return images[:MAX_SAMPLES], names[:MAX_SAMPLES], f"dataset:{dataset.id}"

    probes = [(f"probe_{i:02d}_c{i % 10}.png", synthetic.scene(i % 10, 7000 + i)) for i in range(MAX_SAMPLES)]
    return [p for _, p in probes], [n for n, _ in probes], "procedural-probes"


def _finding_out(f: BackdoorFinding) -> FindingOut:
    return FindingOut(
        id=f.id,
        model_id=f.model_id,
        scan_id=f.scan_id,
        trigger_type=f.trigger_type,
        target_class=f.target_class,
        consistency_rate=f.consistency_rate,
        anomaly_index=f.anomaly_index,
        cluster_score=f.cluster_score,
        confidence=f.confidence,
        evidence_ref=f.evidence_ref,
        created_at=iso(f.created_at),
    )


@router.post("/models/{model_id}/backdoor-scan")
async def start_backdoor_scan(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    model = await get_or_404(db, Model, model_id)
    if model.status == "tampered":
        raise HTTPException(
            status_code=409, detail="Model failed its integrity check; restore it before scanning"
        )
    if model.framework != "onnx" or not (model.graph_summary or {}).get("inputs"):
        raise HTTPException(status_code=422, detail="Only parseable ONNX models can be interrogated")

    model_path = storage.models() / model.sha256
    if not model_path.exists() or await storage.sha256_file(model_path) != model.sha256:
        raise HTTPException(status_code=409, detail="Stored checkpoint no longer matches its registered hash")

    images, names, source = await clean_probe_set(db, model)
    try:
        report = await run_backdoor_scan(model_path, model.graph_summary, images, names)
    except SandboxError as e:
        raise HTTPException(status_code=422, detail=f"Sandboxed scan failed: {e}") from e

    scan_id = str(uuid.uuid4())
    report.update(
        {"scan_id": scan_id, "model_id": model_id, "probe_source": source, "scanned_at": iso(utcnow())}
    )
    evidence_file = storage.evidence() / f"{scan_id}.json"
    evidence_file.write_text(json.dumps(report))

    for t in report["triggers"]:
        db.add(
            BackdoorFinding(
                model_id=model_id,
                scan_id=scan_id,
                trigger_type=t["trigger_type"],
                target_class=t["target_class"],
                consistency_rate=t["consistency_rate"],
                anomaly_index=t["anomaly_index"],
                cluster_score=t["cluster_score"],
                confidence=t["confidence"],
                evidence_ref=f"{storage.relative(evidence_file)}#{t['trigger_type']}",
            )
        )

    before = {"status": model.status}
    model.status = "suspicious" if report["verdict"] == "suspicious" else "verified"
    log_audit(
        db,
        actor=actor,
        action="model.backdoor_scan",
        artifact_type="model",
        artifact_id=model.id,
        before=before,
        after={
            "status": model.status,
            "scan_id": scan_id,
            "top_confidence": report["top_confidence"],
            "escalated": report["escalated"],
        },
    )
    await db.commit()
    await broadcast(
        {
            "type": "node_status",
            "node_type": "model",
            "id": model_id,
            "status": model.status,
            "scan_id": scan_id,
            "top_confidence": report["top_confidence"],
        }
    )
    return report


async def _latest_scan_id(db: AsyncSession, model_id: str) -> str | None:
    stmt = (
        select(BackdoorFinding.scan_id)
        .where(BackdoorFinding.model_id == model_id)
        .order_by(BackdoorFinding.created_at.desc())
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


@router.get("/models/{model_id}/backdoor-findings", response_model=list[FindingOut])
async def get_backdoor_findings(model_id: str, db: AsyncSession = Depends(get_db)):
    scan_id = await _latest_scan_id(db, model_id)
    if not scan_id:
        return []
    stmt = (
        select(BackdoorFinding)
        .where(BackdoorFinding.model_id == model_id, BackdoorFinding.scan_id == scan_id)
        .order_by(BackdoorFinding.confidence.desc())
    )
    return [_finding_out(f) for f in (await db.execute(stmt)).scalars().all()]


@router.get("/models/{model_id}/backdoor-scans/latest")
async def get_latest_scan(model_id: str, db: AsyncSession = Depends(get_db)):
    await get_or_404(db, Model, model_id)
    scan_id = await _latest_scan_id(db, model_id)
    path = storage.evidence() / f"{scan_id}.json" if scan_id else None
    if not path or not path.exists():
        return Response(status_code=204)  # not scanned yet is a state, not an error
    return json.loads(path.read_text())
