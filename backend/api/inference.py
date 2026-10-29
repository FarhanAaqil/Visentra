"""Inference binding router.

POST /inference               run an image through a verified model and bind the hashes
GET  /inference/{id}          retrieve the evidence record
POST /inference/{id}/reverify recompute hashes and diff them against the record
"""

import hashlib
import json
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend import storage
from backend.api.audit import actor_header, log_audit
from backend.api.deps import get_or_404
from backend.api.ws import broadcast
from backend.db.models import Inference, Model, iso
from backend.db.session import get_db

router = APIRouter(prefix="/inference", tags=["inference"])


def _run_onnx_inference(model_path: Path, image_bytes: bytes) -> dict:
    """Run image through ONNX model, return output dict. Falls back to synthetic."""
    try:
        import cv2
        import numpy as np
        import onnxruntime as ort

        sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        img = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")

        inp = sess.get_inputs()[0]
        shape = tuple(d if isinstance(d, int) and d > 0 else 224 for d in inp.shape)
        _, _, h, w = shape if len(shape) == 4 else (1, 3, 224, 224)
        rgb = cv2.cvtColor(cv2.resize(img, (w, h)), cv2.COLOR_BGR2RGB).astype("float32") / 255.0
        norm = (rgb - np.array([0.485, 0.456, 0.406])) / np.array([0.229, 0.224, 0.225])
        logits = sess.run(None, {inp.name: norm.transpose(2, 0, 1)[None].astype("float32")})[0][0]
        probs = np.exp(logits - logits.max())
        probs /= probs.sum()
        top_k = sorted(enumerate(probs.tolist()), key=lambda x: x[1], reverse=True)[:5]
        return {
            "top_class": int(top_k[0][0]),
            "top_confidence": round(float(top_k[0][1]), 6),
            "top_5": [{"class": c, "prob": round(p, 6)} for c, p in top_k],
            "synthetic": False,
        }
    except Exception as e:
        h = int(hashlib.sha256(image_bytes[:512]).hexdigest(), 16)
        cls = h % 1000
        conf = 0.55 + (h % 40) / 100
        return {
            "top_class": cls,
            "top_confidence": round(min(conf, 0.99), 6),
            "top_5": [
                {"class": (cls + i) % 1000, "prob": round(max(0.01, conf - i * 0.12), 6)} for i in range(5)
            ],
            "synthetic": True,
            "synthetic_reason": str(e),
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

    output = _run_onnx_inference(model_path, image_bytes)
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
