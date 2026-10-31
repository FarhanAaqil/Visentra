"""Decoupled four-pillar assurance report.

    S_data     = clamp(100 * intact/total - 10 * min(5, dup_pairs) - 8 * min(5, ood_flagged))
    S_model    = clamp(100 * intact/total - 100 * tampered/total)       binary authenticity only
    S_backdoor = clamp(100 * (1 - min(1, 1.15 * max C_bd)))            behavioural Trojan risk only
    S_infer    = clamp(100 * valid_signed_and_bound / max(1, total))
    overall    = 0.20 S_data + 0.30 S_model + 0.25 S_backdoor + 0.25 S_infer

A suspicious backdoor scan no longer zeroes the model integrity pillar: the
two pillars measure different things and are scored independently.
"""

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_or_404
from backend.assurance.inference import signer
from backend.db.models import BackdoorFinding, Contributor, Dataset, Finding, Inference, Model, iso, utcnow
from backend.db.session import get_db

router = APIRouter(prefix="/report", tags=["report"])

WEIGHTS = {
    "dataset_integrity": 0.20,
    "model_integrity": 0.30,
    "backdoor_screening": 0.25,
    "inference_binding": 0.25,
}

LIMITATIONS = [
    "Backdoor screening probes a fixed trigger library at five anchors plus a blended trigger. It is a "
    "screening tool, not a proof that no trigger exists; adaptive or sample-specific triggers can evade it.",
    "Hash and signature checks prove that bytes did not change after registration. They cannot detect "
    "an artifact that was already malicious when it was first registered; Pillars I and III cover that.",
    "OOD scores use a 512-D hand-built descriptor unless an ONNX backbone is configured, and are a "
    "screening statistic rather than a formal hypothesis test.",
    "Ed25519 signatures prove the server key signed a record. Protect the key file (or SIGNING_KEY); "
    "anyone holding it can mint valid certificates.",
    "This report reflects the pipeline state when it was generated. Re-run the checks before deploying.",
]


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def compute_orthogonal_four_pillar_score(
    ds_intact_ratio: float,
    dup_count: int,
    ood_count: int,
    model_hash_intact_ratio: float,
    max_backdoor_confidence: float,
    valid_signed_inference_ratio: float,
    model_tampered_ratio: float = 0.0,
) -> dict[str, float]:
    s_data = _clamp(100.0 * ds_intact_ratio - 10.0 * min(5, dup_count) - 8.0 * min(5, ood_count))
    s_model = _clamp(100.0 * model_hash_intact_ratio - 100.0 * model_tampered_ratio)
    s_backdoor = _clamp(100.0 * (1.0 - min(1.0, 1.15 * max_backdoor_confidence)))
    s_infer = _clamp(100.0 * valid_signed_inference_ratio)
    pillars = {
        "dataset_integrity": s_data,
        "model_integrity": s_model,
        "backdoor_screening": s_backdoor,
        "inference_binding": s_infer,
    }
    overall = sum(WEIGHTS[k] * v for k, v in pillars.items())
    return {**{k: round(v, 1) for k, v in pillars.items()}, "overall": round(overall, 1)}


class ScoreBreakdown(BaseModel):
    dataset_integrity: float
    model_integrity: float
    backdoor_screening: float
    inference_binding: float
    overall: float


class PillarDetail(BaseModel):
    key: str
    label: str
    score: float
    weight: float
    assessed: bool
    explanation: str
    evidence: dict


class ReportOut(BaseModel):
    contributor_id: str
    contributor_name: str
    generated_at: str
    score: ScoreBreakdown
    grade: str
    summary: str
    pillars: list[PillarDetail]
    findings_count: dict
    limitations: list[str]
    datasets: list[dict]
    models: list[dict]
    inferences: list[dict]


def _grade(overall: float) -> tuple[str, str]:
    if overall >= 85:
        return "A", "Pipeline integrity is HIGH. Every pillar passed its latest checks."
    if overall >= 70:
        return "B", "Pipeline integrity is GOOD, with findings worth reviewing before deployment."
    if overall >= 50:
        return "C", "Pipeline integrity is MODERATE. Resolve the flagged findings before deployment."
    return "D", "Pipeline integrity is LOW. Critical issues detected; do not deploy until they are resolved."


async def build_report(contributor_id: str, db: AsyncSession) -> ReportOut:
    contributor = await get_or_404(db, Contributor, contributor_id)
    datasets = list(
        (await db.execute(select(Dataset).where(Dataset.contributor_id == contributor_id))).scalars()
    )
    models = list((await db.execute(select(Model).where(Model.contributor_id == contributor_id))).scalars())
    model_ids = [m.id for m in models]
    inferences = (
        list((await db.execute(select(Inference).where(Inference.model_id.in_(model_ids)))).scalars())
        if model_ids
        else []
    )

    ds_ids = [d.id for d in datasets]
    findings = (
        list(
            (
                await db.execute(
                    select(Finding).where(Finding.artifact_type == "dataset", Finding.artifact_id.in_(ds_ids))
                )
            ).scalars()
        )
        if ds_ids
        else []
    )
    dup_pairs = sum(f.check_type == "near_duplicate" for f in findings)
    ood_flagged = sum(f.check_type == "ood_anomaly" for f in findings)
    ds_tampered = sum(d.status == "tampered" for d in datasets)
    ds_intact = len(datasets) - ds_tampered

    m_tampered = sum(m.status == "tampered" for m in models)
    m_intact = len(models) - m_tampered
    m_suspicious = sum(m.status == "suspicious" for m in models)

    latest: dict[str, float] = {}
    top_trigger: dict[str, str] = {}
    if model_ids:
        rows = (
            await db.execute(
                select(BackdoorFinding)
                .where(BackdoorFinding.model_id.in_(model_ids))
                .order_by(BackdoorFinding.created_at.desc())
            )
        ).scalars()
        latest_scan: dict[str, str] = {}
        for f in rows:
            latest_scan.setdefault(f.model_id, f.scan_id or "")
            if f.scan_id == latest_scan[f.model_id] and (f.confidence or 0) >= latest.get(f.model_id, -1):
                latest[f.model_id] = f.confidence or 0.0
                top_trigger[f.model_id] = f.trigger_type or ""
    scanned = len(latest)
    max_bd = max(latest.values(), default=0.0)

    valid = sum(i.status == "ok" and bool(i.signature) for i in inferences)
    unsigned = sum(not i.signature for i in inferences)

    n_ds, n_m = max(1, len(datasets)), max(1, len(models))
    score = compute_orthogonal_four_pillar_score(
        ds_intact_ratio=ds_intact / n_ds if datasets else 0.0,
        dup_count=dup_pairs,
        ood_count=ood_flagged,
        model_hash_intact_ratio=m_intact / n_m if models else 0.0,
        model_tampered_ratio=m_tampered / n_m if models else 0.0,
        max_backdoor_confidence=max_bd if scanned else 1.0,
        valid_signed_inference_ratio=valid / max(1, len(inferences)),
    )
    grade, summary = _grade(score["overall"])

    pillars = [
        PillarDetail(
            key="dataset_integrity",
            label="Dataset integrity",
            score=score["dataset_integrity"],
            weight=WEIGHTS["dataset_integrity"],
            assessed=bool(datasets),
            explanation=(
                f"{ds_intact}/{len(datasets)} datasets keep their Merkle root; "
                f"{dup_pairs} near-duplicate pair(s) and {ood_flagged} OOD sample(s) were flagged."
            ),
            evidence={
                "intact": ds_intact,
                "tampered": ds_tampered,
                "duplicates": dup_pairs,
                "ood": ood_flagged,
            },
        ),
        PillarDetail(
            key="model_integrity",
            label="Model integrity",
            score=score["model_integrity"],
            weight=WEIGHTS["model_integrity"],
            assessed=bool(models),
            explanation=f"{m_intact}/{len(models)} checkpoints still hash to their registered SHA-256.",
            evidence={"intact": m_intact, "tampered": m_tampered},
        ),
        PillarDetail(
            key="backdoor_screening",
            label="Backdoor screening",
            score=score["backdoor_screening"],
            weight=WEIGHTS["backdoor_screening"],
            assessed=scanned > 0,
            explanation=(
                f"Highest Trojan confidence across {scanned} scanned model(s) is {max_bd:.2f}; "
                f"{m_suspicious} model(s) are marked suspicious."
                if scanned
                else "No model has been interrogated yet, so this pillar scores zero."
            ),
            evidence={"scanned": scanned, "max_confidence": round(max_bd, 4), "top_trigger": top_trigger},
        ),
        PillarDetail(
            key="inference_binding",
            label="Inference binding",
            score=score["inference_binding"],
            weight=WEIGHTS["inference_binding"],
            assessed=bool(inferences),
            explanation=(
                f"{valid}/{len(inferences)} inference certificates are signed and bound to intact artifacts."
                if inferences
                else "No inferences have been recorded yet, so there is nothing bound to score."
            ),
            evidence={"valid": valid, "total": len(inferences), "unsigned": unsigned},
        ),
    ]

    return ReportOut(
        contributor_id=contributor.id,
        contributor_name=contributor.name,
        generated_at=iso(utcnow()),
        score=ScoreBreakdown(**score),
        grade=grade,
        summary=summary,
        pillars=pillars,
        findings_count={
            "datasets_total": len(datasets),
            "datasets_flagged": sum(d.status == "flagged" for d in datasets),
            "datasets_tampered": ds_tampered,
            "duplicate_pairs": dup_pairs,
            "ood_flagged": ood_flagged,
            "models_total": len(models),
            "models_suspicious": m_suspicious,
            "models_tampered": m_tampered,
            "inferences_total": len(inferences),
            "inferences_mismatch": sum(i.status != "ok" for i in inferences),
        },
        limitations=LIMITATIONS,
        datasets=[
            {
                "id": d.id,
                "version": d.version,
                "status": d.status,
                "sha256": d.sha256,
                "merkle_root": d.merkle_root,
                "samples": d.sample_count or 0,
            }
            for d in datasets
        ],
        models=[
            {
                "id": m.id,
                "version": m.version,
                "framework": m.framework,
                "status": m.status,
                "sha256": m.sha256,
                "arch_fingerprint": m.arch_fingerprint,
                "backdoor_confidence": latest.get(m.id),
            }
            for m in models
        ],
        inferences=[
            {
                "id": i.id,
                "model_id": i.model_id,
                "status": i.status,
                "confidence": i.confidence,
                "signed": bool(i.signature),
            }
            for i in inferences
        ],
    )


@router.get("/{contributor_id}", response_model=ReportOut)
async def get_report(contributor_id: str, db: AsyncSession = Depends(get_db)):
    return await build_report(contributor_id, db)


@router.get("/{contributor_id}/certificate")
async def get_certificate(contributor_id: str, db: AsyncSession = Depends(get_db)):
    """The report wrapped in an Ed25519 signature, ready to export and verify offline."""
    report = await build_report(contributor_id, db)
    return signer.sign_document({"kind": "visentra.assurance-certificate/v1", "report": report.model_dump()})


class CertificateCheck(BaseModel):
    signature_valid: bool
    trusted_key: bool
    key_id: str | None


@router.post("/certificate/verify", response_model=CertificateCheck)
async def verify_certificate(envelope: dict, x_visentra_trust: str | None = Header(default=None)):
    """Check a certificate's signature, and whether it was made with this server's key."""
    sig = envelope.get("signature") or {}
    trusted = {signer.public_key_hex(), *(x_visentra_trust or "").split(",")} - {""}
    return CertificateCheck(
        signature_valid=signer.verify_document(envelope),
        trusted_key=sig.get("public_key") in trusted,
        key_id=sig.get("key_id"),
    )
