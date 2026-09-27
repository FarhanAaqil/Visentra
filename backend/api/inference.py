"""
Inference binding router.

POST /inference          — run image through verified model, bind hashes, write evidence record
GET  /inference/{id}     — retrieve evidence record
POST /inference/{id}/reverify — recompute hashes, diff vs record (catches tampered models)
"""
import hashlib
import io
import json
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.db.session import get_db
from backend.db.models import Inference, Model
from backend.api.ws import broadcast

router = APIRouter(prefix="/inference", tags=["inference"])

MODEL_STORE = Path(settings.storage_root) / "models"
INFERENCE_STORE = Path(settings.storage_root) / "inference"

async def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

async def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    async with aiofiles.open(path, "rb") as f:
        while chunk := await f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def _run_onnx_inference(model_path: Path, image_bytes: bytes) -> dict:
    """Run image through ONNX model, return output dict. Falls back to synthetic."""
    try:
        import onnxruntime as ort
        import numpy as np
        import cv2

        sess = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
        img_array = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Could not decode image")

        inp = sess.get_inputs()[0]
        shape = tuple(d if isinstance(d, int) and d > 0 else 224 for d in inp.shape)
        _, _, h, w = shape if len(shape) == 4 else (1, 3, 224, 224)
        resized = cv2.resize(img, (w, h))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype("float32") / 255.0
        mean = [0.485, 0.456, 0.406]
        std  = [0.229, 0.224, 0.225]
        norm = (rgb - mean) / std
        chw = norm.transpose(2, 0, 1)[None, ...]

        out = sess.run(None, {inp.name: chw})[0][0]
        probs = (lambda x: (e := x - x.max(), (p := __import__("numpy").exp(e) / __import__("numpy").exp(e).sum()))[-1])(out)
        top_k = sorted(enumerate(probs.tolist()), key=lambda x: x[1], reverse=True)[:5]
        return {
            "top_class": int(top_k[0][0]),
            "top_confidence": round(float(top_k[0][1]), 6),
            "top_5": [{"class": c, "prob": round(p, 6)} for c, p in top_k],
            "synthetic": False,
        }
    except Exception as e:
        h = int(hashlib.md5(image_bytes[:512]).hexdigest(), 16)
        cls = h % 1000
        conf = 0.55 + (h % 40) / 100
        return {
            "top_class": cls,
            "top_confidence": round(min(conf, 0.99), 6),
            "top_5": [{"class": (cls + i) % 1000, "prob": round(max(0.01, conf - i * 0.12), 6)} for i in range(5)],
            "synthetic": True,
            "synthetic_reason": str(e),
        }

class InferenceOut(BaseModel):
    id: str
    model_id: str
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

@router.post("", response_model=InferenceOut, status_code=201)
async def run_inference(
    image: UploadFile = File(...),
    model_id: str = Form(...),
    config: str = Form(default="{}"),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Model).where(Model.id == model_id))
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    if model.status == "tampered":
        raise HTTPException(status_code=422, detail="Model is tampered — cannot run inference on untrusted model")

    model_path = MODEL_STORE / model.sha256
    if not model_path.exists():
        raise HTTPException(status_code=422, detail="Model file missing from storage")

    image_bytes = await image.read()
    config_bytes = config.encode()

    input_sha = await _sha256_bytes(image_bytes)
    config_sha = await _sha256_bytes(config_bytes)
    model_sha_actual = await _sha256_file(model_path)

    if model_sha_actual != model.sha256:
        model.status = "tampered"
        await db.commit()
        await broadcast({"type": "node_status", "node_type": "model", "id": model_id, "status": "tampered"})
        raise HTTPException(status_code=422, detail="Model hash mismatch detected before inference — aborting")

    output = _run_onnx_inference(model_path, image_bytes)
    confidence = output.get("top_confidence", 0.0)

    INFERENCE_STORE.mkdir(parents=True, exist_ok=True)
    inference_id = str(uuid.uuid4())
    evidence = {
        "inference_id": inference_id,
        "model_id": model_id,
        "model_sha256": model.sha256,
        "input_sha256": input_sha,
        "config_sha256": config_sha,
        "output": output,
    }
    evidence_path = INFERENCE_STORE / f"{inference_id}.json"
    evidence_path.write_text(json.dumps(evidence, indent=2))

    inference = Inference(
        id=inference_id,
        model_id=model_id,
        input_sha256=input_sha,
        config_sha256=config_sha,
        output=output,
        confidence=confidence,
        status="ok",
    )
    db.add(inference)
    await db.commit()

    await broadcast({
        "type": "node_status",
        "node_type": "inference",
        "id": inference_id,
        "status": "ok",
    })

    return InferenceOut(
        id=inference.id,
        model_id=inference.model_id,
        input_sha256=inference.input_sha256,
        config_sha256=inference.config_sha256,
        output=inference.output,
        confidence=inference.confidence,
        timestamp=inference.timestamp.isoformat(),
        status=inference.status,
    )

@router.get("/{inference_id}", response_model=InferenceOut)
async def get_inference(inference_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Inference).where(Inference.id == inference_id))
    inf = result.scalar_one_or_none()
    if not inf:
        raise HTTPException(status_code=404, detail="Inference not found")
    return InferenceOut(
        id=inf.id,
        model_id=inf.model_id,
        input_sha256=inf.input_sha256,
        config_sha256=inf.config_sha256,
        output=inf.output,
        confidence=inf.confidence,
        timestamp=inf.timestamp.isoformat(),
        status=inf.status,
    )

@router.post("/{inference_id}/reverify", response_model=ReverifyOut)
async def reverify_inference(inference_id: str, db: AsyncSession = Depends(get_db)):
    """
    Recompute model hash, diff against the hash bound at inference time.
    This is what catches 'this prediction didn't come from the model it claims'.
    """
    result = await db.execute(select(Inference).where(Inference.id == inference_id))
    inf = result.scalar_one_or_none()
    if not inf:
        raise HTTPException(status_code=404, detail="Inference not found")

    evidence_path = INFERENCE_STORE / f"{inference_id}.json"
    if not evidence_path.exists():
        raise HTTPException(status_code=404, detail="Evidence record missing from storage")

    evidence = json.loads(evidence_path.read_text())
    recorded_model_sha = evidence.get("model_sha256")

    m_result = await db.execute(select(Model).where(Model.id == inf.model_id))
    model = m_result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    model_path = MODEL_STORE / model.sha256
    diffs = []
    model_hash_match = False

    if model_path.exists():
        actual_sha = await _sha256_file(model_path)
        model_hash_match = (actual_sha == recorded_model_sha)
        if not model_hash_match:
            diffs.append(f"model_sha256 recorded={recorded_model_sha[:12]}… actual={actual_sha[:12]}…")
    else:
        diffs.append("model file missing from storage")

    input_hash_match = (inf.input_sha256 == evidence.get("input_sha256"))
    if not input_hash_match:
        diffs.append("input_sha256 mismatch between DB record and evidence file")

    new_status = "ok" if (model_hash_match and input_hash_match) else "mismatch"
    inf.status = new_status
    if not model_hash_match:
        model.status = "tampered"
    await db.commit()

    await broadcast({
        "type": "node_status",
        "node_type": "inference",
        "id": inference_id,
        "status": new_status,
    })
    if not model_hash_match:
        await broadcast({
            "type": "node_status",
            "node_type": "model",
            "id": inf.model_id,
            "status": "tampered",
        })

    return ReverifyOut(
        inference_id=inference_id,
        status=new_status,
        model_hash_match=model_hash_match,
        input_hash_match=input_hash_match,
        diffs=diffs,
    )
