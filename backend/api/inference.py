"""Signed inference binding (Pillar IV).

POST /inference                run an image through a verified model, bind and sign the evidence tuple
GET  /inference                list inferences (optionally for one model)
GET  /inference/{id}           the record, including its signature
GET  /inference/{id}/evidence  the signed evidence document as stored on disk
POST /inference/{id}/reverify  recompute every binding and check the signature
GET  /keys/public              the verification key
"""

import json
import uuid
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import storage
from backend.api.audit import actor_header, log_audit
from backend.api.deps import get_or_404
from backend.api.ws import broadcast
from backend.assurance import synthetic
from backend.assurance.inference import signer
from backend.assurance.model import runtime
from backend.db.models import Dataset, Inference, Model, iso, utcnow
from backend.db.session import get_db
from backend.sandbox.runner import SandboxError

router = APIRouter(prefix="/inference", tags=["inference"])
keys_router = APIRouter(prefix="/keys", tags=["keys"])


async def run_model(model: Model, model_path: Path, image_bytes: bytes) -> dict:
    """Classify one image inside the sandbox and return the canonical output record."""
    if model.framework != "onnx" or not (model.graph_summary or {}).get("inputs"):
        raise HTTPException(
            status_code=422, detail="This model cannot be executed (not a parseable ONNX graph)"
        )
    img = synthetic.decode(image_bytes)
    if img is None:
        raise HTTPException(status_code=422, detail="Could not decode the input image")

    graph = model.graph_summary
    try:
        fwd = await runtime.forward(model_path, runtime.to_model_rgb(img, graph)[None], graph)
    except SandboxError as e:
        raise HTTPException(status_code=422, detail=f"Sandboxed execution failed: {e}") from e

    probs = fwd.probs[0]
    order = np.argsort(-probs)[:5]
    return {
        "top_class": int(order[0]),
        "top_confidence": round(float(probs[order[0]]), 6),
        "top_5": [{"class": int(c), "prob": round(float(probs[c]), 6)} for c in order],
        "logits": [round(float(v), 5) for v in fwd.logits[0]],
    }


class InferenceOut(BaseModel):
    id: str
    model_id: str
    model_sha256: str | None
    arch_fingerprint: str | None
    dataset_merkle_root: str | None
    input_sha256: str | None
    config_sha256: str | None
    output: dict | None
    confidence: float | None
    timestamp: str
    status: str
    signature: str | None
    public_key: str | None
    key_id: str | None


class Checks(BaseModel):
    signature_valid: bool
    model_hash_match: bool
    input_hash_match: bool
    dataset_root_match: bool | None
    record_matches_evidence: bool


class ReverifyOut(BaseModel):
    inference_id: str
    status: str
    checks: Checks
    model_hash_match: bool
    input_hash_match: bool
    diffs: list[str]


def inference_out(inf: Inference) -> InferenceOut:
    return InferenceOut(
        id=inf.id,
        model_id=inf.model_id,
        model_sha256=inf.model_sha256,
        arch_fingerprint=inf.arch_fingerprint,
        dataset_merkle_root=inf.dataset_merkle_root,
        input_sha256=inf.input_sha256,
        config_sha256=inf.config_sha256,
        output=inf.output,
        confidence=inf.confidence,
        timestamp=iso(inf.timestamp),
        status=inf.status,
        signature=inf.signature,
        public_key=inf.public_key,
        key_id=signer.key_id(inf.public_key) if inf.public_key else None,
    )


def _evidence_path(inference_id: str) -> Path:
    return storage.inference() / f"{inference_id}.json"


def _input_path(input_sha: str) -> Path:
    return storage.area("inference/inputs") / input_sha


def record_tuple(inf: Inference) -> dict:
    return {
        "inference_id": inf.id,
        "dataset_merkle_root": inf.dataset_merkle_root,
        "model_id": inf.model_id,
        "model_sha256": inf.model_sha256,
        "arch_fingerprint": inf.arch_fingerprint,
        "input_sha256": inf.input_sha256,
        "config_sha256": inf.config_sha256,
        "output": inf.output,
        "timestamp": iso(inf.timestamp),
    }


@router.post("", response_model=InferenceOut, status_code=201)
async def run_inference(
    image: UploadFile = File(...),
    model_id: str = Form(...),
    config: str = Form(default="{}"),
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    model = await get_or_404(db, Model, model_id)
    if model.status == "tampered":
        raise HTTPException(status_code=422, detail="Model is tampered, refusing to run inference on it")

    model_path = storage.models() / model.sha256
    if not model_path.exists():
        raise HTTPException(status_code=422, detail="Model file missing from storage")
    if await storage.sha256_file(model_path) != model.sha256:
        model.status = "tampered"
        await db.commit()
        await broadcast({"type": "node_status", "node_type": "model", "id": model_id, "status": "tampered"})
        raise HTTPException(status_code=422, detail="Model hash mismatch detected before inference, aborting")

    dataset_root = None
    if model.dataset_id:
        dataset = await get_or_404(db, Dataset, model.dataset_id)
        dataset_root = dataset.merkle_root

    image_bytes = await image.read()
    output = await run_model(model, model_path, image_bytes)
    input_sha = storage.sha256_bytes(image_bytes)
    _input_path(input_sha).write_bytes(image_bytes)

    inference = Inference(
        id=str(uuid.uuid4()),
        model_id=model_id,
        model_sha256=model.sha256,
        arch_fingerprint=model.arch_fingerprint,
        dataset_merkle_root=dataset_root,
        input_sha256=input_sha,
        config_sha256=storage.sha256_bytes(config.encode()),
        output=output,
        confidence=output["top_confidence"],
        timestamp=utcnow(),
        status="ok",
    )
    evidence = record_tuple(inference)
    inference.signature, inference.public_key = signer.sign_evidence_tuple(evidence)
    _evidence_path(inference.id).write_text(
        json.dumps(
            {
                **evidence,
                "config": config,
                "signature": {
                    "algorithm": signer.ALGORITHM,
                    "value": inference.signature,
                    "public_key": inference.public_key,
                    "key_id": signer.key_id(inference.public_key),
                    "digest": signer.binding_digest(evidence).hex(),
                },
            },
            indent=2,
        )
    )

    db.add(inference)
    log_audit(
        db,
        actor=actor,
        action="inference.run",
        artifact_type="inference",
        artifact_id=inference.id,
        after={
            "model_id": model_id,
            "input_sha256": input_sha,
            "top_class": output["top_class"],
            "signed": True,
        },
    )
    await db.commit()
    await db.refresh(inference)

    await broadcast({"type": "node_status", "node_type": "inference", "id": inference.id, "status": "ok"})
    return inference_out(inference)


@router.get("", response_model=list[InferenceOut])
async def list_inferences(model_id: str | None = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Inference).order_by(Inference.timestamp.desc())
    if model_id:
        stmt = stmt.where(Inference.model_id == model_id)
    return [inference_out(i) for i in (await db.execute(stmt)).scalars().all()]


@router.get("/{inference_id}", response_model=InferenceOut)
async def get_inference(inference_id: str, db: AsyncSession = Depends(get_db)):
    return inference_out(await get_or_404(db, Inference, inference_id))


@router.get("/{inference_id}/evidence")
async def get_evidence(inference_id: str, db: AsyncSession = Depends(get_db)):
    await get_or_404(db, Inference, inference_id)
    path = _evidence_path(inference_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence record missing from storage")
    return json.loads(path.read_text())


@router.post("/{inference_id}/reverify", response_model=ReverifyOut)
async def reverify_inference(
    inference_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    """Recompute every link of the binding tuple and verify the Ed25519 signature over it."""
    inf = await get_or_404(db, Inference, inference_id)
    model = await get_or_404(db, Model, inf.model_id)
    path = _evidence_path(inference_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Evidence record missing from storage")
    evidence = json.loads(path.read_text())
    record = record_tuple(inf)
    diffs: list[str] = []

    signature_valid = signer.verify_evidence_signature(record, inf.signature, inf.public_key)
    if not signature_valid:
        diffs.append("signature does not verify against the recorded tuple")

    on_disk = signer.binding_tuple(evidence)
    record_matches = on_disk == record
    if not record_matches:
        changed = [k for k in signer.BINDING_FIELDS if on_disk.get(k) != record.get(k)]
        diffs.append(f"evidence file and database disagree on: {', '.join(changed)}")

    model_path = storage.models() / model.sha256
    actual_model = await storage.sha256_file(model_path) if model_path.exists() else None
    model_match = actual_model == inf.model_sha256
    if not model_match:
        shown = (actual_model or "missing")[:12]
        diffs.append(f"model_sha256 recorded={(inf.model_sha256 or '')[:12]}… actual={shown}…")

    input_file = _input_path(inf.input_sha256 or "")
    actual_input = await storage.sha256_file(input_file) if input_file.exists() else None
    input_match = actual_input == inf.input_sha256
    if not input_match:
        diffs.append("stored input no longer hashes to the bound input_sha256")

    root_match = None
    if inf.dataset_merkle_root and model.dataset_id:
        dataset = await get_or_404(db, Dataset, model.dataset_id)
        root_match = dataset.status != "tampered" and dataset.merkle_root == inf.dataset_merkle_root
        if not root_match:
            diffs.append("training dataset no longer matches the bound Merkle root")

    ok = signature_valid and record_matches and model_match and input_match and root_match is not False
    before = {"status": inf.status}
    inf.status = "ok" if ok else "mismatch"
    if not model_match:
        model.status = "tampered"
    checks = Checks(
        signature_valid=signature_valid,
        model_hash_match=model_match,
        input_hash_match=input_match,
        dataset_root_match=root_match,
        record_matches_evidence=record_matches,
    )
    log_audit(
        db,
        actor=actor,
        action="inference.reverify",
        artifact_type="inference",
        artifact_id=inf.id,
        before=before,
        after={"status": inf.status, **checks.model_dump(), "diffs": diffs},
    )
    await db.commit()

    await broadcast({"type": "node_status", "node_type": "inference", "id": inf.id, "status": inf.status})
    if not model_match:
        await broadcast({"type": "node_status", "node_type": "model", "id": model.id, "status": "tampered"})

    return ReverifyOut(
        inference_id=inf.id,
        status=inf.status,
        checks=checks,
        model_hash_match=model_match,
        input_hash_match=input_match,
        diffs=diffs,
    )


@keys_router.get("/public")
async def public_key():
    pub = signer.public_key_hex()
    return {"algorithm": signer.ALGORITHM, "public_key": pub, "key_id": signer.key_id(pub)}
