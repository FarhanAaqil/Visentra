"""Demo-only endpoints that simulate supply-chain attacks.

Gated behind settings.enable_demo so a real deployment can switch them off.
"""

import random
import shutil

import cv2
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend import storage
from backend.api.audit import actor_header, log_audit
from backend.api.cascade import cascade_from_model
from backend.api.datasets import dataset_samples
from backend.api.deps import get_or_404, require_demo
from backend.api.models import vault_copy
from backend.api.ws import broadcast
from backend.assurance import synthetic
from backend.db.models import Dataset, Model
from backend.db.session import get_db

router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(require_demo)])


@router.post("/models/{model_id}/tamper")
async def tamper_model(
    model_id: str,
    flips: int = 12,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    """Bit-flip attack: flip one bit in ``flips`` bytes of the weight region, keeping a vault copy."""
    model = await get_or_404(db, Model, model_id)
    stored = storage.models() / model.sha256
    if not stored.exists():
        raise HTTPException(status_code=404, detail="Stored model file not found")

    pristine = vault_copy(model)
    if not pristine.exists():
        shutil.copy2(stored, pristine)

    data = bytearray(stored.read_bytes())
    rng = random.Random(f"{model.id}:{len(data)}")
    regions = (model.graph_summary or {}).get("weight_regions") or []
    if regions:
        # Aim at the weight tensors themselves, the way a Bit-Flip Attack would.
        span = [i for r in regions for i in range(r["offset"], r["offset"] + r["length"])]
    else:
        span = list(range(len(data) // 2, len(data)))
    offsets = sorted(rng.sample(span, k=min(max(1, flips), len(span))))
    for off in offsets:
        data[off] ^= 1 << rng.randrange(8)
    stored.write_bytes(bytes(data))

    before = {"status": model.status}
    model.status = "tampered"
    log_audit(
        db,
        actor=actor,
        action="model.tamper",
        artifact_type="model",
        artifact_id=model.id,
        before=before,
        after={"status": "tampered", "flipped_offsets": offsets},
    )
    invalidated = await cascade_from_model(db, model, actor)
    await db.commit()
    await broadcast({"type": "node_status", "node_type": "model", "id": model_id, "status": "tampered"})
    return {
        "detail": f"Flipped {len(offsets)} bits in the stored checkpoint.",
        "flipped_offsets": offsets,
        "invalidated_inferences": invalidated,
    }


@router.post("/datasets/{dataset_id}/tamper")
async def tamper_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    """Poison one stored sample with a checkerboard patch, as an annotator-side attacker would."""
    dataset = await get_or_404(db, Dataset, dataset_id)
    samples = await dataset_samples(db, dataset_id)
    if not samples:
        raise HTTPException(status_code=404, detail="Dataset has no stored samples to tamper with")

    victim = samples[0]
    path = storage.resolve(victim.path)
    img = cv2.imread(str(path))
    if img is None:
        raise HTTPException(status_code=404, detail="Stored sample file not found")

    backup = storage.vault() / f"sample-{victim.id}{path.suffix}"
    if not backup.exists():
        shutil.copy2(path, backup)
    poisoned = synthetic.stamp_checkerboard(img, img.shape[1] - 12, img.shape[0] - 12, 8)
    cv2.imwrite(str(path), poisoned)

    log_audit(
        db,
        actor=actor,
        action="dataset.tamper",
        artifact_type="dataset",
        artifact_id=dataset.id,
        after={"poisoned_sample": victim.id, "sample_name": victim.name},
    )
    await db.commit()
    return {
        "detail": "Sample poisoned. Verify the dataset to see the Merkle root diverge.",
        "sample_id": victim.id,
    }


@router.post("/datasets/{dataset_id}/restore")
async def restore_dataset(
    dataset_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    """Put back the pristine copies kept in the vault and re-run the integrity check."""
    dataset = await get_or_404(db, Dataset, dataset_id)
    restored = []
    for sample in await dataset_samples(db, dataset_id):
        path = storage.resolve(sample.path)
        backup = storage.vault() / f"sample-{sample.id}{path.suffix}"
        if backup.exists():
            shutil.copy2(backup, path)
            backup.unlink()
            restored.append(sample.id)
    log_audit(
        db,
        actor=actor,
        action="dataset.restore",
        artifact_type="dataset",
        artifact_id=dataset.id,
        after={"restored_samples": restored},
    )
    await db.commit()
    return {"detail": f"Restored {len(restored)} sample(s) from the vault.", "restored": restored}


@router.post("/models/{model_id}/restore")
async def restore_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    """Copy the pristine checkpoint back from the vault; verify afterwards to clear the alarm."""
    model = await get_or_404(db, Model, model_id)
    pristine = vault_copy(model)
    if not pristine.exists():
        raise HTTPException(status_code=404, detail="No vault copy for this model; nothing to restore")

    shutil.copy2(pristine, storage.models() / model.sha256)
    pristine.unlink()
    log_audit(db, actor=actor, action="model.restore", artifact_type="model", artifact_id=model.id)
    await db.commit()
    return {"detail": "Pristine checkpoint restored from the vault. Re-verify to clear the alarm."}
