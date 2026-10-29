"""Lineage graph: Contributor -> Dataset -> Model -> Inference.

Models registered without a parent dataset hang directly off the contributor so
nothing disappears from the graph, but the intended shape is a 4-tier chain.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.deps import get_or_404
from backend.db.models import Contributor, Dataset, Model, iso
from backend.db.session import get_db

router = APIRouter(prefix="/chain", tags=["chain"])


class NodeOut(BaseModel):
    id: str
    type: str
    label: str
    status: str | None = None
    tier: int
    meta: dict = Field(default_factory=dict)


class EdgeOut(BaseModel):
    id: str
    source: str
    target: str
    relation: str


class ChainOut(BaseModel):
    contributor_id: str
    nodes: list[NodeOut]
    edges: list[EdgeOut]


def _edge(source: str, target: str, relation: str) -> EdgeOut:
    return EdgeOut(id=f"{source}->{target}", source=source, target=target, relation=relation)


@router.get("/{contributor_id}", response_model=ChainOut)
async def get_chain(contributor_id: str, db: AsyncSession = Depends(get_db)):
    contributor = await get_or_404(db, Contributor, contributor_id)

    nodes = [
        NodeOut(
            id=contributor.id,
            type="contributor",
            label=contributor.name,
            status="verified",
            tier=0,
            meta={"role": contributor.role, "created_at": iso(contributor.created_at)},
        )
    ]
    edges: list[EdgeOut] = []

    datasets = (
        (
            await db.execute(
                select(Dataset).where(Dataset.contributor_id == contributor_id).order_by(Dataset.created_at)
            )
        )
        .scalars()
        .all()
    )
    dataset_ids = {d.id for d in datasets}
    for ds in datasets:
        nodes.append(
            NodeOut(
                id=ds.id,
                type="dataset",
                label=f"Dataset v{ds.version}",
                status=ds.status,
                tier=1,
                meta={
                    "name": ds.name,
                    "sha256": ds.sha256,
                    "merkle_root": ds.merkle_root,
                    "sample_count": ds.sample_count or 0,
                },
            )
        )
        edges.append(_edge(contributor.id, ds.id, "contributed"))

    models = (
        (
            await db.execute(
                select(Model)
                .where(Model.contributor_id == contributor_id)
                .options(selectinload(Model.inferences))
                .order_by(Model.created_at)
            )
        )
        .scalars()
        .all()
    )
    for m in models:
        nodes.append(
            NodeOut(
                id=m.id,
                type="model",
                label=f"Model v{m.version}",
                status=m.status,
                tier=2,
                meta={
                    "name": m.name,
                    "framework": m.framework,
                    "sha256": m.sha256,
                    "arch": m.arch_fingerprint,
                    "dataset_id": m.dataset_id,
                },
            )
        )
        if m.dataset_id and m.dataset_id in dataset_ids:
            edges.append(_edge(m.dataset_id, m.id, "trained_on"))
        else:
            edges.append(_edge(contributor.id, m.id, "contributed"))

        for inf in sorted(m.inferences, key=lambda i: i.timestamp):
            output = inf.output or {}
            nodes.append(
                NodeOut(
                    id=inf.id,
                    type="inference",
                    label=f"Inference {inf.id[:8]}",
                    status=inf.status,
                    tier=3,
                    meta={
                        "input_sha256": inf.input_sha256,
                        "top_class": output.get("top_class"),
                        "confidence": inf.confidence,
                        "signed": bool(inf.signature),
                        "timestamp": iso(inf.timestamp),
                    },
                )
            )
            edges.append(_edge(m.id, inf.id, "executed"))

    return ChainOut(contributor_id=contributor.id, nodes=nodes, edges=edges)
