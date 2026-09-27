"""
Assurance report router.

GET /report/{contributor_id} — aggregate all findings into a 0–100 score
                               with component breakdown + explicit limitations.
"""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from backend.db.session import get_db
from backend.db.models import (
    Contributor, Dataset, Model, Inference,
    BackdoorFinding, Finding, AuditLog,
)

router = APIRouter(prefix="/report", tags=["report"])


class ScoreBreakdown(BaseModel):
    dataset_integrity: float    # 0–100
    model_integrity: float
    backdoor_screening: float
    inference_binding: float
    overall: float


class ReportOut(BaseModel):
    contributor_id: str
    contributor_name: str
    score: ScoreBreakdown
    summary: str
    findings_count: dict
    limitations: list[str]
    datasets: list[dict]
    models: list[dict]
    inferences: list[dict]


LIMITATIONS = [
    "Backdoor screening uses a fixed trigger library — it is a screening tool, not a proof of absence of all possible triggers.",
    "Hash-based tamper detection does not protect against an attacker who controls the storage layer.",
    "OOD scoring uses embedding similarity and is not a formal statistical test.",
    "Inference evidence records rely on the integrity of the local filesystem.",
    "Digital signatures are not implemented in this build — add PKI before production use.",
    "This report reflects the pipeline state at the time of the last scan. Re-run all checks before each deployment.",
]


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


async def _compute_scores(contributor_id: str, db: AsyncSession) -> tuple[ScoreBreakdown, dict, list, list, list]:
    # --- Datasets ---
    ds_result = await db.execute(select(Dataset).where(Dataset.contributor_id == contributor_id))
    datasets = ds_result.scalars().all()

    ds_verified = sum(1 for d in datasets if d.status == "verified")
    ds_total = len(datasets)
    ds_score = _clamp(100.0 * ds_verified / ds_total) if ds_total else 0.0

    # Deduct for flagged datasets
    ds_flagged = sum(1 for d in datasets if d.status == "flagged")
    ds_score = _clamp(ds_score - ds_flagged * 15)

    # --- Models ---
    m_result = await db.execute(select(Model).where(Model.contributor_id == contributor_id))
    models = m_result.scalars().all()

    m_verified = sum(1 for m in models if m.status == "verified")
    m_suspicious = sum(1 for m in models if m.status == "suspicious")
    m_tampered = sum(1 for m in models if m.status == "tampered")
    m_total = len(models)
    m_score = _clamp(100.0 * m_verified / m_total) if m_total else 0.0
    m_score = _clamp(m_score - m_tampered * 40 - m_suspicious * 20)

    # --- Backdoor ---
    bd_score = 100.0
    model_ids = [m.id for m in models]
    if model_ids:
        bd_result = await db.execute(
            select(BackdoorFinding).where(BackdoorFinding.model_id.in_(model_ids))
        )
        bd_findings = bd_result.scalars().all()
        if bd_findings:
            max_conf = max((f.confidence or 0.0) for f in bd_findings)
            bd_score = _clamp(100.0 - max_conf * 100.0 * 1.2)
        elif not models:
            bd_score = 0.0
        # No findings = clean
    else:
        bd_score = 0.0  # no models = no score

    # --- Inference ---
    inf_score = 100.0
    all_inferences = []
    for m in models:
        inf_result = await db.execute(select(Inference).where(Inference.model_id == m.id))
        inferences = inf_result.scalars().all()
        all_inferences.extend(inferences)

    if all_inferences:
        ok_count = sum(1 for i in all_inferences if i.status == "ok")
        inf_score = _clamp(100.0 * ok_count / len(all_inferences))
    else:
        inf_score = 100.0  # no inferences yet = neutral

    # Weighted overall: dataset 20, model 30, backdoor 25, inference 25
    overall = _clamp(
        0.20 * ds_score +
        0.30 * m_score +
        0.25 * bd_score +
        0.25 * inf_score
    )

    score = ScoreBreakdown(
        dataset_integrity=round(ds_score, 1),
        model_integrity=round(m_score, 1),
        backdoor_screening=round(bd_score, 1),
        inference_binding=round(inf_score, 1),
        overall=round(overall, 1),
    )

    findings_count = {
        "datasets_total": ds_total,
        "datasets_flagged": ds_flagged,
        "datasets_tampered": sum(1 for d in datasets if d.status == "tampered"),
        "models_total": m_total,
        "models_suspicious": m_suspicious,
        "models_tampered": m_tampered,
        "inferences_total": len(all_inferences),
        "inferences_mismatch": sum(1 for i in all_inferences if i.status != "ok"),
    }

    datasets_out = [{"id": d.id, "version": d.version, "status": d.status, "sha256": d.sha256[:12] + "…"} for d in datasets]
    models_out = [{"id": m.id, "version": m.version, "framework": m.framework, "status": m.status} for m in models]
    inferences_out = [{"id": i.id, "model_id": i.model_id, "status": i.status, "confidence": i.confidence} for i in all_inferences]

    return score, findings_count, datasets_out, models_out, inferences_out


@router.get("/{contributor_id}", response_model=ReportOut)
async def get_report(contributor_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contributor).where(Contributor.id == contributor_id))
    contributor = result.scalar_one_or_none()
    if not contributor:
        raise HTTPException(status_code=404, detail="Contributor not found")

    score, findings_count, datasets, models, inferences = await _compute_scores(contributor_id, db)

    if score.overall >= 80:
        summary = "Pipeline integrity is HIGH. All registered artifacts passed their latest checks."
    elif score.overall >= 50:
        summary = "Pipeline integrity is MODERATE. Some findings require attention before deployment."
    else:
        summary = "Pipeline integrity is LOW. Critical issues detected — do not deploy until resolved."

    return ReportOut(
        contributor_id=contributor_id,
        contributor_name=contributor.name,
        score=score,
        summary=summary,
        findings_count=findings_count,
        limitations=LIMITATIONS,
        datasets=datasets,
        models=models,
        inferences=inferences,
    )
