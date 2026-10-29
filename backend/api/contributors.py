from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.audit import actor_header, log_audit
from backend.api.deps import get_or_404
from backend.db.models import Contributor, iso
from backend.db.session import get_db

router = APIRouter(prefix="/contributors", tags=["contributors"])


class ContributorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="ML Engineer", max_length=64)


class ContributorOut(BaseModel):
    id: str
    name: str
    role: str | None
    created_at: str


def _out(c: Contributor) -> ContributorOut:
    return ContributorOut(id=c.id, name=c.name, role=c.role, created_at=iso(c.created_at))


@router.post("", response_model=ContributorOut, status_code=201)
async def create_contributor(
    body: ContributorCreate,
    db: AsyncSession = Depends(get_db),
    actor: str = Depends(actor_header),
):
    contributor = Contributor(name=body.name.strip(), role=body.role)
    db.add(contributor)
    await db.flush()
    log_audit(
        db,
        actor=actor,
        action="contributor.create",
        artifact_type="contributor",
        artifact_id=contributor.id,
        after={"name": contributor.name, "role": contributor.role},
    )
    await db.commit()
    await db.refresh(contributor)
    return _out(contributor)


@router.get("", response_model=list[ContributorOut])
async def list_contributors(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Contributor).order_by(Contributor.created_at.desc()))).scalars().all()
    return [_out(r) for r in rows]


@router.get("/{contributor_id}", response_model=ContributorOut)
async def get_contributor(contributor_id: str, db: AsyncSession = Depends(get_db)):
    return _out(await get_or_404(db, Contributor, contributor_id))
