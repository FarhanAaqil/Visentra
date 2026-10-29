"""Inference binding router.

POST /inference               run an image through a verified model and bind the hashes
GET  /inference/{id}          retrieve the evidence record
POST /inference/{id}/reverify recompute hashes and diff them against the record
"""

import json
import uuid
from pathlib import Path

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend import storage
from backend.api.audit import actor_header, log_audit
from backend.api.deps import get_or_404
from backend.api.ws import broadcast
from backend.assurance import synthetic
from backend.assurance.model import runtime
from backend.db.models import Inference, Model, iso
from backend.db.session import get_db
from backend.sandbox.runner import SandboxError

router = APIRouter(prefix="/inference", tags=["inference"])


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
    input_sha256: str | None
    config_sha256: str | None
    output: dict | None
    confidence: float | None
    timestamp: str
    status: str


class ReverifyOut(BaseModel):
    inference_id: str
    status: str
    model_hash_match: bool
    input_hash_match: bool
    diffs: list[str]


def inference_out(inf: Inference) -> InferenceOut:
    return InferenceOut(
        id=inf.id,
        model_id=inf.model_id,
        model_sha256=inf.model_sha256,
        input_sha256=inf.input_sha256,
        config_sha256=inf.config_sha256,
        output=inf.output,
        confidence=inf.confidence,
        timestamp=iso(inf.timestamp),
        status=inf.status,
    )


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

    image_bytes = await image.read()
    input_sha = storage.sha256_bytes(image_bytes)
    config_sha = storage.sha256_bytes(config.encode())

    if await storage.sha256_file(model_path) != model.sha256:
        model.status = "tampered"
        await db.commit()
        await broadcast({"type": "node_status", "node_type": "model", "id": model_id, "status": "tampered"})
        raise HTTPException(status_code=422, detail="Model hash mismatch detected before inference, aborting")

    output = await run_model(model, model_path, image_bytes)
    inference_id = str(uuid.uuid4())
    evidence = {
        "inference_id": inference_id,
        "model_id": model_id,
        "model_sha256": model.sha256,
        "input_sha256": input_sha,
        "config_sha256": config_sha,
        "output": output,
    }
    (storage.inference() / f"{inference_id}.json").write_text(json.dumps(evidence, indent=2))

    inference = Inference(
        id=inference_id,
        model_id=model_id,
        model_sha256=model.sha256,
        input_sha256=input_sha,
        config_sha256=config_sha,
        output=output,
        confidence=output.get("top_confidence", 0.0),
        status="ok",
    )
    db.add(inference)
    log_audit(
        db,
        actor=actor,
        action="inference.run",
        artifact_type="inference",
        artifact_id=inference_id,
        after={"model_id": model_id, "input_sha256": input_sha, "top_class": output.get("top_class")},
    )
    await db.commit()
    await db.refresh(inference)

    await broadcast({"type": "node_status", "node_type": "inference", "id": inference_id, "status": "ok"})
    return inference_out(inference)


@router.get("/{inference_id}", response_model=InferenceOut)
async def get_inference(inference_id: str, db: AsyncSession = Depends(get_db)):
    return inference_out(await get_or_404(db, Inference, inference_id))


@router.post("/{inference_id}/reverify", response_model=ReverifyOut)
async def reverify_inference(
    inference_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    """Recompute the model hash and diff it against the hash bound at inference time."""
    inf = await get_or_404(db, Inference, inference_id)
    evidence_path = storage.inference() / f"{inference_id}.json"
    if not evidence_path.exists():
        raise HTTPException(status_code=404, detail="Evidence record missing from storage")

    evidence = json.loads(evidence_path.read_text())
    recorded_model_sha = evidence.get("model_sha256") or ""
    model = await get_or_404(db, Model, inf.model_id)

    model_path = storage.models() / model.sha256
    diffs = []
    model_hash_match = False
    if model_path.exists():
        actual_sha = await storage.sha256_file(model_path)
        model_hash_match = actual_sha == recorded_model_sha
        if not model_hash_match:
            diffs.append(f"model_sha256 recorded={recorded_model_sha[:12]}… actual={actual_sha[:12]}…")
    else:
        diffs.append("model file missing from storage")

    input_hash_match = inf.input_sha256 == evidence.get("input_sha256")
    if not input_hash_match:
        diffs.append("input_sha256 mismatch between DB record and evidence file")

    before = {"status": inf.status}
    inf.status = "ok" if (model_hash_match and input_hash_match) else "mismatch"
    if not model_hash_match:
        model.status = "tampered"
    log_audit(
        db,
        actor=actor,
        action="inference.reverify",
        artifact_type="inference",
        artifact_id=inf.id,
        before=before,
        after={"status": inf.status, "diffs": diffs},
    )
    await db.commit()

    await broadcast(
        {"type": "node_status", "node_type": "inference", "id": inference_id, "status": inf.status}
    )
    if not model_hash_match:
        await broadcast(
            {"type": "node_status", "node_type": "model", "id": inf.model_id, "status": "tampered"}
        )

    return ReverifyOut(
        inference_id=inference_id,
        status=inf.status,
        model_hash_match=model_hash_match,
        input_hash_match=input_hash_match,
        diffs=diffs,
    )
