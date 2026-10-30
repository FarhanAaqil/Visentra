"""Live cascade invalidation across the lineage graph.

When an upstream dataset or model fails verification, every inference that
depends on it loses its certificate: rows flip to ``mismatch`` immediately in
the database, then the UI is told hop by hop with a short stagger so the red
wave visibly travels down the edges.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.audit import log_audit
from backend.api.ws import broadcast
from backend.config import settings
from backend.db.models import Inference, Model

_tasks: set[asyncio.Task] = set()


async def _announce(origin_type: str, origin_id: str, hops: list[tuple[str, str, str]]) -> None:
    await broadcast(
        {"type": "cascade_start", "origin_type": origin_type, "origin_id": origin_id, "hops": len(hops)}
    )
    for i, (node_type, node_id, status) in enumerate(hops):
        await asyncio.sleep(settings.cascade_delay_s)
        await broadcast(
            {
                "type": "node_status",
                "node_type": node_type,
                "id": node_id,
                "status": status,
                "cascade_from": origin_id,
                "hop": i + 1,
            }
        )
    await broadcast({"type": "cascade_end", "origin_id": origin_id})


def _schedule(origin_type: str, origin_id: str, hops: list[tuple[str, str, str]]) -> None:
    task = asyncio.create_task(_announce(origin_type, origin_id, hops))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def invalidate_inferences(
    db: AsyncSession,
    *,
    model_ids: list[str],
    origin_type: str,
    origin_id: str,
    actor: str,
    reason: str,
) -> list[str]:
    """Mark dependent inferences as mismatched. The caller commits."""
    if not model_ids:
        return []
    stmt = (
        select(Inference)
        .where(Inference.model_id.in_(model_ids), Inference.status == "ok")
        .order_by(Inference.timestamp)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    for inf in rows:
        inf.status = "mismatch"
        log_audit(
            db,
            actor=actor,
            action="inference.invalidate",
            artifact_type="inference",
            artifact_id=inf.id,
            before={"status": "ok"},
            after={"status": "mismatch", "reason": reason, "origin": origin_id},
        )
    return [inf.id for inf in rows]


async def cascade_from_model(db: AsyncSession, model: Model, actor: str) -> list[str]:
    ids = await invalidate_inferences(
        db,
        model_ids=[model.id],
        origin_type="model",
        origin_id=model.id,
        actor=actor,
        reason="parent model failed hash verification",
    )
    _schedule("model", model.id, [("inference", i, "mismatch") for i in ids])
    return ids


async def cascade_from_dataset(db: AsyncSession, dataset_id: str, actor: str) -> list[str]:
    models = list((await db.execute(select(Model).where(Model.dataset_id == dataset_id))).scalars().all())
    ids = await invalidate_inferences(
        db,
        model_ids=[m.id for m in models],
        origin_type="dataset",
        origin_id=dataset_id,
        actor=actor,
        reason="training dataset failed Merkle verification",
    )
    by_model: dict[str, list[str]] = {}
    for inf in (await db.execute(select(Inference).where(Inference.id.in_(ids)))).scalars().all():
        by_model.setdefault(inf.model_id, []).append(inf.id)
    hops: list[tuple[str, str, str]] = []
    for m in models:
        hops.append(("model", m.id, m.status))  # pulse the edge; the model's own hash is still intact
        hops.extend(("inference", i, "mismatch") for i in by_model.get(m.id, []))
    _schedule("dataset", dataset_id, hops)
    return ids
