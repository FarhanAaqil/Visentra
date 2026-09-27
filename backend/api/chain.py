from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.db.session import get_db
from backend.db.models import Contributor, Dataset, Model, Inference

router = APIRouter(prefix="/chain", tags=["chain"])


class NodeOut(BaseModel):
    id: str
    type: str   # "contributor" | "dataset" | "model" | "inference"
    label: str
    status: str | None = None
    meta: dict = {}


class EdgeOut(BaseModel):
    source: str
    target: str


class ChainOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]


@router.get("/{contributor_id}", response_model=ChainOut)
async def get_chain(contributor_id: str, db: AsyncSession = Depends(get_db)):
    """Return full lineage graph data for a contributor."""
    result = await db.execute(select(Contributor).where(Contributor.id == contributor_id))
    contributor = result.scalar_one_or_none()
    if not contributor:
        raise HTTPException(status_code=404, detail="Contributor not found")

    nodes: list[NodeOut] = []
    edges: list[EdgeOut] = []

    # Contributor node
    nodes.append(NodeOut(id=contributor.id, type="contributor", label=contributor.name))

    # Datasets
    ds_result = await db.execute(select(Dataset).where(Dataset.contributor_id == contributor_id))
    datasets = ds_result.scalars().all()
    for ds in datasets:
        nodes.append(NodeOut(
            id=ds.id, type="dataset", label=f"Dataset v{ds.version}", status=ds.status,
            meta={"sha256": ds.sha256[:12] + "…"},
        ))
        edges.append(EdgeOut(source=contributor.id, target=ds.id))

    # Models
    m_result = await db.execute(select(Model).where(Model.contributor_id == contributor_id))
    models = m_result.scalars().all()
    for m in models:
        nodes.append(NodeOut(
            id=m.id, type="model", label=f"Model v{m.version} ({m.framework})", status=m.status,
            meta={"sha256": m.sha256[:12] + "…", "arch": m.arch_fingerprint},
        ))
        edges.append(EdgeOut(source=contributor.id, target=m.id))

        # Inferences hanging off this model
        inf_result = await db.execute(select(Inference).where(Inference.model_id == m.id))
        inferences = inf_result.scalars().all()
        for inf in inferences:
            nodes.append(NodeOut(
                id=inf.id, type="inference", label=f"Inference {inf.id[:8]}…", status=inf.status,
                meta={"input_sha256": (inf.input_sha256 or "")[:12] + "…"},
            ))
            edges.append(EdgeOut(source=m.id, target=inf.id))

    return ChainOut(nodes=nodes, edges=edges)
